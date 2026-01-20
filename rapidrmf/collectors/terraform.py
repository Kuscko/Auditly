from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


def collect_terraform(
    environment: str,
    plan_path: Path | str,
    apply_log_path: Optional[Path | str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    key_prefix: str = "terraform",
) -> (List[ArtifactRecord], EvidenceManifest):
    plan = Path(plan_path)
    artifacts: List[ArtifactRecord] = []
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/plan/{plan.name}",
            filename=plan.name,
            sha256=sha256_file(plan),
            size=plan.stat().st_size,
            metadata={"kind": "terraform-plan", **(extra_metadata or {})},
        )
    )
    if apply_log_path:
        apply = Path(apply_log_path)
        artifacts.append(
            ArtifactRecord(
                key=f"{key_prefix}/apply/{apply.name}",
                filename=apply.name,
                sha256=sha256_file(apply),
                size=apply.stat().st_size,
                metadata={"kind": "terraform-apply-log", **(extra_metadata or {})},
            )
        )
    manifest = EvidenceManifest.create(
        environment=environment, artifacts=artifacts, notes="terraform collection"
    )
    return artifacts, manifest
