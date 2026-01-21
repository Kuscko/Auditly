from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .cli_bundle import bundle_app

# Import sub-apps
from .cli_collect import collect_app
from .cli_db import db_app
from .cli_policy import policy_app
from .cli_report import report_app
from .cli_scan import scan_app
from .cli_scheduler import scheduler_app
from .config import AppConfig
from .logging_utils import setup_logging
from .validators import CONTROL_REQUIREMENTS, FAMILY_PATTERNS, get_control_requirement

app = typer.Typer(help="RapidRMF utility CLI")


@app.callback()
def _init_logging(
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
        case_sensitive=False,
    ),
    log_json: bool = typer.Option(
        False,
        "--log-json",
        help="Emit logs in JSON format",
    ),
):
    """CLI-wide initialization for logging."""
    setup_logging(level=log_level, json=log_json)


# Register sub-applications
app.add_typer(collect_app, name="collect")
app.add_typer(report_app, name="report")
app.add_typer(policy_app, name="policy")
app.add_typer(scan_app, name="scan")
app.add_typer(bundle_app, name="bundle")
app.add_typer(db_app, name="db")
app.add_typer(scheduler_app, name="scheduler")


@app.command()
def init_config(out: Path = typer.Option("config.yaml", help="Output config path")):
    """Create a starter config file."""
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    if not example.exists():
        raise typer.Exit(code=1)
    out_path = Path(out)
    out_path.write_text(example.read_text())
    print(f"[green]Wrote config template to {out_path}")


@app.command()
def check_catalogs(
    config: Path = typer.Option("config.yaml", exists=True, help="Path to config.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed catalog info"),
):
    """Validate configured OSCAL catalogs and profiles."""
    from .oscal import OscalCatalog, OscalProfile, load_oscal

    console = Console()

    try:
        cfg = AppConfig.load(config)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(code=1)

    catalogs_dict = cfg.catalogs.get_all_catalogs()

    if not catalogs_dict:
        console.print("[yellow]No catalogs configured in config.yaml[/yellow]")
        return

    table = Table(title="OSCAL Catalog/Profile Validation")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Title", style="white")
    table.add_column("Controls", justify="right", style="blue")

    total_valid = 0
    total_invalid = 0

    for name, path in catalogs_dict.items():
        try:
            oscal_obj = load_oscal(path)
            if oscal_obj is None:
                table.add_row(name, "Unknown", "[red]Invalid[/red]", "Could not load", "—")
                total_invalid += 1
                continue

            if isinstance(oscal_obj, OscalCatalog):
                control_ids = oscal_obj.control_ids()
                title = oscal_obj.metadata().get("title", "Untitled")
                table.add_row(
                    name, "Catalog", "[green]✓ Valid[/green]", title, str(len(control_ids))
                )
                total_valid += 1

                if verbose:
                    console.print(
                        f"\n[cyan]{name}[/cyan] controls: {', '.join(control_ids[:10])}"
                        + (f" ... (+{len(control_ids)-10} more)" if len(control_ids) > 10 else "")
                    )

            elif isinstance(oscal_obj, OscalProfile):
                imported_ids = oscal_obj.imported_control_ids()
                title = oscal_obj.title() or "Untitled"
                import_hrefs = oscal_obj.import_hrefs()
                table.add_row(
                    name,
                    "Profile",
                    "[green]✓ Valid[/green]",
                    title,
                    str(len(imported_ids)) if imported_ids else "—",
                )
                total_valid += 1

                if verbose:
                    console.print(f"\n[cyan]{name}[/cyan] imports: {', '.join(import_hrefs)}")
                    if imported_ids:
                        console.print(
                            f"  Included controls: {', '.join(imported_ids[:10])}"
                            + (
                                f" ... (+{len(imported_ids)-10} more)"
                                if len(imported_ids) > 10
                                else ""
                            )
                        )

        except Exception as e:
            table.add_row(name, "Error", "[red]✗ Invalid[/red]", str(e)[:50], "—")
            total_invalid += 1

    console.print(table)
    console.print(f"\n[green]Valid: {total_valid}[/green] | [red]Invalid: {total_invalid}[/red]")

    if total_invalid > 0:
        raise typer.Exit(code=1)


