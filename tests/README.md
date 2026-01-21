# Tests

This directory contains validation and integration suites for auditly.

## Directory Structure

```
tests/
├── integration/          # Database integration tests
│   ├── docker-compose.test.yml    # PostgreSQL test container
│   ├── config.postgres-test.yaml  # Test configuration
│   └── test_postgres_e2e.py       # End-to-end database test
├── terraform/           # Azure validation pipeline
├── comprehensive_validation_test.py
├── smoke_test.py
├── verify_evidence_mappings.py
└── README.md           # This file
```

## Test Suites

### Database Integration Tests (NEW in v0.2)

Located in `integration/` - validates PostgreSQL persistence and query operations.

**Setup:**
```powershell
# Start PostgreSQL container
cd tests/integration
docker-compose -f docker-compose.test.yml up -d

# Apply migrations
$env:auditly_DATABASE_URL = "postgresql+asyncpg://auditly:auditly_local_pass@localhost:5433/auditly_test"
auditly db upgrade

# Run test
python test_postgres_e2e.py
```

**Test Coverage:**
- Catalog/control management (upsert operations)
- System and evidence creation
- Evidence manifest with entries
- Control validation with 3 outcomes (pass, fail, insufficient_evidence)
- Validation result persistence
- Query operations (latest results, filter by status, control history)

See [integration/README.md](integration/README.md) for detailed documentation.

### Validation Suites

- **Comprehensive validation**: [README_VALIDATION.md](README_VALIDATION.md) and [comprehensive_validation_test.py](comprehensive_validation_test.py)
- **Smoke/integration**: [smoke_test.py](smoke_test.py)
- **Evidence mapping verification**: [verify_evidence_mappings.py](verify_evidence_mappings.py)
- **Azure validation pipeline**: [terraform/azure/README.md](terraform/azure/README.md)

## Running Tests
```powershell
# Comprehensive validation (loads all catalogs and evidence types)
$env:PYTHONPATH = "."
python tests/comprehensive_validation_test.py

# Smoke suite
$env:PYTHONPATH = "."
python tests/smoke_test.py
```

## Outputs
- Validation reports: `validation_reports/validation_report_<timestamp>.html/json`
- Azure pipeline artifacts: `tests/terraform/azure/output/`

## Tips
- Set PYTHONPATH to repo root so modules resolve
- Keep catalogs and mapping.yaml present when running validation tests
- For Azure pipeline, authenticate with `az login` before running Terraform or collectors
