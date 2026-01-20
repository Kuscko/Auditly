from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print

from .reporting.validation_reports import generate_auditor_report, generate_engineer_report
from .validators import (
    FAMILY_PATTERNS,
    validate_controls,
)

policy_app = typer.Typer(help="Policy evaluation tools (validate, conftest, wasm)")


@policy_app.command("validate", help="Validate controls from evidence + system state")
def policy_validate(
    evidence_file: Optional[Path] = typer.Option(None, help="JSON file with evidence dict"),
    system_state_file: Optional[Path] = typer.Option(None, help="JSON file with live system state"),
    out_json: Optional[Path] = typer.Option(None, help="Write validation results to JSON"),
    out_engineer: Optional[Path] = typer.Option(None, help="Write engineer-focused HTML report"),
    out_auditor: Optional[Path] = typer.Option(
        None, help="Write auditor-focused HTML report (with evidence)"
    ),
    control_ids: Optional[str] = typer.Option(
        None, help="Comma-separated control IDs (default: all families)"
    ),
    config: Optional[Path] = typer.Option(
        None, help="Config file (to persist validation results to DB)"
    ),
    env: Optional[str] = typer.Option(None, help="Environment name (required for DB persistence)"),
):
    import json as _json

    from .cli_common import persist_validation_if_db

    # Generate all control IDs from family patterns if not specified
    if control_ids:
        control_list = [c.strip() for c in control_ids.split(",")]
    else:
        # Generate comprehensive list across all families (sample representative controls)
        control_list = []
        for family in FAMILY_PATTERNS.keys():
            # Generate sample controls for each family (1-25 for most families)
            # This covers the typical range; adjust as needed
            control_list.extend([f"{family}-{i}" for i in range(1, 26)])

    evidence = {}
    if evidence_file:
        evidence = _json.loads(evidence_file.read_text())

    system_state = None
    if system_state_file:
        system_state = _json.loads(system_state_file.read_text())

    results = validate_controls(control_list, evidence, system_state)

    summary = {
        "passed": sum(1 for r in results.values() if r.status.value == "pass"),
        "failed": sum(1 for r in results.values() if r.status.value == "fail"),
        "insufficient": sum(
            1 for r in results.values() if r.status.value == "insufficient_evidence"
        ),
        "controls": {
            cid: {
                "status": r.status.value,
                "message": r.message,
                "evidence_keys": r.evidence_keys,
                "metadata": r.metadata,
                "remediation": r.remediation,
            }
            for cid, r in results.items()
        },
    }

    print(
        f"[cyan]Validation: {summary['passed']} passed, {summary['failed']} failed, {summary['insufficient']} insufficient"
    )

    # Persist to database if config provided
    if config and env:
        from .config import AppConfig

        app_config = AppConfig.from_yaml(config)
        envcfg = app_config.get_environment(env)
        persist_validation_if_db(envcfg, env, results)
    elif config and not env:
        print("[yellow]Config provided but no --env specified; skipping DB persistence")

    if out_json:
        out_json.write_text(_json.dumps(summary, indent=2))
        print(f"[green]Wrote validation results to {out_json}")

    if out_engineer:
        evidence_dict = evidence if evidence else {}
        generate_engineer_report(results, evidence_dict, out_engineer)
        print(f"[green]Wrote engineer report to {out_engineer}")

    if out_auditor:
        evidence_dict = evidence if evidence else {}
        generate_auditor_report(results, evidence_dict, out_auditor)
        print(f"[green]Wrote auditor report to {out_auditor}")


@policy_app.command("conftest", help="Run Conftest (OPA/Rego) on a target")
def policy_conftest(
    target: Path = typer.Option(..., exists=True, help="Path to IaC directory or file"),
    policy_dir: Optional[Path] = typer.Option(
        None, exists=True, help="Path to Rego policy dir (optional)"
    ),
    out_json: Optional[Path] = typer.Option(None, help="Write raw JSON results to this path"),
):
    from .policy.conftest_runner import conftest_available, run_conftest

    if not conftest_available():
        raise typer.BadParameter("conftest not found in PATH; install Conftest to use this command")
    results = run_conftest(target, policy_dir)
    summary = {
        "targets": len(results),
        "failures": sum(r.failures for r in results),
        "warnings": sum(r.warnings for r in results),
        "passes": sum(r.passes for r in results),
    }
    print(f"[cyan]Conftest summary: {summary}")
    if out_json:
        import json as _json

        out_json.write_text(_json.dumps([r.raw for r in results], indent=2))
        print(f"[green]Wrote raw Conftest JSON to {out_json}")


@policy_app.command("wasm", help="Evaluate compiled OPA WASM policy")
def policy_wasm(
    wasm_file: Path = typer.Option(..., exists=True, help="Path to OPA WASM policy file"),
    target: Path = typer.Option(..., exists=True, help="Path to target file (JSON/YAML/text)"),
    out_json: Optional[Path] = typer.Option(None, help="Write raw JSON results to this path"),
):
    import json as _json

    from .policy.wasm_runner import evaluate_wasm_policy, wasm_available

    if not wasm_available():
        raise typer.BadParameter("wasmtime not installed; run: pip install wasmtime")

    # Read target
    try:
        if target.suffix in (".json", ".yaml", ".yml"):
            input_data = _json.loads(target.read_text())
        else:
            input_data = {"path": str(target), "content": target.read_text()}
    except Exception as e:
        raise typer.BadParameter(f"Failed to read target: {e}")

    result = evaluate_wasm_policy(wasm_file, input_data)
    print(
        f"[cyan]WASM policy result: allowed={result.allowed}, violations={len(result.violations)}"
    )
    if out_json:
        out_json.write_text(_json.dumps(result.raw, indent=2))
        print(f"[green]Wrote raw WASM result to {out_json}")
