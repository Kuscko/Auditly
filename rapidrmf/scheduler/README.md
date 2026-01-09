# Scheduled Validation (Foundation)

This module provides scaffolding for scheduled validation runs. It will run validations on a schedule (e.g., nightly), persist job state to the database, and reuse existing validation + persistence flows.

## Status
- Scaffold created
- Next: add APScheduler, job state persistence, and validation wiring

## Planned Features
- Nightly validation window per environment (configurable)
- Job tracking and metrics persisted to DB (`job_runs` table)
- Reuse existing `Repository` for persistence of validation results
- Config-driven targets (systems/catalogs) to validate

## Usage (Preview)

```python
from rapidrmf.scheduler import runner

# Start a scheduler that triggers nightly validation for a given environment
runner.start_scheduler(config_path="./config.yaml", env_name="production")
```

## Implementation Notes
- Scheduler: APScheduler (`BackgroundScheduler`) – cron trigger
- DB: SQLAlchemy models + repository methods for job state
- Validation: Use existing validators + `persist_validation_if_db` flow

## Next Steps
1. Add APScheduler dependency and initialize scheduler
2. Implement `job_runs` model/migration and repository methods
3. Wire `run_scheduled_validation()` to:
   - resolve environment via config
   - retrieve targets (systems/catalogs)
   - run validations
   - persist results
4. Add CLI command to start/stop the scheduler
