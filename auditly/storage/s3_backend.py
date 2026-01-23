"""S3 backend implementation for auditly evidence vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import boto3

from .base import EvidenceVault


class S3EvidenceVault(EvidenceVault):
    """Evidence vault implementation using AWS S3 as the backend."""

    def __init__(self, bucket: str, region: str, profile: Optional[str] = None) -> None:
        """Initialize the S3EvidenceVault with connection details."""
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.s3 = session.client("s3", region_name=region)
        self.bucket = bucket
        self._ensure_bucket(region)

    def _ensure_bucket(self, region: str) -> None:
        """Ensure the S3 bucket exists; create if missing."""
        # Best-effort create; ignore if exists/no perms
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.s3.create_bucket(
                    Bucket=self.bucket, CreateBucketConfiguration={"LocationConstraint": region}
                )
            except Exception:
                pass

    def put_file(
        self, src_path: Path | str, dest_key: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Upload a file to the S3 bucket."""
        p = Path(src_path)
        self.s3.upload_file(str(p), self.bucket, dest_key, ExtraArgs={"Metadata": metadata or {}})
        return {"bucket": self.bucket, "key": dest_key, "size": p.stat().st_size}

    def put_json(
        self, dest_key: str, data: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Upload a JSON string as an object to the S3 bucket."""
        b = data.encode()
        self.s3.put_object(
            Bucket=self.bucket,
            Key=dest_key,
            Body=b,
            ContentType="application/json",
            Metadata=metadata or {},
        )
        return {"bucket": self.bucket, "key": dest_key, "size": len(b)}

    def exists(self, dest_key: str) -> bool:
        """Check if an object exists in the S3 bucket."""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=dest_key)
            return True
        except Exception:
            return False

    def list(self, prefix: str) -> list[str]:
        """List object keys in the S3 bucket with the given prefix."""
        keys: list[str] = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                keys.append(item["Key"])
        return keys

    def fetch(self, key: str, out_path: Path | str) -> None:
        """Download an object from the S3 bucket to a local path."""
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.s3.download_file(self.bucket, key, str(p))

    def get_json(self, key: str) -> Dict[str, Any]:
        """Retrieve and decode a JSON object from the S3 bucket."""
        import json

        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        data = response["Body"].read()
        return json.loads(data.decode())

    def get_metadata(self, key: str) -> Dict[str, Any]:
        """Get metadata for an object in the S3 bucket."""
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)
            return {
                "size": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag"),
                "content_type": response.get("ContentType"),
                "metadata": response.get("Metadata", {}),
            }
        except Exception:
            return {}
