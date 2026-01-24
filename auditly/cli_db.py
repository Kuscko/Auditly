"""CLI commands for database operations (upgrade, migrate) in auditly."""

from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from .db.migrate import upgrade as db_upgrade_fn

db_app = typer.Typer(help="Database operations (upgrade, migrate)")


@db_app.command("upgrade", help="Run Alembic upgrade head")
def db_upgrade(
    alembic_cfg: Path = typer.Option(Path("alembic.ini"), exists=True, help="Path to alembic.ini"),
):
    """Run database migrations (alembic upgrade head)."""
    db_upgrade_fn(str(alembic_cfg))
    print("[green]Database upgrade complete")


@db_app.command("migrate-from-files", help="Migrate file-based manifests into database")
def db_migrate_from_files(
    manifest_dir: Path = typer.Option(
        Path(".auditly_manifests"), help="Directory containing manifest JSON files"
    ),
    database_url: str = typer.Option(..., help="Database URL for connection"),
):
    """Import existing file-based manifests and artifacts into the database."""
    from .db.file_migration import migrate_manifests

    # The migrate_manifests function requires env and env_description, which are not provided here.
    # We'll use a default env name and pass None for env_description.
    count = migrate_manifests(
        manifest_dir, env="default", database_url=database_url, env_description=None
    )
    print(f"[green]Migrated {count} manifests to database")
