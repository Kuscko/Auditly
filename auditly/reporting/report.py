"""Reporting utilities for control coverage and readiness summaries."""

from __future__ import annotations

import json
from pathlib import Path

from ..evidence import EvidenceManifest


def control_coverage_placeholder(control_ids: list[str], manifests: list[EvidenceManifest]) -> dict:
    """Calculate control coverage summary stats as a placeholder."""
    evidence_kinds = set()
    for m in manifests:
        for a in m.artifacts:
            k = a.metadata.get("kind") if isinstance(a.metadata, dict) else None
            if k:
                evidence_kinds.add(k)
    return {
        "controls_total": len(control_ids),
        "controls_with_evidence": 0,
        "controls_unknown": len(control_ids),
        "evidence_kinds": sorted(evidence_kinds),
    }


def readiness_summary(manifests: list[EvidenceManifest]) -> dict:
    """Summarize readiness based on evidence manifests."""
    total_artifacts = sum(len(m.artifacts) for m in manifests)
    envs = sorted({m.environment for m in manifests})
    return {
        "environments": envs,
        "artifact_count": total_artifacts,
        "manifests": [json.loads(m.to_json()) for m in manifests],
        "score": min(100, len(manifests) * 10),  # placeholder heuristic
    }


def write_html(summary: dict, out_path: Path | str) -> None:
    """Write readiness summary as HTML to output path."""
    p = Path(out_path)
    controls = summary.get("controls", {})
    # Build control coverage table
    coverage_html = ""
    if "covered_ids" in controls and "uncovered_ids" in controls:
        coverage_html = f"""
      <h2>Control Coverage</h2>
      <p>Total Controls: {controls.get('total', 0)}</p>
      <p>Covered: {controls.get('covered', 0)} ({controls.get('coverage_percent', 0)}%)</p>
      <p>Uncovered: {controls.get('uncovered', 0)}</p>

      <h3>Covered Controls</h3>
      <table border="1" cellpadding="5" style="border-collapse: collapse;">
        <tr><th>Control ID</th><th>Evidence Count</th></tr>
        {''.join(f'<tr><td>{cid}</td><td>{len(controls.get("control_evidence", {}).get(cid, []))}</td></tr>' for cid in controls.get('covered_ids', [])[:20])}
      </table>

      <h3>Uncovered Controls (first 20)</h3>
      <ul>
        {''.join(f'<li>{cid}</li>' for cid in controls.get('uncovered_ids', [])[:20])}
      </ul>
      """
    else:
        # Fallback to placeholder
        coverage_html = f"""
      <h2>Control Coverage (Placeholder)</h2>
      <p>Controls Total: {controls.get('controls_total', 'N/A')}</p>
      <p>Controls With Evidence: {controls.get('controls_with_evidence', 0)}</p>
      <p>Controls Unknown: {controls.get('controls_unknown', 'N/A')}</p>
      <p>Evidence Kinds Seen: {', '.join(controls.get('evidence_kinds', []))}</p>
      """

    html = f"""
    <html><head><title>Readiness Report</title></head>
    <body>
      <h1>Readiness Summary</h1>
      <p>Environments: {', '.join(summary['environments'])}</p>
      <p>Artifacts: {summary['artifact_count']}</p>
      <p>Score (placeholder): {summary['score']}</p>
      {coverage_html}
      <h2>Raw Summary</h2>
    """
    p.write_text(html)
