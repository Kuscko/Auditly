"""Repository for evidence operations."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Evidence, EvidenceManifest, EvidenceManifestEntry, System


class EvidenceRepository:
    """Repository for evidence and manifest operations."""

    def __init__(self, session: AsyncSession):
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
