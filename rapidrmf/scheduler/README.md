# Scheduled Validation

This module provides automated scheduled validation runs. It executes validations on a schedule (e.g., nightly), persists job state to the database, and reuses existing validation + persistence flows.

## Status
✅ **Complete** - Foundation scheduler implementation finished
- APScheduler dependency added (`requirements.txt`)
- Job state persistence implemented (`JobRun` model + Alembic migration)
- Scheduler CLI added: `rapidrmf scheduler start`, `once`, and `runs`
- Validation execution wired to DB/validators with full persistence
- Job run tracking with metrics and error handling
- CLI to inspect recent job runs with filtering and JSON output

## Architecture

The scheduler module uses a **separation of concerns pattern** to isolate business logic from scheduling infrastructure:

### Structure
```
rapidrmf/scheduler/
├── core.py      # Pure validation job logic (no APScheduler dependency)
├── runner.py    # APScheduler integration wrapper (backward compatible)
└── README.md
```

### Benefits
- **Testability**: Core logic can be tested without APScheduler
- **Flexibility**: Easy to swap schedulers or run jobs directly
- **Separation**: Business logic isolated from infrastructure concerns
- **Backward Compatible**: Existing scheduler code works unchanged

### Usage

**Option 1: Use APScheduler Integration (backward compatible)**
```python
from rapidrmf.scheduler.runner import start_scheduler, run_scheduled_validation

# Start background scheduler
start_scheduler(config_path="config.yaml", env_name="production", cron="0 2 * * *")

# Run single job through scheduler
run_scheduled_validation(config_path="config.yaml", env_name="production")
```

**Option 2: Use Core Logic Directly (recommended for custom scheduling)**
```python
from rapidrmf.scheduler.core import run_validation_job, run_validation_job_sync

# Async execution
result = await run_validation_job(config_path="config.yaml", env_name="production")

# Sync execution
result = run_validation_job_sync(config_path="config.yaml", env_name="production")

# Result contains: {"status": "success", "job_id": 123, "metrics": {...}}
```

## Features
- **Scheduled Validation**: Nightly validation window per environment (configurable via cron)
- **Job Tracking**: All runs tracked in `job_runs` table with status, timestamps, metrics
- **Full Validation Flow**: Loads config, initializes DB, fetches systems/controls/evidence, runs validators
- **Result Persistence**: ValidationResult records persisted via existing Repository methods
- **Error Handling**: Exceptions captured and recorded in job runs
- **CLI Inspection**: View recent runs, filter by status/environment, export as JSON
- **Config-Driven**: All targets and database URLs sourced from config file

## Installation

Install dependencies (includes APScheduler):

```powershell
.\.venv\Scripts\pip.exe install -r requirements.txt
```

Apply database migrations (adds `job_runs` table):

```powershell
.\.venv\Scripts\alembic.exe -x dbUrl=postgresql+asyncpg://rapidrmf:rapidrmf_local_pass@localhost:5433/rapidrmf_test upgrade head
```

## Usage

### Programmatic API

```python
from rapidrmf.scheduler import runner

# Start a scheduler that triggers nightly validation for a given environment
runner.start_scheduler(config_path="./config.yaml", env_name="production")

# Run a single validation job immediately
runner.run_scheduled_validation(config_path="./config.yaml", env_name="production")
```

### CLI Commands

```powershell
# Start background scheduler (02:00 daily by default)
.\.venv\Scripts\python.exe -m rapidrmf scheduler start --config config.yaml --env production --cron "0 2 * * *"

# Run a single validation job immediately (useful for testing)
.\.venv\Scripts\python.exe -m rapidrmf scheduler once --config config.yaml --env production

# View recent job runs (table output)
.\.venv\Scripts\python.exe -m rapidrmf scheduler runs --config config.yaml --env production --limit 20

# Filter by job status
.\.venv\Scripts\python.exe -m rapidrmf scheduler runs --config config.yaml --status failed --limit 10

# Export as JSON for scripting/monitoring
.\.venv\Scripts\python.exe -m rapidrmf scheduler runs --config config.yaml --env production --json
```

## Implementation Details

### Scheduler
- **Engine**: APScheduler (`BackgroundScheduler`) with cron trigger
- **Default Schedule**: 02:00 AM daily (customizable via `--cron` flag)
- **Execution**: Async validation flow wrapped in `asyncio.run()`

### Database
- **ORM**: SQLAlchemy models + async repository methods
- **Job State**: Tracked in `job_runs` table (status, timestamps, metrics, errors)
- **Validation Results**: Persisted via existing `Repository.add_validation_result()`

