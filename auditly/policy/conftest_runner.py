"""Conftest runner for policy validation results."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List


@dataclass
class ConftestResult:
    """Result of a conftest policy validation run."""

    target: str
    failures: int
    warnings: int
    passes: int
    raw: Any


def conftest_available() -> bool:
    """Check if conftest binary is available in PATH."""
    return shutil.which("conftest") is not None


def run_conftest(
    target_dir: Path | str, policy_dir: Path | str | None = None
) -> List[ConftestResult]:
    """Run conftest policy validation and return results."""
    if not conftest_available():
        raise RuntimeError("conftest binary not found in PATH")

    cmd = ["conftest", "test", "--output", "json"]
    if policy_dir:
        cmd += ["-p", str(policy_dir)]
    cmd += [str(target_dir)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout.strip()
    if proc.returncode not in (0, 1):
        # 0 = pass, 1 = some failures; other codes are errors
        raise RuntimeError(f"conftest error: {proc.stderr}")
    try:
        data = json.loads(out) if out else []
    except json.JSONDecodeError:
        data = []

    results: List[ConftestResult] = []
    for entry in data:
        # Each entry corresponds to a file/test target
        warnings = sum(1 for r in entry.get("results", []) if r.get("severity") == "warning")
        failures = sum(1 for r in entry.get("failures", [])) + sum(
            1 for r in entry.get("results", []) if r.get("fail") is True
        )
        passes = sum(1 for r in entry.get("successes", []))
        results.append(
            ConftestResult(
                target=entry.get("filename") or entry.get("filepath", "unknown"),
                failures=failures,
                warnings=warnings,
                passes=passes,
                raw=entry,
            )
        )
    return results