@app.command()
def list_validators(
    filter_family: Optional[str] = typer.Option(
        None, "--family", "-f", help="Filter by control family (e.g., CM, AC, SC)"
    ),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Show all families including those with only pattern-based rules"
    ),
):
    """List available control validators and their requirements."""
    console = Console()

    if show_all:
        # Show family patterns
        console.print("\n[bold cyan]Control Family Patterns:[/bold cyan]")
        console.print(
            "[dim]These patterns apply to ALL controls in a family unless overridden[/dim]\n"
        )

        family_table = Table()
        family_table.add_column("Family", style="cyan", no_wrap=True)
        family_table.add_column("Description", style="white")
        family_table.add_column("Required Any", style="yellow")
        family_table.add_column("Required All", style="green")

        for family_code in sorted(FAMILY_PATTERNS.keys()):
            if filter_family and family_code.upper() != filter_family.upper():
                continue
            pattern = FAMILY_PATTERNS[family_code]
            family_table.add_row(
                family_code,
                pattern.description_template,
                ", ".join(pattern.required_any) if pattern.required_any else "—",
                ", ".join(pattern.required_all) if pattern.required_all else "—",
            )

        console.print(family_table)
        console.print(f"\n[dim]Total families: {len(FAMILY_PATTERNS)}[/dim]\n")

    # Show specific control overrides
    console.print("\n[bold cyan]Specific Control Overrides:[/bold cyan]")
    console.print("[dim]These controls have custom requirements beyond family patterns[/dim]\n")

    table = Table()
    table.add_column("Control", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Required Any", style="yellow")
    table.add_column("Required All", style="green")

    for req in sorted(CONTROL_REQUIREMENTS.values(), key=lambda x: x.control_id):
        control_upper = req.control_id.upper()

        # Filter by family if specified
        if filter_family:
            family = control_upper.split("-")[0] if "-" in control_upper else ""
            if family.upper() != filter_family.upper():
                continue

        table.add_row(
            control_upper,
            req.description,
            ", ".join(req.required_any) if req.required_any else "—",
            ", ".join(req.required_all) if req.required_all else "—",
        )

    console.print(table)
    console.print(f"\n[dim]Specific overrides: {len(CONTROL_REQUIREMENTS)}[/dim]")
    console.print("[dim]Use --all flag to see family patterns covering all controls[/dim]")


@app.command()
def check_validator_coverage(
    config: Path = typer.Option("config.yaml", exists=True, help="Path to config.yaml"),
    profile: Optional[str] = typer.Option(
        None, help="Specific profile to check (e.g., fedramp_high)"
    ),
):
    """Check validator coverage across all controls in configured catalogs."""
    from .oscal import OscalCatalog, OscalProfile, load_oscal

    console = Console()

    try:
        cfg = AppConfig.load(config)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(code=1)

    catalogs_dict = cfg.catalogs.get_all_catalogs()

    if not catalogs_dict:
        console.print("[yellow]No catalogs configured[/yellow]")
        raise typer.Exit(code=1)

    # If profile specified, only check that one
    if profile:
        if profile not in catalogs_dict:
            console.print(f"[red]Profile '{profile}' not found in config[/red]")
            raise typer.Exit(code=1)
        catalogs_dict = {profile: catalogs_dict[profile]}

    table = Table(title="Validator Coverage Report")
    table.add_column("Catalog/Profile", style="cyan")
    table.add_column("Total Controls", justify="right", style="white")
    table.add_column("Covered", justify="right", style="green")
    table.add_column("Coverage %", justify="right", style="yellow")
    table.add_column("Method", style="dim")

    for name, path in catalogs_dict.items():
        oscal_obj = load_oscal(path)
        if oscal_obj is None:
            continue

        if isinstance(oscal_obj, OscalCatalog):
            control_ids = oscal_obj.control_ids()
        elif isinstance(oscal_obj, OscalProfile):
            control_ids = oscal_obj.imported_control_ids()
        else:
            continue

        if not control_ids:
            continue

        # Check coverage
        specific_overrides = 0
        family_patterns = 0
        uncovered = 0

        for cid in control_ids:
            req = get_control_requirement(cid)
            if req:
                if cid.lower() in CONTROL_REQUIREMENTS:
                    specific_overrides += 1
                else:
                    family_patterns += 1
            else:
                uncovered += 1

        covered = specific_overrides + family_patterns
        total = len(control_ids)
        pct = (covered / total * 100) if total > 0 else 0

        method = []
        if specific_overrides > 0:
            method.append(f"{specific_overrides} override")
        if family_patterns > 0:
            method.append(f"{family_patterns} pattern")
        if uncovered > 0:
            method.append(f"[red]{uncovered} uncovered[/red]")

        table.add_row(
            name, str(total), str(covered), f"{pct:.1f}%", ", ".join(method) if method else "—"
        )

    console.print(table)
    console.print("\n[dim]Coverage methods:[/dim]")
    console.print("  [cyan]override[/cyan] = specific control requirements")
    console.print("  [yellow]pattern[/yellow] = family-based pattern matching")


@app.command()
def test_validator(
    control_id: str = typer.Argument(..., help="Control ID to test (e.g., CM-2)"),
    evidence: str = typer.Option(
        "", help="Comma-separated evidence types (e.g., terraform-plan,change-request)"
    ),
):
    """Test a control validator with sample evidence."""
    from .validators import ComplianceValidator, ValidationStatus

    console = Console()

    control_upper = control_id.upper()
    req = get_control_requirement(control_id)

    if not req:
        console.print(f"[red]No validator or family pattern found for {control_upper}[/red]")
        console.print("[yellow]Run 'list-validators --all' to see available patterns[/yellow]")
        raise typer.Exit(code=1)

    # Parse evidence
    evidence_set = set(e.strip() for e in evidence.split(",") if e.strip())

    console.print(f"\n[bold]Testing {control_upper}[/bold]")
    console.print(
        f"Validator source: {'[cyan]Specific override[/cyan]' if control_id.lower() in CONTROL_REQUIREMENTS else '[yellow]Family pattern[/yellow]'}"
    )
    console.print(f"Evidence provided: {', '.join(evidence_set) if evidence_set else '(none)'}\n")

    # Run validation
    validator = ComplianceValidator(req)
    result = validator.validate(evidence_set)

    # Display result
    status_color = {
        ValidationStatus.PASS: "green",
        ValidationStatus.FAIL: "red",
        ValidationStatus.INSUFFICIENT_EVIDENCE: "yellow",
        ValidationStatus.UNKNOWN: "dim",
    }

    color = status_color.get(result.status, "white")
    panel = Panel(
        f"[bold]{result.status.value.upper()}[/bold]\n\n"
        f"{result.message}\n\n"
        + (f"[dim]Remediation: {result.remediation}[/dim]" if result.remediation else ""),
        title=f"{control_upper} Validation",
        border_style=color,
    )

    console.print(panel)


if __name__ == "__main__":
    app()