### Validation Flow
1. Load `AppConfig` from YAML
2. Initialize DB connection from environment config
3. Start a `JobRun` record (status: `running`)
4. Fetch all systems for environment from DB
5. Fetch all controls from DB
6. Fetch all evidence for each system
7. Execute `validate_controls()` with fetched data
8. Persist each `ValidationResult` to DB
9. Update `JobRun` with metrics and status (`success`/`failed`)
10. Handle exceptions and record errors in job run

### JobRun Schema
- **Table**: `job_runs`
- **Fields**:
  - `id` (int, primary key)
  - `job_type` (str) - e.g., "validation"
  - `environment` (str) - environment name from config
  - `status` (enum) - `running`, `success`, `failed`
  - `started_at` (datetime) - job start timestamp
  - `finished_at` (datetime, nullable) - job completion timestamp
  - `error` (text, nullable) - exception details if failed
  - `metrics` (JSON) - e.g., `{"results_saved": 42, "errors": 0}`
  - `attributes` (JSON) - extensible metadata
- **Status Lifecycle**: `running` → `success` or `failed`

### Repository API

**Job Run Management:**
```python
# Start a new job run
job = await repo.start_job_run(
    job_type="validation",
    environment="production",
    attributes={"triggered_by": "scheduler"}
)

# Finish a job run (success)
await repo.finish_job_run(
    job=job,
    status="success",
    metrics={"results_saved": 42, "errors": 0}
)

# Finish a job run (failure)
await repo.finish_job_run(
    job=job,
    status="failed",
    error=str(exception),
    metrics={"results_saved": 0, "errors": 1}
)

# Query recent job runs
runs = await repo.get_recent_job_runs(
    job_type="validation",
    environment="production",
    limit=50
)
```

**Validation Support:**
```python
# Listing helpers for scheduled validation
controls = await repo.list_controls()
systems = await repo.list_systems_by_environment("production")
evidence = await repo.list_evidence_for_system(system)
```

## Configuration Example

```yaml
environments:
  production:
    description: "Production environment"
    database_url: "postgresql+asyncpg://user:pass@localhost:5432/rapidrmf"
    storage:
      type: "minio"
      endpoint: "s3.example.com"
      bucket: "evidence-prod"
      # ... other storage config

catalogs:
  nist-800-53-rev5:
    path: "catalogs/NIST_SP-800-53_rev5_catalog.json"
```

## CLI Inspection Examples

**Table view (default):**
```
┌────┬──────────────┬─────────┬───────────────────────┬───────────────────────┬────────────┐
│ ID │ Env          │ Status  │ Started               │ Finished              │ Error      │
├────┼──────────────┼─────────┼───────────────────────┼───────────────────────┼────────────┤
│ 12 │ production   │ success │ 2026-01-08 02:00:15   │ 2026-01-08 02:03:42   │            │
│ 11 │ production   │ failed  │ 2026-01-07 02:00:10   │ 2026-01-07 02:00:12   │ Database…  │
│ 10 │ staging      │ success │ 2026-01-06 02:00:05   │ 2026-01-06 02:01:30   │            │
└────┴──────────────┴─────────┴───────────────────────┴───────────────────────┴────────────┘
```

**JSON output:**
```json
[
  {
    "id": 12,
    "environment": "production",
    "status": "success",
    "started_at": "2026-01-08T02:00:15",
    "finished_at": "2026-01-08T02:03:42",
    "error": null,
    "metrics": {"results_saved": 42, "errors": 0},
    "attributes": {"triggered_by": "scheduler"}
  }
]
```

## Error Handling
- **Exceptions During Validation**: Captured and recorded in `JobRun.error` field
- **Job Status**: Set to `failed` with error details
- **Partial Success**: If some validations succeed before error, those results are persisted
- **Retry Logic**: Not implemented in foundation - consider APScheduler's retry policies

## Monitoring Integration
- Export job runs as JSON for external monitoring systems
- Query `job_runs` table directly for dashboards
- Monitor `status` field for failed jobs
- Check `finished_at - started_at` for execution duration
- Review `metrics.errors` for validation error counts

## Future Enhancements
1. **Selective Validation**: Filter systems/controls via config (currently validates all)
2. **Parallel Execution**: Validate multiple systems concurrently
3. **Graceful Shutdown**: Signal handling for clean scheduler termination
4. **Advanced Logging**: Structured logs with job run IDs
5. **Retry Policies**: Automatic retry of failed jobs
6. **Notification Hooks**: Email/webhook alerts on job failures
7. **Incremental Validation**: Only validate changed evidence
8. **Performance Metrics**: Track validation execution time per control
