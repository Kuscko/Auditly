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
- `upsert_system()` - Create/update system records
- `add_evidence()` - Store evidence metadata
- `create_manifest()` - Create evidence collection manifest
- `add_manifest_entries()` - Link evidence to manifests
- `add_validation_result()` - Store validation outcomes
- `add_finding()` - Record compliance findings

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

Add `database_url` to your environment config:

```yaml
database_url: postgresql+asyncpg://user:pass@localhost:5432/rapidrmf
```

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
from rapidrmf.db.repository import upsert_system, add_evidence

async with get_async_session() as session:
    # Create/update a system
    system = await upsert_system(
        session=session,
        system_id="prod-app-01",
        name="Production Application",
        system_type="web-application"
    )
    
    # Add evidence
    evidence = await add_evidence(
        session=session,
        system_id="prod-app-01",
        evidence_type="terraform",
        source="terraform-state",
        vault_path="s3://evidence/prod-app-01/terraform/state.json"
    )
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
- Use `persist_if_db()` helper in CLI commands for optional DB persistence
