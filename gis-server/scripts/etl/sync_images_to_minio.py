import argparse
import hashlib
import io
import logging
import mimetypes
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.config.database import SessionLocal
from src.config.settings import settings
from src.models.realestate import ScrapedListing, ScrapedListingImage

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

NO_SUCH_OBJECT_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download listing images from source URLs and sync them to MinIO"
    )
    parser.add_argument(
        "--statuses",
        default="pending,failed",
        help="Comma-separated image statuses to process (default: pending,failed)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of image rows to process",
    )
    parser.add_argument(
        "--commit-batch",
        type=int,
        default=25,
        help="Commit every N rows",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="HTTP timeout per image download",
    )
    parser.add_argument(
        "--bucket",
        default=settings.MINIO_BUCKET,
        help="Target MinIO bucket name",
    )
    parser.add_argument(
        "--prefix",
        default=settings.MINIO_OBJECT_PREFIX,
        help="Object key prefix for uploaded images",
    )
    parser.add_argument(
        "--endpoint",
        default=settings.MINIO_ENDPOINT,
        help="MinIO endpoint (host:port or URL)",
    )
    parser.add_argument(
        "--access-key",
        default=settings.MINIO_ACCESS_KEY,
        help="MinIO access key",
    )
    parser.add_argument(
        "--secret-key",
        default=settings.MINIO_SECRET_KEY,
        help="MinIO secret key",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        default=settings.MINIO_SECURE,
        help="Use TLS when connecting to MinIO",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process rows even if object metadata already exists",
    )
    return parser.parse_args()


def parse_minio_endpoint(raw_endpoint: str, default_secure: bool) -> tuple[str, bool]:
    endpoint = raw_endpoint.strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        parsed = urlparse(endpoint)
        secure = parsed.scheme == "https"
        return parsed.netloc, secure
    return endpoint, default_secure


def get_minio_client(endpoint: str, access_key: str, secret_key: str, secure: bool):
    try:
        from minio import Minio
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'minio'. Install with `uv add minio` or run with "
            "`uv run --with minio python -m scripts.etl.sync_images_to_minio ...`"
        ) from exc

    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def ensure_bucket(client, bucket: str) -> None:
    if client.bucket_exists(bucket):
        return
    logger.info("Creating bucket '%s'", bucket)
    client.make_bucket(bucket)


def extension_from_content_type(content_type: str, source_url: str) -> str:
    if content_type:
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            normalized = guessed.lower().lstrip(".")
            if normalized == "jpe":
                return "jpg"
            return normalized

    parsed_path = urlparse(source_url).path
    suffix = os.path.splitext(parsed_path)[1].lower().lstrip(".")
    if suffix:
        return suffix
    return "bin"


def object_key_for_image(
    prefix: str, source: str, checksum_sha256: str, extension: str
) -> str:
    clean_prefix = prefix.strip("/")
    clean_source = source.strip().lower() or "unknown"
    return f"{clean_prefix}/{clean_source}/{checksum_sha256[:2]}/{checksum_sha256}.{extension}"


def object_exists(client, bucket: str, object_key: str) -> bool:
    try:
        client.stat_object(bucket, object_key)
        return True
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in NO_SUCH_OBJECT_CODES:
            return False
        raise


def fetch_candidates(
    db: Session,
    statuses: list[str],
    limit: int,
    force: bool,
):
    query = (
        db.query(ScrapedListingImage, ScrapedListing.source)
        .join(ScrapedListing, ScrapedListing.id == ScrapedListingImage.listing_id)
        .filter(ScrapedListingImage.fetch_status.in_(statuses))
        .filter(ScrapedListingImage.source_url.isnot(None))
        .order_by(ScrapedListingImage.id.asc())
    )

    if not force:
        query = query.filter(ScrapedListingImage.object_key.is_(None))

    if limit > 0:
        query = query.limit(limit)

    return query.all()


def process_one_image(
    image_row: ScrapedListingImage,
    source: str,
    client,
    bucket: str,
    prefix: str,
    http_client: httpx.Client,
) -> None:
    response = http_client.get(image_row.source_url)
    image_row.last_http_status = response.status_code

    if response.status_code != 200:
        image_row.fetch_status = "failed"
        image_row.fetch_error = f"HTTP {response.status_code}"
        image_row.updated_at = datetime.now(timezone.utc)
        return

    content_type = (
        (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    )
    body = response.content

    if not content_type.startswith("image/"):
        image_row.fetch_status = "failed"
        image_row.fetch_error = f"Unsupported content type: {content_type or 'unknown'}"
        image_row.updated_at = datetime.now(timezone.utc)
        return

    checksum_sha256 = hashlib.sha256(body).hexdigest()
    extension = extension_from_content_type(content_type, image_row.source_url)
    object_key = object_key_for_image(
        prefix=prefix,
        source=source,
        checksum_sha256=checksum_sha256,
        extension=extension,
    )

    if not object_exists(client, bucket, object_key):
        client.put_object(
            bucket_name=bucket,
            object_name=object_key,
            data=io.BytesIO(body),
            length=len(body),
            content_type=content_type,
        )

    image_row.storage_bucket = bucket
    image_row.object_key = object_key
    image_row.object_uri = f"s3://{bucket}/{object_key}"
    image_row.checksum_sha256 = checksum_sha256
    image_row.mime_type = content_type
    image_row.size_bytes = len(body)
    image_row.fetch_status = "uploaded"
    image_row.fetch_error = None
    image_row.fetched_at = datetime.now(timezone.utc)
    image_row.updated_at = datetime.now(timezone.utc)


def main() -> None:
    args = parse_args()
    statuses = [s.strip().lower() for s in args.statuses.split(",") if s.strip()]
    if not statuses:
        raise ValueError("At least one status is required via --statuses")

    endpoint, secure = parse_minio_endpoint(args.endpoint, args.secure)
    client = get_minio_client(
        endpoint=endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        secure=secure,
    )
    ensure_bucket(client, args.bucket)

    db = SessionLocal()
    uploaded = 0
    failed = 0

    try:
        candidates = fetch_candidates(
            db,
            statuses=statuses,
            limit=max(args.limit, 0),
            force=args.force,
        )
        logger.info("Selected %s image rows", len(candidates))

        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(float(max(args.timeout_seconds, 1))),
        ) as http_client:
            for idx, (image_row, source) in enumerate(candidates, start=1):
                try:
                    process_one_image(
                        image_row=image_row,
                        source=source,
                        client=client,
                        bucket=args.bucket,
                        prefix=args.prefix,
                        http_client=http_client,
                    )
                except Exception as exc:
                    image_row.fetch_status = "failed"
                    image_row.fetch_error = str(exc)[:1000]
                    image_row.updated_at = datetime.now(timezone.utc)

                if image_row.fetch_status == "uploaded":
                    uploaded += 1
                elif image_row.fetch_status == "failed":
                    failed += 1

                if idx % max(args.commit_batch, 1) == 0:
                    db.commit()
                    logger.info(
                        "Progress: processed=%s uploaded=%s failed=%s",
                        idx,
                        uploaded,
                        failed,
                    )

        db.commit()
        logger.info(
            "Completed sync: selected=%s uploaded=%s failed=%s",
            len(candidates),
            uploaded,
            failed,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
