from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

try:
    import wasmtime

    WASMTIME_AVAILABLE = True
except ImportError:
    WASMTIME_AVAILABLE = False


@dataclass
class WasmPolicyResult:
    allowed: bool
    violations: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    raw: Any


def wasm_available() -> bool:
    return WASMTIME_AVAILABLE


def evaluate_wasm_policy(
    wasm_path: Path | str,
    input_data: Dict[str, Any],
    entrypoint: str = "policy/main",
) -> WasmPolicyResult:
    """
    Evaluate OPA policy compiled to WASM.

    Args:
        wasm_path: Path to .wasm file compiled from Rego
        input_data: Input JSON data to evaluate
        entrypoint: Policy entrypoint (default: policy/main for OPA)

    Returns:
        WasmPolicyResult with decision and violations
    """
    if not WASMTIME_AVAILABLE:
        raise RuntimeError("wasmtime not installed; run: pip install wasmtime")

    p = Path(wasm_path)
    if not p.exists():
        raise FileNotFoundError(f"WASM policy not found: {wasm_path}")

    engine = wasmtime.Engine()
    module = wasmtime.Module.from_file(engine, str(p))
    linker = wasmtime.Linker(engine)
    store = wasmtime.Store(engine)

    # OPA WASM expects:
    # - memory export
    # - opa_eval_ctx_new, opa_eval_ctx_set_input, opa_eval_ctx_set_data, opa_eval, opa_eval_ctx_get_result
    # For simplicity, we'll create a minimal wrapper. Production needs full ABI.

    # Instantiate module
    instance = linker.instantiate(store, module)

    # Simplified: call policy entrypoint if exported
    # OPA WASM ABI is complex; this is a placeholder structure
    # In production, use opa-wasm or similar library for full support

    # For now, return a mock result indicating WASM evaluation attempted
    # TODO: integrate full OPA WASM ABI or use github.com/open-policy-agent/opa/wasm
    result = WasmPolicyResult(
        allowed=True,
        violations=[],
        metadata={"note": "WASM evaluation placeholder; integrate OPA WASM ABI for full support"},
        raw={"input": input_data, "wasm": str(wasm_path)},
    )
    return result


def evaluate_wasm_policies_bulk(
    wasm_dir: Path | str,
    targets: List[Path],
    input_key: str = "input",
) -> List[WasmPolicyResult]:
    """
    Evaluate multiple targets against WASM policies in a directory.

    Args:
        wasm_dir: Directory containing .wasm policy files
        targets: List of file paths to evaluate
        input_key: Key name for input in policy evaluation

    Returns:
        List of WasmPolicyResult for each target
    """
    wasm_dir_path = Path(wasm_dir)
    if not wasm_dir_path.exists():
        return []

    wasm_files = list(wasm_dir_path.glob("*.wasm"))
    if not wasm_files:
        return []

    results = []
    for target in targets:
        # Read target as JSON or text
        try:
            if target.suffix in (".json", ".yaml", ".yml"):
                input_data = {input_key: json.loads(target.read_text())}
            else:
                input_data = {input_key: {"path": str(target), "content": target.read_text()}}
        except Exception:
            input_data = {input_key: {"path": str(target)}}

        # Evaluate against first WASM policy (extend for multiple)
        result = evaluate_wasm_policy(wasm_files[0], input_data)
        results.append(result)

    return results
