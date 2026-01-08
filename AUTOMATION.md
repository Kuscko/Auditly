# Automation Overview

RapidRMF automates evidence collection, validation, scanning, and reporting to reduce ATO toil by 80-90%.

## Automation layers
- Evidence collection: Terraform, CI/CD (GitHub/GitLab/Argo), Azure
- Policy enforcement: Conftest and OPA WASM
- Control validation: 69 validators across 20 families
- System scanning: IAM, encryption, backup scanners
- Exception tracking: Waivers with auto-expiry

See the module readmes for details:
- [rapidrmf/README.md](rapidrmf/README.md)
- [rapidrmf/collectors/README.md](rapidrmf/collectors/README.md)
- [rapidrmf/policy/README.md](rapidrmf/policy/README.md)
- [rapidrmf/reporting/README.md](rapidrmf/reporting/README.md)
