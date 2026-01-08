# Comprehensive Validation Testing

This directory contains comprehensive validation testing infrastructure for RapidRMF.

## Files

### `test_evidence_data.json`
Complete reference data showing all evidence types and their mappings to control families. This file documents:
- 60+ evidence artifact types
- Evidence categorized by control domain (Access Control, Audit, Configuration Management, etc.)
- Mappings showing which evidence types satisfy which control families
- Example controls for each evidence type

**Purpose**: Reference documentation for evidence patterns and validation rules

### `comprehensive_validation_test.py`
End-to-end validation test that validates ALL controls across ALL catalogs with comprehensive evidence coverage.

**Features**:
- Loads all 8 OSCAL catalogs/profiles (NIST 800-53 Rev5, FedRAMP baselines, NIST 800-53B baselines)
- Validates 543 unique controls
- Tests all 20 control families
- Uses comprehensive evidence set covering all 60+ evidence types
- Generates detailed HTML and JSON reports

**Usage**:
```powershell
$env:PYTHONPATH = "."
python tests/comprehensive_validation_test.py
```

## Test Results

The comprehensive test validates:
- **543 unique controls** across all catalogs
- **20 control families**: AC, AT, AU, CA, CM, CP, IA, IR, MA, MP, PE, PL, PM, PS, PT, RA, SA, SC, SI, SR
- **8 OSCAL catalogs/profiles**:
  - NIST 800-53 Rev5: 324 controls
  - NIST 800-53B Low: 149 controls
  - NIST 800-53B Moderate: 287 controls
  - NIST 800-53B High: 370 controls
  - FedRAMP Low: 156 controls
  - FedRAMP Moderate: 323 controls
  - FedRAMP High: 410 controls
  - FedRAMP LI-SaaS: 156 controls

### Report Output

Reports are generated in `validation_reports/` directory with timestamp:
- **HTML Report**: Interactive report with expandable control details, family summaries, and statistics
- **JSON Report**: Machine-readable report for programmatic analysis

## Evidence Coverage

The test uses a comprehensive evidence set covering all domains:

### Configuration Management (9 evidence types)
- terraform-plan, ansible-playbook, cloudformation-template
- github-workflow, gitlab-pipeline, argo-workflow
- change-request, conftest-result, opa-result

### Access Control (4 evidence types)
- iam-config, rbac-config, iam-policy, audit-log

### Audit & Accountability (5 evidence types)
- logging-config, cloudtrail-config, siem-config
- log-sample, log-analysis

### Awareness & Training (3 evidence types)
- training-records, training-plan, security-awareness-evidence

### Contingency Planning (3 evidence types)
- backup-config, disaster-recovery-plan, contingency-plan

### Identification & Authentication (2 evidence types)
- mfa-config, authentication-config

### Incident Response (3 evidence types)
- incident-response-plan, runbook, alert-config

### Maintenance (3 evidence types)
- maintenance-log, patch-management-config, maintenance-procedure

### Media Protection (2 evidence types)
- media-protection-policy, data-sanitization-procedure

### Physical Protection (3 evidence types)
- physical-security-policy, datacenter-attestation, facility-documentation

### Planning (3 evidence types)
- security-plan, system-security-plan, risk-assessment

### Personnel Security (3 evidence types)
- personnel-screening, background-check-policy, termination-procedure

### Risk Assessment (2 evidence types)
- vulnerability-scan, penetration-test

### Security Assessment (3 evidence types)
- assessment-report, security-assessment, audit-report

### System & Communications Protection (8 evidence types)
- encryption-config, network-config, network-diagram
- security-group-config, tls-config, certificate
- kms-config, key-rotation-policy

### System & Information Integrity (2 evidence types)
- ids-config, malware-protection-config

### System & Services Acquisition (3 evidence types)
- sdlc-documentation, acquisition-policy, supply-chain-risk-assessment

### Supply Chain (2 evidence types)
- vendor-assessment, sbom

### Program Management (3 evidence types)
- program-management-plan, governance-documentation, policy-documentation

### Privacy (3 evidence types)
- privacy-policy, pii-inventory, data-flow-diagram

## Validation Results

With comprehensive evidence coverage, the test achieves:
- 100% pass rate: all 543 controls validated successfully
- 20/20 families: complete coverage across all control families
- Pattern-based: uses family patterns plus specific control overrides
- Scalable: no code bloat; declarative validation rules

## Viewing Results

### HTML Report
- Open `validation_reports/validation_report_<timestamp>.html` in any browser
- Interactive interface with:
  - Overall statistics dashboard
  - Catalog statistics table
  - Family-by-family breakdown with expandable control details
  - Evidence types used per control
  - Validation messages and suggestions

### JSON Report
- Machine-readable format at `validation_reports/validation_report_<timestamp>.json`
- Complete test results including:
  - Metadata (timestamp, config, control counts)
  - Per-control results with evidence and validation details
  - Statistics by status and family
  - Catalog statistics

## Integration

This comprehensive test serves as:
1. **Validation Suite**: Ensure all controls can be validated
2. **Coverage Analysis**: Verify family patterns cover all controls
3. **Documentation**: Show evidence patterns and requirements
4. **Regression Testing**: Catch validation logic changes
5. **Demonstration**: Showcase RapidRMF capabilities

## Next Steps

To extend the validation testing:
1. Add specific control overrides in `rapidrmf/validators.py`
2. Extend family patterns with additional evidence types
3. Create targeted tests for specific compliance scenarios
4. Implement live system state validation tests
5. Add CI/CD integration for automated validation
