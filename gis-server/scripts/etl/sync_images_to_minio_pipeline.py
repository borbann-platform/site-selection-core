import argparse
import logging
import math
import os
import subprocess
import sys
from collections.abc import Iterable


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run sync_images_to_minio in repeatable batches until pending images "
            "drop below target or max rounds reached."
        )
    )
    parser.add_argument(
        "--batch-limit",
        type=int,
        default=1000,
        help="Rows per sync_images_to_minio run (default: 1000)",
    )
    parser.add_argument(
        "--commit-batch",
        type=int,
        default=50,
        help="Commit frequency passed to sync_images_to_minio (default: 50)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=20,
        help="Maximum pipeline rounds (default: 20)",
    )
    parser.add_argument(
        "--target-pending",
        type=int,
        default=0,
        help="Stop when pending <= target (default: 0)",
    )
    parser.add_argument(
        "--with-minio-dep",
        action="store_true",
        help="Use 'uv run --with minio' for environments missing minio package",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned actions",
    )
    return parser.parse_args()


def run_cmd(command: Iterable[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        text=True,
        capture_output=True,
    )


def get_pending_count() -> int:
    query = (
        "from sqlalchemy import text; "
        "from src.config.database import SessionLocal; "
        "db=SessionLocal(); "
        'print(db.execute(text("select count(*) from scraped_listing_images '
        "where fetch_status='pending'\")).scalar()); "
        "db.close()"
    )
    proc = run_cmd(["uv", "run", "python", "-c", query])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Failed to query pending count")

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No output from pending-count query")

    return int(lines[-1])


def run_sync_batch(batch_limit: int, commit_batch: int, with_minio_dep: bool) -> int:
    base = ["uv", "run"]
    if with_minio_dep:
        base.extend(["--with", "minio"])

    command = base + [
        "python",
        "-m",
        "scripts.etl.sync_images_to_minio",
        "--limit",
        str(batch_limit),
        "--commit-batch",
        str(commit_batch),
    ]

    logger.info("Running batch command: %s", " ".join(command))
    proc = subprocess.run(command, check=False)
    return proc.returncode


def main() -> None:
    args = parse_args()

    initial_pending = get_pending_count()
    logger.info("Initial pending images: %s", initial_pending)

    if initial_pending <= args.target_pending:
        logger.info(
            "Pending already at/below target (%s). Nothing to do.", args.target_pending
        )
        return

    estimated_rounds = max(1, math.ceil(initial_pending / max(args.batch_limit, 1)))
    logger.info(
        "Estimated rounds to clear queue: ~%s (max rounds configured: %s)",
        estimated_rounds,
        args.max_rounds,
    )

    if args.dry_run:
        logger.info("Dry run mode enabled. Exiting without executing sync.")
        return

    for round_index in range(1, args.max_rounds + 1):
        before_pending = get_pending_count()
        if before_pending <= args.target_pending:
            logger.info(
                "Target reached before round %s. Pending=%s",
                round_index,
                before_pending,
            )
            return

        logger.info(
            "Round %s/%s starting. Pending before run: %s",
            round_index,
            args.max_rounds,
            before_pending,
        )

        exit_code = run_sync_batch(
            batch_limit=args.batch_limit,
            commit_batch=args.commit_batch,
            with_minio_dep=args.with_minio_dep,
        )
        if exit_code != 0:
            logger.error(
                "Batch round %s failed with exit code %s", round_index, exit_code
            )
            sys.exit(exit_code)

        after_pending = get_pending_count()
        reduced_by = before_pending - after_pending
        logger.info(
            "Round %s complete. Pending after run: %s (reduced by %s)",
            round_index,
            after_pending,
            reduced_by,
        )

        if reduced_by <= 0:
            logger.warning(
                "No pending reduction detected in round %s. Stopping to avoid busy loop.",
                round_index,
            )
            return

    final_pending = get_pending_count()
    logger.info(
        "Reached max rounds (%s). Final pending images: %s",
        args.max_rounds,
        final_pending,
    )


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
