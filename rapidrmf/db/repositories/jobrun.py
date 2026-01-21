"""Repository for job run operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import JobRun


class JobRunRepository:
    """Repository for scheduled job runs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_job_run(
        self, job_type: str, environment: str, attributes: dict | None = None
    ) -> JobRun:
        """Start a job run."""
        job = JobRun(
            job_type=job_type,
            environment=environment,
            status="running",
            attributes=attributes or {},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def finish_job_run(
        self,
        job: JobRun,
        status: str = "success",
        error: str | None = None,
        metrics: dict | None = None,
        attributes_update: dict | None = None,
    ) -> JobRun:
        """Finish a job run."""
        job.status = status
        job.error = error
        job.metrics = metrics or job.metrics
        if attributes_update:
            job.attributes.update(attributes_update)
        job.finished_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def get_recent_job_runs(
        self, job_type: str | None = None, environment: str | None = None, limit: int = 50
    ) -> list[JobRun]:
        """Get recent job runs."""
        stmt = select(JobRun)
        if job_type:
            stmt = stmt.where(JobRun.job_type == job_type)
        if environment:
            stmt = stmt.where(JobRun.environment == environment)
        stmt = stmt.order_by(JobRun.started_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
