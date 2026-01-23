"""Validation logic, result types, and compliance requirements for auditly."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum

from .db import get_sync_session, init_db_sync
from .db.models import Evidence as DBEvidence
from .evidence_lifecycle import EvidenceLifecycleManager
from .performance import incremental_validator, performance_metrics, validation_cache


class ValidationStatus(Enum):
    """Validation status for compliance checks."""

    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of a compliance validation for a control."""

    control_id: str
    status: ValidationStatus
    message: str
    evidence_keys: list[str]
    metadata: dict[str, object]
    remediation: str | None = None


@dataclass
class ControlRequirement:
    """Define what evidence types satisfy a control."""

    control_id: str
    required_any: list[str]  # At least one of these evidence types
    required_all: list[str]  # All of these evidence types
    description: str
    remediation: str


@dataclass
class FamilyPattern:
    """Define evidence patterns for an entire control family."""

    family: str
    required_any: list[str]
    required_all: list[str]
    description_template: str
    remediation_template: str


# Control family patterns (applies to all controls in family unless overridden)
FAMILY_PATTERNS = {
    "AC": FamilyPattern(
        family="AC",
        required_any=["terraform-plan", "iam-config", "rbac-config", "iam-policy"],
        required_all=["audit-log"],
        description_template="Access Control",
        remediation_template="Provide access control configuration and audit logs",
    ),
    "AU": FamilyPattern(
        family="AU",
        required_any=["logging-config", "cloudtrail-config", "audit-log", "siem-config"],
        required_all=[],
        description_template="Audit and Accountability",
        remediation_template="Provide audit logging configuration or logs",
    ),
    "AT": FamilyPattern(
        family="AT",
        required_any=["training-records", "training-plan", "security-awareness-evidence"],
        required_all=[],
        description_template="Awareness and Training",
        remediation_template="Provide training records or security awareness documentation",
    ),
    "CM": FamilyPattern(
        family="CM",
        required_any=[
            "terraform-plan",
            "ansible-playbook",
            "cloudformation-template",
            "github-workflow",
        ],
        required_all=["change-request"],
        description_template="Configuration Management",
        remediation_template="Provide IaC configuration and change management documentation",
    ),
    "CP": FamilyPattern(
        family="CP",
        required_any=["backup-config", "disaster-recovery-plan", "contingency-plan"],
        required_all=[],
        description_template="Contingency Planning",
        remediation_template="Provide backup configuration or contingency planning documentation",
    ),
    "IA": FamilyPattern(
        family="IA",
        required_any=["mfa-config", "authentication-config", "iam-config"],
        required_all=[],
        description_template="Identification and Authentication",
        remediation_template="Provide authentication and identity management configuration",
    ),
    "IR": FamilyPattern(
        family="IR",
        required_any=["incident-response-plan", "runbook", "alert-config"],
        required_all=[],
        description_template="Incident Response",
        remediation_template="Provide incident response procedures or alerting configuration",
    ),
    "MA": FamilyPattern(
        family="MA",
        required_any=["maintenance-log", "patch-management-config", "maintenance-procedure"],
        required_all=[],
        description_template="Maintenance",
        remediation_template="Provide maintenance logs or patch management configuration",
    ),
    "MP": FamilyPattern(
        family="MP",
        required_any=["media-protection-policy", "data-sanitization-procedure"],
        required_all=[],
        description_template="Media Protection",
        remediation_template="Provide media protection policies or procedures",
    ),
    "PE": FamilyPattern(
        family="PE",
        required_any=[
            "physical-security-policy",
            "datacenter-attestation",
            "facility-documentation",
        ],
        required_all=[],
        description_template="Physical and Environmental Protection",
        remediation_template="Provide physical security documentation or datacenter attestations",
    ),
    "PL": FamilyPattern(
        family="PL",
        required_any=["security-plan", "system-security-plan", "risk-assessment"],
        required_all=[],
        description_template="Planning",
        remediation_template="Provide security planning documentation",
    ),
    "PS": FamilyPattern(
        family="PS",
        required_any=["personnel-screening", "background-check-policy", "termination-procedure"],
        required_all=[],
        description_template="Personnel Security",
        remediation_template="Provide personnel security policies or procedures",
    ),
    "RA": FamilyPattern(
        family="RA",
        required_any=["risk-assessment", "vulnerability-scan", "penetration-test"],
        required_all=[],
        description_template="Risk Assessment",
        remediation_template="Provide risk assessment or vulnerability scanning results",
    ),
    "CA": FamilyPattern(
        family="CA",
        required_any=["assessment-report", "security-assessment", "audit-report"],
        required_all=[],
        description_template="Security Assessment and Authorization",
        remediation_template="Provide security assessment documentation",
    ),
    "SC": FamilyPattern(
        family="SC",
        required_any=["terraform-plan", "encryption-config", "network-config", "conftest-result"],
        required_all=[],
        description_template="System and Communications Protection",
        remediation_template="Provide system protection configuration or policy validation",
    ),
    "SI": FamilyPattern(
        family="SI",
        required_any=["vulnerability-scan", "ids-config", "malware-protection-config"],
        required_all=[],
        description_template="System and Information Integrity",
        remediation_template="Provide vulnerability scanning or integrity monitoring configuration",
    ),
    "SA": FamilyPattern(
        family="SA",
        required_any=["sdlc-documentation", "acquisition-policy", "supply-chain-risk-assessment"],
        required_all=[],
        description_template="System and Services Acquisition",
        remediation_template="Provide acquisition or development lifecycle documentation",
    ),
    "SR": FamilyPattern(
        family="SR",
        required_any=["supply-chain-risk-assessment", "vendor-assessment", "sbom"],
        required_all=[],
        description_template="Supply Chain Risk Management",
        remediation_template="Provide supply chain risk documentation or SBOM",
    ),
    "PM": FamilyPattern(
        family="PM",
        required_any=[
            "program-management-plan",
            "governance-documentation",
            "policy-documentation",
        ],
        required_all=[],
        description_template="Program Management",
        remediation_template="Provide program management or governance documentation",
    ),
    "PT": FamilyPattern(
        family="PT",
        required_any=["privacy-policy", "pii-inventory", "data-flow-diagram"],
        required_all=[],
        description_template="PII Processing and Transparency",
        remediation_template="Provide privacy policies or PII processing documentation",
    ),
}


