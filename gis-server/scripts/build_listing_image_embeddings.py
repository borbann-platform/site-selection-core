#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import logging
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import settings


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmarks"
DEFAULT_MANIFEST = BENCHMARK_DIR / "listing_image_embedding_manifest_v1.parquet"
DEFAULT_OUTPUT = BENCHMARK_DIR / "listing_image_embeddings_v1.parquet"
DEFAULT_AUDIT_JSON = BENCHMARK_DIR / "listing_image_embeddings_v1_audit.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build listing-level CLIP image embeddings from manifest"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--model-id", type=str, default="openai/clip-vit-base-patch32")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument(
        "--uploaded-only",
        action="store_true",
        help="Use only manifest rows where fetch_status is uploaded",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Optional cap for total image rows (0 means no cap)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="auto, cpu, or cuda",
    )
    return parser.parse_args()


def resolve_device(choice: str) -> str:
    if choice == "cpu":
        return "cpu"
    if choice == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_manifest(
    manifest_path: Path,
    max_images: int,
    uploaded_only: bool,
) -> pd.DataFrame:
    df = pd.read_parquet(manifest_path)
    required = {
        "row_id",
        "image_selected",
        "image_reference_uri",
        "fetch_status",
        "checksum_sha256",
        "source_site",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Manifest missing required columns: {missing}")

    selected = df.loc[df["image_selected"] == 1].copy()
    selected["image_reference_uri"] = selected["image_reference_uri"].fillna("")
    selected = selected.loc[selected["image_reference_uri"].str.len() > 0].copy()
    if uploaded_only:
        selected = selected.loc[selected["fetch_status"] == "uploaded"].copy()
    if max_images > 0:
        selected = selected.head(max_images).copy()
    selected = selected.reset_index(drop=True)
    return selected


def parse_minio_endpoint(raw_endpoint: str, default_secure: bool) -> tuple[str, bool]:
    endpoint = raw_endpoint.strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        parsed = urlparse(endpoint)
        secure = parsed.scheme == "https"
        return parsed.netloc, secure
    return endpoint, default_secure


def get_minio_client():
    try:
        from minio import Minio
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'minio'. Install with `uv add minio`"
        ) from exc

    endpoint, secure = parse_minio_endpoint(
        settings.MINIO_ENDPOINT, settings.MINIO_SECURE
    )
    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
    )


def fetch_image_bytes(
    uri: str,
    http_client: httpx.Client,
    minio_client: Any,
) -> bytes:
    if uri.startswith("s3://"):
        parsed = urlparse(uri)
        bucket = parsed.netloc
        object_key = parsed.path.lstrip("/")
        response = minio_client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    response = http_client.get(uri)
    response.raise_for_status()
    return response.content


