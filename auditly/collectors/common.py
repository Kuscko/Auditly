"""Common utilities and helpers for collectors."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def finalize_evidence(
    data: dict[str, Any],
    *,
    collector: str,
    account_id: str | None = None,
    region: str | None = None,
    version: str = "1.0.0",
) -> dict[str, Any]:
    """Attach standard metadata and sha256 to evidence payload.

    This helper ensures consistent metadata shape and hashing across collectors.
    """
    evidence = dict(data)
    evidence["metadata"] = {
        "collected_at": datetime.utcnow().isoformat(),
        "account_id": account_id,
        "region": region,
        "collector": collector,
        "version": version,
    }

    evidence_json = json.dumps(evidence, sort_keys=True, default=str)
    evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()
    return evidence
