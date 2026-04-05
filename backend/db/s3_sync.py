"""
S3 data sync helper.

On startup in production (when S3_BUCKET env var is set), downloads
bestball.db and the gamelogs/adp_history Parquet files from S3 so the
Railway instance has fresh data without bundling large files in the repo.

The sync is intentionally one-way at startup: Railway reads from S3.
Writes back to S3 are performed only by the nightly ETL GitHub Action.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def sync_data_from_s3() -> None:
    """Download data files from S3 if S3_BUCKET is configured.

    No-ops silently when running locally (S3_BUCKET not set).
    """
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        logger.info("S3_BUCKET not set — skipping S3 sync (local mode)")
        return

    try:
        import boto3  # type: ignore[import]
    except ImportError:
        logger.warning("boto3 not installed — skipping S3 sync")
        return

    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
    s3 = boto3.client("s3", region_name=region)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "gamelogs").mkdir(exist_ok=True)
    (data_dir / "adp_history").mkdir(exist_ok=True)

    # List and download every object under data/ in the bucket.
    paginator = s3.get_paginator("list_objects_v2")
    downloaded = 0
    skipped = 0

    for page in paginator.paginate(Bucket=bucket, Prefix="data/"):
        for obj in page.get("Contents", []):
            key: str = obj["Key"]
            local_path = Path(key)

            # Skip directory placeholders.
            if key.endswith("/"):
                continue

            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Only re-download if S3 object is newer than local file.
            if local_path.exists():
                local_mtime = local_path.stat().st_mtime
                s3_mtime = obj["LastModified"].timestamp()
                if s3_mtime <= local_mtime:
                    skipped += 1
                    continue

            logger.info("Downloading s3://%s/%s → %s", bucket, key, local_path)
            s3.download_file(bucket, key, str(local_path))
            downloaded += 1

    logger.info("S3 sync complete: %d downloaded, %d up-to-date", downloaded, skipped)
