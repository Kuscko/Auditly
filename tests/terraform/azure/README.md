# Azure Validation Testing

This directory contains automation for validating auditly against Azure infrastructure.

## Files

- **main.tf** - Terraform configuration for test Azure environment (Storage Account, Key Vault, Log Analytics)
- **generate_system_config.py** - Generates `system-config.json` from Terraform outputs for scanning
- **run_azure_validation.ps1** - End-to-end PowerShell automation script

## Quick Start

### 1. Apply Terraform (if needed)

```powershell
cd tests/terraform/azure
terraform init
terraform plan
terraform apply -auto-approve
```

### 2. Run Full Validation Pipeline

```powershell
# Automated end-to-end validation
.\run_azure_validation.ps1
```

This script will:
1. Apply Terraform (optional, use `-SkipTerraform` if already deployed)
2. Generate `system-config.json` from Terraform outputs
3. Create evidence bundle with Terraform artifacts
4. Run compliance scanners (IAM, encryption, backup)
5. Validate policies against evidence
6. Generate summary report

**Output:** All artifacts saved to `./output/` directory.

### 3. Manual Step-by-Step

If you prefer manual control:

```powershell
# Generate system config from Terraform
python generate_system_config.py --terraform-dir . --output system-config.json --pretty

# Run scanners
python -m auditly scan system --config-file system-config.json --out-json scan-results.json

# Validate policies (requires evidence.json)
python -m auditly policy validate `
  --evidence-file evidence.json `
  --system-state-file system-config.json `
  --out-json validation-results.json
```

## System Config Generation

The `generate_system_config.py` script reads Terraform outputs and creates a JSON file compatible with auditly scanners:

```json
{
  "metadata": {
    "generated_by": "terraform",
    "resource_group": "kuscko-rg",
    "description": "Azure test environment"
  },
  "iam_policies": [...],
  "storage_accounts": [
    {
      "name": "auditlystore",
      "storage_encrypted": true,
      "https_only": true,
      "min_tls_version": "TLS1_2"
    }
  ],
  "key_vaults": [
    {
      "name": "auditly-kv",
      "soft_delete_enabled": true,
      "purge_protection_enabled": true,
      "rbac_authorization_enabled": true
    }
  ],
  "backup_policy": {...}
}
```

**Customization:** After generation, review and update:
- IAM policies (add actual RBAC assignments)
- MFA enforcement status
- Backup policies (RPO/RTO values)

## Evidence Collection

The automation script creates a minimal `evidence.json`:

```json
{
  "terraform-plan": {
    "timestamp": "2026-01-07T12:00:00Z",
    "valid": true
  },
  "storage-account-encrypted": {
    "encryption_enabled": true,
    "https_only": true
  },
  "key-vault-security": {
    "soft_delete_enabled": true,
    "purge_protection_enabled": true
  }
}
```

For production use, collect evidence using auditly commands:

```powershell
python -m auditly collect terraform --config config.yaml --env edge --plan terraform.plan
python -m auditly collect github --config config.yaml --env edge --repo org/repo
```

## Expected Results

### Scanners

The scanners will check:
- **IAM:** Overly permissive policies, MFA enforcement
- **Encryption:** Storage/Key Vault encryption settings, TLS versions
- **Backup:** RPO/RTO compliance, backup testing

### Validators

Policy validation checks controls like:
- **CM-2:** Baseline configuration (Terraform plan)
- **SC-13:** Cryptographic protection (storage encryption)
- **AC-2:** Account management (IAM policies)

### Sample Output

```
Generated system-config.json
-> Scan Summary:
  - iam: 1 findings (status: warning)
  - encryption: 0 findings (status: pass)
  - backup: 1 findings (status: warning)

-> Validation Summary:
  - Passed: 2
  - Failed: 0
  - Insufficient: 1
```

## Cleanup

```powershell
terraform destroy -auto-approve
Remove-Item -Recurse -Force ./output
```

## Integration with CI/CD

Add to GitHub Actions:

```yaml
- name: Run Azure Validation
  run: |
    cd tests/terraform/azure
    terraform init
    terraform apply -auto-approve
    python generate_system_config.py --output system-config.json
    python -m auditly scan system --config-file system-config.json --out-json scan-results.json
```

## Troubleshooting

**Terraform not in PATH:**
- Add Terraform to your PATH or use full path to `terraform.exe`

**Python module errors:**
- Ensure auditly is installed: `pip install -e .` from repo root
- Activate virtual environment if using one

**Azure authentication:**
- Run `az login` before Terraform operations
- Ensure correct subscription: `az account set --subscription <id>`

## Further Automation

To fully automate the workflow:

1. **Azure Resource Tagging** - Tag resources with control mappings
2. **Azure Policy Integration** - Use Azure Policy for continuous compliance
3. **Scheduled Scans** - Run validation via Azure DevOps/GitHub Actions on a schedule
4. **Alert Integration** - Send scan findings to Azure Monitor/Log Analytics
5. **Evidence Auto-Upload** - Automatically upload Terraform state to evidence vault

See main [README.md](../../../README.md) for complete auditly workflow details.
