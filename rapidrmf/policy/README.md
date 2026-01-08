# Policy Engines

Policy enforcement supports Rego via Conftest and OPA WASM for offline or air-gapped evaluation.

## Conftest (Rego) in CI/CD
```powershell
python -m rapidrmf policy conftest --target path/to/iac --out-json conftest-results.json
```
- Use for inline IaC checks in pipelines
- Output JSON can be stored as evidence and mapped to controls

## OPA WASM (offline)
```powershell
# Compile Rego to WASM
opa build -t wasm -e policy/main policy/
tar -xzf policy.tar.gz policy.wasm

# Evaluate offline
python -m rapidrmf policy wasm --wasm-file policy.wasm --input input.json --out-json wasm-results.json
```
- Works without the opa binary at runtime
- Ideal for air-gapped enclaves

## Best practices
- Keep policy bundles versioned with the IaC they guard
- Export JSON outputs for auditors; include commit hashes in metadata
- Use the same Rego packages for Conftest and WASM to avoid drift
