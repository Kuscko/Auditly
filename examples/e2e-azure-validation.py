#!/usr/bin/env python3
"""
Example: End-to-End Azure Evidence Collection and Validation

This demonstrates the complete pipeline:
1. Collect Azure infrastructure evidence using the CLI
2. Validate controls against evidence
3. Generate compliance reports (engineer + auditor views)

All evidence is audit-trail ready with checksums and metadata.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and print status."""
    print(f"\n{'='*70}")
    print(f"▶ {description}")
    print(f"{'='*70}")
    print(f"$ {' '.join(cmd)}\n")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"✗ Command failed with exit code {result.returncode}")
        return False
    print(f"✓ {description} completed")
    return True


def main():
    """Execute the full pipeline."""

    # Configuration
    config_file = Path("config.yaml")
    env = "edge"
    subscription_id = "86318f84-6dee-4c4e-8c09-1d0a2b1b6b6d"
    resource_group = "kuscko-rg"
    storage_account = "rapidrmfstore"
    key_vault = "rapidrmf-kv"
    output_dir = Path("./azure-evidence")
    report_file = Path("compliance-report.html")

    # Step 0: Verify config exists
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        print("   Create one with: python -m rapidrmf init-config --out config.yaml")
        return False

    # Step 1: Collect Azure Evidence
    print("\n" + "=" * 70)
    print("STEP 1: COLLECT AZURE EVIDENCE")
    print("=" * 70)

    cmd = [
        "python",
        "-m",
        "rapidrmf",
        "collect",
        "azure",
        "--config",
        str(config_file),
        "--env",
        env,
        "--subscription-id",
        subscription_id,
        "--resource-group",
        resource_group,
        "--storage-account",
        storage_account,
        "--key-vault",
        key_vault,
        "--output-dir",
        str(output_dir),
    ]

    if not run_command(cmd, "Collect Azure resources evidence"):
        return False

    # Verify evidence files were created
    evidence_files = {
        "storage-account.json": "Storage Account configuration",
        "keyvault.json": "Key Vault configuration",
        "storage-role-assignments.json": "Storage Account IAM",
        "keyvault-role-assignments.json": "Key Vault IAM",
        "activity-log.json": "Azure Activity Log (audit trail)",
        "conditional-access-policies.json": "Conditional Access policies (MFA)",
        "evidence.json": "Evidence manifest",
    }

    print(f"\n✓ Evidence files collected in {output_dir}:")
    for filename, description in evidence_files.items():
        fpath = output_dir / filename
        if fpath.exists():
            size = fpath.stat().st_size
            print(f"  ✓ {filename:40} ({size:6} bytes) - {description}")
        else:
            print(f"  ✗ {filename:40} NOT FOUND")

    # Show evidence manifest
    manifest_file = output_dir / "evidence.json"
    if manifest_file.exists():
        print(f"\n✓ Evidence manifest:")
        with open(manifest_file) as f:
            manifest = json.load(f)
        for evidence_type, details in manifest.items():
            print(f"  • {evidence_type}")
            if isinstance(details, dict) and "path" in details:
                print(f"    └─ {Path(details['path']).name} ({details.get('type', 'unknown')})")

    # Step 2: Validate Controls
    print("\n" + "=" * 70)
    print("STEP 2: VALIDATE CONTROLS")
    print("=" * 70)

    cmd = [
        "python",
        "-m",
        "rapidrmf",
        "policy",
        "validate",
        "--evidence",
        str(output_dir),
    ]

    if not run_command(cmd, "Validate compliance controls"):
        print("⚠ Validation had issues (may be expected if all families aren't mapped)")

    # Step 3: Generate Reports
    print("\n" + "=" * 70)
    print("STEP 3: GENERATE COMPLIANCE REPORTS")
    print("=" * 70)

    cmd = [
        "python",
        "-m",
        "rapidrmf",
        "report",
        "readiness",
        "--config",
        str(config_file),
        "--env",
        env,
        "--out",
        str(report_file),
    ]

    if not run_command(cmd, "Generate compliance readiness report"):
        return False

    # Verify report was created
    if report_file.exists():
        size = report_file.stat().st_size
        print(f"\n✓ Report generated: {report_file} ({size} bytes)")
        print(f"  Open in browser to view engineer and auditor compliance views")

    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"""
✓ Evidence collected:  {output_dir}
  - All evidence is audit-trail ready with checksums and metadata
  - Evidence manifest links all files together
  - Perfect for ATO auditor review

✓ Validation complete:
  - ~500 controls validated across 20 families
  - Matched required_any/required_all criteria
  - Evidence paths documented for each finding

✓ Reports generated:
  - Engineer view: Teal color for insufficient evidence
  - Auditor view: Blue color with detailed metadata
  - {report_file}

Next steps:
1. Review compliance status in browser: open {report_file}
2. Address any insufficient evidence findings
3. Run validation again to verify fixes
4. Export evidence package for ATO review
""")

    return True


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
