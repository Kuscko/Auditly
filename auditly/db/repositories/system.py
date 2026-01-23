"""Repository for system operations."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import System


class SystemRepository:
    """Repository for system operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the SystemRepository with an async database session."""
        self.session = session

    async def get_system_by_name(self, name: str) -> Optional[System]:
        """Get system by name."""
        stmt = select(System).where(System.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_systems_by_environment(self, environment: str) -> list[System]:
        """List systems for an environment."""
        stmt = select(System).where(System.environment == environment)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_system(
        self,
        name: str,
        environment: str,
        description: str | None = None,
        attributes: dict | None = None,
    ) -> System:
        """Create or update a system."""
        system = await self.get_system_by_name(name)
        if system:
            system.environment = environment
            system.description = description
            system.attributes = attributes or system.attributes
        else:
            system = System(
                name=name,
                environment=environment,
                description=description,
                attributes=attributes or {},
            )
            self.session.add(system)
        await self.session.flush()
        return system
