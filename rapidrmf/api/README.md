# RapidRMF REST API

Minimal REST API for RapidRMF compliance automation.

## Overview

This API provides three core endpoints that wrap existing CLI functionality:
- `/collect` - Trigger evidence collection from cloud providers
- `/validate` - Run validation against collected evidence
- `/report` - Generate compliance reports

**Design Principle**: DRY (Don't Repeat Yourself)
- All API endpoints reuse existing CLI/collection/validation logic
- No duplication between API and CLI implementations
- API is a thin HTTP wrapper around core functionality

## Architecture

The API module follows a **modular router pattern** for clean separation of concerns:

### Structure
```
rapidrmf/api/
├── app.py              # Main FastAPI app (registers routers)
├── operations.py       # Business logic shared across endpoints
├── models.py           # Pydantic request/response models
└── routers/
    ├── __init__.py     # Router exports
    ├── collect.py      # Collection endpoints
    ├── validate.py     # Validation endpoints
    └── report.py       # Reporting endpoints
```

### Benefits
- **Focused files**: Each router handles a single domain (collect/validate/report)
- **Testability**: Routers can be tested independently
- **Maintainability**: Easy to locate and modify specific endpoint logic
- **Scalability**: Add new routers without modifying existing code

### Usage
```python
# Import the configured FastAPI app
from rapidrmf.api import app

# Or import individual routers for custom configuration
from rapidrmf.api.routers import collect_router, validate_router, report_router
```

## Quick Start

### Install Dependencies

```powershell
pip install -r requirements.txt
```

### Start the API Server

```powershell
# Development mode (auto-reload)
python -m rapidrmf.api

# Or using uvicorn directly
uvicorn rapidrmf.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/

## API Endpoints

### POST `/collect`

Collect evidence from cloud providers or CI/CD systems.

**Supported Providers**:
- `terraform` - Terraform plan/apply logs
- `github` - GitHub Actions workflows
- `gitlab` - GitLab CI/CD pipelines
- `argo` - Argo Workflows
- `azure` - Azure resource configurations

**Example - Terraform**:
```json
POST /collect
{
  "environment": "production",
  "provider": "terraform",
  "terraform_plan_path": "/path/to/plan.json",
  "terraform_apply_path": "/path/to/apply.log"
}
```

**Example - GitHub Actions**:
```json
POST /collect
{
  "environment": "production",
  "provider": "github",
  "github_repo": "owner/repo",
  "github_token": "ghp_xxxxx",
  "github_run_id": 12345
}
```

**Response**:
```json
{
  "success": true,
  "artifacts_uploaded": 5,
  "manifest_key": "manifests/production/terraform-manifest.json",
  "environment": "production",
  "provider": "terraform",
  "message": "Collected 5 artifacts from terraform"
}
```

### POST `/validate`

Validate controls against collected evidence.

**Example**:
```json
POST /validate
{
  "environment": "production",
  "control_ids": ["AC-2", "CM-2", "SC-7"]
}
```

If `control_ids` is omitted, validates all controls from configured OSCAL catalogs.

**Response**:
```json
{
  "success": true,
  "environment": "production",
  "controls_validated": 3,
  "results": {
    "AC-2": {
      "control_id": "AC-2",
      "status": "pass",
      "message": "Account Management - Evidence provided",
      "evidence_keys": ["terraform-plan", "audit-log"],
      "metadata": {...},
      "remediation": null
    },
    ...
  },
  "summary": {
    "passed": 2,
    "failed": 0,
    "insufficient": 1,
    "unknown": 0
  }
}
```

**Validation Statuses**:
- `pass` - Control requirements satisfied
- `fail` - Control explicitly failed (not currently used in pattern-based validator)
- `insufficient_evidence` - Missing required evidence
- `unknown` - No validation rule defined

### POST `/report`

Generate compliance reports.

**Report Types**:
- `readiness` - Full compliance readiness with control coverage
- `engineer` - Engineer-focused validation report with remediation
- `auditor` - Auditor-focused validation report

**Example - Readiness Report**:
```json
POST /report
{
  "environment": "production",
  "report_type": "readiness"
}
```

**Example - Engineer Report**:
```json
POST /report
{
  "environment": "production",
  "report_type": "engineer",
  "control_ids": ["AC-2", "CM-2", "SC-7"]
}
```

**Response**:
```json
{
  "success": true,
  "environment": "production",
  "report_type": "readiness",
  "report_path": "/tmp/rapidrmf-readiness-abc123.html",
  "report_html": "<html>...</html>",
  "summary": {
    "manifests": 3,
    "artifacts": 42,
    "validation": {
      "passed": 35,
      "failed": 2,
      "insufficient": 5
    }
  }
}
```

### GET `/report/html`

Generate and return HTML report directly for browser viewing.

**Query Parameters**:
- `environment` (required) - Environment key
- `report_type` (optional) - Report type (default: `readiness`)
- `config_path` (optional) - Path to config file (default: `config.yaml`)

**Example**:
```
GET /report/html?environment=production&report_type=readiness
```

Returns HTML that can be viewed directly in a browser.

## Configuration

The API uses the same `config.yaml` as the CLI. Ensure your config file includes:

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

## Authentication

Currently, the API does not include built-in authentication. For production deployments:

1. **API Gateway**: Deploy behind an API gateway (AWS API Gateway, Azure API Management, etc.)
2. **Reverse Proxy**: Use nginx/Traefik with OAuth2 proxy
3. **Network Security**: Restrict access via VPC/firewall rules
4. **Future Enhancement**: Add JWT/OAuth2 authentication middleware

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message details",
  ...
}
```

HTTP status codes:
- `200` - Success
- `400` - Bad request (validation error)
- `500` - Internal server error

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rapidrmf/ rapidrmf/
COPY config.yaml catalogs/ ./

CMD ["uvicorn", "rapidrmf.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
services:
  rapidrmf-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./catalogs:/app/catalogs
      - ./evidence:/app/evidence
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/rapidrmf
```

### Kubernetes

See Helm charts (future enhancement).

## Testing

### Manual Testing with curl

**Collect Terraform Evidence**:
```bash
curl -X POST http://localhost:8000/collect \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "production",
    "provider": "terraform",
    "terraform_plan_path": "/path/to/plan.json"
  }'
```

**Validate Controls**:
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "production",
    "control_ids": ["AC-2", "CM-2"]
  }'
```

**Generate Report**:
```bash
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "production",
    "report_type": "readiness"
  }' | jq -r '.report_html' > report.html
```

### Python Client

```python
import requests

# Collect evidence
response = requests.post("http://localhost:8000/collect", json={
    "environment": "production",
    "provider": "terraform",
    "terraform_plan_path": "/path/to/plan.json"
})
print(response.json())

# Validate controls
response = requests.post("http://localhost:8000/validate", json={
    "environment": "production",
    "control_ids": ["AC-2", "CM-2", "SC-7"]
})
results = response.json()
print(f"Passed: {results['summary']['passed']}")

# Generate report
response = requests.post("http://localhost:8000/report", json={
    "environment": "production",
    "report_type": "readiness"
})
with open("report.html", "w") as f:
    f.write(response.json()["report_html"])
```

## Architecture

### Code Organization

```
rapidrmf/api/
├── __init__.py          # Module init
├── __main__.py          # Dev server entry point
├── app.py               # FastAPI application and endpoints
├── models.py            # Pydantic request/response models
├── operations.py        # Core logic (wraps existing CLI/collectors/validators)
└── README.md            # This file
```

### Design Principles

1. **DRY**: All API operations delegate to existing modules:
   - `operations.collect_evidence()` → wraps `rapidrmf.collectors.*`
   - `operations.validate_evidence()` → wraps `rapidrmf.validators.validate_controls()`
   - `operations.generate_report()` → wraps `rapidrmf.reporting.*`

2. **No Duplication**: API does NOT reimplement collection/validation logic
   - CLI commands call collectors directly
   - API calls the same collectors via `operations.py`
   - Single source of truth for business logic

3. **Thin HTTP Layer**: API focuses on:
   - HTTP request/response handling
   - Parameter validation (Pydantic)
   - Error formatting
   - Logging

## Future Enhancements

- [ ] Authentication (JWT/OAuth2)
- [ ] Rate limiting
- [ ] Async endpoint handlers for long-running operations
- [ ] WebSocket support for real-time validation progress
- [ ] Job queue integration (Celery/RQ) for background processing
- [ ] GraphQL API alternative
- [ ] OpenAPI spec generation and client SDKs
- [ ] Metrics and observability (Prometheus/OpenTelemetry)
