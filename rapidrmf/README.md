# RapidRMF Package

This package contains the RapidRMF CLI and core services for collecting evidence, validating controls, scanning live systems, and producing audit-ready reports.

## Modules at a glance
- CLI entrypoints: [cli.py](cli.py)
- Config models: [config.py](config.py)
- Evidence and manifests: [evidence.py](evidence.py)
- Collectors: [collectors](collectors/README.md)
- Storage backends: [storage](storage/README.md)
- Compliance logic: [validators.py](validators.py), [scanners.py](scanners.py), [waivers.py](waivers.py)
- Policy engines: [policy](policy/README.md)
- Reporting: [reporting](reporting/README.md)

## Automation layers
- Evidence collection: Terraform, GitHub, GitLab, Argo, Azure (file-based with SHA256 manifests)
- Validation and scanning: 69 validators across 20 families plus IAM/encryption/backup scanners
- Policy enforcement: Conftest (Rego) and OPA WASM for offline evaluation
- Bundles: Ed25519-signed exports for air-gapped transfer between enclaves

## Typical workflows

### Collect
```powershell
python -m rapidrmf collect terraform --config config.yaml --env edge --plan plan.out
python -m rapidrmf collect github --config config.yaml --env edge --repo owner/repo --branch main
python -m rapidrmf collect azure --config config.yaml --env edge --subscription-id <sub> --resource-group <rg> --storage-account <sa> --key-vault <kv>
```

### Validate and scan
```powershell
python -m rapidrmf policy validate --evidence ./evidence
python -m rapidrmf scan system --config-file system-config.json --out-json scan-results.json
```

### Report
```powershell
python -m rapidrmf report readiness --config config.yaml --env edge --out report.html
```

### Air-gapped bundles
```powershell
python -m rapidrmf bundle keygen --out-dir .keys --name rapidrmf
python -m rapidrmf bundle create --config config.yaml --env edge --out-path evidence-bundle.tar.gz
python -m rapidrmf bundle verify --bundle-path evidence-bundle.tar.gz --public-key-path .keys\rapidrmf.ed25519.pub
python -m rapidrmf bundle import --config config.yaml --env govcloud-il5 --bundle-path evidence-bundle.tar.gz --public-key-path .keys\rapidrmf.ed25519.pub
```

## Configuration tips
- Define enclaves under `environments` in config.yaml (edge -> MinIO, il5/il6 -> S3)
- Keep mapping.yaml and waivers.yaml alongside config to drive coverage and exception tracking
- Use separate buckets/prefixes per enclave to avoid cross-enclave leakage

## Where to go next
- Collector details and evidence lists: [collectors/README.md](collectors/README.md)
- Storage backends and config examples: [storage/README.md](storage/README.md)
- Policy engines: [policy/README.md](policy/README.md)
- Reporting views and outputs: [reporting/README.md](reporting/README.md)
- Validation and scanning tests: [../tests/README.md](../tests/README.md)
