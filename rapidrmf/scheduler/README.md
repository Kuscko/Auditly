# Scheduled Validation (Foundation)

This module provides scaffolding for scheduled validation runs. It will run validations on a schedule (e.g., nightly), persist job state to the database, and reuse existing validation + persistence flows.

## Status
- APScheduler dependency added (`requirements.txt`)
- Job state persistence scaffolded (`JobRun` model + Alembic migration)
- Scheduler CLI added: `rapidrmf scheduler start` and `rapidrmf scheduler once`
- Next: wire validation execution + persistence into `run_scheduled_validation()`

## Planned Features
- Nightly validation window per environment (configurable)
- Job tracking and metrics persisted to DB (`job_runs` table)
- Reuse existing `Repository` for persistence of validation results
- Config-driven targets (systems/catalogs) to validate

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

```python
from rapidrmf.scheduler import runner

# Start a scheduler that triggers nightly validation for a given environment
runner.start_scheduler(config_path="./config.yaml", env_name="production")
```

CLI commands:

```powershell
# Start background scheduler (02:00 daily by default)
.\.venv\Scripts\python.exe -m rapidrmf scheduler start --config config.yaml --env production --cron "0 2 * * *"

# Run a single validation job immediately
.\.venv\Scripts\python.exe -m rapidrmf scheduler once --config config.yaml --env production
```

## Implementation Notes
- Scheduler: APScheduler (`BackgroundScheduler`) – cron trigger
- DB: SQLAlchemy models + repository methods for job state
- Validation: Use existing validators + `persist_validation_if_db` flow

### JobRun schema
- Table: `job_runs`
- Fields: `id`, `job_type`, `environment`, `status`, `started_at`, `finished_at`, `error`, `metrics` (JSON), `attributes` (JSON)
- Status lifecycle: `pending` → `running` → `success`/`failed`

### Repository API
- `start_job_run(job_type, environment, attributes=None)` → `JobRun`
- `finish_job_run(job, status="success", error=None, metrics=None, attributes_update=None)` → `JobRun`
- `get_recent_job_runs(job_type=None, environment=None, limit=50)` → list of `JobRun`

## Next Steps
1. Wire `run_scheduled_validation()` to:
   - resolve environment via config
   - retrieve targets (systems/catalogs)
   - run validations
   - persist results
2. Add CLI to view recent job runs/status (optional)
3. Graceful scheduler shutdown + logging improvements
