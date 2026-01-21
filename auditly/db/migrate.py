"""Helpers to run Alembic migrations programmatically."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config


def get_alembic_config(database_url: Optional[str] = None) -> Config:
    """
    Get Alembic configuration.

    Priority order for database URL:
    1. Explicit database_url parameter
    2. auditly_DATABASE_URL environment variable
    3. alembic.ini default
    """
    here = Path(__file__).resolve().parent.parent
    cfg = Config(str(here / "alembic.ini"))

    # Override URL if provided or from environment
    url = database_url or os.getenv("auditly_DATABASE_URL")
    if url:
        cfg.set_main_option("sqlalchemy.url", url)

    return cfg


def upgrade(head: str = "head", database_url: Optional[str] = None) -> None:
    cfg = get_alembic_config(database_url)
    command.upgrade(cfg, head)


def downgrade(revision: str = "-1", database_url: Optional[str] = None) -> None:
    cfg = get_alembic_config(database_url)
    command.downgrade(cfg, revision)