def image_to_rgb(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGB")


def build_rows(
    rows: pd.DataFrame,
    model: Any,
    processor: Any,
    device: str,
    batch_size: int,
    timeout_seconds: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    minio_client = get_minio_client()
    embedding_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    cache: dict[str, np.ndarray] = {}

    with httpx.Client(
        timeout=httpx.Timeout(float(max(timeout_seconds, 1)))
    ) as http_client:
        images: list[Image.Image] = []
        meta: list[dict[str, Any]] = []

        def flush_batch() -> None:
            if not images:
                return
            inputs = processor(images=images, return_tensors="pt", padding=True)
            pixel_values = inputs["pixel_values"].to(device)
            with torch.no_grad():
                outputs = model.vision_model(pixel_values=pixel_values)
                feats = outputs.pooler_output
                feats = torch.nn.functional.normalize(feats, p=2, dim=1)
            arr = feats.detach().cpu().numpy().astype(np.float32)

            for idx, item in enumerate(meta):
                emb = arr[idx]
                cache_key = item.get("cache_key")
                if cache_key:
                    cache[cache_key] = emb
                entry = item.copy()
                entry["embedding"] = emb
                embedding_rows.append(entry)

            images.clear()
            meta.clear()

        for row in rows.to_dict(orient="records"):
            row_id = str(row["row_id"])
            image_uri = str(row["image_reference_uri"])
            source_site = str(row.get("source_site") or "unknown")
            checksum = row.get("checksum_sha256")
            cache_key = str(checksum) if checksum else ""

            if cache_key and cache_key in cache:
                embedding_rows.append(
                    {
                        "row_id": row_id,
                        "source_site": source_site,
                        "fetch_status": row.get("fetch_status"),
                        "image_reference_uri": image_uri,
                        "checksum_sha256": checksum,
                        "embedding": cache[cache_key],
                    }
                )
                continue

            try:
                payload = fetch_image_bytes(
                    image_uri, http_client=http_client, minio_client=minio_client
                )
                image = image_to_rgb(payload)
                images.append(image)
                meta.append(
                    {
                        "row_id": row_id,
                        "source_site": source_site,
                        "fetch_status": row.get("fetch_status"),
                        "image_reference_uri": image_uri,
                        "checksum_sha256": checksum,
                        "cache_key": cache_key,
                    }
                )
                if len(images) >= max(batch_size, 1):
                    flush_batch()
            except Exception as exc:
                failures.append(
                    {
                        "row_id": row_id,
                        "source_site": source_site,
                        "image_reference_uri": image_uri,
                        "error": str(exc)[:400],
                    }
                )

        flush_batch()

    if not embedding_rows:
        return pd.DataFrame(), {"failures": failures, "cached_hits": 0}

    emb_df = pd.DataFrame(embedding_rows)
    emb_dim = int(len(emb_df.iloc[0]["embedding"]))
    matrix = np.vstack(
        [np.asarray(value, dtype=np.float32) for value in emb_df["embedding"]]
    )
    col_names = [f"img_emb_{i}" for i in range(emb_dim)]
    emb_matrix_df = pd.DataFrame(matrix, columns=col_names)
    emb_df = pd.concat(
        [emb_df.drop(columns=["embedding"]).reset_index(drop=True), emb_matrix_df],
        axis=1,
    )

    metrics = {
        "processed_rows": int(len(rows)),
        "embedded_rows": int(len(emb_df)),
        "failed_rows": int(len(failures)),
        "unique_cached_checksums": int(len(cache)),
        "embedding_dim": emb_dim,
        "failures": failures[:200],
    }
    return emb_df, metrics


def aggregate_listing_embeddings(emb_df: pd.DataFrame) -> pd.DataFrame:
    emb_cols = [col for col in emb_df.columns if col.startswith("img_emb_")]
    group_cols = ["row_id"]

    agg_numeric = emb_df.groupby(group_cols)[emb_cols].mean().reset_index()
    coverage = (
        emb_df.groupby("row_id")
        .agg(
            image_embedding_count=("row_id", "size"),
            uploaded_image_embedding_count=(
                "fetch_status",
                lambda values: int((values == "uploaded").sum()),
            ),
        )
        .reset_index()
    )
    result = agg_numeric.merge(coverage, on="row_id", how="left")
    result["has_image_embedding"] = 1
    return result


def build_audit(
    metrics: dict[str, Any],
    listing_embeddings: pd.DataFrame,
    model_id: str,
    device: str,
) -> dict[str, Any]:
    return {
        "embedding_version": "listing_image_embeddings_v1",
        "model_id": model_id,
        "device": device,
        "processed_image_rows": metrics["processed_rows"],
        "embedded_image_rows": metrics["embedded_rows"],
        "failed_image_rows": metrics["failed_rows"],
        "embedding_dim": metrics["embedding_dim"],
        "listing_rows_with_embeddings": int(len(listing_embeddings)),
        "avg_images_per_listing": float(
            listing_embeddings["image_embedding_count"].mean()
            if len(listing_embeddings) > 0
            else 0.0
        ),
        "avg_uploaded_images_per_listing": float(
            listing_embeddings["uploaded_image_embedding_count"].mean()
            if len(listing_embeddings) > 0
            else 0.0
        ),
        "failures_sample": metrics.get("failures", []),
        "notes": [
            "Listing embeddings are CLIP image features mean-pooled at row_id level.",
            "Image embeddings are L2-normalized before pooling.",
            "Rows without embeddings should fallback to zeros plus has_image_embedding=0.",
        ],
    }


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_json.parent.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    logger.info("Loading CLIP model %s on %s", args.model_id, device)
    processor = CLIPProcessor.from_pretrained(args.model_id)
    model = CLIPModel.from_pretrained(args.model_id).to(device)
    model.eval()

    selected = load_manifest(
        args.manifest,
        max_images=args.max_images,
        uploaded_only=args.uploaded_only,
    )
    logger.info("Selected %s image rows from manifest", len(selected))

    emb_df, metrics = build_rows(
        rows=selected,
        model=model,
        processor=processor,
        device=device,
        batch_size=max(args.batch_size, 1),
        timeout_seconds=max(args.timeout_seconds, 1),
    )

    if emb_df.empty:
        raise RuntimeError(
            "No embeddings were produced; inspect failures in audit output"
        )

    listing_embeddings = aggregate_listing_embeddings(emb_df)
    listing_embeddings.to_parquet(args.output, index=False)

    audit = build_audit(
        metrics=metrics,
        listing_embeddings=listing_embeddings,
        model_id=args.model_id,
        device=device,
    )
    args.audit_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    logger.info("Saved listing embeddings: %s", args.output)
    logger.info("Saved listing embedding audit: %s", args.audit_json)
    logger.info(
        "Embeddings complete: listing_rows=%s embedding_dim=%s failed_rows=%s",
        len(listing_embeddings),
        audit["embedding_dim"],
        audit["failed_image_rows"],
    )


if __name__ == "__main__":
    main()
