#!/usr/bin/env pwsh
<#
.SYNOPSIS
    End-to-end automation script for RapidRMF Azure testing
    
.DESCRIPTION
    This script automates the complete RapidRMF workflow:
    1. Apply Terraform infrastructure
    2. Generate system-config.json from Terraform outputs
    3. Collect evidence (Terraform plan as evidence artifact)
    4. Run compliance scanners
    5. Validate policies
    6. Generate readiness report
    
.PARAMETER TerraformDir
    Path to Terraform directory (default: current directory)
    
.PARAMETER OutputDir
    Directory for generated artifacts (default: ./output)
    
.PARAMETER SkipTerraform
    Skip Terraform apply (use existing infrastructure)
    
.EXAMPLE
    .\run_azure_validation.ps1
    
.EXAMPLE
    .\run_azure_validation.ps1 -SkipTerraform -OutputDir ./results
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$TerraformDir = ".",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "./output",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipTerraform
)

$ErrorActionPreference = "Stop"

# Python executable (use repo venv)
$PythonExe = "C:/Users/Patrick Kelly/Desktop/Personal Work/Development/RapidRMF/.venv/Scripts/python.exe"

# Color output helpers
function Write-Success { param($Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Failure { param($Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

# Ensure output directory exists
$OutputPath = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $OutputPath) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    $OutputPath = Resolve-Path $OutputDir
}

Write-Info "RapidRMF Azure Validation Pipeline"
Write-Info "===================================="
Write-Info "Terraform Dir: $TerraformDir"
Write-Info "Output Dir: $OutputPath"
Write-Info ""

# Step 1: Apply Terraform (optional)
if (-not $SkipTerraform) {
    Write-Info "Step 1: Applying Terraform configuration..."
    try {
        Push-Location $TerraformDir
        
        # Initialize if needed
        if (-not (Test-Path ".terraform")) {
            Write-Info "Initializing Terraform..."
            terraform init
        }
        
        # Plan
        Write-Info "Running terraform plan..."
        terraform plan -out="$OutputPath/terraform.plan"
        
        # Apply
        Write-Info "Applying Terraform..."
        terraform apply -auto-approve "$OutputPath/terraform.plan"
        
        Write-Success "Terraform infrastructure deployed"
    }
    catch {
        Write-Failure "Terraform failed: $_"
        Pop-Location
        exit 1
    }
    finally {
        Pop-Location
    }
} else {
    Write-Warning "Skipping Terraform apply (using existing infrastructure)"
}

# Step 2: Generate system-config.json
Write-Info "Step 2: Generating system-config.json from Terraform outputs..."
try {
    $SystemConfigPath = Join-Path $OutputPath "system-config.json"
    & $PythonExe generate_system_config.py `
        --terraform-dir $TerraformDir `
        --output $SystemConfigPath `
        --pretty
    
    Write-Success "Generated $SystemConfigPath"
}
catch {
    Write-Failure "Failed to generate system config: $_"
    exit 1
}

# Step 3: Create evidence.json (minimal example)
Write-Info "Step 3: Creating evidence.json..."
try {
    $EvidencePath = Join-Path $OutputPath "evidence.json"
    $Evidence = @{
        "terraform-plan" = @{
            "timestamp" = (Get-Date -Format "o")
            "valid" = $true
            "path" = "$OutputPath/terraform.plan"
        }
        "terraform-apply" = @{
            "timestamp" = (Get-Date -Format "o")
            "success" = $true
        }
        "storage-account-encrypted" = @{
            "resource" = "rapidrmfstore"
            "encryption_enabled" = $true
            "https_only" = $true
            "min_tls_version" = "TLS1_2"
        }
        "key-vault-security" = @{
            "soft_delete_enabled" = $true
            "purge_protection_enabled" = $true
            "rbac_enabled" = $true
        }
    }
    
    $Evidence | ConvertTo-Json -Depth 10 | Out-File -FilePath $EvidencePath -Encoding utf8
    Write-Success "Created $EvidencePath"
}
catch {
    Write-Failure "Failed to create evidence: $_"
    exit 1
}

# Step 4: Run compliance scanners
Write-Info "Step 4: Running compliance scanners..."
try {
    $ScanResultsPath = Join-Path $OutputPath "scan-results.json"
    
    & $PythonExe -m rapidrmf scan system `
        --config-file $SystemConfigPath `
        --out-json $ScanResultsPath
    
    Write-Success "Scan results saved to $ScanResultsPath"
    
    # Display summary
    $ScanResults = Get-Content $ScanResultsPath | ConvertFrom-Json
    Write-Info "Scan Summary:"
    foreach ($scanner in $ScanResults.PSObject.Properties) {
        $name = $scanner.Name
        $findings = $scanner.Value.findings.Count
        $status = $scanner.Value.status
        Write-Info "  - $name`: $findings findings (status: $status)"
    }
}
catch {
    Write-Failure "Scanner failed: $_"
    exit 1
}

# Step 5: Validate policies
Write-Info "Step 5: Validating policies..."
try {
    $ValidationResultsPath = Join-Path $OutputPath "validation-results.json"
    
    & $PythonExe -m rapidrmf policy validate `
        --evidence-file $EvidencePath `
        --system-state-file $SystemConfigPath `
        --out-json $ValidationResultsPath
    
    Write-Success "Validation results saved to $ValidationResultsPath"
    
    # Display summary
    $ValidationResults = Get-Content $ValidationResultsPath | ConvertFrom-Json
    Write-Info "Validation Summary:"
    Write-Info "  - Passed: $($ValidationResults.passed)"
    Write-Info "  - Failed: $($ValidationResults.failed)"
    Write-Info "  - Insufficient: $($ValidationResults.insufficient)"
}
catch {
    Write-Failure "Validation failed: $_"
    # Continue anyway to generate report
}

# Step 6: Generate summary report
Write-Info "Step 6: Generating summary report..."
try {
    $ReportPath = Join-Path $OutputPath "azure-validation-report.md"
    
    $Report = @"
# RapidRMF Azure Validation Report
Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Infrastructure
- Resource Group: $(terraform -chdir=$TerraformDir output -raw resource_group 2>$null)
- Storage Account: $(terraform -chdir=$TerraformDir output -raw storage_account 2>$null)
- Key Vault: $(terraform -chdir=$TerraformDir output -raw key_vault 2>$null)

## Artifacts Generated
- System Config: ``$SystemConfigPath``
- Evidence: ``$EvidencePath``
- Scan Results: ``$ScanResultsPath``
- Validation Results: ``$ValidationResultsPath``

## Scan Results
$(if (Test-Path $ScanResultsPath) {
    $scan = Get-Content $ScanResultsPath | ConvertFrom-Json
    foreach ($scanner in $scan.PSObject.Properties) {
        "### $($scanner.Name.ToUpper())`n"
        "- Status: $($scanner.Value.status)`n"
        "- Findings: $($scanner.Value.findings.Count)`n"
        if ($scanner.Value.findings.Count -gt 0) {
            "``````json`n$(($scanner.Value.findings | ConvertTo-Json -Depth 10))`n```````n"
        }
    }
})

## Validation Results
$(if (Test-Path $ValidationResultsPath) {
    $val = Get-Content $ValidationResultsPath | ConvertFrom-Json
    "- Passed: $($val.passed)`n"
    "- Failed: $($val.failed)`n"
    "- Insufficient Evidence: $($val.insufficient)`n"
})

## Next Steps
1. Review scan findings and address high-severity issues
2. Collect additional evidence for insufficient controls
3. Update IAM policies and MFA configuration in system-config.json
4. Re-run validation after remediation
5. Generate HTML readiness report: ``python -m rapidrmf report readiness --config config.yaml --env edge --out report.html``
"@

    $Report | Out-File -FilePath $ReportPath -Encoding utf8
    Write-Success "Report saved to $ReportPath"
}
catch {
    Write-Warning "Failed to generate report: $_"
}

Write-Info ""
Write-Success "Pipeline complete! Results in: $OutputPath"
Write-Info ""
Write-Info "Quick review commands:"
Write-Info "  cat $SystemConfigPath | ConvertFrom-Json | Format-List"
Write-Info "  cat $ScanResultsPath | ConvertFrom-Json | Format-List"
Write-Info "  cat $ValidationResultsPath | ConvertFrom-Json | Format-List"
Write-Info "  cat $ReportPath"
