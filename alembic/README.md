# Alembic Database Migrations

Database schema versioning and migration management for RapidRMF using Alembic.

## Overview

This directory contains Alembic migration infrastructure for managing database schema changes. Alembic tracks schema versions and provides upgrade/downgrade capabilities.

## Structure

```
alembic/
├── README                    # Alembic default readme
├── env.py                   # Migration environment configuration
├── script.py.mako          # Template for new migrations
└── versions/               # Migration scripts (version controlled)
    └── b297497b0925_*.py   # Initial schema migration
```

## Key Files

### `env.py`
Configures the migration environment.

- Loads SQLAlchemy models from `rapidrmf.db.models`
- Supports both async (asyncpg) and sync (psycopg2) connections
- Configures target metadata for autogeneration
- Sets up transaction context for migrations

### `script.py.mako`
Template used when generating new migrations via `alembic revision`.

### `versions/`
Contains timestamped migration scripts. Each file represents a specific schema change:
- **Upgrade**: Forward migration (add tables, columns, indexes)
- **Downgrade**: Rollback migration (undo changes)

## Configuration

Alembic configuration is in `alembic.ini` at the project root. The database URL can be configured in three ways (priority order):

### 1. Command-Line Override (Highest Priority)

```bash
alembic -x dbUrl=postgresql+psycopg2://user:pass@localhost:5432/rapidrmf upgrade head
```

Use this for one-off migrations or when you need to target a specific database.

### 2. Environment Variable

```bash
# Set environment variable
export RAPIDRMF_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/rapidrmf"

# Then run migrations
alembic upgrade head
```

Recommended for production deployments and CI/CD pipelines.

### 3. alembic.ini File (Default)

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite+aiosqlite:///./dev.db  # Default for local development
```

Used when no override is provided. Default is SQLite for local development and migration autogeneration.

### Production Database URLs

**PostgreSQL** (recommended for production):
```bash
# Async driver (for async operations)
postgresql+asyncpg://user:password@localhost:5432/rapidrmf

# Sync driver (for Alembic migrations)
postgresql+psycopg2://user:password@localhost:5432/rapidrmf
```

**SQLite** (local development only):
```bash
# Async
sqlite+aiosqlite:///./rapidrmf.db

# Sync
sqlite:///./rapidrmf.db
```

### Example: Production Migration

```bash
# Set database URL
export RAPIDRMF_DATABASE_URL="postgresql+psycopg2://rmf_user:secure_pass@db.example.com:5432/rapidrmf_prod"

# Run migrations
alembic upgrade head

# Or use CLI override
alembic -x dbUrl="postgresql+psycopg2://rmf_user:secure_pass@db.example.com:5432/rapidrmf_prod" upgrade head
```

## Common Operations

### Apply Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade one version forward
alembic upgrade +1

# Via RapidRMF CLI (recommended)
rapidrmf db upgrade
```

### Rollback Migrations

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade b297497b0925
```

### Check Current Version

```bash
# Show current database version
alembic current

# Show migration history
alembic history
```

### Generate New Migration

When you modify SQLAlchemy models in `rapidrmf/db/models.py`:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add new column to findings table"

# Create empty migration template
alembic revision -m "custom migration"
```

**Important**: Always review auto-generated migrations before applying!

## Initial Migration

The initial migration (`b297497b0925_*`) creates the foundational schema:

- **systems** table
- **evidence** and **evidence_manifests** tables
- **catalogs**, **controls**, **control_requirements** tables
- **validation_results** table
- **findings** table
- All indexes and foreign key constraints

## Development Workflow

1. **Modify models** in `rapidrmf/db/models.py`
2. **Generate migration**: `alembic revision --autogenerate -m "description"`
3. **Review migration** in `alembic/versions/`
4. **Test migration**: 
   ```bash
   alembic upgrade head  # Apply
   alembic downgrade -1  # Test rollback
   alembic upgrade head  # Re-apply
   ```
5. **Commit migration file** to version control

## Best Practices

- **Always review** auto-generated migrations for accuracy
- **Test both upgrade and downgrade** paths
- **Use descriptive names** for migration messages
- **One logical change per migration** (easier to rollback)
- **Commit migrations** to git immediately after creation
- **Never modify applied migrations** (create new ones instead)
- **Handle data migrations carefully** (backup before complex changes)

## Database Support

- **PostgreSQL**: Production recommended (use `postgresql+asyncpg://` or `postgresql+psycopg2://`)
- **SQLite**: Local development (use `sqlite+aiosqlite://` for async, `sqlite://` for sync)

Both dialects supported via Alembic's environment configuration.

## Troubleshooting

### Migration Conflicts

If multiple developers create migrations simultaneously:

```bash
# Show migration branches
alembic branches

# Merge branches by creating a merge migration
alembic merge -m "merge heads" <rev1> <rev2>
```

### Reset Database

For local development only:

```bash
# Drop all tables
alembic downgrade base

# Recreate schema
alembic upgrade head
```

### Manual Schema Inspection

```bash
# Show pending migrations
alembic current
alembic history

# Show SQL without applying
alembic upgrade head --sql
```

## Integration with RapidRMF

The RapidRMF CLI provides convenience commands:

```bash
# Run migrations
rapidrmf db upgrade

# Migrate file-based manifests to database
rapidrmf db migrate-from-files --system-id prod-app-01 --manifest-dir ./vault/manifests/
```

These commands use `rapidrmf/db/migrate.py` which wraps Alembic programmatically.
