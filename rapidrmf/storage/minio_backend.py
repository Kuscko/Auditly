from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from minio import Minio
from minio.error import S3Error

from .base import EvidenceVault


class MinioEvidenceVault(EvidenceVault):
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = True,
    ) -> None:
        self.bucket = bucket
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_file(self, src_path: Path | str, dest_key: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        p = Path(src_path)
        self.client.fput_object(self.bucket, dest_key, str(p), metadata=metadata or {})
        return {"bucket": self.bucket, "key": dest_key, "size": p.stat().st_size}

    def put_json(self, dest_key: str, data: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        import io

        b = data.encode()
        self.client.put_object(
            self.bucket, dest_key, io.BytesIO(b), length=len(b), content_type="application/json", metadata=metadata or {}
        )
        return {"bucket": self.bucket, "key": dest_key, "size": len(b)}

    def exists(self, dest_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, dest_key)
            return True
        except S3Error:
            return False

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for obj in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            if getattr(obj, "object_name", None):
                keys.append(obj.object_name)
        return keys

    def fetch(self, key: str, out_path: Path | str) -> None:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.client.fget_object(self.bucket, key, str(p))

    def get_json(self, key: str) -> Dict[str, Any]:
        import json
        response = self.client.get_object(self.bucket, key)
        data = response.read()
        response.close()
        response.release_conn()
        return json.loads(data.decode())

    def get_metadata(self, key: str) -> Dict[str, Any]:
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
