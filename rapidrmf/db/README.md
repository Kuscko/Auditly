# Database Layer

PostgreSQL/SQLite persistence layer for RapidRMF evidence, validation results, and compliance artifacts.

## Overview

This module provides database persistence using SQLAlchemy 2.x with both async and sync support. It stores:

- **Systems**: Target systems under assessment
- **Evidence**: Collected artifacts (Terraform, GitHub, GitLab, Argo, Azure)
- **Manifests**: Evidence collection metadata
- **Catalogs & Controls**: OSCAL catalogs and control definitions
- **Validation Results**: Control validation outcomes
- **Findings**: Compliance findings and audit trails

## Files

### `__init__.py`
Database initialization and session management.

- `init_db_async()` / `init_db_sync()` - Initialize database engines
- `get_async_session()` / `get_sync_session()` - Session factories
- Configure connection strings via `database_url` in config

### `models.py`
SQLAlchemy ORM models defining the schema.

**Tables**:
- `systems` - Target systems with metadata
- `evidence` - Raw evidence artifacts (references S3/MinIO vault)
- `evidence_manifests` - Evidence collection sessions
- `evidence_manifest_entries` - Links manifests to evidence items
- `catalogs` - OSCAL security catalogs
- `controls` - Individual security controls
- `control_requirements` - Specific requirements per control
- `validation_results` - Control validation outcomes
- `findings` - Compliance findings with severity/status

### `repository.py`
Async repository layer for database operations.

**Key Methods**:

*System & Evidence:*
- `upsert_system()` - Create/update system records
- `add_evidence()` - Store evidence metadata
- `create_manifest()` - Create evidence collection manifest
- `add_manifest_entries()` - Link evidence to manifests

*Catalogs & Controls (NEW in v0.2):*
- `upsert_catalog()` - Create/update control catalogs (NIST 800-53, CIS, etc.)
- `get_catalog_by_name()` - Retrieve catalog by name
- `upsert_control()` - Create/update control definitions
- `get_control_by_id()` - Retrieve control by ID

*Validation Results (NEW in v0.2):*
- `add_validation_result()` - Store control validation outcomes with evidence
- `get_latest_validation_results()` - Query recent validation results
- `get_validation_results_by_status()` - Filter by status (pass, fail, insufficient_evidence)
- `get_validation_history_for_control()` - Get validation history for specific control

*Findings:*
- `add_finding()` - Record compliance findings with severity/status

### `migrate.py`
Programmatic Alembic migration control.

- `upgrade()` - Apply pending migrations
- `downgrade()` - Rollback migrations
- `get_alembic_config()` - Load Alembic configuration

### `file_migration.py`
Utility to migrate file-based manifests to the database.

- `migrate_manifests()` - Read JSON manifests from vault, persist to DB
- Useful for transitioning from file-only storage to DB persistence

## Usage

### Configuration

Add `database_url` to your environment config. The URL can be configured in three ways (priority order):

1. **Config file** (`config.yaml`):
```yaml
environments:
  production:
    database_url: postgresql+asyncpg://user:pass@localhost:5432/rapidrmf
```

2. **Environment variable**:
```bash
export RAPIDRMF_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/rapidrmf"
```

3. **Programmatic override**:
```python
from rapidrmf.db import init_db_async
await init_db_async("postgresql+asyncpg://user:pass@localhost:5432/rapidrmf")
```

**Database URL Formats**:

- PostgreSQL (async): `postgresql+asyncpg://user:pass@host:5432/dbname`
- PostgreSQL (sync): `postgresql+psycopg2://user:pass@host:5432/dbname`
- SQLite (async): `sqlite+aiosqlite:///./rapidrmf.db`
- SQLite (sync): `sqlite:///./rapidrmf.db`

For local development with SQLite:
```yaml
database_url: sqlite+aiosqlite:///./rapidrmf.db
```

### Initialization

```python
from rapidrmf.db import init_db_async, get_async_session

# Initialize database
await init_db_async()

# Get a session
async with get_async_session() as session:
    # Use session for queries
    pass
```

### Using the Repository

```python
from rapidrmf.db.repository import Repository
from rapidrmf.db import get_async_session

async with get_async_session() as session:
    repo = Repository(session)
    
    # Create/update a system
    system = await repo.upsert_system(
        system_id="prod-app-01",
        name="Production Application",
        system_type="web-application"
    )
    
    # Add evidence
    evidence = await repo.add_evidence(
        system=system,
        evidence_type="terraform",
        key="terraform-plan",
        source="terraform-state",
        vault_path="s3://evidence/prod-app-01/terraform/state.json"
    )
    
    # NEW v0.2: Store validation results
    catalog = await repo.upsert_catalog(
        name="nist-800-53-rev5",
        title="NIST SP 800-53 Rev 5",
        version="5.1.1"
    )
    
    control = await repo.upsert_control(
        catalog=catalog,
        control_id="AC-2",
        title="Account Management"
    )
    
    result = await repo.add_validation_result(
        system=system,
        control=control,
        status=ValidationStatus.PASS,
        message="Control requirements met",
        evidence_keys=["terraform-plan", "audit-log"],
        remediation=None
    )
    
    # Query validation results
    latest = await repo.get_latest_validation_results(system, limit=10)
    passed = await repo.get_validation_results_by_status(system, ValidationStatus.PASS)
    
    await session.commit()
```

### Running Migrations

```bash
# Via CLI
rapidrmf db upgrade

# Programmatically
from rapidrmf.db.migrate import upgrade
upgrade()
```

## Schema Design

- **Partition key**: `system_id` used across tables for multi-tenancy
- **Indexes**: Critical columns indexed for query performance
- **Relationships**: Foreign keys with cascade deletes for data integrity
- **JSON fields**: Flexible `attributes` column for extensibility

## Migration Strategy

1. **New deployments**: Run `rapidrmf db upgrade` to create schema
2. **Existing deployments**: Use `rapidrmf db migrate-from-files` to import file-based manifests
3. **Schema updates**: Alembic auto-generates migrations from model changes

## Best Practices

- Use `database_url` for Postgres in production
- Use SQLite for local development/testing
- Always use repository methods instead of direct ORM queries
- Persist evidence metadata to DB; store artifacts in S3/MinIO vault
- Use `persist_validation_if_db()` helper in CLI commands for optional DB persistence

### CLI Integration (NEW in v0.2)

Commands now support optional database persistence via `--config` and `--env` flags:

```bash
# Validate controls and persist results to database
rapidrmf policy validate \
  --evidence-file evidence.json \
  --config config.yaml \
  --env production

# Evidence collection automatically persists when DB configured
rapidrmf collect terraform \
  --plan-file plan.json \
  --config config.yaml \
  --env production
```

When `--config` and `--env` are provided:
- System records are created/updated automatically
- Evidence metadata is stored in database
- Validation results are persisted with evidence mappings
- Controls and catalogs are created on-demand

### Testing

See [tests/integration/README.md](../../tests/integration/README.md) for database integration tests:

```bash
# Start PostgreSQL test container
cd tests/integration
docker-compose -f docker-compose.test.yml up -d

# Run end-to-end test
python test_postgres_e2e.py
```

Tests validate all database operations including catalog management, validation persistence, and query methods.
