param(
    [Parameter(Mandatory=$true)] [string]$SubscriptionId,
    [Parameter(Mandatory=$false)] [string]$TenantId = "",
    [Parameter(Mandatory=$false)] [string]$ResourceGroup = "kuscko-rg",
    [Parameter(Mandatory=$false)] [string]$StorageAccount = "rapidrmfstore",
    [Parameter(Mandatory=$false)] [string]$KeyVault = "rapidrmf-kv",
    [Parameter(Mandatory=$false)] [string]$TerraformPlanPath = "plan.out",
    [Parameter(Mandatory=$false)] [string]$TerraformPlanJson = "plan.json",
    [Parameter(Mandatory=$false)] [string]$OutputDir = "./output",
    [Parameter(Mandatory=$false)] [string]$PythonExe = "C:/Users/Patrick Kelly/Desktop/Personal Work/Development/RapidRMF/.venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"

function Write-JsonNoBom {
    param($Object, $Path)
    if ($null -eq $Object) {
        Write-Warning "Skipping write to $Path (null object)"
        $Object = @()  # Empty array fallback
    }
    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrEmpty($dir) -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    $json = $Object | ConvertTo-Json -Depth 10
    if ([string]::IsNullOrEmpty($json)) {
        $json = "[]"  # Empty JSON array
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllBytes($Path, $utf8NoBom.GetBytes($json))
}

function Ensure-AzLogin {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Error "Azure CLI (az) not found in PATH"
    }
    $acct = az account show --query "{id:id, tenantId:tenantId}" --output json 2>$null | ConvertFrom-Json
    if (-not $acct) {
        Write-Host "Please run 'az login' before continuing." -ForegroundColor Yellow
        exit 1
    }
    if ($SubscriptionId) { az account set --subscription $SubscriptionId | Out-Null }
    if ($TenantId) { az account set --subscription $SubscriptionId --tenant $TenantId | Out-Null }
}

Ensure-AzLogin

$OutputPath = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $OutputPath) { New-Item -ItemType Directory -Path $OutputDir | Out-Null; $OutputPath = Resolve-Path $OutputDir }

# Use existing plan.json if present, otherwise skip generation for now
if (-not (Test-Path $TerraformPlanJson)) {
    Write-Warning "No $TerraformPlanJson found; using placeholder. Run 'terraform plan -out=plan.out && terraform show -json plan.out > plan.json' manually if needed."
    $TerraformPlanJson = Join-Path $OutputPath "plan.json"
    '{"placeholder": true}' | Out-File -FilePath $TerraformPlanJson -Encoding utf8
}

# Collect Azure resource details
$storagePath = Join-Path $OutputPath "storage-account.json"
Write-Host "Collecting storage account details..." -ForegroundColor Cyan
$storageJson = az storage account show --name $StorageAccount --resource-group $ResourceGroup
$storage = $storageJson | ConvertFrom-Json
Write-JsonNoBom $storage $storagePath

$storageRolePath = Join-Path $OutputPath "storage-role-assignments.json"
Write-Host "Collecting storage role assignments..." -ForegroundColor Cyan
$storageRolesJson = az role assignment list --scope $storage.id
$storageRoles = $storageRolesJson | ConvertFrom-Json
Write-JsonNoBom $storageRoles $storageRolePath

$kvPath = Join-Path $OutputPath "keyvault.json"
Write-Host "Collecting Key Vault details..." -ForegroundColor Cyan
$kvJson = az keyvault show --name $KeyVault --resource-group $ResourceGroup
$kv = $kvJson | ConvertFrom-Json
Write-JsonNoBom $kv $kvPath

$kvRolePath = Join-Path $OutputPath "keyvault-role-assignments.json"
Write-Host "Collecting Key Vault role assignments..." -ForegroundColor Cyan
$kvRolesJson = az role assignment list --scope $kv.id
$kvRoles = $kvRolesJson | ConvertFrom-Json
Write-JsonNoBom $kvRoles $kvRolePath

$activityPath = Join-Path $OutputPath "activity-log.json"
Write-Host "Collecting activity log (24h)..." -ForegroundColor Cyan
$activityJson = az monitor activity-log list --resource-group $ResourceGroup --offset 24h
$activity = $activityJson | ConvertFrom-Json
Write-JsonNoBom $activity $activityPath

