"""
End-to-end smoke test for auditly.
Tests evidence collection, validation, and reporting across all control families.
"""

import json
from pathlib import Path

import pytest

from auditly.config import AppConfig
from auditly.evidence import ArtifactRecord, EvidenceManifest
from auditly.oscal import OscalCatalog, OscalProfile, load_oscal
from auditly.reporting.report import readiness_summary
from auditly.validators import FAMILY_PATTERNS, get_control_requirement, validate_controls


def load_test_evidence_data():
    """Load test evidence data with family mappings."""
    test_data_path = Path(__file__).parent / "test_evidence_data.json"
    with open(test_data_path, encoding="utf-8") as f:
        return json.load(f)


def get_evidence_for_families(families: set[str], test_data: dict) -> dict[str, bool]:
    """Get evidence relevant to specific control families."""
    evidence = {}

    for _category, artifacts_dict in test_data["evidence_artifacts"].items():
        for evidence_type, evidence_info in artifacts_dict.items():
            satisfies_families = set(evidence_info.get("satisfies_families", []))
            # Add evidence if it satisfies any of the requested families
            if satisfies_families & families:
                evidence[evidence_type] = True

    return evidence


def create_comprehensive_evidence():
    """Create test evidence covering all control families with realistic mappings."""
    test_data = load_test_evidence_data()

    # Get evidence for all families
    all_families = {
        "AC",
        "AU",
        "AT",
        "CM",
        "CP",
        "IA",
        "IR",
        "MA",
        "MP",
        "PE",
        "PL",
        "PS",
        "RA",
        "CA",
        "SC",
        "SI",
        "SA",
        "SR",
        "PM",
        "PT",
    }

    return get_evidence_for_families(all_families, test_data)


def test_catalog_loading():
    """Test OSCAL catalog/profile loading."""
    print("\n=== Testing Catalog Loading ===")

    catalog_path = Path("catalogs/nist-800-53r5.json")
    if not catalog_path.exists():
        print(f"[WARN] Catalog not found: {catalog_path}")
        pytest.skip(f"Catalog not found: {catalog_path}")

    catalog = load_oscal(catalog_path)
    assert isinstance(catalog, OscalCatalog), "Failed to load catalog"

    control_ids = catalog.control_ids()
    print(f"[PASS] Loaded NIST 800-53 Rev5: {len(control_ids)} controls")

    # Test profile loading
    profile_path = Path("catalogs/fedramp-rev5-moderate.json")
    if profile_path.exists():
        profile = load_oscal(profile_path)
        assert isinstance(profile, OscalProfile), "Failed to load profile"
        imported = profile.imported_control_ids()
        print(f"[PASS] Loaded FedRAMP Moderate: {len(imported)} controls")


def test_validator_coverage():
    """Test validator coverage across all families."""
    print("\n=== Testing Validator Coverage ===")

    # Test each family
    families_tested = 0
    families_passed = 0

    for family_code in sorted(FAMILY_PATTERNS.keys()):
        test_control = f"{family_code}-1"
        req = get_control_requirement(test_control)

        if req:
            families_tested += 1
            families_passed += 1
            print(f"[PASS] {family_code}: Pattern available")
        else:
            families_tested += 1
            print(f"[FAIL] {family_code}: No pattern found")

    print(f"\nFamily coverage: {families_passed}/{families_tested}")
    assert (
        families_passed == families_tested
    ), f"Only {families_passed}/{families_tested} families have patterns"