# Specific control overrides (higher priority than family patterns)
# Specific control overrides (higher priority than family patterns)
CONTROL_REQUIREMENTS = {
    # Configuration Management - specific requirements
    "cm-2": ControlRequirement(
        control_id="cm-2",
        required_any=["terraform-plan", "ansible-playbook", "cloudformation-template"],
        required_all=["change-request"],
        description="Baseline Configuration",
        remediation="Provide IaC artifact and change approval",
    ),
    "cm-3": ControlRequirement(
        control_id="cm-3",
        required_any=["github-workflow", "gitlab-pipeline", "argo-workflow"],
        required_all=["change-request"],
        description="Configuration Change Control",
        remediation="Provide CI/CD pipeline evidence and change approval",
    ),
    "cm-6": ControlRequirement(
        control_id="cm-6",
        required_any=["terraform-plan", "ansible-playbook", "conftest-result"],
        required_all=[],
        description="Configuration Settings",
        remediation="Provide configuration baseline via IaC or policy",
    ),
    "cm-7": ControlRequirement(
        control_id="cm-7",
        required_any=["conftest-result", "opa-result"],
        required_all=[],
        description="Least Functionality",
        remediation="Provide policy validation results",
    ),
    # Access Control - specific requirements
    "ac-2": ControlRequirement(
        control_id="ac-2",
        required_any=["terraform-plan", "iam-config"],
        required_all=["audit-log"],
        description="Account Management",
        remediation="Provide IAM configuration and audit logs",
    ),
    "ac-3": ControlRequirement(
        control_id="ac-3",
        required_any=["iam-policy", "rbac-config"],
        required_all=[],
        description="Access Enforcement",
        remediation="Provide access control policy configuration",
    ),
    # System and Communications Protection - specific requirements
    "sc-7": ControlRequirement(
        control_id="sc-7",
        required_any=["terraform-plan", "network-diagram", "security-group-config"],
        required_all=[],
        description="Boundary Protection",
        remediation="Provide network segmentation evidence",
    ),
    "sc-8": ControlRequirement(
        control_id="sc-8",
        required_any=["tls-config", "certificate"],
        required_all=[],
        description="Transmission Confidentiality",
        remediation="Provide TLS/encryption configuration",
    ),
    "sc-12": ControlRequirement(
        control_id="sc-12",
        required_any=["kms-config", "key-rotation-policy"],
        required_all=[],
        description="Cryptographic Key Management",
        remediation="Provide key management service configuration",
    ),
    "sc-13": ControlRequirement(
        control_id="sc-13",
        required_any=["encryption-config", "conftest-result"],
        required_all=[],
        description="Cryptographic Protection",
        remediation="Provide encryption configuration or policy validation",
    ),
    "sc-28": ControlRequirement(
        control_id="sc-28",
        required_any=["terraform-plan", "encryption-config"],
        required_all=[],
        description="Protection of Information at Rest",
        remediation="Provide storage encryption configuration",
    ),
    # Audit and Accountability - specific requirements
    "au-2": ControlRequirement(
        control_id="au-2",
        required_any=["logging-config", "cloudtrail-config", "audit-log"],
        required_all=[],
        description="Audit Events",
        remediation="Provide audit logging configuration or audit log samples",
    ),
    "au-3": ControlRequirement(
        control_id="au-3",
        required_any=["audit-log", "log-sample"],
        required_all=[],
        description="Content of Audit Records",
        remediation="Provide sample audit logs",
    ),
    "au-6": ControlRequirement(
        control_id="au-6",
        required_any=["siem-config", "log-analysis"],
        required_all=[],
        description="Audit Review, Analysis, and Reporting",
        remediation="Provide log monitoring/analysis configuration",
    ),
}


