"""CLI commands for generating compliance readiness and validation reports."""

from __future__ import annotations

from pathlib import Path

import typer

from .config import AppConfig
from .evidence import ArtifactRecord, EvidenceManifest
from .mapping import ControlMapping, compute_control_coverage, match_evidence_to_controls
from .oscal import OscalCatalog, OscalProfile, load_oscal
from .reporting.report import control_coverage_placeholder, readiness_summary, write_html
from .reporting.validation_reports import generate_auditor_report, generate_engineer_report
from .validators import validate_controls
from .waivers import WaiverRegistry

report_app = typer.Typer(help="Generate compliance readiness reports")


@report_app.command("readiness", help="Generate HTML readiness report")
def report_readiness(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    out: Path = typer.Option(Path("report.html"), help="Output HTML path"),
):
    """Generate an HTML readiness report for compliance evidence in the given environment."""
    staging = Path(".auditly_manifests")
    staging.mkdir(exist_ok=True)
    if not any(staging.glob(f"{env}-*.json")):
        dummy = EvidenceManifest.create(
            env, [ArtifactRecord(key="noop", filename="noop", sha256="0", size=0, metadata={})]
        )
        (staging / f"{env}-dummy.json").write_text(dummy.to_json())

    manifests = []
    for p in staging.glob(f"{env}-*.json"):
        import json as _json

        data = _json.loads(p.read_text())
        m = EvidenceManifest(
            version=data["version"],
            environment=data["environment"],
            created_at=data["created_at"],
            artifacts=[ArtifactRecord(**a) for a in data["artifacts"]],
            overall_hash=data.get("overall_hash"),
            notes=data.get("notes"),
        )
        manifests.append(m)

    summary = readiness_summary(manifests)
    try:
        cfg = AppConfig.load(config)
        control_ids = []
        for _, cat_path in cfg.catalogs.get_all_catalogs().items():
            oscal_obj = load_oscal(cat_path)
            if isinstance(oscal_obj, OscalCatalog):
                control_ids.extend(oscal_obj.control_ids())
            elif isinstance(oscal_obj, OscalProfile):
                imported = oscal_obj.imported_control_ids()
                if imported:
                    control_ids.extend(imported)

        seen = set()
        control_ids = [x for x in control_ids if not (x in seen or seen.add(x))]

        mapping_path = Path("mapping.yaml")
        if not mapping_path.exists():
            mapping_path = Path("mapping.example.yaml")

        control_evidence = {}
        if mapping_path.exists():
            mapping = ControlMapping.from_yaml(mapping_path)
            control_evidence = match_evidence_to_controls(manifests, mapping)
            summary["controls"] = compute_control_coverage(control_ids, control_evidence)
        else:
            summary["controls"] = control_coverage_placeholder(control_ids, manifests)

        evidence_dict = {
            a.metadata.get("kind", "unknown"): True for m in manifests for a in m.artifacts
        }
        validation_results = validate_controls(control_ids, evidence_dict)
        summary["validation"] = {
            "passed": sum(1 for r in validation_results.values() if r.status.value == "pass"),
            "failed": sum(1 for r in validation_results.values() if r.status.value == "fail"),
            "insufficient": sum(
                1 for r in validation_results.values() if r.status.value == "insufficient_evidence"
            ),
        }

        waiver_file = Path("waivers.yaml")
        if waiver_file.exists():
            registry = WaiverRegistry.from_yaml(waiver_file)
            summary["waivers"] = registry.summary()
    except Exception as e:
        summary["controls"] = {"error": f"failed to compute coverage: {e}"}
        summary["validation"] = {"error": str(e)}
    write_html(summary, out)
    typer.echo(f"Wrote readiness report to {out}")


@report_app.command("engineer", help="Generate engineer-focused validation report")
def report_engineer(
    evidence_file: Path = typer.Option(..., exists=True, help="JSON file with evidence dict"),
    control_ids: str | None = typer.Option(
        None, help="Comma-separated control IDs (default: sample)"
    ),
    out: Path = typer.Option(Path("engineer-report.html"), help="Output HTML path"),
):
    """Generate an engineer-focused validation report from evidence and control IDs."""
    import json as _json

    from .validators import FAMILY_PATTERNS

    if control_ids:
        control_list = [c.strip() for c in control_ids.split(",")]
    else:
        control_list = []
        for family in FAMILY_PATTERNS.keys():
            control_list.extend([f"{family}-{i}" for i in range(1, 26)])

    evidence = _json.loads(evidence_file.read_text())
    results = validate_controls(control_list, evidence)
    generate_engineer_report(results, evidence, out)
    typer.echo(f"Wrote engineer report to {out}")


@report_app.command("auditor", help="Generate auditor-focused validation report")
def report_auditor(
    evidence_file: Path = typer.Option(..., exists=True, help="JSON file with evidence dict"),
    control_ids: str | None = typer.Option(
        None, help="Comma-separated control IDs (default: sample)"
    ),
    out: Path = typer.Option(Path("auditor-report.html"), help="Output HTML path"),
):
    """Generate an auditor-focused validation report from evidence and control IDs."""
    import json as _json

    from .validators import FAMILY_PATTERNS

    if control_ids:
        control_list = [c.strip() for c in control_ids.split(",")]
    else:
        control_list = []
        for family in FAMILY_PATTERNS.keys():
            control_list.extend([f"{family}-{i}" for i in range(1, 26)])

    evidence = _json.loads(evidence_file.read_text())
    results = validate_controls(control_list, evidence)
    generate_auditor_report(results, evidence, out)
    typer.echo(f"Wrote auditor report to {out}")