@pytest.mark.skip(reason="test_evidence_data.json not included in repository")
def test_evidence_validation():
    """Test validation with comprehensive evidence using realistic family mappings."""
    print("\n=== Testing Evidence Validation ===")

    # Load test data for realistic evidence mapping
    test_data = load_test_evidence_data()

    # Load a baseline
    profile_path = Path("catalogs/fedramp-rev5-moderate.json")
    if not profile_path.exists():
        print("[WARN] Profile not found, using sample controls")
        control_ids = ["AC-2", "CM-2", "SC-13", "AU-2", "RA-5", "PL-2"]
    else:
        profile = load_oscal(profile_path)
        control_ids = profile.imported_control_ids()[:50]  # Test subset for speed

    # Get comprehensive evidence (all families)
    evidence = create_comprehensive_evidence()

    print(f"Validating {len(control_ids)} controls with family-specific evidence...")
    print(f"Total evidence types available: {len(evidence)}")

    # Validate and show some examples
    results = validate_controls(control_ids, evidence)

    # Show sample of what controls are validated with what evidence
    print("\nSample validations by family:")
    sample_families = {}
    for cid in control_ids:
        family = cid.split("-")[0].upper()  # Ensure uppercase for matching
        if family not in sample_families:
            # Get evidence for this family
            family_evidence = get_evidence_for_families({family}, test_data)
            # Removed unused assignment to 'req' (F841)
            status = results[cid].status.value
            print(f"  {cid.upper()} ({family}): {len(family_evidence)} evidence types → {status}")
            sample_families[family] = family_evidence

            if len(sample_families) >= 8:  # Show 8 different families
                break

    passed = sum(1 for r in results.values() if r.status.value == "pass")
    failed = sum(1 for r in results.values() if r.status.value == "fail")
    insufficient = sum(1 for r in results.values() if r.status.value == "insufficient_evidence")
    unknown = sum(1 for r in results.values() if r.status.value == "unknown")

    print(f"\n  [PASS] Passed: {passed}")
    print(f"  [WARN] Insufficient: {insufficient}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ❓ Unknown: {unknown}")

    # Should have high pass rate with comprehensive evidence
    pass_rate = (passed / len(control_ids)) * 100 if control_ids else 0
    print(f"\nPass rate: {pass_rate:.1f}%")

    assert pass_rate >= 80, f"Pass rate too low: {pass_rate:.1f}%"

    print("✅ Validation test passed")


def test_manifest_creation():
    """Test evidence manifest creation."""
    print("\n=== Testing Manifest Creation ===")

    from datetime import datetime

    # Add sample artifacts (using correct ArtifactRecord fields)
    artifacts = [
        ArtifactRecord(
            key="terraform/plan.json",
            filename="plan.json",
            sha256="abc123",
            size=1024,
            metadata={"kind": "terraform-plan", "version": "1.0"},
        ),
        ArtifactRecord(
            key="github/workflow-run-123.log",
            filename="workflow-run-123.log",
            sha256="def456",
            size=2048,
            metadata={"kind": "github-workflow", "run_id": "123"},
        ),
        ArtifactRecord(
            key="audit/cloudtrail.log",
            filename="cloudtrail.log",
            sha256="ghi789",
            size=4096,
            metadata={"kind": "audit-log", "source": "cloudtrail"},
        ),
    ]

    manifest = EvidenceManifest(
        version="1.0",
        environment="test-env",
        created_at=datetime.now().timestamp(),
        artifacts=artifacts,
    )

    print(f"✅ Created manifest with {len(manifest.artifacts)} artifacts")

    # Test JSON serialization
    manifest.compute_overall_hash()
    manifest_json = manifest.to_json()
    assert "environment" in manifest_json, "Manifest JSON missing 'environment' field"
    assert "artifacts" in manifest_json, "Manifest JSON missing 'artifacts' field"
    print("✅ Manifest serialization works")


def test_report_generation():
    """Test report generation."""
    print("\n=== Testing Report Generation ===")

    from datetime import datetime

    # Create sample manifests
    manifest1 = EvidenceManifest(
        version="1.0",
        environment="test-env",
        created_at=datetime.now().timestamp(),
        artifacts=[
            ArtifactRecord(
                key="terraform/plan.json",
                filename="plan.json",
                sha256="abc123",
                size=1024,
                metadata={"kind": "terraform-plan"},
            )
        ],
    )

    manifests = [manifest1]

    summary = readiness_summary(manifests)

    assert "environments" in summary, "Summary missing 'environments' field"
    print(f"✅ Generated summary for {summary['environments']} environment(s)")
    print(f"   Total artifacts: {summary['artifact_count']}")


def test_config_validation():
    """Test configuration loading and validation."""
    print("\n=== Testing Configuration ===")

    config_path = Path("config.example.yaml")
    if not config_path.exists():
        print("⚠️  config.example.yaml not found")
        pytest.skip("config.example.yaml not found")

    cfg = AppConfig.load(config_path)
    print(f"✅ Loaded config: {cfg.organization or 'unnamed'}")

    catalogs = cfg.catalogs.get_all_catalogs()
    print(f"   Catalogs configured: {len(catalogs)}")

    assert len(catalogs) > 0, "No catalogs configured"
    print("✅ Config validation passed")


def run_smoke_test():
    """Run complete end-to-end smoke test."""
    print("=" * 60)
    print("auditly End-to-End Smoke Test")
    print("=" * 60)

    tests = [
        ("Configuration", test_config_validation),
        ("Catalog Loading", test_catalog_loading),
        ("Validator Coverage", test_validator_coverage),
        ("Evidence Validation", test_evidence_validation),
        ("Manifest Creation", test_manifest_creation),
        ("Report Generation", test_report_generation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All smoke tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(run_smoke_test())
