"""Minio backend implementation for auditly evidence vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from minio import Minio
from minio.error import S3Error

from .base import EvidenceVault


class MinioEvidenceVault(EvidenceVault):
    """Evidence vault implementation using Minio as the backend."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool = True,
    ) -> None:
        """Initialize the MinioEvidenceVault with connection details."""
        self.bucket = bucket
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Ensure the bucket exists in Minio; create if missing."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_file(
        self, src_path: Path | str, dest_key: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Upload a file to the Minio bucket."""
        p = Path(src_path)
        self.client.fput_object(self.bucket, dest_key, str(p), metadata=metadata or {})
        return {"bucket": self.bucket, "key": dest_key, "size": p.stat().st_size}

    def put_json(
        self, dest_key: str, data: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Upload a JSON string as an object to the Minio bucket."""
        import io

        b = data.encode()
        self.client.put_object(
            self.bucket,
            dest_key,
            io.BytesIO(b),
            length=len(b),
            content_type="application/json",
            metadata=metadata or {},
        )
        return {"bucket": self.bucket, "key": dest_key, "size": len(b)}

    def exists(self, dest_key: str) -> bool:
        """Check if an object exists in the Minio bucket."""
        try:
            self.client.stat_object(self.bucket, dest_key)
            return True
        except S3Error:
            return False

    def list(self, prefix: str) -> list[str]:
        """List object keys in the Minio bucket with the given prefix."""
        keys: list[str] = []
        for obj in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            if getattr(obj, "object_name", None):
                keys.append(obj.object_name)
        return keys

    def fetch(self, key: str, out_path: Path | str) -> None:
        """Download an object from the Minio bucket to a local path."""
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.client.fget_object(self.bucket, key, str(p))

    def get_json(self, key: str) -> dict[str, Any]:
        """Retrieve and decode a JSON object from the Minio bucket."""
        import json

        response = self.client.get_object(self.bucket, key)
        data = response.read()
        response.close()
        response.release_conn()
        return json.loads(data.decode())

    def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for an object in the Minio bucket."""
        try:
            stat = self.client.stat_object(self.bucket, key)
            return {
                "size": stat.size,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "metadata": stat.metadata or {},
            }
        except S3Error:
            return {}
