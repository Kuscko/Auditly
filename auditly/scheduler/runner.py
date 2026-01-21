"""Scheduled validation runner using APScheduler.

DEPRECATED: This module provides backward compatibility for scheduler initialization.
New code should use auditly.scheduler.core.run_validation_job directly.

This module integrates APScheduler for cron-based job scheduling.
"""

from __future__ import annotations

import logging

from .core import run_validation_job_sync

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
    """Run scheduled validation for a given environment (sync wrapper).

    This function is called by APScheduler and delegates to core logic.
    """
    try:
        result = run_validation_job_sync(config_path, env_name)

        if result["status"] == "success":
            logger.info("Scheduled validation succeeded (env=%s)", env_name)
        else:
            logger.error(
                "Scheduled validation failed (env=%s): %s",
                env_name,
                result.get("error", "Unknown error"),
            )
    except Exception as exc:
        logger.exception("Unexpected error in scheduled validation (env=%s): %s", env_name, exc)
