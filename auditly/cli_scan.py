"""CLI commands for compliance scanning (system, waivers)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print

from .scanners import run_scanners
from .waivers import WaiverRegistry

scan_app = typer.Typer(help="Compliance scanning (system, waivers)")


@scan_app.command("system", help="Run IAM/encryption/backup scanners")
def scan_system(
    config_file: Path = typer.Option(..., help="System config JSON"),
    out_json: Optional[Path] = typer.Option(None, help="Write scan results to JSON"),
):
    """Run IAM/encryption/backup scanners and print summary."""
    # Default scanner types
    scanner_types = ["iam", "encryption", "backup"]
    import json as _json

    config = _json.loads(config_file.read_text())
    results = run_scanners(config, scanner_types)

    summary = {
        "total_findings": sum(len(r.findings) for r in results.values()),
        "high_severity": sum(
            len([f for f in r.findings if f.get("severity") == "high"]) for r in results.values()
        ),
        "scanners": {
            k: {"status": r.status, "findings": len(r.findings)} for k, r in results.items()
        },
    }

    print(
        f"[cyan]Scan complete: {summary['total_findings']} findings ({summary['high_severity']} high severity)"
    )

    if out_json:
        out_json.write_text(
            _json.dumps({k: _json.loads(v.to_json()) for k, v in results.items()}, indent=2)
        )
        print(f"[green]Wrote scan results to {out_json}")


@scan_app.command("waivers", help="Summarize waiver exceptions and expiries")
def scan_waivers(
    waivers_file: Path = typer.Option(Path("waivers.yaml"), help="Waivers YAML file"),
):
    """Summarize waiver exceptions and expiries from waivers file."""
    registry = WaiverRegistry.from_yaml(waivers_file)
    summary = registry.summary()

    print(
        f"[cyan]Waivers: {summary['active']} active, {summary['expired']} expired, {summary['expiring_soon']} expiring soon"
    )
    if summary["expiring_soon_ids"]:
        print(f"[yellow]Expiring soon: {', '.join(summary['expiring_soon_ids'])}")
