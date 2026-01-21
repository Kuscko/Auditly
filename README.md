# RapidRMF

RapidRMF automates compliance evidence collection, validation, and reporting for regulated environments. It runs offline on edge networks, writes tamper-evident manifests, and scales to GovCloud with MinIO or S3 vaults.

## What it does
- Collects evidence from Terraform, CI/CD (GitHub, GitLab, Argo), and Azure infrastructure with checksums and manifests
- Validates controls and scans live systems to surface gaps before audits
- Generates dual-view readiness reports for engineers and auditors
- Moves evidence safely between enclaves with signed, air-gapped bundles

## Fast start
1) Install and activate a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
2) Launch a local MinIO vault (example for the edge enclave):
```powershell
docker run -d -p 9000:9000 -p 9001:9001 ^
  -e MINIO_ROOT_USER=minioadmin ^
  -e MINIO_ROOT_PASSWORD=minioadmin ^
  --name rapidrmf-minio minio/minio server /data --console-address ":9001"
```
3) Initialize configuration and point the edge environment at http://localhost:9000:
```powershell
python -m rapidrmf init-config --out config.yaml
```
4) Collect Azure evidence and generate a report:
```powershell
python -m rapidrmf collect azure --config config.yaml --env edge --output-dir ./evidence
python -m rapidrmf report readiness --config config.yaml --env edge --out report.html
```
Open report.html to review coverage and findings.

## Core commands

### Evidence Collection
```bash
# Collect evidence with database persistence
rapidrmf collect <terraform|github|gitlab|argo|azure> \
  --config config.yaml \
  --env <env>

# Example: Azure with database
rapidrmf collect azure \
  --config config.yaml \
  --env edge \
  --output-dir ./evidence

# Run multiple collections concurrently from a JSON list
rapidrmf collect batch \
  --requests-file requests.json \
  --timeout 120
```

Where `requests.json` contains:
```json
[
  {"config_path": "config.yaml", "environment": "prod", "provider": "terraform", "terraform_plan_path": "plan.json"},
  {"config_path": "config.yaml", "environment": "prod", "provider": "github", "github_repo": "org/repo", "github_token": "...", "github_run_id": 12345}
]
```

### Validation & Database
```bash
# Validate controls and persist results to database
rapidrmf policy validate \
  --evidence-file evidence.json \
  --config config.yaml \
  --env production

# Run database migrations
rapidrmf db upgrade
rapidrmf db downgrade
rapidrmf db current
```

### Scanning & Reporting
```bash
# Run security scanners
rapidrmf scan system \
  --config-file system-config.json \
  --out-json scan-results.json

# Generate readiness report
rapidrmf report readiness \
  --config config.yaml \
  --env <env> \
  --out report.html
```

### Air-Gap Transfer
```bash
# Create signed bundle
rapidrmf bundle create \
  --config config.yaml \
  --env edge \
  --out-path evidence-bundle.tar.gz
```

## What's included

### v0.3 (Current - Core Engine Complete)

| Feature | Status |
|---------|--------|
| **Python 3.14 Support** | ✓ Full Python 3.14 compatibility with SQLAlchemy 2.0.36 |
| **AWS Evidence Collector** | ✓ IAM, EC2, S3, CloudTrail, VPC, RDS, KMS, Secrets Manager |
| **GCP Evidence Collector** | ✓ Compute, Storage, IAM, Cloud SQL, Cloud Logging |
| **Evidence Lifecycle** | ✓ Versioning, staleness detection, deduplication, correlation |
| **Advanced Validation** | ✓ Control dependencies, custom validators, findings lifecycle |
| **Performance Optimization** | ✓ Caching, parallel collection (async), incremental validation |
| **Batch API & CLI** | ✓ Concurrent collection via /batch endpoint and CLI commands |
| **PostgreSQL Backend** | ✓ SQLAlchemy 2.x with async/sync, Alembic migrations |
| **Code Quality** | ✓ Black/Ruff/mypy configured, pre-commit hooks, 103 passing tests |

### v0.2 (Released - Database Persistence)

| Feature | Status |
|---------|--------|
| **PostgreSQL Database** | ✓ SQLAlchemy 2.x with async/sync support |
| **Alembic Migrations** | ✓ Schema versioning and production config |
| **Evidence Persistence** | ✓ Systems, evidence, manifests stored in DB |
| **Validation Persistence** | ✓ Control validation results with history |
| **Catalog Management** | ✓ NIST 800-53, CIS controls in database |
| **Query Operations** | ✓ Latest results, filter by status, control history |
| **CLI Integration** | ✓ Optional DB persistence via --config --env flags |
| **Integration Tests** | ✓ End-to-end PostgreSQL validation suite |

### v0.1 (Released)

| Feature | Status |
|---------|--------|
| **Evidence Collection** | ✓ Azure, Terraform, GitHub Actions, GitLab CI, Argo |
| **Compliance Validation** | ✓ 69 validators across 20 families (NIST/FedRAMP/STIG) |
| **Security Scanning** | ✓ IAM, encryption, backup posture |
| **Waiver Tracking** | ✓ Auto-expiry, compensating controls |
| **Reporting** | ✓ Dual-view (engineer + auditor), HTML/JSON export |
| **Storage** | ✓ MinIO (edge), S3 (GovCloud) |
| **Air-Gap Transfer** | ✓ Ed25519-signed bundles, SHA256 manifests |
| **Multi-Enclave** | ✓ Edge/IL2/IL4/IL5/IL6 isolation |
| **Offline Operation** | ✓ Policy engines (Conftest + OPA WASM) |

## v0.4 Roadmap: REST API & Integration

**Next Phase** (starting now):
- [ ] **REST API Tier 1**: Evidence CRUD, validation endpoints, control status queries
- [ ] **Report APIs**: Generate readiness reports (HTML/JSON), export findings
- [ ] **CI/CD Integration**: GitHub/GitLab pre-deployment compliance checks
- [ ] **Webhook Support**: Auto-trigger validation on system/evidence changes
- [ ] **API Documentation**: OpenAPI specs, interactive Swagger UI

**Deferred to v0.5+** (after APIs stable):
- Web dashboard UI for visual compliance monitoring
- Interactive reports with dashboards and drilling-down
- Advanced framework support (HIPAA, PCI, ISO 27001)
- Multi-tenancy and RBAC UI
- AI-powered recommendations

**Philosophy**: Build functional APIs first, then UI layers on top.
Test coverage: 103 passing, 4 skipped (all core features validated).

Full feature list: [ROADMAP.md](ROADMAP.md)

## Learn more
- Architecture and modules: [rapidrmf/README.md](rapidrmf/README.md)
- **Database layer**: [rapidrmf/db/README.md](rapidrmf/db/README.md) - PostgreSQL persistence, migrations, repository pattern
- Collectors (Terraform, CI/CD, Azure): [rapidrmf/collectors/README.md](rapidrmf/collectors/README.md)
- Storage backends: [rapidrmf/storage/README.md](rapidrmf/storage/README.md)
- Policy engines: [rapidrmf/policy/README.md](rapidrmf/policy/README.md)
- Reporting: [rapidrmf/reporting/README.md](rapidrmf/reporting/README.md)
- **Tests and validation**: [tests/README.md](tests/README.md) - Integration tests with PostgreSQL
- Development roadmap: [ROADMAP.md](ROADMAP.md)
