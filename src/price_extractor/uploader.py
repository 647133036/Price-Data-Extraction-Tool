from __future__ import annotations

import logging
from pathlib import Path

from .config import AwsSettings

logger = logging.getLogger(__name__)


class S3Uploader:
    def __init__(self, settings: AwsSettings):
        self.settings = settings

    def upload(self, files: list[Path], extraction_date: str) -> list[str]:
        if not self.settings.enabled:
            logger.info("AWS upload disabled")
            return []
        if not self.settings.s3_bucket:
            raise ValueError("AWS upload is enabled but s3_bucket is empty")

        session_kwargs = {"region_name": self.settings.region}
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for AWS uploads") from exc

        if self.settings.profile_name:
            session = boto3.Session(
                profile_name=self.settings.profile_name,
                region_name=self.settings.region,
            )
        else:
            session = boto3.Session(**session_kwargs)
        client = session.client("s3")
        uploaded: list[str] = []
        prefix = "/".join(part for part in [self.settings.s3_prefix.strip("/"), extraction_date] if part)
        for path in files:
            key = f"{prefix}/{path.name}" if prefix else path.name
            logger.info("Uploading %s to s3://%s/%s", path, self.settings.s3_bucket, key)
            client.upload_file(str(path), self.settings.s3_bucket, key)
            uploaded.append(f"s3://{self.settings.s3_bucket}/{key}")
        return uploaded
