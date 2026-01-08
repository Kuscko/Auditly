"""Helpers to run Alembic migrations programmatically."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config


def get_alembic_config(database_url: Optional[str] = None) -> Config:
    here = Path(__file__).resolve().parent.parent
    cfg = Config(str(here / "alembic.ini"))
    if database_url:
        cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade(head: str = "head", database_url: Optional[str] = None) -> None:
    cfg = get_alembic_config(database_url)
    command.upgrade(cfg, head)


def downgrade(revision: str = "-1", database_url: Optional[str] = None) -> None:
    cfg = get_alembic_config(database_url)
    command.downgrade(cfg, revision)
