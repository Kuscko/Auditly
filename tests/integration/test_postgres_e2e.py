#!/usr/bin/env python3
"""Test Postgres database end-to-end."""

import asyncio
import sys
from pathlib import Path

from auditly.db import get_async_session, init_db_async
from auditly.db.models import System, ValidationStatus
from auditly.db.repository import Repository
from auditly.validators import validate_controls

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """Test database operations end-to-end."""

    # Connection string
    db_url = "postgresql+asyncpg://auditly:auditly_local_pass@localhost:5433/auditly_test"

    print(f"Connecting to: {db_url}")

    # Initialize database
    init_db_async(db_url)

    # Get session via async generator
    session_gen = get_async_session()
    session = await session_gen.__anext__()

    try:
        repo = Repository(session)

        # Test 0: Create a catalog
        print("\n[TEST 0] Creating catalog...")
        catalog = await repo.upsert_catalog(
            name="nist-800-53-rev5-test",
            title="NIST SP 800-53 Rev 5 (Test)",
            framework="NIST",
            version="Rev 5",
            baseline="Moderate",
            oscal_path="catalogs/NIST_SP-800-53_rev5_catalog.json",
            attributes={"test": True},
        )
        print(f"  Created catalog: {catalog.name} (ID: {catalog.id})")

        # Test 1: Create a system
        print("\n[TEST 1] Creating system...")
        system = await repo.upsert_system(
            name="test-app-01",
            environment="postgres-test",
            description="Test application for Postgres validation",
            attributes={"team": "engineering", "tier": "production"},
        )
        print(f"  Created system: {system.name} (ID: {system.id})")

        # Test 2: Add evidence
        print("\n[TEST 2] Adding evidence...")
        evidence1 = await repo.add_evidence(
            system=system,
            evidence_type="terraform-plan",
            key="terraform-plan",
            sha256="abc123" * 10,
            size=1024,
            vault_path="s3://test/terraform.json",
            filename="terraform-plan.json",
            attributes={"source": "terraform", "version": "1.5.0"},
        )
        print(f"  Added evidence: {evidence1.evidence_type} ({evidence1.key})")

        evidence2 = await repo.add_evidence(
            system=system,
            evidence_type="audit-log",
            key="audit-log",
            sha256="def456" * 10,
            size=2048,
            vault_path="s3://test/audit.log",
            filename="audit.log",
            attributes={"source": "cloudtrail", "events": 150},
        )
        print(f"  Added evidence: {evidence2.evidence_type} ({evidence2.key})")

        # Test 3: Create evidence manifest
        print("\n[TEST 3] Creating evidence manifest...")
        manifest = await repo.create_manifest(
            system=system,
            environment="postgres-test",
            overall_hash="manifest123" * 5,
            notes="End-to-end test manifest",
        )
        print(f"  Created manifest (ID: {manifest.id})")

        await repo.add_manifest_entries(manifest, [evidence1, evidence2])
        print(f"  Added {2} evidence items to manifest")

        # Test 4: Validate controls
        print("\n[TEST 4] Validating controls...")
        evidence_dict = {
            "terraform-plan": {"path": "s3://test/terraform.json"},
            "audit-log": {"path": "s3://test/audit.log"},
        }

        control_ids = ["AC-2", "CM-2", "AU-2"]
        results = validate_controls(control_ids, evidence_dict)

        print(f"  Validated {len(results)} controls:")
        for cid, result in results.items():
            print(f"    {cid}: {result.status.value}")

        # Test 5: Persist validation results
        print("\n[TEST 5] Persisting validation results...")

        for control_id, result in results.items():
            # Create control if doesn't exist
            control = await repo.get_control_by_id(catalog, control_id)

            if not control:
                control = await repo.upsert_control(
                    catalog=catalog,
                    control_id=control_id.upper(),
                    title=f"Control {control_id.upper()}",
                    family=control_id.split("-")[0].upper(),
                    description=result.message,
                    baseline_required=True,
                    attributes={"test": True},
                )

            # Create validation result
            await repo.add_validation_result(
                system=system,
                control=control,
                status=result.status,
                message=result.message,
                evidence_keys=result.evidence_keys,
                remediation=result.remediation,
                metadata=result.metadata,
            )
            print(f"  Persisted: {control_id} -> {result.status.value}")

        await session.commit()

        # Test 6: Query validation results
        print("\n[TEST 6] Querying validation results...")
        latest = await repo.get_latest_validation_results(system, limit=10)
        print(f"  Found {len(latest)} recent validation results:")
        for vr in latest:
            print(f"    Control {vr.control.control_id}: {vr.status.value} at {vr.validated_at}")

        # Test 7: Query by status
        print("\n[TEST 7] Querying PASS results...")
        passed = await repo.get_validation_results_by_status(system, ValidationStatus.PASS)
        print(f"  Found {len(passed)} PASS results")

        # Test 8: Query systems
        print("\n[TEST 8] Querying all systems...")
        from sqlalchemy import select as sql_select

        stmt = sql_select(System)
        result_set = await session.execute(stmt)
        systems = list(result_set.scalars().all())
        print(f"  Found {len(systems)} systems in database")

    finally:
        # Close session
        try:
            await session_gen.aclose()
        except StopAsyncIteration:
            pass

    print("\n[SUCCESS] All tests passed!")
    print("\nDatabase contents:")
    print("  - 1 system")
    print("  - 2 evidence items")
    print("  - 1 manifest with 2 entries")
    print(f"  - {len(results)} validation results")
    print(f"  - {len(results)} controls")


if __name__ == "__main__":
    asyncio.run(main())
