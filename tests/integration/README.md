# Database Integration Tests

This directory contains integration tests for auditly's PostgreSQL database layer.

## Quick Start

### 1. Start PostgreSQL Container

```bash
docker-compose -f docker-compose.test.yml up -d
```

This starts PostgreSQL 15 on port 5433 with database `auditly_test`.

### 2. Apply Migrations

```bash
# From project root
$env:auditly_DATABASE_URL = "postgresql+asyncpg://auditly:auditly_local_pass@localhost:5433/auditly_test"
auditly db upgrade
```

### 3. Run Test

```bash
python test_postgres_e2e.py
```

## Test Coverage

The end-to-end test validates all database operations:

**TEST 0: Catalog Management**
- Creates NIST 800-53 Rev 5 catalog
- Tests `upsert_catalog` (insert/update logic)

**TEST 1: System Management**
- Creates test system "test-app-01"
- Tests `upsert_system` with metadata

**TEST 2: Evidence Storage**
- Adds terraform plan and audit log evidence
- Validates evidence key indexing

**TEST 3: Evidence Manifest**
- Creates manifest with 2 evidence entries
- Tests manifest-to-evidence relationships

**TEST 4: Control Validation**
- Validates 3 controls (AC-2, CM-2, AU-2)
- Tests all validation statuses:
  - `PASS` - Control requirements met
  - `INSUFFICIENT_EVIDENCE` - Missing required evidence
  - `FAIL` - Control requirements not met

**TEST 5: Validation Persistence**
- Persists validation results to database
- Converts validator enums to DB enums
- Stores evidence keys, remediation, metadata

**TEST 6: Query Latest Results**
- Queries recent validation results with ordering
- Uses eager loading for control relationships

**TEST 7: Query by Status**
- Filters validation results by status
- Tests indexed queries

**TEST 8: System Queries**
- Lists all systems in database
- Validates basic repository queries

## Database Configuration

**Connection String:**
```
postgresql+asyncpg://auditly:auditly_local_pass@localhost:5433/auditly_test
```

**Test Config File:** `config.postgres-test.yaml`

```yaml
database:
  url: postgresql+asyncpg://auditly:auditly_local_pass@localhost:5433/auditly_test

storage:
  type: minio
  endpoint: localhost:9000
  bucket: auditly-evidence-test
```

## Schema

The test validates all 9 application tables:

1. **systems** - Systems under assessment
2. **evidence** - Evidence artifacts
3. **evidence_manifests** - Manifest metadata
4. **evidence_manifest_entries** - Evidence-to-manifest mappings
5. **catalogs** - Control catalogs (NIST 800-53, CIS, etc.)
6. **controls** - Individual controls
7. **control_requirements** - Control requirements
8. **validation_results** - Validation outcomes
9. **findings** - Security findings

Plus **alembic_version** for migration tracking.

## Cleanup

Stop and remove container with data volume:

```bash
docker-compose -f docker-compose.test.yml down -v
```

## Troubleshooting

**Connection refused:**
- Wait for PostgreSQL to start: `docker exec auditly-postgres-test pg_isready -U auditly`

**Import errors:**
- Run from project root or tests/integration directory
- Script automatically adds project root to Python path

**Enum conversion errors:**
- Repository converts validators.ValidationStatus to DB enum automatically
- Uses `.value` attribute for string conversion

**Lazy loading errors:**
- Repository methods use `selectinload()` for relationships
- Prevents "greenlet_spawn not called" errors in async context

## Expected Output

```
Connecting to: postgresql+asyncpg://auditly:...

[TEST 0] Creating catalog...
  Created catalog: nist-800-53-rev5-test (ID: 1)

[TEST 1] Creating system...
  Created system: test-app-01 (ID: 1)

[TEST 2] Adding evidence...
  Added evidence: terraform-plan (terraform-plan)
  Added evidence: audit-log (audit-log)

[TEST 3] Creating evidence manifest...
  Created manifest (ID: 1)
  Added 2 evidence items to manifest

[TEST 4] Validating controls...
  Validated 3 controls:
    AC-2: pass
    CM-2: insufficient_evidence
    AU-2: pass

[TEST 5] Persisting validation results...
  Persisted: AC-2 -> pass
  Persisted: CM-2 -> insufficient_evidence
  Persisted: AU-2 -> pass

[TEST 6] Querying validation results...
  Found 3 recent validation results:
    Control AU-2: pass at 2026-01-09 00:24:10
    Control CM-2: insufficient_evidence at 2026-01-09 00:24:10
    Control AC-2: pass at 2026-01-09 00:24:10

[TEST 7] Querying PASS results...
  Found 2 PASS results

[TEST 8] Querying all systems...
  Found 1 systems in database

[SUCCESS] All tests passed!
```
