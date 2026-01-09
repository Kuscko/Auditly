from __future__ import annotations

import typer
from rich import print
from rich.table import Table

from .scheduler import runner
from .config import AppConfig
from .db import init_db_async, get_async_session
from .db.repository import Repository

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


@scheduler_app.command("runs")
def list_runs(
    config: str = typer.Option("config.yaml", help="Path to config file"),
    env: str = typer.Option(None, help="Environment name filter"),
    status: str = typer.Option(None, help="Filter by job status (running, success, failed)"),
    limit: int = typer.Option(20, help="Max runs to display"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show recent scheduler job runs."""

    cfg = AppConfig.load(config)
    if env and env not in cfg.environments:
        print(f"[yellow]Environment '{env}' not found in config[/yellow]")
        raise typer.Exit(code=1)

    envcfg = cfg.environments.get(env or next(iter(cfg.environments), None))
    if not envcfg or not envcfg.database_url:
        print("[yellow]No database_url configured; cannot read job runs[/yellow]")
        raise typer.Exit(code=1)

    init_db_async(envcfg.database_url)

    async def _list():
        session_gen = get_async_session()
        session = await session_gen.__anext__()
        repo = Repository(session)
        runs = await repo.get_recent_job_runs(job_type="validation", environment=env, limit=limit)
        
        # Filter by status if provided
        if status:
            runs = [r for r in runs if r.status == status]
        
        if json_output:
            import json
            data = [
                {
                    "id": r.id,
                    "environment": r.environment,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "error": r.error,
                    "metrics": r.metrics,
                    "attributes": r.attributes,
                }
                for r in runs
            ]
            print(json.dumps(data, indent=2))
        else:
            table = Table(title="Recent Job Runs", show_lines=False)
            table.add_column("ID", style="cyan")
            table.add_column("Env", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Started", style="white")
            table.add_column("Finished", style="white")
            table.add_column("Error", style="red")
            for r in runs:
                table.add_row(
                    str(r.id),
                    r.environment,
                    r.status,
                    str(r.started_at),
                    str(r.finished_at) if r.finished_at else "—",
                    (r.error or "").split("\n")[0][:80],
                )
            print(table)
        
        await session.close()

    import asyncio
    asyncio.run(_list())
