#!/usr/bin/env python3
"""
Comprehensive Validation Test for auditly

Tests ALL controls from ALL catalogs with complete evidence coverage.
Generates detailed HTML and JSON reports showing:
- All controls tested
- Evidence used per control
- Validation results per control
- Coverage by family
- Overall statistics
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from auditly.config import AppConfig
from auditly.oscal import OscalCatalog, OscalProfile, load_oscal
from auditly.validators import (
    ComplianceValidator,
    ValidationResult,
    ValidationStatus,
    get_control_requirement,
)


def load_test_evidence() -> Dict[str, Any]:
    """Load comprehensive test evidence patterns"""
    test_data_path = Path(__file__).parent / "test_evidence_data.json"
    with open(test_data_path, encoding="utf-8") as f:
        return json.load(f)


def create_evidence_for_control(control_id: str, test_data: Dict[str, Any]) -> Dict[str, object]:
    """Create evidence dictionary for a specific control based on family and requirements"""
    evidence: Dict[str, object] = {}

    # Extract family from control ID (e.g., "AC-2" -> "AC")
    family = control_id.split("-")[0].upper()

    # Map evidence types to this control based on family membership
    for _category, artifacts_dict in test_data["evidence_artifacts"].items():
        for evidence_type, evidence_info in artifacts_dict.items():
            satisfies_families = evidence_info.get("satisfies_families", [])
            # Add evidence if it satisfies this control's family
            if family in satisfies_families:
                evidence[evidence_type] = f"test-artifact-{evidence_type}.json"

    # If no family-specific evidence found, add a generic set to avoid empty evidence
    if not evidence:
        evidence["audit-log"] = "test-artifact-audit-log.json"
        evidence["security-plan"] = "test-artifact-security-plan.json"

    return evidence


def validate_all_controls(config_path: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate all controls from all catalogs"""
    print("=" * 80)
    print("auditly Comprehensive Validation Test")
    print("=" * 80)
    print()

    # Load configuration
    print("Loading configuration...")
    config = AppConfig.load(config_path)
    print(f"✅ Loaded config: {config.organization}")
    print()

    # Load all catalogs and profiles
    print("Loading OSCAL catalogs and profiles...")
    all_controls: Dict[str, list[str]] = {}  # control_id -> catalog_name
    catalog_stats = {}

    for catalog_name, catalog_path in config.catalogs.get_all_catalogs().items():
        print(f"  Loading {catalog_name}...")
        oscal_obj = load_oscal(catalog_path)

        if isinstance(oscal_obj, OscalCatalog):
            control_ids = oscal_obj.control_ids()
        elif isinstance(oscal_obj, OscalProfile):
            control_ids = oscal_obj.imported_control_ids()
        else:
            continue

        catalog_stats[catalog_name] = len(control_ids)
        for control_id in control_ids:
            if control_id not in all_controls:
                all_controls[control_id] = []
            all_controls[control_id].append(catalog_name)

        print(f"    ✅ {len(control_ids)} controls")

    print()
    print(f"Total unique controls across all catalogs: {len(all_controls)}")
    print()

    # Validate each control
    print("Validating all controls...")
    print()

    by_status: defaultdict[str, int] = defaultdict(int)
    by_family = defaultdict(
        lambda: {"total": 0, "pass": 0, "insufficient": 0, "failed": 0, "unknown": 0}
    )  # type: ignore

    results: Dict[str, Any] = {
        "metadata": {
            "test_timestamp": datetime.now().isoformat() + "Z",
            "total_controls": len(all_controls),
            "total_catalogs": len(catalog_stats),
            "catalog_stats": catalog_stats,
            "config_path": str(config_path),
        },
        "controls": {},
        "statistics": {
            "by_status": by_status,
            "by_family": by_family,
        },
    }

    validator = None  # Will be created per-control

    # Process controls by family for organized output
    controls_by_family = defaultdict(list)
    for control_id in sorted(all_controls.keys()):
        family = control_id.split("-")[0]
        controls_by_family[family].append(control_id)

    total_processed = 0
    for family in sorted(controls_by_family.keys()):
        control_list = controls_by_family[family]
        print(f"Family {family}: {len(control_list)} controls")

        for control_id in control_list:
            # Get control requirement
            requirement = get_control_requirement(control_id)

            # Create evidence dictionary
            evidence = create_evidence_for_control(control_id, test_data)
            evidence_keys = set(evidence.keys())

            # Validate
            if requirement:
                validator = ComplianceValidator(requirement)
                result = validator.validate(evidence_keys, evidence)
            else:
                # No validator - this shouldn't happen with family patterns
                result = ValidationResult(
                    control_id=control_id,
                    status=ValidationStatus.UNKNOWN,
                    message="No validation pattern found",
                    evidence_keys=[],
                    metadata={},
                )

            # Record results
            status_str = result.status if isinstance(result.status, str) else result.status.value
            results["controls"][control_id] = {
                "catalogs": all_controls[control_id],
                "requirement": requirement.description if requirement else "No requirement defined",
                "evidence_types": list(evidence.keys()),
                "evidence_count": len(evidence),
                "status": status_str,
                "message": result.message,
                "suggestions": (
                    result.suggestions
                    if hasattr(result, "suggestions") and result.suggestions
                    else []
                ),
                "metadata": result.metadata,
            }

            # Update statistics
            results["statistics"]["by_status"][status_str] += 1
            results["statistics"]["by_family"][family]["total"] += 1
            results["statistics"]["by_family"][family][status_str] += 1

            total_processed += 1
            if total_processed % 50 == 0:
                print(f"  Processed {total_processed}/{len(all_controls)} controls...")

    print(f"✅ Validation complete: {total_processed} controls processed")
    print()

    return results


