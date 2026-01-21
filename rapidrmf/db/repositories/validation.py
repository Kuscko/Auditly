"""Repository for validation operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Control, Finding, System, ValidationResult


class ValidationRepository:
    """Repository for validation results and findings."""

    def __init__(self, session: AsyncSession):
        self.session = session

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
        """Add validation result."""
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
        """Add finding."""
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

    async def get_latest_validation_results(
        self, system: System, limit: int = 100
    ) -> list[ValidationResult]:
        """Get most recent validation results for a system."""
        stmt = (
            select(ValidationResult)
            .where(ValidationResult.system_id == system.id)
            .options(selectinload(ValidationResult.control))
            .order_by(ValidationResult.validated_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_validation_results_by_status(
        self, system: System, status
    ) -> list[ValidationResult]:
        """Get validation results filtered by status."""
        stmt = (
            select(ValidationResult)
            .where(ValidationResult.system_id == system.id, ValidationResult.status == status)
            .options(selectinload(ValidationResult.control))
            .order_by(ValidationResult.validated_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_validation_history_for_control(
        self, system: System, control: Control, limit: int = 10
    ) -> list[ValidationResult]:
        """Get validation history for a specific control."""
        stmt = (
            select(ValidationResult)
            .where(
                ValidationResult.system_id == system.id,
                ValidationResult.control_id == control.id,
            )
            .options(selectinload(ValidationResult.control))
            .order_by(ValidationResult.validated_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
