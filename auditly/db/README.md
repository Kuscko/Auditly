# Database Layer

PostgreSQL/SQLite persistence layer for auditly evidence, validation results, and compliance artifacts.

## Overview

This module provides database persistence using SQLAlchemy 2.x with both async and sync support. It stores:

- **Systems**: Target systems under assessment
- **Evidence**: Collected artifacts (Terraform, GitHub, GitLab, Argo, Azure)
- **Manifests**: Evidence collection metadata
- **Catalogs & Controls**: OSCAL catalogs and control definitions
- **Validation Results**: Control validation outcomes
- **Findings**: Compliance findings and audit trails

## Architecture

The database layer uses a **domain-specific repository pattern** for clean separation of concerns:

### Structure
```
auditly/db/
├── __init__.py           # Database initialization and session management
├── models.py             # SQLAlchemy ORM models
├── repository.py         # Unified repository (backward compatible)
├── migrate.py            # Alembic migration control
├── file_migration.py     # File-to-DB migration utilities
└── repositories/
    ├── __init__.py       # Repository exports
    ├── catalog.py        # Catalog operations
    ├── control.py        # Control operations
    ├── system.py         # System operations
    ├── evidence.py       # Evidence/manifest operations
    ├── validation.py     # Validation results and findings
    └── jobrun.py         # Job run tracking
```

### Benefits
- **Single Responsibility**: Each repository manages one domain entity
- **Testability**: Repositories can be tested in isolation
- **Composability**: Mix and match repositories as needed
- **Backward Compatible**: Original `Repository` class delegates to domain repos

### Usage

**Option 1: Unified Repository (backward compatible)**
```python
from auditly.db.repository import Repository

async with get_async_session() as session:
    repo = Repository(session)
    catalog = await repo.upsert_catalog("nist-800-53", "NIST SP 800-53", "NIST")
    control = await repo.upsert_control(catalog, "AC-2", "Account Management", "AC")
```

**Option 2: Domain-Specific Repositories (recommended for new code)**
```python
from auditly.db.repositories import CatalogRepository, ControlRepository

async with get_async_session() as session:
    catalog_repo = CatalogRepository(session)
    control_repo = ControlRepository(session)

    catalog = await catalog_repo.upsert_catalog("nist-800-53", "NIST SP 800-53", "NIST")
    control = await control_repo.upsert_control(catalog, "AC-2", "Account Management", "AC")
```

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
Unified async repository (backward compatible - delegates to domain repositories).

**Migration Note**: This file now acts as a compatibility wrapper. New code should use domain-specific repositories from `auditly.db.repositories` for better modularity.

### `repositories/` (NEW)
Domain-specific repository classes:

**`catalog.py`** - Catalog operations
- `get_catalog_by_name()` - Retrieve catalog by name
- `upsert_catalog()` - Create/update control catalogs

**`control.py`** - Control operations
- `get_control_by_id()` - Retrieve control by ID
- `upsert_control()` - Create/update control definitions
- `list_controls()` - List all controls
- `get_control_requirements()` - Get control requirements

**`system.py`** - System operations
- `get_system_by_name()` - Retrieve system by name
- `list_systems_by_environment()` - List systems per environment
- `upsert_system()` - Create/update system records

**`evidence.py`** - Evidence and manifest operations
- `add_evidence()` - Store evidence metadata
- `list_evidence_for_system()` - Query evidence for system
- `create_manifest()` - Create evidence collection manifest
- `add_manifest_entries()` - Link evidence to manifests

**`validation.py`** - Validation results and findings
- `add_validation_result()` - Store control validation outcomes
- `add_finding()` - Record compliance findings
- `get_latest_validation_results()` - Query recent results
- `get_validation_results_by_status()` - Filter by status
- `get_validation_history_for_control()` - Get control history

**`jobrun.py`** - Job run tracking
- `start_job_run()` - Start a scheduled job
- `finish_job_run()` - Complete job with status/metrics
- `get_recent_job_runs()` - Query recent job runs

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
    database_url: postgresql+asyncpg://user:pass@localhost:5432/auditly
```

2. **Environment variable**:
```bash
export auditly_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/auditly"
```

3. **Programmatic override**:
```python
from auditly.db import init_db_async
await init_db_async("postgresql+asyncpg://user:pass@localhost:5432/auditly")
```

**Database URL Formats**:

- PostgreSQL (async): `postgresql+asyncpg://user:pass@host:5432/dbname`
- PostgreSQL (sync): `postgresql+psycopg://user:pass@host:5432/dbname`
- SQLite (async): `sqlite+aiosqlite:///./auditly.db`
- SQLite (sync): `sqlite:///./auditly.db`

For local development with SQLite:
```yaml
database_url: sqlite+aiosqlite:///./auditly.db
```

### Initialization

```python
from auditly.db import init_db_async, get_async_session

# Initialize database
await init_db_async()

# Get a session
async with get_async_session() as session:
    # Use session for queries
    pass
```

### Using the Repository

```python
from auditly.db.repository import Repository
from auditly.db import get_async_session

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
auditly db upgrade

# Programmatically
from auditly.db.migrate import upgrade
upgrade()
```

## Schema Design

- **Partition key**: `system_id` used across tables for multi-tenancy
- **Indexes**: Critical columns indexed for query performance
- **Relationships**: Foreign keys with cascade deletes for data integrity
- **JSON fields**: Flexible `attributes` column for extensibility

## Migration Strategy

1. **New deployments**: Run `auditly db upgrade` to create schema
2. **Existing deployments**: Use `auditly db migrate-from-files` to import file-based manifests
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
auditly policy validate \
  --evidence-file evidence.json \
  --config config.yaml \
  --env production

# Evidence collection automatically persists when DB configured
auditly collect terraform \
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
