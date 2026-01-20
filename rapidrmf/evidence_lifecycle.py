"""Evidence lifecycle utilities: staleness detection, deduplication, chain of custody."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Evidence, EvidenceAccessLog, EvidenceVersion


class EvidenceLifecycleManager:
    """Manage evidence lifecycle: staleness, deduplication, access tracking."""

    def __init__(self, session: Session):
        self.session = session

    def detect_stale_evidence(
        self,
        system_id: int,
        staleness_threshold_days: int = 30,
        evidence_type: Optional[str] = None,
    ) -> List[Evidence]:
        """
        Find evidence that hasn't been updated within the staleness threshold.

        Args:
            system_id: System ID to check
            staleness_threshold_days: Evidence older than this is considered stale
            evidence_type: Optional filter by evidence type

        Returns:
            List of stale Evidence records
        """
        threshold_date = datetime.utcnow() - timedelta(days=staleness_threshold_days)

        query = select(Evidence).where(
            Evidence.system_id == system_id,
            Evidence.collected_at < threshold_date,
        )

        if evidence_type:
            query = query.where(Evidence.evidence_type == evidence_type)

        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_evidence_versions(self, evidence_id: int) -> List[EvidenceVersion]:
        """
        Get all versions of an evidence record, ordered by version number.

        Args:
            evidence_id: Evidence ID

        Returns:
            List of EvidenceVersion records
        """
        query = (
            select(EvidenceVersion)
            .where(EvidenceVersion.evidence_id == evidence_id)
            .order_by(EvidenceVersion.version.asc())
        )
        result = self.session.execute(query)
        return list(result.scalars().all())

    def detect_duplicate_evidence(
        self,
        system_id: int,
        sha256_hash: str,
        exclude_evidence_id: Optional[int] = None,
    ) -> List[Evidence]:
        """
        Find duplicate evidence by SHA256 hash.

        Args:
            system_id: System ID
            sha256_hash: SHA256 hash to search for
            exclude_evidence_id: Optional evidence ID to exclude from results

        Returns:
            List of Evidence records with matching hash
        """
        query = select(Evidence).where(
            Evidence.system_id == system_id,
            Evidence.sha256 == sha256_hash,
        )

        if exclude_evidence_id:
            query = query.where(Evidence.id != exclude_evidence_id)

        result = self.session.execute(query)
        return list(result.scalars().all())

    def get_evidence_drift(
        self,
        evidence_id: int,
        version1: int,
        version2: int,
    ) -> Dict[str, Any]:
        """
        Compare two versions of evidence to detect configuration drift.

        Args:
            evidence_id: Evidence ID
            version1: First version number
            version2: Second version number

        Returns:
            Dict with drift analysis
        """
        v1 = self.session.execute(
            select(EvidenceVersion).where(
                EvidenceVersion.evidence_id == evidence_id,
                EvidenceVersion.version == version1,
            )
        ).scalar_one_or_none()

        v2 = self.session.execute(
            select(EvidenceVersion).where(
                EvidenceVersion.evidence_id == evidence_id,
                EvidenceVersion.version == version2,
            )
        ).scalar_one_or_none()

        if not v1 or not v2:
            return {"error": "Version not found"}

        # Simple drift detection: compare JSON data
        data1 = v1.data
        data2 = v2.data

        # Find changed keys
        all_keys = set(data1.keys()) | set(data2.keys())
        changes = {}

        for key in all_keys:
            val1 = data1.get(key)
            val2 = data2.get(key)

            if val1 != val2:
                changes[key] = {
                    "old": val1,
                    "new": val2,
                    "change_type": "added"
                    if key not in data1
                    else ("removed" if key not in data2 else "modified"),
                }

        return {
            "evidence_id": evidence_id,
            "version1": version1,
            "version2": version2,
            "collected_at_v1": v1.collected_at.isoformat(),
            "collected_at_v2": v2.collected_at.isoformat(),
            "changes": changes,
            "drift_detected": len(changes) > 0,
        }

    def get_access_log(
        self,
        evidence_id: int,
        limit: int = 100,
    ) -> List[EvidenceAccessLog]:
        """
        Get access log for evidence.

        Args:
            evidence_id: Evidence ID
            limit: Maximum number of entries to return

        Returns:
            List of EvidenceAccessLog records
        """
        query = (
            select(EvidenceAccessLog)
            .where(EvidenceAccessLog.evidence_id == evidence_id)
            .order_by(EvidenceAccessLog.timestamp.desc())
            .limit(limit)
        )
        result = self.session.execute(query)
        return list(result.scalars().all())

    def log_evidence_access(
        self,
        evidence_id: int,
        user_id: str,
        action: str,
        ip_address: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> EvidenceAccessLog:
        """
        Log evidence access for audit trail.

        Args:
            evidence_id: Evidence ID
            user_id: User or system identifier
            action: Action taken (read, write, delete, validate)
            ip_address: Optional IP address
            attributes: Optional additional attributes

        Returns:
            Created EvidenceAccessLog record
        """
        log_entry = EvidenceAccessLog(
            evidence_id=evidence_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            attributes=attributes or {},
        )
        self.session.add(log_entry)
        self.session.flush()
        return log_entry

    def mark_evidence_expired(
        self,
        evidence_id: int,
        expires_at: datetime,
    ) -> Evidence:
        """
        Mark evidence as expired for retention policy.

        Args:
            evidence_id: Evidence ID
            expires_at: Expiration timestamp

        Returns:
            Updated Evidence record
        """
        evidence = self.session.get(Evidence, evidence_id)
        if evidence:
            evidence.expires_at = expires_at
            self.session.flush()
        return evidence

    def get_evidence_age_days(self, evidence: Evidence) -> int:
        """
        Calculate age of evidence in days.

        Args:
            evidence: Evidence record

        Returns:
            Age in days
        """
        age = datetime.utcnow() - evidence.collected_at
        return age.days

    def needs_recollection(
        self,
        evidence: Evidence,
        recollection_threshold_days: int = 30,
    ) -> bool:
        """
        Check if evidence needs to be recollected.

        Args:
            evidence: Evidence record
            recollection_threshold_days: Threshold for staleness

        Returns:
            True if evidence should be recollected
        """
        return self.get_evidence_age_days(evidence) > recollection_threshold_days