def generate_html_report(results: Dict[str, Any], output_path: Path):
    """Generate comprehensive HTML report"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>auditly Comprehensive Validation Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }}
        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
        }}
        .metadata {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .metadata p {{
            margin: 5px 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #fff;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }}
        .stat-card.passed {{ border-color: #27ae60; background: #d4edda; }}
        .stat-card.insufficient {{ border-color: #f39c12; background: #fff3cd; }}
        .stat-card.failed {{ border-color: #e74c3c; background: #f8d7da; }}
        .stat-card.unknown {{ border-color: #95a5a6; background: #e2e3e5; }}
        .stat-number {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status.passed {{ background: #27ae60; color: white; }}
        .status.insufficient {{ background: #f39c12; color: white; }}
        .status.failed {{ background: #e74c3c; color: white; }}
        .status.unknown {{ background: #95a5a6; color: white; }}
        .evidence-list {{
            font-size: 12px;
            color: #7f8c8d;
            max-width: 400px;
        }}
        .family-section {{
            margin: 30px 0;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            overflow: hidden;
        }}
        .family-header {{
            background: #3498db;
            color: white;
            padding: 15px;
            font-size: 18px;
            font-weight: bold;
        }}
        .family-stats {{
            display: flex;
            justify-content: space-around;
            padding: 15px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }}
        .family-stat {{
            text-align: center;
        }}
        .control-row {{
            padding: 0;
        }}
        .control-details {{
            display: none;
            padding: 15px;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
        }}
        .control-details.show {{
            display: block;
        }}
        .toggle-btn {{
            cursor: pointer;
            color: #3498db;
            text-decoration: underline;
        }}
        .catalog-badge {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ auditly Comprehensive Validation Report</h1>

        <div class="metadata">
            <p><strong>Test Timestamp:</strong> {results['metadata']['test_timestamp']}</p>
            <p><strong>Configuration:</strong> {results['metadata']['config_path']}</p>
            <p><strong>Total Controls:</strong> {results['metadata']['total_controls']}</p>
            <p><strong>Catalogs Tested:</strong> {results['metadata']['total_catalogs']}</p>
        </div>

        <h2>📊 Overall Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card passed">
                <div class="stat-label">Passed</div>
                <div class="stat-number">{results['statistics']['by_status'].get('pass', 0)}</div>
                <div class="stat-label">{results['statistics']['by_status'].get('pass', 0) / results['metadata']['total_controls'] * 100:.1f}%</div>
            </div>
            <div class="stat-card insufficient">
                <div class="stat-label">Insufficient</div>
                <div class="stat-number">{results['statistics']['by_status'].get('insufficient', 0)}</div>
                <div class="stat-label">{results['statistics']['by_status'].get('insufficient', 0) / results['metadata']['total_controls'] * 100:.1f}%</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-label">Failed</div>
                <div class="stat-number">{results['statistics']['by_status'].get('failed', 0)}</div>
                <div class="stat-label">{results['statistics']['by_status'].get('failed', 0) / results['metadata']['total_controls'] * 100:.1f}%</div>
            </div>
            <div class="stat-card unknown">
                <div class="stat-label">Unknown</div>
                <div class="stat-number">{results['statistics']['by_status'].get('unknown', 0)}</div>
                <div class="stat-label">{results['statistics']['by_status'].get('unknown', 0) / results['metadata']['total_controls'] * 100:.1f}%</div>
            </div>
        </div>

        <h2>📁 Catalog Statistics</h2>
        <table>
            <thead>
                <tr>
                    <th>Catalog</th>
                    <th>Control Count</th>
                </tr>
            </thead>
            <tbody>
"""

    for catalog_name, count in sorted(results["metadata"]["catalog_stats"].items()):
        html += f"""
                <tr>
                    <td>{catalog_name}</td>
                    <td>{count}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <h2>📋 Validation Results by Family</h2>
"""

    # Group controls by family
    controls_by_family = defaultdict(list)
    for control_id, control_data in results["controls"].items():
        family = control_id.split("-")[0]
        controls_by_family[family].append((control_id, control_data))

    for family in sorted(controls_by_family.keys()):
        family_stats = results["statistics"]["by_family"][family]
        controls = controls_by_family[family]

        html += f"""
        <div class="family-section">
            <div class="family-header">Family {family} ({family_stats['total']} controls)</div>
            <div class="family-stats">
                <div class="family-stat">
                    <strong>{family_stats['pass']}</strong><br>
                    <small>Passed</small>
                </div>
                <div class="family-stat">
                    <strong>{family_stats['insufficient']}</strong><br>
                    <small>Insufficient</small>
                </div>
                <div class="family-stat">
                    <strong>{family_stats['failed']}</strong><br>
                    <small>Failed</small>
                </div>
                <div class="family-stat">
                    <strong>{family_stats['unknown']}</strong><br>
                    <small>Unknown</small>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Control ID</th>
                        <th>Status</th>
                        <th>Catalogs</th>
                        <th>Evidence Count</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
"""

        for control_id, control_data in sorted(controls):
            catalog_badges = "".join(
                [f'<span class="catalog-badge">{cat}</span>' for cat in control_data["catalogs"]]
            )
            details_id = control_id.replace(".", "_")

            html += f"""
                    <tr class="control-row">
                        <td><strong>{control_id}</strong></td>
                        <td><span class="status {control_data['status']}">{control_data['status']}</span></td>
                        <td>{catalog_badges}</td>
                        <td>{control_data['evidence_count']}</td>
                        <td><span class="toggle-btn" onclick="toggleDetails('{details_id}')">Show Details</span></td>
                    </tr>
                    <tr>
                        <td colspan="5" style="padding: 0;">
                            <div class="control-details" id="{details_id}">
                                <p><strong>Requirement:</strong> {control_data['requirement']}</p>
                                <p><strong>Message:</strong> {control_data['message']}</p>
                                <p><strong>Evidence Types ({len(control_data['evidence_types'])}):</strong><br>
                                <span class="evidence-list">{', '.join(sorted(control_data['evidence_types']))}</span></p>
"""

            if control_data["suggestions"]:
                html += """
                                <p><strong>Suggestions:</strong></p>
                                <ul>
"""
                for suggestion in control_data["suggestions"]:
                    html += f"                                    <li>{suggestion}</li>\n"
                html += """
                                </ul>
"""

            html += """
                            </div>
                        </td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""

    html += """
    </div>

    <script>
        function toggleDetails(id) {
            const element = document.getElementById(id);
            element.classList.toggle('show');
        }
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def generate_json_report(results: Dict[str, Any], output_path: Path):
    """Generate JSON report"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def print_summary(results: Dict[str, Any]):
    """Print summary to console"""
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print()

    total = results["metadata"]["total_controls"]
    by_status = results["statistics"]["by_status"]

    print(f"Total Controls Tested: {total}")
    print(
        f"  ✅ Passed:       {by_status.get('pass', 0):4d} ({by_status.get('pass', 0)/total*100:5.1f}%)"
    )
    print(
        f"  ⚠️  Insufficient: {by_status.get('insufficient', 0):4d} ({by_status.get('insufficient', 0)/total*100:5.1f}%)"
    )
    print(
        f"  ❌ Failed:       {by_status.get('failed', 0):4d} ({by_status.get('failed', 0)/total*100:5.1f}%)"
    )
    print(
        f"  ❓ Unknown:      {by_status.get('unknown', 0):4d} ({by_status.get('unknown', 0)/total*100:5.1f}%)"
    )
    print()

    print("Family Coverage:")
    for family in sorted(results["statistics"]["by_family"].keys()):
        stats = results["statistics"]["by_family"][family]
        print(
            f"  {family}: {stats['total']} controls "
            f"({stats['pass']} passed, {stats['insufficient']} insufficient, "
            f"{stats['failed']} failed, {stats['unknown']} unknown)"
        )
    print()

    print("Catalogs Tested:")
    for catalog_name, count in sorted(results["metadata"]["catalog_stats"].items()):
        print(f"  {catalog_name}: {count} controls")
    print()


def main():
    """Main test execution"""
    # Load test data
    test_data = load_test_evidence()

    # Run validation
    config_path = "config.example.yaml"
    results = validate_all_controls(config_path, test_data)

    # Generate reports
    print("Generating reports...")
    output_dir = Path(__file__).parent / "validation_reports"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = output_dir / f"validation_report_{timestamp}.html"
    json_path = output_dir / f"validation_report_{timestamp}.json"

    generate_html_report(results, html_path)
    generate_json_report(results, json_path)

    print(f"✅ HTML report: {html_path}")
    print(f"✅ JSON report: {json_path}")
    print()

    # Print summary
    print_summary(results)

    print("=" * 80)
    print("🎉 Comprehensive validation test complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