def get_control_requirement(control_id: str) -> ControlRequirement | None:
    """
    Get control requirement, falling back to family pattern if no specific requirement exists.

    Args:
        control_id: Control ID (e.g., "AC-2" or "ac-2")

    Returns:
        ControlRequirement or None
    """
    control_lower = control_id.lower()

    # Check for specific requirement first
    if control_lower in CONTROL_REQUIREMENTS:
        return CONTROL_REQUIREMENTS[control_lower]

    # Fall back to family pattern
    family = control_id.upper().split("-")[0] if "-" in control_id else ""
    if family in FAMILY_PATTERNS:
        pattern = FAMILY_PATTERNS[family]
        return ControlRequirement(
            control_id=control_lower,
            required_any=pattern.required_any,
            required_all=pattern.required_all,
            description=f"{pattern.description_template} ({control_id.upper()})",
            remediation=pattern.remediation_template,
        )

    return None


class ComplianceValidator:
    """Simple pattern-based validator using evidence requirements."""

    def __init__(self, requirement: ControlRequirement):
        """Initialize a pattern-based compliance validator with a requirement."""
        self.requirement = requirement

    def validate(
        self, evidence_keys: set[str], evidence_details: dict[str, object]
    ) -> ValidationResult:
        """
        Validate that evidence satisfies the control requirement.

        Args:
            evidence_keys: Set of evidence type keys present
            evidence_details: Full evidence dict with paths/metadata

        Returns:
            ValidationResult
        """
        req = self.requirement

        # Normalize control IDs (handle both uppercase and lowercase)
        control_id = req.control_id.upper()

        # Check required_all
        missing_required = [k for k in req.required_all if k not in evidence_keys]
        matched_required_all = [k for k in req.required_all if k in evidence_keys]

        if missing_required:
            return ValidationResult(
                control_id=control_id,
                status=ValidationStatus.INSUFFICIENT_EVIDENCE,
                message=f"Missing required evidence: {', '.join(missing_required)}",
                evidence_keys=list(evidence_keys),
                metadata={
                    "missing": missing_required,
                    "matched_required_all": matched_required_all,
                    "required_all": req.required_all,
                    "required_any": req.required_any,
                },
                remediation=req.remediation,
            )

        # Check required_any
        matched_required_any = [k for k in req.required_any if k in evidence_keys]
        has_any = len(matched_required_any) > 0 if req.required_any else True

        if not has_any:
            return ValidationResult(
                control_id=control_id,
                status=ValidationStatus.INSUFFICIENT_EVIDENCE,
                message=f"Need at least one of: {', '.join(req.required_any)}",
                evidence_keys=list(evidence_keys),
                metadata={
                    "options": req.required_any,
                    "required_all": req.required_all,
                    "required_any": req.required_any,
                },
                remediation=req.remediation,
            )

        # All requirements satisfied - include evidence locations
        matched = [k for k in evidence_keys if k in req.required_any or k in req.required_all]
        evidence_locations = {}
        for key in matched:
            if key in evidence_details:
                ev = evidence_details[key]
                if isinstance(ev, dict):
                    evidence_locations[key] = {
                        "path": ev.get("path", "(inline)"),
                        "timestamp": ev.get("timestamp"),
                        "source": ev.get("source"),
                    }
                else:
                    evidence_locations[key] = {"value": str(ev)[:100]}

        return ValidationResult(
            control_id=control_id,
            status=ValidationStatus.PASS,
            message=f"{req.description} - Evidence provided",
            evidence_keys=matched,
            metadata={
                "satisfied": True,
                "matched_required_any": matched_required_any,
                "matched_required_all": matched_required_all,
                "required_any": req.required_any,
                "required_all": req.required_all,
                "evidence_locations": evidence_locations,
            },
        )


