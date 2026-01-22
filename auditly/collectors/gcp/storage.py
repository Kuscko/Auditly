"""GCP Cloud Storage evidence collector for auditly compliance automation.

Collects evidence about:
- Storage buckets (IAM policies, encryption, versioning)
- Bucket lifecycle policies
- CORS configuration
- Public access settings
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class StorageCollector:
    """Collector for GCP Cloud Storage evidence.

    Compliance Controls Mapped:
    - AC-3: Access Enforcement (bucket IAM policies)
    - AC-6: Least Privilege (IAM bindings)
    - SC-7: Boundary Protection (public access controls)
    - SC-12: Cryptographic Key Establishment (encryption keys)
    - SC-13: Cryptographic Protection (encryption at rest)
    - SC-28: Protection of Information at Rest (bucket encryption)
    - SI-12: Information Handling (retention policies)
    """

    def __init__(self, client: Any):
        """Initialize Storage collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-storage required for Storage collector")

        self.storage_client = storage.Client(
            project=self.project_id,
            credentials=client.credentials,
        )

    def collect_all(self) -> dict[str, Any]:
        """Collect all Cloud Storage evidence.

        Returns:
            Dictionary containing all Storage evidence types
        """
        evidence = {
            "buckets": self.collect_buckets(),
            "metadata": {
                "collector": "GCPStorageCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_buckets(self) -> list[dict[str, Any]]:
        """Collect storage buckets with security configuration.

        Returns:
            List of bucket dictionaries
        """
        buckets = []

        try:
            for bucket in self.storage_client.list_buckets():
                bucket_dict = {
                    "name": bucket.name,
                    "id": bucket.id,
                    "location": bucket.location,
                    "location_type": bucket.location_type,
                    "storage_class": bucket.storage_class,
                    "time_created": (
                        bucket.time_created.isoformat() if bucket.time_created else None
                    ),
                    "versioning_enabled": bucket.versioning_enabled,
                    "labels": dict(bucket.labels) if bucket.labels else {},
                    "default_event_based_hold": bucket.default_event_based_hold,
                    "retention_policy": (
                        {
                            "retention_period": (
                                bucket.retention_policy.retention_period
                                if bucket.retention_policy
                                else None
                            ),
                            "effective_time": (
                                bucket.retention_policy.effective_time.isoformat()
                                if bucket.retention_policy
                                and bucket.retention_policy.effective_time
                                else None
                            ),
                            "is_locked": (
                                bucket.retention_policy.is_locked
                                if bucket.retention_policy
                                else None
                            ),
                        }
                        if bucket.retention_policy
                        else None
                    ),
                    "default_kms_key_name": bucket.default_kms_key_name,
                    "iam_configuration": (
                        {
                            "uniform_bucket_level_access_enabled": (
                                bucket.iam_configuration.uniform_bucket_level_access_enabled
                                if bucket.iam_configuration
                                else False
                            ),
                            "uniform_bucket_level_access_locked_time": (
                                bucket.iam_configuration.uniform_bucket_level_access_locked_time.isoformat()
                                if bucket.iam_configuration
                                and bucket.iam_configuration.uniform_bucket_level_access_locked_time
                                else None
                            ),
                            "public_access_prevention": (
                                bucket.iam_configuration.public_access_prevention
                                if bucket.iam_configuration
                                else None
                            ),
                        }
                        if bucket.iam_configuration
                        else {}
                    ),
                }

                # Get IAM policy
                try:
                    policy = bucket.get_iam_policy()
                    bindings = []
                    for role, members in policy.items():
                        bindings.append(
                            {
                                "role": role,
                                "members": list(members),
                            }
                        )
                    bucket_dict["iam_policy"] = bindings
                except Exception as e:
                    logger.warning("Error getting IAM policy for bucket %s: %s", bucket.name, e)
                    bucket_dict["iam_policy"] = []

                # Get lifecycle rules
                try:
                    lifecycle_rules = []
                    if bucket.lifecycle_rules:
                        for rule in bucket.lifecycle_rules:
                            lifecycle_rules.append(
                                {
                                    "action": dict(rule.get("action", {})),
                                    "condition": dict(rule.get("condition", {})),
                                }
                            )
                    bucket_dict["lifecycle_rules"] = lifecycle_rules
                except Exception as e:
                    logger.warning(
                        "Error getting lifecycle rules for bucket %s: %s", bucket.name, e
                    )
                    bucket_dict["lifecycle_rules"] = []

                # Get CORS configuration
                try:
                    if bucket.cors:
                        bucket_dict["cors"] = [
                            {
                                "origin": cors.get("origin", []),
                                "method": cors.get("method", []),
                                "responseHeader": cors.get("responseHeader", []),
                                "maxAgeSeconds": cors.get("maxAgeSeconds"),
                            }
                            for cors in bucket.cors
                        ]
                    else:
                        bucket_dict["cors"] = []
                except Exception as e:
                    logger.warning("Error getting CORS for bucket %s: %s", bucket.name, e)
                    bucket_dict["cors"] = []

                buckets.append(bucket_dict)

            logger.info("Collected %d buckets", len(buckets))
        except Exception as e:
            logger.error("Error collecting buckets: %s", e)

        return buckets
