# RapidRMF Architectural Refactoring

## Overview
This refactoring splits monolithic files into focused, domain-specific modules following the pattern established in `cli.py`.

## Changes Summary

### 1. API Module (`rapidrmf/api/`)

**Before:** All endpoints in `app.py` (282 lines)

**After:**
- `app.py` - Clean FastAPI app with router registration (35 lines)
- `routers/collect.py` - Collection endpoint logic (107 lines)
- `routers/validate.py` - Validation endpoint logic (72 lines)
- `routers/report.py` - Reporting endpoint logic (115 lines)
- `routers/__init__.py` - Router exports

**Benefits:**
- Each router is independently testable
- Clear separation of concerns by API domain
- Easy to add new routers without touching app.py
- Follows FastAPI best practices

### 2. Database Module (`rapidrmf/db/`)

**Before:** Single `repository.py` with all operations (266 lines)

**After:**
- `repository.py` - Backward-compatible wrapper that delegates to domain repos
- `repositories/catalog.py` - Catalog operations (60 lines)
- `repositories/control.py` - Control operations (78 lines)
- `repositories/system.py` - System operations (55 lines)
- `repositories/evidence.py` - Evidence/manifest operations (95 lines)
- `repositories/validation.py` - Validation results and findings (124 lines)
- `repositories/jobrun.py` - Job run operations (64 lines)
- `repositories/__init__.py` - Repository exports

**Benefits:**
- Each repository manages a single domain
- Easier to test individual repositories
- Backward compatible - existing code continues to work
- New code can import domain-specific repos: `from rapidrmf.db.repositories import CatalogRepository`

### 3. Scheduler Module (`rapidrmf/scheduler/`)

**Before:** Single `runner.py` with business logic + APScheduler (136 lines)

**After:**
- `core.py` - Pure business logic for validation jobs (143 lines)
- `runner.py` - APScheduler integration wrapper (72 lines)

**Benefits:**
- Core logic can be tested without APScheduler dependency
- Business logic separated from scheduling infrastructure
- Easy to swap schedulers or run jobs directly
- Backward compatible - existing scheduler code works unchanged

## Migration Guide

### For API Consumers
No changes needed - the FastAPI app still exports the same endpoints.

### For DB Repository Users

**Option 1: Continue using unified Repository (backward compatible)**
```python
from rapidrmf.db.repository import Repository
repo = Repository(session)
await repo.upsert_catalog(...)
```

**Option 2: Use domain-specific repositories (recommended for new code)**
```python
from rapidrmf.db.repositories import CatalogRepository, ControlRepository
catalog_repo = CatalogRepository(session)
control_repo = ControlRepository(session)
await catalog_repo.upsert_catalog(...)
```

### For Scheduler Users

**Option 1: Continue using runner (backward compatible)**
```python
from rapidrmf.scheduler.runner import start_scheduler
start_scheduler(config_path, env_name, cron="0 2 * * *")
```

**Option 2: Use core logic directly (recommended for custom scheduling)**
```python
from rapidrmf.scheduler.core import run_validation_job
result = await run_validation_job(config_path, env_name)
# Or synchronous:
from rapidrmf.scheduler.core import run_validation_job_sync
result = run_validation_job_sync(config_path, env_name)
```

## Testing Checklist

- [ ] API endpoints respond correctly
- [ ] Database operations work with both old and new repository imports
- [ ] Scheduler jobs execute successfully
- [ ] All existing tests pass
- [ ] Import statements work as expected

## Next Steps

1. Run full test suite
2. Update any documentation referencing old structure
3. Consider adding integration tests for new routers/repositories
4. Gradually migrate codebase to use domain-specific imports