def validate_controls(
    control_ids: list[str],
    evidence: dict[str, object],
    system_state: dict[str, object] | None = None,
    database_url: str | None = None,
    user_id: str = "validator",
    *,
    previous_evidence: dict[str, object] | None = None,
    use_cache: bool = True,
    cache_ttl: int | None = None,
    incremental: bool = True,
) -> dict[str, ValidationResult]:
    """
    Validate multiple controls against available evidence.

    Args:
        control_ids: List of control IDs to validate
        evidence: Evidence dict (keys are evidence types)
        system_state: Optional live system state (unused in simple validator)
        database_url: Optional database URL for access logging
        user_id: User/system identifier for access logs

    Returns:
        Dict of control_id -> ValidationResult
    """
    evidence_keys = set(evidence.keys())
    results: dict[str, ValidationResult] = {}

    # Lazy import to avoid circular import with validators_advanced
    from .validators_advanced import custom_validators, dependency_graph

    # Optionally register evidence dependencies for incremental runs
    if incremental:
        for cid in control_ids:
            req = get_control_requirement(cid)
            if req:
                deps = list({*req.required_any, *req.required_all})
                incremental_validator.register_evidence_types(cid, deps)

    # Determine which controls actually need validation
    controls_to_validate = control_ids
    if incremental and previous_evidence is not None:
        controls_to_validate = incremental_validator.get_controls_needing_validation(
            control_ids,
            current_evidence=evidence,
            previous_evidence=previous_evidence,
        )
        if controls_to_validate:
            performance_metrics.record_incremental_validation()

    # Respect dependency ordering to avoid blocked validations
    ordered_controls = dependency_graph.get_validation_order(controls_to_validate)

    # Log evidence access if database available
    if database_url:
        try:
            init_db_sync(database_url)
            session = get_sync_session()
            lifecycle_mgr = EvidenceLifecycleManager(session)

            # Log access for each evidence artifact used in validation
            for evidence_type, evidence_data in evidence.items():
                if isinstance(evidence_data, dict) and "sha256" in evidence_data:
                    # Find evidence by hash
                    evidence_records = (
                        session.query(DBEvidence).filter_by(sha256=evidence_data["sha256"]).all()
                    )

                    for ev in evidence_records:
                        lifecycle_mgr.log_evidence_access(
                            evidence_id=ev.id,
                            user_id=user_id,
                            action="validate",
                            attributes={
                                "control_ids": control_ids,
                                "evidence_type": evidence_type,
                            },
                        )

            session.commit()
            session.close()
        except Exception:
            # Silently continue if access logging fails
            pass

    for cid in ordered_controls:
        cid_upper = cid.upper()
        req = get_control_requirement(cid)

        # Cache key based on control + evidence hash
        cache_key = None
        if use_cache:
            evidence_hash = hashlib.sha256(
                json.dumps(evidence, sort_keys=True, default=str).encode()
            ).hexdigest()
            cache_key = validation_cache.make_key("control", cid_upper, evidence_hash)
            cached = validation_cache.get(cache_key)
            if cached is not None:
                results[cid_upper] = cached
                performance_metrics.record_validation(duration=0.0, cached=True)
                continue

        # Check dependency blockers
        can_validate, blockers = dependency_graph.validate_with_dependencies(
            cid_upper,
            validation_results=results,
            strict=False,
        )
        if not can_validate:
            results[cid_upper] = ValidationResult(
                control_id=cid_upper,
                status=ValidationStatus.INSUFFICIENT_EVIDENCE,
                message=f"Blocked by prerequisites: {', '.join(blockers)}",
                evidence_keys=list(evidence_keys),
                metadata={"blockers": blockers},
            )
            if cache_key:
                validation_cache.set(cache_key, results[cid_upper], ttl=cache_ttl)
            continue

        if req:
            validator = ComplianceValidator(req)
            start = time.perf_counter()

            # Custom validators can override or short-circuit
            custom_result = custom_validators.validate(cid_upper, evidence, system_state)
            if custom_result:
                results[cid_upper] = custom_result
            else:
                results[cid_upper] = validator.validate(evidence_keys, evidence)

            duration = time.perf_counter() - start
            performance_metrics.record_validation(duration=duration, cached=False)
            if cache_key:
                validation_cache.set(cache_key, results[cid_upper], ttl=cache_ttl)
        else:
            # No validator or family pattern - mark as unknown
            results[cid_upper] = ValidationResult(
                control_id=cid_upper,
                status=ValidationStatus.UNKNOWN,
                message="No validation rule or family pattern defined for this control",
                evidence_keys=[],
                metadata={"available_evidence": list(evidence_keys)},
                remediation="Define validation requirements in validators.py or add family pattern",
            )
            if cache_key:
                validation_cache.set(cache_key, results[cid_upper], ttl=cache_ttl)

    # Snapshot evidence for incremental comparisons next run
    if incremental and previous_evidence is not None:
        incremental_validator.snapshot_evidence(evidence)

    return results
