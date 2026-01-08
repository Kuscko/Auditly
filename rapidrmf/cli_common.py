from __future__ import annotations

from pathlib import Path
from typing import Optional, Iterable

from rich import print

from .config import MinioStorageConfig, S3StorageConfig
from .storage.minio_backend import MinioEvidenceVault
from .storage.s3_backend import S3EvidenceVault
from .db import init_db_sync, get_sync_session
from .db.models import System, Evidence, EvidenceManifest as DBManifest, EvidenceManifestEntry


def vault_from_envcfg(envcfg):
    if isinstance(envcfg.storage, MinioStorageConfig):
        return MinioEvidenceVault(
            endpoint=envcfg.storage.endpoint,
            bucket=envcfg.storage.bucket,
            access_key=envcfg.storage.access_key,
            secret_key=envcfg.storage.secret_key,
            secure=envcfg.storage.secure,
        )
    if isinstance(envcfg.storage, S3StorageConfig):
        return S3EvidenceVault(
            bucket=envcfg.storage.bucket,
            region=envcfg.storage.region,
            profile=envcfg.storage.profile,
        )
    raise ValueError("Unsupported storage backend")


def get_db_session(envcfg):
    if not getattr(envcfg, "database_url", None):
        return None
    try:
        init_db_sync(envcfg.database_url)
        return get_sync_session()
    except Exception as exc:
        print(f"[yellow]Database not available; continuing without DB persistence: {exc}")
        return None


def persist_manifest_and_artifacts(session, env: str, env_description: str | None, manifest, artifacts: Iterable):
    from datetime import datetime

    system = session.query(System).filter_by(name=env).one_or_none()
    if not system:
        system = System(name=env, environment=env, description=env_description, attributes={})
        session.add(system)
        session.flush()

    evidence_rows = []
    for a in artifacts:
        ev = Evidence(
            system=system,
            evidence_type=a.metadata.get("kind", "unknown") if isinstance(a.metadata, dict) else "unknown",
            key=a.key,
            vault_path=None,
            filename=a.filename,
            sha256=a.sha256,
            size=a.size,
            attributes=a.metadata if isinstance(a.metadata, dict) else {},
        )
        session.add(ev)
        evidence_rows.append(ev)
    session.flush()

    created_dt = datetime.utcfromtimestamp(manifest.created_at)
    db_manifest = DBManifest(
        system=system,
        environment=manifest.environment,
        version=manifest.version,
        created_at=created_dt,
        overall_hash=manifest.overall_hash or manifest.compute_overall_hash(),
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

    session.commit()


def persist_if_db(envcfg, env: str, manifest, artifacts: Iterable):
    session = get_db_session(envcfg)
    if not session:
        return
    try:
        persist_manifest_and_artifacts(session, env, getattr(envcfg, "description", None), manifest, artifacts)
        print("[green]Persisted evidence and manifest to database")
    except Exception as exc:
        print(f"[yellow]DB persistence failed; continuing: {exc}")
