from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .evidence import EvidenceManifest


@dataclass
class MappingRule:
    """Maps evidence attributes to control IDs."""

    control_ids: List[str]
    evidence_kind: str
    required_metadata: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


@dataclass
class ControlMapping:
    """Collection of mapping rules."""

    rules: List[MappingRule]

    @staticmethod
    def from_yaml(path: Path | str) -> ControlMapping:
        p = Path(path)
        if not p.exists():
            return ControlMapping(rules=[])
        data = yaml.safe_load(p.read_text())
        rules = []
        for item in data.get("mappings", []):
            rules.append(
                MappingRule(
                    control_ids=item.get("control_ids", []),
                    evidence_kind=item["evidence_kind"],
                    required_metadata=item.get("required_metadata"),
                    description=item.get("description"),
                )
            )
        return ControlMapping(rules=rules)

    def save(self, path: Path | str) -> None:
        p = Path(path)
        data = {
            "mappings": [
                {
                    "control_ids": r.control_ids,
                    "evidence_kind": r.evidence_kind,
                    "required_metadata": r.required_metadata,
                    "description": r.description,
                }
                for r in self.rules
            ]
        }
        p.write_text(yaml.safe_dump(data, sort_keys=False))


def match_evidence_to_controls(
    manifests: List[EvidenceManifest],
    mapping: ControlMapping,
) -> Dict[str, List[str]]:
    """
    Match evidence artifacts to controls based on mapping rules.

    Args:
        manifests: List of evidence manifests
        mapping: Control mapping rules

    Returns:
        Dict mapping control_id -> list of evidence keys
    """
    control_evidence: Dict[str, List[str]] = {}

    for manifest in manifests:
        for artifact in manifest.artifacts:
            kind = artifact.metadata.get("kind") if isinstance(artifact.metadata, dict) else None
            if not kind:
                continue

            for rule in mapping.rules:
                if rule.evidence_kind != kind:
                    continue

                # Check required metadata if specified
                if rule.required_metadata:
                    match = all(
                        artifact.metadata.get(k) == v for k, v in rule.required_metadata.items()
                    )
                    if not match:
                        continue

                # Add this artifact to all mapped controls
                for control_id in rule.control_ids:
                    if control_id not in control_evidence:
                        control_evidence[control_id] = []
                    control_evidence[control_id].append(artifact.key)

    return control_evidence


def compute_control_coverage(
    all_control_ids: List[str],
    control_evidence: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Compute control coverage statistics.

    Args:
        all_control_ids: All control IDs from catalogs
        control_evidence: Mapping of control_id -> evidence keys

    Returns:
        Coverage summary with counts and percentages
    """
    covered_ids = set(control_evidence.keys())
    all_ids_set = set(all_control_ids)

    covered = len(covered_ids & all_ids_set)
    total = len(all_ids_set)
    uncovered = total - covered
    coverage_pct = (covered / total * 100) if total > 0 else 0

    return {
        "total": total,
        "covered": covered,
        "uncovered": uncovered,
        "coverage_percent": round(coverage_pct, 1),
        "covered_ids": sorted(covered_ids & all_ids_set),
        "uncovered_ids": sorted(all_ids_set - covered_ids),
        "control_evidence": control_evidence,
    }
