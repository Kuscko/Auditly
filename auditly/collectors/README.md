# Collectors

Collectors pull artifacts and metadata, hash them, and write manifests so evidence can be validated and audited. All collectors upload to the configured vault (MinIO or S3) and can also emit local files with `--output-dir`.

## Available collectors
- Terraform: plan/apply artifacts
- GitHub Actions: workflow logs and artifacts
- GitLab CI: pipeline job logs and artifacts
- Argo Workflows: workflow logs and step artifacts
- Azure: storage, Key Vault, IAM role assignments, activity logs, and conditional access

## Quick commands
```powershell
# Terraform
python -m auditly collect terraform --config config.yaml --env edge --plan plan.out --apply apply.log

# GitHub
python -m auditly collect github --config config.yaml --env edge --repo owner/repo --branch main --token $env:GITHUB_TOKEN

# GitLab
python -m auditly collect gitlab --config config.yaml --env edge --project-id group/proj --ref main --token $env:GITLAB_TOKEN

# Argo
python -m auditly collect argo --config config.yaml --env edge --base-url https://argo-server:2746 --workflow-name my-workflow

# Azure
python -m auditly collect azure --config config.yaml --env edge --subscription-id <sub> --resource-group <rg> --storage-account <sa> --key-vault <kv> --output-dir ./azure-evidence
```

## Azure evidence collected
- storage-account.json: encryption, HTTPS, TLS
- keyvault.json: soft delete, purge protection, RBAC mode
- storage-role-assignments.json: IAM roles for storage
- keyvault-role-assignments.json: IAM roles for Key Vault
- activity-log.json: 24-hour audit trail
- conditional-access-policies.json: MFA enforcement snapshot
- evidence.json: manifest with checksums, timestamps, and metadata

### Azure prerequisites
- `az login` and subscription context set
- Reader on subscription for storage/Key Vault/activity log
- Graph API Policy.Read.All to retrieve conditional access (collector continues if missing)

## Vault behavior
- With `--output-dir`, evidence is written locally and to the vault
- Without `--output-dir`, evidence is staged in a temp directory then uploaded
- Manifests are stored under `manifests/{env}/<collector>-manifest.json`

## Data flow
1) Collect artifacts and metadata
2) Hash files and write evidence.json manifest
3) Upload artifacts and manifest to the enclave vault
4) Validate controls and generate reports using stored evidence

## Tips
- Pass `--metadata key=value` to add context to manifests
- Keep `config.yaml` per enclave; never reuse edge credentials for il5/il6
- Use short-lived tokens for CI collectors (GitHub/GitLab/Argo)
