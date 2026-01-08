# Tests

This directory contains validation and integration suites for RapidRMF.

## Suites
- Comprehensive validation: [README_VALIDATION.md](README_VALIDATION.md) and [comprehensive_validation_test.py](comprehensive_validation_test.py)
- Smoke/integration: [smoke_test.py](smoke_test.py)
- Evidence mapping verification: [verify_evidence_mappings.py](verify_evidence_mappings.py)
- Azure validation pipeline: [terraform/azure/README.md](terraform/azure/README.md)

## Running key tests
```powershell
# Comprehensive validation (loads all catalogs and evidence types)
$env:PYTHONPATH = "."
python tests/comprehensive_validation_test.py

# Smoke suite
$env:PYTHONPATH = "."
python tests/smoke_test.py
```

## Outputs
- Validation reports: `validation_reports/validation_report_<timestamp>.html/json`
- Azure pipeline artifacts: `tests/terraform/azure/output/`

## Tips
- Set PYTHONPATH to repo root so modules resolve
- Keep catalogs and mapping.yaml present when running validation tests
- For Azure pipeline, authenticate with `az login` before running Terraform or collectors