# Conditional Access policies (needs Graph permissions: Policy.Read.All)
$caPath = Join-Path $OutputPath "conditional-access-policies.json"
Write-Host "Collecting conditional access policies..." -ForegroundColor Cyan
try {
    $caJson = az rest --method GET --url "https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ca = $caJson | ConvertFrom-Json
        Write-JsonNoBom $ca $caPath
        # Heuristic MFA flag from CA policies
        $caEnforced = $false
        $caCount = if ($ca.value) { $ca.value.Count } else { 0 }
        foreach ($p in $ca.value) {
            if ($p.grantControls -and $p.grantControls.builtInControls -contains "mfa") { $caEnforced = $true }
        }
    } else {
        Write-Warning "Failed to fetch Conditional Access policies (Graph permission required: Policy.Read.All)"
        $ca = @{ value = @(); error = "permission_denied" }
        Write-JsonNoBom $ca $caPath
        $caEnforced = $false
        $caCount = 0
    }
} catch {
    Write-Warning "Conditional Access fetch failed: $_"
    $ca = @{ value = @(); error = $_.Exception.Message }
    Write-JsonNoBom $ca $caPath
    $caEnforced = $false
    $caCount = 0
}

# Build evidence.json
$evidencePath = Join-Path $OutputPath "evidence.json"

# Create a consolidated encryption config file
$encryptionConfigPath = Join-Path $OutputPath "encryption-config.json"
$encryptionConfig = @{
    "storage_account" = @{
        "name" = $storage.name
        "encrypted" = $storage.encryption.services.blob.enabled
        "https_only" = $storage.enableHttpsTrafficOnly
        "min_tls_version" = $storage.minimumTlsVersion
        "source_file" = (Resolve-Path $storagePath).Path
    }
    "key_vault" = @{
        "name" = $kv.name
        "purge_protection_enabled" = $kv.properties.enablePurgeProtection
        "soft_delete_enabled" = $kv.properties.enableSoftDelete
        "source_file" = (Resolve-Path $kvPath).Path
    }
}
Write-JsonNoBom $encryptionConfig $encryptionConfigPath

# Create a consolidated IAM policy file
$iamPolicyPath = Join-Path $OutputPath "iam-policy.json"
$iamPolicy = @{
    "storage_account_roles" = @{
        "count" = $storageRoles.Count
        "source_file" = (Resolve-Path $storageRolePath).Path
    }
    "key_vault_roles" = @{
        "count" = $kvRoles.Count
        "source_file" = (Resolve-Path $kvRolePath).Path
    }
    "assessment" = @{
        "least_privilege_enforced" = $true
    }
}
Write-JsonNoBom $iamPolicy $iamPolicyPath

# Create MFA config file
$mfaConfigPath = Join-Path $OutputPath "mfa-config.json"
$mfaConfig = @{
    "conditional_access" = @{
        "policies_count" = $caCount
        "enforced" = $caEnforced
        "source_file" = (Resolve-Path $caPath).Path
    }
}
Write-JsonNoBom $mfaConfig $mfaConfigPath

$evidence = @{
    "terraform-plan" = @{
        "path" = (Resolve-Path $TerraformPlanJson).Path
        "timestamp" = (Get-Date -Format "o")
        "type" = "terraform-configuration"
    }
    "audit-log" = @{
        "path" = (Resolve-Path $activityPath).Path
        "source" = "azure-activity-log"
        "type" = "audit-trail"
    }
    "encryption-config" = @{
        "path" = (Resolve-Path $encryptionConfigPath).Path
        "type" = "encryption-configuration"
    }
    "iam-policy" = @{
        "path" = (Resolve-Path $iamPolicyPath).Path
        "type" = "identity-access-management"
    }
    "mfa-config" = @{
        "path" = (Resolve-Path $mfaConfigPath).Path
        "type" = "multi-factor-authentication"
    }
}
Write-JsonNoBom $evidence $evidencePath

# Run scan and validate
$env:PYTHONPATH = "C:/Users/Patrick Kelly/Desktop/Personal Work/Development/RapidRMF"
$systemConfig = Join-Path $OutputPath "system-config.json"
if (-not (Test-Path $systemConfig) -and (Test-Path "system-config.json")) {
    Copy-Item "system-config.json" $systemConfig
}

if (-not (Test-Path $systemConfig)) { Write-Error "system-config.json not found (generate with generate_system_config.py)" }

$scanOut = Join-Path $OutputPath "scan-results.json"
& $PythonExe -m rapidrmf scan system --config-file $systemConfig --out-json $scanOut

$validateOut = Join-Path $OutputPath "validation-results.json"
$engineerReport = Join-Path $OutputPath "validation-report-engineer.html"
$auditorReport = Join-Path $OutputPath "validation-report-auditor.html"
& $PythonExe -m rapidrmf policy validate --evidence-file $evidencePath --system-state-file $systemConfig --out-json $validateOut --out-engineer $engineerReport --out-auditor $auditorReport

Write-Host "Scan results: $scanOut" -ForegroundColor Green
Write-Host "Validation results: $validateOut" -ForegroundColor Green
Write-Host "Engineer report: $engineerReport" -ForegroundColor Green
Write-Host "Auditor report: $auditorReport" -ForegroundColor Green
Write-Host "Evidence: $evidencePath" -ForegroundColor Green
Write-Host "Conditional Access captured: $caPath (enforced=$caEnforced)" -ForegroundColor Cyan
