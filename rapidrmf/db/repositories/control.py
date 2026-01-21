"""Repository for control operations."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Catalog, Control, ControlRequirement


class ControlRepository:
    """Repository for control operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_control_by_id(self, catalog: Catalog, control_id: str) -> Optional[Control]:
        """Get control by ID within a catalog."""
        stmt = select(Control).where(
            Control.catalog_id == catalog.id, Control.control_id == control_id.upper()
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

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
        """Create or update a control."""
        control = await self.get_control_by_id(catalog, control_id)
        if control:
            control.title = title
            control.family = family
            control.description = description
            control.remediation = remediation
            control.baseline_required = baseline_required
            control.attributes = attributes or control.attributes
        else:
            control = Control(
                catalog=catalog,
                control_id=control_id.upper(),
                title=title,
                family=family,
                description=description,
                remediation=remediation,
                baseline_required=baseline_required,
                attributes=attributes or {},
            )
            self.session.add(control)
        await self.session.flush()
        return control

    async def list_controls(self) -> list[Control]:
        """List all controls."""
        stmt = select(Control)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_control_requirements(self, control_ids: list[int]) -> list[ControlRequirement]:
        """Get control requirements for specific controls."""
        stmt = select(ControlRequirement).where(ControlRequirement.control_id.in_(control_ids))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
