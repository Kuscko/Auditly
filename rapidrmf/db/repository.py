"""Repository layer for database operations."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    System,
    Evidence,
    EvidenceManifest,
    EvidenceManifestEntry,
    ValidationResult,
    Finding,
    ControlRequirement,
    Control,
    Catalog,
    JobRun,
)


class Repository:
    """Async repository for core entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Catalogs
    async def get_catalog_by_name(self, name: str) -> Optional[Catalog]:
        stmt = select(Catalog).where(Catalog.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_catalog(self, name: str, title: str, framework: str, version: str | None = None, baseline: str | None = None, oscal_path: str | None = None, attributes: dict | None = None) -> Catalog:
        catalog = await self.get_catalog_by_name(name)
        if catalog:
            catalog.title = title
            catalog.framework = framework
            catalog.version = version
            catalog.baseline = baseline
            catalog.oscal_path = oscal_path
            catalog.attributes = attributes or catalog.attributes
        else:
            catalog = Catalog(name=name, title=title, framework=framework, version=version, baseline=baseline, oscal_path=oscal_path, attributes=attributes or {})
            self.session.add(catalog)
        await self.session.flush()
        return catalog
    
    # Controls
    async def get_control_by_id(self, catalog: Catalog, control_id: str) -> Optional[Control]:
        stmt = select(Control).where(Control.catalog_id == catalog.id, Control.control_id == control_id.upper())
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
    
    async def upsert_control(self, catalog: Catalog, control_id: str, title: str, family: str, description: str | None = None, remediation: str | None = None, baseline_required: bool = False, attributes: dict | None = None) -> Control:
        control = await self.get_control_by_id(catalog, control_id)
        if control:
            control.title = title
            control.family = family
            control.description = description
            control.remediation = remediation
            control.baseline_required = baseline_required
            control.attributes = attributes or control.attributes
        else:
            control = Control(catalog=catalog, control_id=control_id.upper(), title=title, family=family, description=description, remediation=remediation, baseline_required=baseline_required, attributes=attributes or {})
            self.session.add(control)
        await self.session.flush()
        return control

    async def list_controls(self) -> list[Control]:
        stmt = select(Control)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Systems
    async def get_system_by_name(self, name: str) -> Optional[System]:
        stmt = select(System).where(System.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_systems_by_environment(self, environment: str) -> list[System]:
        stmt = select(System).where(System.environment == environment)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_system(self, name: str, environment: str, description: str | None = None, attributes: dict | None = None) -> System:
        system = await self.get_system_by_name(name)
        if system:
            system.environment = environment
            system.description = description
            system.attributes = attributes or system.attributes
        else:
            system = System(name=name, environment=environment, description=description, attributes=attributes or {})
            self.session.add(system)
        await self.session.flush()
        return system

    # Evidence
    async def add_evidence(self, system: System, evidence_type: str, key: str, sha256: str, size: int | None = None, vault_path: str | None = None, filename: str | None = None, attributes: dict | None = None, expires_at=None) -> Evidence:
        ev = Evidence(
            system=system,
            evidence_type=evidence_type,
            key=key,
            sha256=sha256,
            size=size,
            vault_path=vault_path,
            filename=filename,
            attributes=attributes or {},
            expires_at=expires_at,
        )
        self.session.add(ev)
        await self.session.flush()
        return ev

    async def list_evidence_for_system(self, system: System) -> list[Evidence]:
        stmt = select(Evidence).where(Evidence.system_id == system.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Manifests
    async def create_manifest(self, system: Optional[System], environment: str, overall_hash: str, notes: str | None = None, attributes: dict | None = None) -> EvidenceManifest:
        manifest = EvidenceManifest(
            system_id=system.id if system else None,
            environment=environment,
            overall_hash=overall_hash,
            notes=notes,
            attributes=attributes or {},
        )
        self.session.add(manifest)
        await self.session.flush()
        return manifest

    async def add_manifest_entries(self, manifest: EvidenceManifest, evidence_list: Iterable[Evidence]):
        for ev in evidence_list:
            entry = EvidenceManifestEntry(
                manifest=manifest,
                evidence=ev,
                key=ev.key,
                filename=ev.filename or "",
                sha256=ev.sha256,
                size=ev.size,
            )
            self.session.add(entry)
        await self.session.flush()

    # Validation
    async def add_validation_result(self, system: System, control: Control, status, message: str | None, evidence_keys: list[str], remediation: str | None, metadata: dict | None = None) -> ValidationResult:
        # Convert status to DB enum if needed
        from rapidrmf.validators import ValidationStatus as ValidatorStatus
        if isinstance(status, ValidatorStatus):
            # Map validator enum to DB enum
            db_status = ValidationResult.status.type.python_type[status.name]
        else:
            db_status = status
        
        result = ValidationResult(
            system=system,
            control=control,
            status=db_status,
            message=message,
            evidence_keys=evidence_keys,
            remediation=remediation,
            attributes=metadata or {},
        )
        self.session.add(result)
        await self.session.flush()
        return result

    # Findings
    async def add_finding(self, system: System, control: Control | None, title: str, description: str, severity: str, status: str = "open", metadata: dict | None = None) -> Finding:
        finding = Finding(
            system=system,
            control=control,
            title=title,
            description=description,
            severity=severity,
            status=status,
            attributes=metadata or {},
        )
        self.session.add(finding)
        await self.session.flush()
        return finding

    # Control requirements helpers
    async def get_control_requirements(self, control_ids: list[int]) -> list[ControlRequirement]:
        stmt = select(ControlRequirement).where(ControlRequirement.control_id.in_(control_ids))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
    
    # Validation result queries
    async def get_latest_validation_results(self, system: System, limit: int = 100) -> list[ValidationResult]:
        """Get most recent validation results for a system."""
        stmt = select(ValidationResult).where(
            ValidationResult.system_id == system.id
        ).options(
            selectinload(ValidationResult.control)
        ).order_by(
            ValidationResult.validated_at.desc()
        ).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
    
    async def get_validation_results_by_status(self, system: System, status) -> list[ValidationResult]:
        """Get validation results filtered by status (pass, fail, insufficient_evidence, etc.)."""
        stmt = select(ValidationResult).where(
            ValidationResult.system_id == system.id,
            ValidationResult.status == status
        ).options(
            selectinload(ValidationResult.control)
        ).order_by(
            ValidationResult.validated_at.desc()
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
    
    async def get_validation_history_for_control(self, system: System, control: Control, limit: int = 10) -> list[ValidationResult]:
        """Get validation history for a specific control."""
        stmt = select(ValidationResult).where(
            ValidationResult.system_id == system.id,
            ValidationResult.control_id == control.id
        ).options(
            selectinload(ValidationResult.control)
        ).order_by(
            ValidationResult.validated_at.desc()
        ).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # Job runs (scheduler)
    async def start_job_run(self, job_type: str, environment: str, attributes: dict | None = None) -> JobRun:
        job = JobRun(
            job_type=job_type,
            environment=environment,
            status="running",
            attributes=attributes or {},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def finish_job_run(self, job: JobRun, status: str = "success", error: str | None = None, metrics: dict | None = None, attributes_update: dict | None = None) -> JobRun:
        job.status = status
        job.error = error
        job.metrics = metrics or job.metrics
        if attributes_update:
            job.attributes.update(attributes_update)
        # finished_at will be set by DB default or here via SQLAlchemy
        from datetime import datetime
        job.finished_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def get_recent_job_runs(self, job_type: str | None = None, environment: str | None = None, limit: int = 50) -> list[JobRun]:
        stmt = select(JobRun)
        if job_type:
            stmt = stmt.where(JobRun.job_type == job_type)
        if environment:
            stmt = stmt.where(JobRun.environment == environment)
        stmt = stmt.order_by(JobRun.started_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
