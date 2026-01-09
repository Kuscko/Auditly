"""Scheduled validation runner scaffolding.

This module sets up a scheduler to run validations on a cron-like schedule.
Runs validations on a cron-like schedule, persists job state, and reuses existing validation + DB persistence flows.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rapidrmf.config import AppConfig
from rapidrmf.db import init_db_async, get_async_session
from rapidrmf.db.repository import Repository
from rapidrmf.validators import validate_controls

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover - APScheduler may be optional in some envs
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None  # type: ignore


def start_scheduler(config_path: str, env_name: str, cron: str = "0 2 * * *") -> None:
    """Start the scheduled validation runner.

    Args:
        config_path: Path to environment configuration file (config.yaml)
        env_name: Environment name (e.g., production)
        cron: Cron expression for scheduling (default: daily at 02:00)
    """
    if BackgroundScheduler is None or CronTrigger is None:
        logger.warning("APScheduler not installed. Please add 'apscheduler' to requirements.")
        return

    scheduler = BackgroundScheduler()
    trigger = CronTrigger.from_crontab(cron)

    scheduler.add_job(
        run_scheduled_validation,
        trigger=trigger,
        kwargs={"config_path": config_path, "env_name": env_name},
        id=f"validation:{env_name}",
        replace_existing=True,
    )

    logger.info("Starting scheduler for environment '%s' (cron=%s)", env_name, cron)
    scheduler.start()


def run_scheduled_validation(config_path: str, env_name: str) -> None:
    """Run scheduled validation for a given environment (sync wrapper)."""

    async def _run():
        cfg = AppConfig.load(Path(config_path))
        envcfg = cfg.environments.get(env_name)
        if not envcfg:
            logger.warning("Environment '%s' not found in config", env_name)
            return
        if not envcfg.database_url:
            logger.warning("Environment '%s' has no database_url; skipping scheduled validation", env_name)
            return

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

            if not systems or not controls:
                logger.warning(
                    "No systems (%d) or controls (%d) found for env=%s; skipping",
                    len(systems), len(controls), env_name,
                )
            else:
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
            logger.info("Scheduled validation succeeded (env=%s)", env_name)
        except Exception as exc:  # pragma: no cover - runtime exception path
            metrics["errors"] = metrics.get("errors", 0) + 1
            await repo.finish_job_run(job, status="failed", error=str(exc), metrics=metrics)
            await session.rollback()
            logger.exception("Scheduled validation failed (env=%s): %s", env_name, exc)
        finally:
            await session.close()

    asyncio.run(_run())
