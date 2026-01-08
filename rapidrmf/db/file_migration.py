"""Utility to migrate existing file-based manifests into the database."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import init_db_sync, get_sync_session
from .models import System, Evidence, EvidenceManifest as DBManifest, EvidenceManifestEntry


def migrate_manifests(manifests_dir: Path | str, env: str, database_url: str, env_description: Optional[str] = None) -> int:
    """
    Load manifest JSON files from a directory and persist them into the database.

    Args:
        manifests_dir: Directory containing manifest JSON files (e.g., manifests/<env>/...) or a single file.
        env: Environment key/name to assign to the system record.
        database_url: SQLAlchemy URL for the target database.
        env_description: Optional system description.

    Returns:
        Count of manifests migrated.
    """
    path = Path(manifests_dir)
    if not path.exists():
        raise FileNotFoundError(f"Manifests path not found: {path}")

    init_db_sync(database_url)
    session = get_sync_session()

    system = session.query(System).filter_by(name=env).one_or_none()
    if not system:
        system = System(name=env, environment=env, description=env_description, attributes={})
        session.add(system)
        session.flush()

    manifest_files = [path] if path.is_file() else list(path.rglob("*.json"))
    migrated = 0

    for mf in manifest_files:
        data = json.loads(mf.read_text())
        artifacts = data.get("artifacts", [])
        created_at_ts = data.get("created_at") or 0
        created_at = datetime.utcfromtimestamp(created_at_ts) if created_at_ts else datetime.utcnow()
        overall_hash = data.get("overall_hash")
        version = data.get("version", "0.1")
        environment = data.get("environment", env)

        evidence_rows = []
        for a in artifacts:
            ev = Evidence(
                system=system,
                evidence_type=a.get("metadata", {}).get("kind", "unknown"),
                key=a.get("key", ""),
                vault_path=None,
                filename=a.get("filename"),
                sha256=a.get("sha256", ""),
                size=a.get("size"),
                attributes=a.get("metadata", {}),
            )
            session.add(ev)
            evidence_rows.append(ev)
        session.flush()

        db_manifest = DBManifest(
            system=system,
            environment=environment,
            version=version,
            created_at=created_at,
            overall_hash=overall_hash,
            attributes={},
        )
        session.add(db_manifest)
        session.flush()

        for ev in evidence_rows:
            entry = EvidenceManifestEntry(
                manifest=db_manifest,
                evidence=ev,
                key=ev.key,
                filename=ev.filename or "",
                sha256=ev.sha256,
                size=ev.size,
            )
            session.add(entry)

        migrated += 1

    session.commit()
    return migrated
