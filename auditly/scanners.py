from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ScannerType(Enum):
    IAM = "iam"
    ENCRYPTION = "encryption"
    BACKUP = "backup"
    NETWORK = "network"
    SBOM = "sbom"
    DATA_LINEAGE = "data-lineage"


@dataclass
class ScanResult:
    scanner_type: ScannerType
    timestamp: float
    findings: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"  # pass, fail, warning
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "scanner_type": self.scanner_type.value,
                "timestamp": self.timestamp,
                "status": self.status,
                "findings": self.findings,
                "metadata": self.metadata,
            }
        )


class ComplianceScanner:
    """Base class for compliance scanners."""

    def __init__(self, scanner_type: ScannerType):
        self.scanner_type = scanner_type

    def scan(self, config: Dict[str, Any]) -> ScanResult:
        """Scan and return results."""
        raise NotImplementedError


class IAMScanner(ComplianceScanner):
    """Scan IAM policies for least-privilege, MFA, account management."""

    def __init__(self):
        super().__init__(ScannerType.IAM)

    def scan(self, config: Dict[str, Any]) -> ScanResult:
        import time

        result = ScanResult(
            scanner_type=self.scanner_type,
            timestamp=time.time(),
        )

        # Check for overly permissive policies
        policies = config.get("iam_policies", [])
        findings = []

        for policy in policies:
            actions = policy.get("actions", [])
            if "*" in actions:
                findings.append(
                    {
                        "severity": "high",
                        "issue": "Overly permissive policy (wildcard actions)",
                        "policy": policy.get("name"),
                        "recommendation": "Restrict to specific actions (least privilege)",
                    }
                )

            resources = policy.get("resources", [])
            if "*" in resources:
                findings.append(
                    {
                        "severity": "high",
                        "issue": "Overly permissive policy (wildcard resources)",
                        "policy": policy.get("name"),
                        "recommendation": "Restrict to specific resources",
                    }
                )

        # Check for MFA enforcement
        mfa_enforced = config.get("mfa_enforced", False)
        if not mfa_enforced:
            findings.append(
                {
                    "severity": "high",
                    "issue": "MFA not enforced for console access",
                    "recommendation": "Enable MFA requirement for all users",
                }
            )

        result.findings = findings
        result.status = (
            "pass"
            if len(findings) == 0
            else "fail"
            if any(f["severity"] == "high" for f in findings)
            else "warning"
        )
        result.metadata = {"policies_scanned": len(policies), "mfa_enforced": mfa_enforced}

        return result


class EncryptionScanner(ComplianceScanner):
    """Scan for encryption at rest and in transit."""

    def __init__(self):
        super().__init__(ScannerType.ENCRYPTION)

    def scan(self, config: Dict[str, Any]) -> ScanResult:
        import time

        result = ScanResult(
            scanner_type=self.scanner_type,
            timestamp=time.time(),
        )

        findings = []

        # Check RDS encryption
        rds = config.get("rds", [])
        for db in rds:
            if not db.get("storage_encrypted", False):
                findings.append(
                    {
                        "severity": "high",
                        "issue": "RDS database not encrypted at rest",
                        "resource": db.get("name"),
                        "recommendation": "Enable storage_encrypted = true",
                    }
                )

            if not db.get("backup_encrypted", False):
                findings.append(
                    {
                        "severity": "medium",
                        "issue": "RDS backups not encrypted",
                        "resource": db.get("name"),
                    }
                )

        # Check EBS encryption
        ebs = config.get("ebs", [])
        for volume in ebs:
            if not volume.get("encrypted", False):
                findings.append(
                    {
                        "severity": "high",
                        "issue": "EBS volume not encrypted",
                        "resource": volume.get("name"),
                        "recommendation": "Enable encrypted = true",
                    }
                )

        # Check TLS/SSL on load balancers
        lbs = config.get("load_balancers", [])
        for lb in lbs:
            for listener in lb.get("listeners", []):
                if listener.get("protocol") != "HTTPS":
                    findings.append(
                        {
                            "severity": "high",
                            "issue": "Load balancer listener not using HTTPS",
                            "resource": lb.get("name"),
                            "listener": listener.get("port"),
                            "recommendation": "Use HTTPS protocol",
                        }
                    )

        result.findings = findings
        result.status = (
            "pass"
            if len(findings) == 0
            else "fail"
            if any(f["severity"] == "high" for f in findings)
            else "warning"
        )
        result.metadata = {
            "rds_checked": len(rds),
            "ebs_checked": len(ebs),
            "load_balancers_checked": len(lbs),
        }

        return result


class BackupScanner(ComplianceScanner):
    """Scan backup and recovery configuration (RPO/RTO)."""

    def __init__(self):
        super().__init__(ScannerType.BACKUP)

    def scan(self, config: Dict[str, Any]) -> ScanResult:
        import time

        result = ScanResult(
            scanner_type=self.scanner_type,
            timestamp=time.time(),
        )

        findings = []

        # Check backup frequency vs RTO/RPO requirements
        backup_policy = config.get("backup_policy", {})
        rto_minutes = backup_policy.get("rto_minutes", 0)
        rpo_minutes = backup_policy.get("rpo_minutes", 0)
        backup_frequency_minutes = backup_policy.get("frequency_minutes", 1440)

        if rpo_minutes > 0 and backup_frequency_minutes > rpo_minutes:
            findings.append(
                {
                    "severity": "high",
                    "issue": f"Backup frequency ({backup_frequency_minutes}m) exceeds RPO ({rpo_minutes}m)",
                    "recommendation": f"Increase backup frequency to <= {rpo_minutes} minutes",
                }
            )

        # Check retention
        retention_days = backup_policy.get("retention_days", 0)
        if retention_days < 30:
            findings.append(
                {
                    "severity": "medium",
                    "issue": f"Backup retention ({retention_days}d) below 30-day recommendation",
                    "recommendation": "Extend retention to >= 30 days",
                }
            )

        # Check if backups are tested
        tested = backup_policy.get("tested", False)
        if not tested:
            findings.append(
                {
                    "severity": "high",
                    "issue": "Backups not regularly tested for recovery",
                    "recommendation": "Implement monthly backup restore tests",
                }
            )

        result.findings = findings
        result.status = "pass" if len(findings) == 0 else "fail"
        result.metadata = {
            "rto_minutes": rto_minutes,
            "rpo_minutes": rpo_minutes,
            "backup_frequency_minutes": backup_frequency_minutes,
            "retention_days": retention_days,
            "tested": tested,
        }

        return result


# Scanner registry
SCANNERS = {
    "iam": IAMScanner(),
    "encryption": EncryptionScanner(),
    "backup": BackupScanner(),
}


def run_scanners(config: Dict[str, Any], scanner_types: List[str] = None) -> Dict[str, ScanResult]:
    """Run all or specified scanners against system config."""
    if scanner_types is None:
        scanner_types = list(SCANNERS.keys())

    results = {}
    for stype in scanner_types:
        if stype in SCANNERS:
            results[stype] = SCANNERS[stype].scan(config)

    return results
