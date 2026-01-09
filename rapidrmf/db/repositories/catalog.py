"""Repository for catalog operations."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Catalog


class CatalogRepository:
    """Repository for catalog operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_catalog_by_name(self, name: str) -> Optional[Catalog]:
        """Get catalog by name."""
        stmt = select(Catalog).where(Catalog.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

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
        """Create or update a catalog."""
        catalog = await self.get_catalog_by_name(name)
        if catalog:
            catalog.title = title
            catalog.framework = framework
            catalog.version = version
            catalog.baseline = baseline
            catalog.oscal_path = oscal_path
            catalog.attributes = attributes or catalog.attributes
        else:
            catalog = Catalog(
                name=name,
                title=title,
                framework=framework,
                version=version,
                baseline=baseline,
                oscal_path=oscal_path,
                attributes=attributes or {},
            )
            self.session.add(catalog)
        await self.session.flush()
        return catalog
