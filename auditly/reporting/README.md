# Reporting

Reporting produces dual-view readiness outputs for engineers and auditors.

## Generate a report
```powershell
python -m auditly report readiness --config config.yaml --env edge --out report.html
```
Outputs:
- HTML report with engineer view (guidance, remediation) and auditor view (evidence paths, checksums, timestamps)
- JSON payloads for automation in [reporting/validation_reports.py](validation_reports.py)

## What is shown
- Control coverage across catalogs (NIST 800-53, FedRAMP, STIG, Zero Trust)
- Validation results (pass, fail, insufficient)
- Scanner findings (IAM, encryption, backup)
- Waiver status with expiry warnings
- Evidence manifest references and hashes

## Tips
- Keep evidence and mapping.yaml in sync before generating reports
- Store report.html with the evidence manifest for a complete audit trail
- Use separate reports per enclave to avoid mixing evidence
