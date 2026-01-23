"""Repository layer for database operations.

DEPRECATED: This monolithic Repository class is maintained for backward compatibility.
New code should use domain-specific repositories from auditly.db.repositories:
    - CatalogRepository
    - ControlRepository
    - SystemRepository
    - EvidenceRepository
    - ValidationRepository
    - JobRunRepository
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Catalog,
    Control,
    ControlRequirement,
    Evidence,
    EvidenceManifest,
    Finding,
    JobRun,
    System,
    ValidationResult,
)
from .repositories import (
    CatalogRepository,
    ControlRepository,
    EvidenceRepository,
    JobRunRepository,
    SystemRepository,
    ValidationRepository,
)


class Repository:
    """Unified repository (backward compatible).

    Delegates to domain-specific repositories internally.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the Repository with a database session."""
        self.session = session
        self._catalog_repo = CatalogRepository(session)
        self._control_repo = ControlRepository(session)
        self._system_repo = SystemRepository(session)
        self._evidence_repo = EvidenceRepository(session)
        self._validation_repo = ValidationRepository(session)
        self._jobrun_repo = JobRunRepository(session)

    # Catalogs - delegate to CatalogRepository
    async def get_catalog_by_name(self, name: str) -> Catalog | None:
        """Get a catalog by its name."""
        return await self._catalog_repo.get_catalog_by_name(name)

    async def upsert_catalog(
        self,
        name: str,
        title: str,
        framework: str,
        version: str | None = None,
        baseline: str | None = None,
        oscal_path: str | None = None,
        attributes: dict | None = None,
    ) -> Catalog:
        """Insert or update a catalog."""
        return await self._catalog_repo.upsert_catalog(
            name, title, framework, version, baseline, oscal_path, attributes
        )

    # Controls - delegate to ControlRepository
    async def get_control_by_id(self, catalog: Catalog, control_id: str) -> Control | None:
        """Get a control by its ID from a catalog."""
        return await self._control_repo.get_control_by_id(catalog, control_id)

    async def upsert_control(
        self,
        catalog: Catalog,
        control_id: str,
        title: str,
        family: str,
        description: str | None = None,
        remediation: str | None = None,
        baseline_required: bool = False,
        attributes: dict | None = None,
    ) -> Control:
        """Insert or update a control in a catalog."""
        return await self._control_repo.upsert_control(
            catalog,
            control_id,
            title,
            family,
            description,
            remediation,
            baseline_required,
            attributes,
        )

    async def list_controls(self) -> list[Control]:
        """List all controls."""
        return await self._control_repo.list_controls()

    async def get_control_requirements(self, control_ids: list[int]) -> list[ControlRequirement]:
        """Get requirements for a list of control IDs."""
        return await self._control_repo.get_control_requirements(control_ids)

    # Systems - delegate to SystemRepository
    async def get_system_by_name(self, name: str) -> System | None:
        """Get a system by its name."""
        return await self._system_repo.get_system_by_name(name)

    async def list_systems_by_environment(self, environment: str) -> list[System]:
        """List all systems for a given environment."""
        return await self._system_repo.list_systems_by_environment(environment)

    async def upsert_system(
        self,
        name: str,
        environment: str,
        description: str | None = None,
        attributes: dict | None = None,
    ) -> System:
        """Insert or update a system."""
        return await self._system_repo.upsert_system(name, environment, description, attributes)

    # Evidence - delegate to EvidenceRepository
    async def add_evidence(
        self,
        system: System,
        evidence_type: str,
        key: str,
        sha256: str,
        size: int | None = None,
        vault_path: str | None = None,
        filename: str | None = None,
        attributes: dict | None = None,
        expires_at=None,
    ) -> Evidence:
        """Add evidence for a system."""
        return await self._evidence_repo.add_evidence(
            system, evidence_type, key, sha256, size, vault_path, filename, attributes, expires_at
        )

    async def list_evidence_for_system(self, system: System) -> list[Evidence]:
        """List all evidence for a system."""
        return await self._evidence_repo.list_evidence_for_system(system)

    async def create_manifest(
        self,
        system: System | None,
        environment: str,
        overall_hash: str,
        notes: str | None = None,
        attributes: dict | None = None,
    ) -> EvidenceManifest:
        """Create an evidence manifest for a system and environment."""
        return await self._evidence_repo.create_manifest(
            system, environment, overall_hash, notes, attributes
        )

    async def add_manifest_entries(
        self, manifest: EvidenceManifest, evidence_list: Iterable[Evidence]
    ):
        """Add entries to an evidence manifest."""
        return await self._evidence_repo.add_manifest_entries(manifest, evidence_list)

    # Validation - delegate to ValidationRepository
    async def add_validation_result(
        self,
        system: System,
        control: Control,
        status,
        message: str | None,
        evidence_keys: list[str],
        remediation: str | None,
        metadata: dict | None = None,
    ) -> ValidationResult:
        """Add a validation result for a system and control."""
        return await self._validation_repo.add_validation_result(
            system, control, status, message, evidence_keys, remediation, metadata
        )

    async def add_finding(
        self,
        system: System,
        control: Control | None,
        title: str,
        description: str,
        severity: str,
        status: str = "open",
        metadata: dict | None = None,
    ) -> Finding:
        """Add a finding for a system and control."""
        return await self._validation_repo.add_finding(
            system, control, title, description, severity, status, metadata
        )

    async def get_latest_validation_results(
        self, system: System, limit: int = 100
    ) -> list[ValidationResult]:
        """Get the latest validation results for a system."""
        return await self._validation_repo.get_latest_validation_results(system, limit)

    async def get_validation_results_by_status(
        self, system: System, status
    ) -> list[ValidationResult]:
        """Get validation results for a system filtered by status."""
        return await self._validation_repo.get_validation_results_by_status(system, status)

    async def get_validation_history_for_control(
        self, system: System, control: Control, limit: int = 10
    ) -> list[ValidationResult]:
        """Get validation history for a control in a system."""
        return await self._validation_repo.get_validation_history_for_control(
            system, control, limit
        )

    # Job runs - delegate to JobRunRepository
    async def start_job_run(
        self, job_type: str, environment: str, attributes: dict | None = None
    ) -> JobRun:
        """Start a new job run."""
        return await self._jobrun_repo.start_job_run(job_type, environment, attributes)

    async def finish_job_run(
        self,
        job: JobRun,
        status: str = "success",
        error: str | None = None,
        metrics: dict | None = None,
        attributes_update: dict | None = None,
    ) -> JobRun:
        """Finish a job run and update its status."""
        return await self._jobrun_repo.finish_job_run(
            job, status, error, metrics, attributes_update
        )

    async def get_recent_job_runs(
        self, job_type: str | None = None, environment: str | None = None, limit: int = 50
    ) -> list[JobRun]:
        """Get recent job runs, optionally filtered by type and environment."""
        return await self._jobrun_repo.get_recent_job_runs(job_type, environment, limit)
