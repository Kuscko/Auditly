"""Core scheduling logic for validation runners.

This module contains the core business logic for scheduled validation runs,
independent of APScheduler or CLI concerns.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rapidrmf.config import AppConfig
from rapidrmf.db import get_async_session, init_db_async
from rapidrmf.db.repository import Repository
from rapidrmf.validators import validate_controls

logger = logging.getLogger(__name__)


async def run_validation_job(config_path: str, env_name: str) -> dict:
    """Run a validation job for a given environment.

    Args:
        config_path: Path to environment configuration file (config.yaml)
        env_name: Environment name (e.g., production)

    Returns:
        Dict with job results and metrics

    Raises:
        ValueError: If environment is not found or misconfigured
    """
    cfg = AppConfig.load(Path(config_path))
    envcfg = cfg.environments.get(env_name)

    if not envcfg:
        raise ValueError(f"Environment '{env_name}' not found in config")

    if not envcfg.database_url:
        raise ValueError(f"Environment '{env_name}' has no database_url configured")

    init_db_async(envcfg.database_url)

    session_gen = get_async_session()
    session = await session_gen.__anext__()
    repo = Repository(session)

    job = await repo.start_job_run(
        job_type="validation",
        environment=env_name,
        attributes={"config_path": str(config_path)},
    )

    metrics = {"systems": 0, "controls": 0, "results": 0, "errors": 0}

    try:
        systems = await repo.list_systems_by_environment(env_name)
        controls = await repo.list_controls()
        control_map = {c.control_id.upper(): c for c in controls}
        control_ids = list(control_map.keys())

        metrics["systems"] = len(systems)
        metrics["controls"] = len(control_ids)

        if not systems:
            logger.warning("No systems found for environment '%s'", env_name)
        if not controls:
            logger.warning("No controls found in database")

        for sys in systems:
            evidence_rows = await repo.list_evidence_for_system(sys)
            evidence_dict = {}

            for ev in evidence_rows:
                payload = {
                    "key": ev.key,
                    "sha256": ev.sha256,
                    "path": ev.vault_path,
                    "size": ev.size,
                    "filename": ev.filename,
                }
                evidence_dict.setdefault(ev.evidence_type, []).append(payload)

            results = validate_controls(control_ids, evidence_dict, system_state=None)

            for cid, res in results.items():
                control = control_map.get(cid.upper())
                if not control:
                    continue

                await repo.add_validation_result(
                    system=sys,
                    control=control,
                    status=res.status,
                    message=res.message,
                    evidence_keys=res.evidence_keys,
                    remediation=res.remediation,
                    metadata=res.metadata,
                )
                metrics["results"] += 1

        await repo.finish_job_run(job, status="success", metrics=metrics)
        await session.commit()

        logger.info(
            "Validation job completed successfully: %d systems, %d controls, %d results",
            metrics["systems"],
            metrics["controls"],
            metrics["results"],
        )

        return {
            "status": "success",
            "job_id": job.id,
            "metrics": metrics,
        }

    except Exception as exc:
        metrics["errors"] = metrics.get("errors", 0) + 1
        await repo.finish_job_run(job, status="failed", error=str(exc), metrics=metrics)
        await session.rollback()

        logger.exception("Validation job failed for environment '%s'", env_name)

        return {
            "status": "failed",
            "job_id": job.id,
            "error": str(exc),
            "metrics": metrics,
        }

    finally:
        await session.close()


def run_validation_job_sync(config_path: str, env_name: str) -> dict:
    """Synchronous wrapper for run_validation_job.

    Args:
        config_path: Path to environment configuration file
        env_name: Environment name

    Returns:
        Dict with job results and metrics
    """
    return asyncio.run(run_validation_job(config_path, env_name))
