from __future__ import annotations

from typing import Iterable

from rich import print
from sqlalchemy import func

from .config import MinioStorageConfig, S3StorageConfig
from .db import get_sync_session, init_db_sync
from .db.models import Evidence, EvidenceManifestEntry, EvidenceVersion, System
from .db.models import EvidenceManifest as DBManifest
from .storage.minio_backend import MinioEvidenceVault
from .storage.s3_backend import S3EvidenceVault


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


def persist_manifest_and_artifacts(
    session, env: str, env_description: str | None, manifest, artifacts: Iterable
):
    from datetime import datetime

    collected_dt = datetime.utcfromtimestamp(manifest.created_at)

    system = session.query(System).filter_by(name=env).one_or_none()
    if not system:
        system = System(name=env, environment=env, description=env_description, attributes={})
        session.add(system)
        session.flush()

    evidence_rows = []
    for a in artifacts:
        metadata = a.metadata if isinstance(a.metadata, dict) else {}
        cleaned_metadata = {k: v for k, v in metadata.items() if k != "_local_path"}
        ev = Evidence(
            system=system,
            evidence_type=metadata.get("kind", "unknown")
            if isinstance(metadata, dict)
            else "unknown",
            key=a.key,
            vault_path=None,
            filename=a.filename,
            sha256=a.sha256,
            size=a.size,
            attributes=cleaned_metadata,
        )
        session.add(ev)
        session.flush()

        next_version = (
            session.query(func.coalesce(func.max(EvidenceVersion.version), 0))
            .filter(EvidenceVersion.evidence_id == ev.id)
            .scalar()
            or 0
        ) + 1

        version_payload = {
            "key": a.key,
            "filename": a.filename,
            "sha256": a.sha256,
            "size": a.size,
            "metadata": cleaned_metadata,
        }

        version = EvidenceVersion(
            evidence=ev,
            version=next_version,
            data=version_payload,
            collected_at=collected_dt,
            collector_version=getattr(manifest, "version", None),
            attributes={"source": "cli_collect", "environment": env},
        )
        session.add(version)
        evidence_rows.append(ev)

    db_manifest = DBManifest(
        system=system,
        environment=manifest.environment,
        version=manifest.version,
        created_at=collected_dt,
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
        persist_manifest_and_artifacts(
            session, env, getattr(envcfg, "description", None), manifest, artifacts
        )
        print("[green]Persisted evidence and manifest to database")
    except Exception as exc:
        print(f"[yellow]DB persistence failed; continuing: {exc}")


def persist_validation_results(session, env: str, results_dict):
    """
    Persist validation results to database.

    Args:
        session: Database session
        env: Environment/system name
        results_dict: Dict of control_id -> ValidationResult
    """
    from .db.models import Control
    from .db.models import ValidationStatus as DBValidationStatus
    from .validators import ValidationStatus

    # Get or create system
    system = session.query(System).filter_by(name=env).one_or_none()
    if not system:
        system = System(name=env, environment=env, description=None, attributes={})
        session.add(system)
        session.flush()

    # Process each validation result
    for control_id, result in results_dict.items():
        # Get or create control
        control = session.query(Control).filter_by(control_id=control_id.upper()).one_or_none()
        if not control:
            control = Control(
                control_id=control_id.upper(),
                title=result.metadata.get("description", f"Control {control_id.upper()}"),
                description=result.message,
                family=control_id.split("-")[0].upper() if "-" in control_id else "UNKNOWN",
                attributes={},
            )
            session.add(control)
            session.flush()

        # Map ValidationStatus enum to DB enum
        if isinstance(result.status, ValidationStatus):
            db_status = DBValidationStatus[result.status.name]
        else:
            db_status = DBValidationStatus.UNKNOWN

        # Create validation result
        from .db.models import ValidationResult as DBValidationResult

        validation = DBValidationResult(
            system=system,
            control=control,
            status=db_status,
            message=result.message,
            evidence_keys=result.evidence_keys,
            remediation=result.remediation,
            attributes=result.metadata or {},
        )
        session.add(validation)

    session.commit()


def persist_validation_if_db(envcfg, env: str, results_dict):
    """
    Persist validation results to DB if database_url configured.

    Args:
        envcfg: Environment configuration
        env: Environment/system name
        results_dict: Dict of control_id -> ValidationResult
    """
    session = get_db_session(envcfg)
    if not session:
        return
    try:
        persist_validation_results(session, env, results_dict)
        print(f"[green]Persisted {len(results_dict)} validation results to database")
    except Exception as exc:
        print(f"[yellow]Validation persistence failed; continuing: {exc}")
