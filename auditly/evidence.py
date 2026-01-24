"""Evidence utilities and data structures for artifact tracking and hashing."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


def sha256_file(path: Path | str) -> str:
    """Compute the SHA-256 hash of a file at the given path."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ArtifactRecord:
    """Record representing a single evidence artifact."""

    key: str
    filename: str
    sha256: str
    size: int
    metadata: dict[str, object]


@dataclass
class EvidenceManifest:
    """Manifest containing metadata and artifact records for evidence collection."""

    version: str
    environment: str
    created_at: float
    artifacts: list[ArtifactRecord]
    overall_hash: str | None = None
    notes: str | None = None

    def compute_overall_hash(self) -> str:
        """Compute a hash representing the entire manifest and its artifacts."""
        data = json.dumps(
            {
                "environment": self.environment,
                "artifacts": [asdict(a) for a in self.artifacts],
            },
            sort_keys=True,
        ).encode()
        self.overall_hash = hashlib.sha256(data).hexdigest()
        return self.overall_hash

    def to_json(self) -> str:
        """Serialize the manifest to a JSON string."""
        if not self.overall_hash:
            self.compute_overall_hash()
        return json.dumps(asdict(self), indent=2, sort_keys=False)

    @staticmethod
    def create(
        environment: str, artifacts: list[ArtifactRecord], notes: str | None = None
    ) -> EvidenceManifest:
        """Create a new EvidenceManifest with the current timestamp."""
        m = EvidenceManifest(
            version="1.0",
            environment=environment,
            created_at=time.time(),
            artifacts=artifacts,
            notes=notes,
        )
        m.compute_overall_hash()
        return m
