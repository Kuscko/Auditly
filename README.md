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
- Collect evidence: `python -m rapidrmf collect <terraform|github|gitlab|argo|azure> --config config.yaml --env <env>`
- Validate controls: `python -m rapidrmf policy validate --evidence ./evidence`
- Run scanners: `python -m rapidrmf scan system --config-file system-config.json --out-json scan-results.json`
- Generate readiness report: `python -m rapidrmf report readiness --config config.yaml --env <env> --out report.html`
- Create signed bundle: `python -m rapidrmf bundle create --config config.yaml --env edge --out-path evidence-bundle.tar.gz`

## What's included (v0.1)

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

## Coming next (roadmap)

- [ ] AWS, GCP multi-cloud collectors
- [ ] PostgreSQL/Cosmos DB persistent storage
- [ ] Continuous compliance monitoring
- [ ] POA&M and ATO package generation
- [ ] HIPAA, PCI DSS, ISO 27001 frameworks
- [ ] REST API and CI/CD webhooks
- [ ] Kubernetes deployment and Helm charts
- See the full [roadmap](ROADMAP.md) for 100+ planned features

## Learn more
- Architecture and modules: [rapidrmf/README.md](rapidrmf/README.md)
- Collectors (Terraform, CI/CD, Azure): [rapidrmf/collectors/README.md](rapidrmf/collectors/README.md)
- Storage backends: [rapidrmf/storage/README.md](rapidrmf/storage/README.md)
- Policy engines: [rapidrmf/policy/README.md](rapidrmf/policy/README.md)
- Reporting: [rapidrmf/reporting/README.md](rapidrmf/reporting/README.md)
- Tests and validation suites: [tests/README.md](tests/README.md)
- Development roadmap: [ROADMAP.md](ROADMAP.md)
