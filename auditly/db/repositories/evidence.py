"""Repository for evidence operations."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Evidence,
    EvidenceAccessLog,
    EvidenceManifest,
    EvidenceManifestEntry,
    EvidenceVersion,
    System,
)


class EvidenceRepository:
    """Repository for evidence and manifest operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the EvidenceRepository with a database session."""
        self.session = session

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
        """Add evidence record."""
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
        """List all evidence for a system."""
        stmt = select(Evidence).where(Evidence.system_id == system.id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_manifest(
        self,
        system: Optional[System],
        environment: str,
        overall_hash: str,
        notes: str | None = None,
        attributes: dict | None = None,
    ) -> EvidenceManifest:
        """Create evidence manifest."""
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

    async def add_manifest_entries(
        self, manifest: EvidenceManifest, evidence_list: Iterable[Evidence]
    ):
        """Add entries to manifest."""
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

        async def add_evidence_version(
            self,
            evidence: Evidence,
            data: dict,
            collector_version: str | None = None,
            signature: str | None = None,
            collected_at: Optional[datetime] = None,
            attributes: dict | None = None,
        ) -> EvidenceVersion:
            """Create a new version record for an evidence row."""
            stmt = select(func.coalesce(func.max(EvidenceVersion.version), 0)).where(
                EvidenceVersion.evidence_id == evidence.id
            )
            res = await self.session.execute(stmt)
            next_version = (res.scalar_one() or 0) + 1

            version = EvidenceVersion(
                evidence=evidence,
                version=next_version,
                data=data,
                collected_at=collected_at or datetime.utcnow(),
                collector_version=collector_version,
                signature=signature,
                attributes=attributes or {},
            )
            self.session.add(version)
            await self.session.flush()
            return version

        async def log_access(
            self,
            evidence: Evidence,
            user_id: str,
            action: str,
            ip_address: str | None = None,
            attributes: dict | None = None,
        ) -> EvidenceAccessLog:
            """Log access to evidence for auditability."""
            entry = EvidenceAccessLog(
                evidence=evidence,
                user_id=user_id,
                action=action,
                ip_address=ip_address,
                attributes=attributes or {},
            )
            self.session.add(entry)
            await self.session.flush()
            return entry
