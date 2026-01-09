from __future__ import annotations

import typer
from rich import print

from .scheduler import runner

scheduler_app = typer.Typer(help="Scheduled validation controls")


@scheduler_app.command()
def start(
    config: str = typer.Option("config.yaml", help="Path to config file"),
    env: str = typer.Option("production", help="Environment name"),
    cron: str = typer.Option("0 2 * * *", help="Cron expression for schedule"),
):
    """Start the background scheduler for validation runs."""
    print(f"[cyan]Starting scheduler[/cyan] for env=[bold]{env}[/bold] cron=[bold]{cron}[/bold]")
    runner.start_scheduler(config_path=config, env_name=env, cron=cron)
    print("[green]Scheduler started[/green] (runs in background)")


@scheduler_app.command()
def once(
    config: str = typer.Option("config.yaml", help="Path to config file"),
    env: str = typer.Option("production", help="Environment name"),
):
    """Run a single scheduled validation immediately (for testing)."""
    print(f"[cyan]Running one validation job[/cyan] for env=[bold]{env}[/bold]")
    runner.run_scheduled_validation(config_path=config, env_name=env)
    print("[green]Validation job completed[/green]")
