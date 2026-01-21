from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


def sha256_file(path: Path | str) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ArtifactRecord:
    key: str
    filename: str
    sha256: str
    size: int
    metadata: Dict[str, Any]


@dataclass
class EvidenceManifest:
    version: str
    environment: str
    created_at: float
    artifacts: List[ArtifactRecord]
    overall_hash: Optional[str] = None
    notes: Optional[str] = None

    def compute_overall_hash(self) -> str:
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
        if not self.overall_hash:
            self.compute_overall_hash()
        return json.dumps(asdict(self), indent=2, sort_keys=False)

    @staticmethod
    def create(
        environment: str, artifacts: List[ArtifactRecord], notes: Optional[str] = None
    ) -> EvidenceManifest:
        m = EvidenceManifest(
            version="1.0",
            environment=environment,
            created_at=time.time(),
            artifacts=artifacts,
            notes=notes,
        )
        m.compute_overall_hash()
        return m
