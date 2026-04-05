"""
One-time upload of data files to S3.

Run this after load_historical.py completes to push the populated
bestball.db and Parquet game log files to S3.

Usage:
  python scripts/upload_to_s3.py

Reads credentials from stacking-dingers-etl_accessKeys.csv (repo root).
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("upload_to_s3")

BUCKET = "stacking-dingers-data-310971188738-us-east-2-an"
REGION = "us-east-2"
CREDS_FILE = Path("stacking-dingers-etl_accessKeys.csv")

FILES_TO_UPLOAD = [
    ("data/bestball.db",              "data/bestball.db"),
    ("data/fangraphs_player_map.csv", "data/fangraphs_player_map.csv"),
]

DIRS_TO_SYNC = [
    "data/gamelogs",
    "data/adp_history",
]


def load_credentials() -> tuple[str, str]:
    with open(CREDS_FILE) as f:
        rows = list(csv.reader(f))
    return rows[1][0].strip(), rows[1][1].strip()


def upload_file(s3, local_path: str, s3_key: str) -> None:
    p = Path(local_path)
    if not p.exists():
        logger.warning(f"  Skipping {local_path} -- file not found")
        return
    size_mb = p.stat().st_size / 1_048_576
    logger.info(f"  Uploading {local_path} ({size_mb:.1f} MB) -> s3://{BUCKET}/{s3_key}")
    s3.upload_file(str(p), BUCKET, s3_key)


def sync_directory(s3, local_dir: str) -> int:
    """Upload all files in a directory, maintaining the path as the S3 prefix."""
    d = Path(local_dir)
    if not d.exists():
        logger.warning(f"  Skipping {local_dir} -- directory not found")
        return 0
    files = list(d.rglob("*"))
    files = [f for f in files if f.is_file()]
    if not files:
        logger.info(f"  {local_dir} is empty -- nothing to upload")
        return 0
    uploaded = 0
    for f in files:
        s3_key = f.as_posix()  # keeps data/gamelogs/2022.parquet etc.
        size_mb = f.stat().st_size / 1_048_576
        logger.info(f"  {f} ({size_mb:.1f} MB) -> s3://{BUCKET}/{s3_key}")
        s3.upload_file(str(f), BUCKET, s3_key)
        uploaded += 1
    return uploaded


def run() -> None:
    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    ak_id, ak_secret = load_credentials()
    s3 = boto3.client(
        "s3",
        aws_access_key_id=ak_id,
        aws_secret_access_key=ak_secret,
        region_name=REGION,
    )

    logger.info(f"Uploading to s3://{BUCKET}/")

    logger.info("\n-- Individual files --")
    for local, key in FILES_TO_UPLOAD:
        upload_file(s3, local, key)

    logger.info("\n-- Directories --")
    total = 0
    for d in DIRS_TO_SYNC:
        n = sync_directory(s3, d)
        total += n

    logger.info(f"\nDone. Uploaded {total} Parquet files + individual files.")
    logger.info("Railway will pull these on next deploy/restart via s3_sync.py.")


if __name__ == "__main__":
    run()
