"""Repository layer for database operations."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    System,
    Evidence,
    EvidenceManifest,
    EvidenceManifestEntry,
    ValidationResult,
    Finding,
    ControlRequirement,
    Control,
)


class Repository:
    """Async repository for core entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Systems
    async def get_system_by_name(self, name: str) -> Optional[System]:
        stmt = select(System).where(System.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

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

    # Manifests
    async def create_manifest(self, system: Optional[System], environment: str, overall_hash: str, notes: str | None = None, attributes: dict | None = None) -> EvidenceManifest:
        manifest = EvidenceManifest(
            system=system,
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
        result = ValidationResult(
            system=system,
            control=control,
            status=status,
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
