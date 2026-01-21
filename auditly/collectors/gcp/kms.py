"""GCP Cloud KMS evidence collector for auditly compliance automation.

Collects evidence about:
- Key rings and crypto keys
- Key versions and rotation
- IAM policies on keys
- Key protection level (HSM/software)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from google.cloud import kms_v1

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class KMSCollector:
    """Collector for GCP Cloud KMS evidence.

    Compliance Controls Mapped:
    - SC-12: Cryptographic Key Establishment (key management)
    - SC-13: Cryptographic Protection (encryption)
    - SI-16: Memory Protection (HSM-backed keys)
    """

    def __init__(self, client: Any):
        """Initialize KMS collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-kms required for KMS collector")

        self.kms_client = kms_v1.KeyManagementServiceClient(credentials=client.credentials)

    def collect_all(self) -> dict[str, Any]:
        """Collect all Cloud KMS evidence.

        Returns:
            Dictionary containing all KMS evidence types
        """
        evidence = {
            "key_rings": self.collect_key_rings(),
            "crypto_keys": self.collect_crypto_keys(),
            "metadata": {
                "collector": "GCPKMSCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_key_rings(self) -> list[dict[str, Any]]:
        """Collect KMS key rings across all locations.

        Returns:
            List of key ring dictionaries
        """
        key_rings = []

        try:
            # Common GCP KMS locations
            locations = ["global", "us", "us-central1", "us-east1", "europe-west1", "asia-east1"]

            for location in locations:
                try:
                    parent = f"projects/{self.project_id}/locations/{location}"
                    request = kms_v1.ListKeyRingsRequest(parent=parent)

                    for key_ring in self.kms_client.list_key_rings(request=request):
                        key_ring_dict = {
                            "name": key_ring.name,
                            "location": location,
                            "create_time": (
                                key_ring.create_time.isoformat() if key_ring.create_time else None
                            ),
                        }
                        key_rings.append(key_ring_dict)

                except Exception as e:
                    logger.debug("No key rings in location %s: %s", location, e)

            logger.info("Collected %d key rings", len(key_rings))
        except Exception as e:
            logger.error("Error collecting key rings: %s", e)

        return key_rings

    def collect_crypto_keys(self) -> list[dict[str, Any]]:
        """Collect crypto keys with version and rotation info.

        Returns:
            List of crypto key dictionaries
        """
        crypto_keys = []

        try:
            # Common GCP KMS locations
            locations = ["global", "us", "us-central1", "us-east1", "europe-west1", "asia-east1"]

            for location in locations:
                try:
                    # First list key rings in this location
                    parent = f"projects/{self.project_id}/locations/{location}"
                    key_ring_request = kms_v1.ListKeyRingsRequest(parent=parent)

                    for key_ring in self.kms_client.list_key_rings(request=key_ring_request):
                        # List crypto keys in this key ring
                        try:
                            crypto_key_request = kms_v1.ListCryptoKeysRequest(parent=key_ring.name)

                            for crypto_key in self.kms_client.list_crypto_keys(
                                request=crypto_key_request
                            ):
                                key_dict = {
                                    "name": crypto_key.name,
                                    "key_ring": key_ring.name,
                                    "purpose": (
                                        crypto_key.purpose.name if crypto_key.purpose else None
                                    ),
                                    "create_time": (
                                        crypto_key.create_time.isoformat()
                                        if crypto_key.create_time
                                        else None
                                    ),
                                    "next_rotation_time": (
                                        crypto_key.next_rotation_time.isoformat()
                                        if crypto_key.next_rotation_time
                                        else None
                                    ),
                                    "rotation_period": (
                                        crypto_key.rotation_period.seconds
                                        if crypto_key.rotation_period
                                        else None
                                    ),
                                    "primary_version": (
                                        {
                                            "name": (
                                                crypto_key.primary.name
                                                if crypto_key.primary
                                                else None
                                            ),
                                            "state": (
                                                crypto_key.primary.state.name
                                                if crypto_key.primary and crypto_key.primary.state
                                                else None
                                            ),
                                            "protection_level": (
                                                crypto_key.primary.protection_level.name
                                                if crypto_key.primary
                                                and crypto_key.primary.protection_level
                                                else None
                                            ),
                                            "algorithm": (
                                                crypto_key.primary.algorithm.name
                                                if crypto_key.primary
                                                and crypto_key.primary.algorithm
                                                else None
                                            ),
                                            "create_time": (
                                                crypto_key.primary.create_time.isoformat()
                                                if crypto_key.primary
                                                and crypto_key.primary.create_time
                                                else None
                                            ),
                                        }
                                        if crypto_key.primary
                                        else None
                                    ),
                                    "labels": dict(crypto_key.labels) if crypto_key.labels else {},
                                }

                                # Get all versions of this key
                                try:
                                    versions_request = kms_v1.ListCryptoKeyVersionsRequest(
                                        parent=crypto_key.name
                                    )
                                    versions = []
                                    for version in self.kms_client.list_crypto_key_versions(
                                        request=versions_request
                                    ):
                                        versions.append(
                                            {
                                                "name": version.name,
                                                "state": (
                                                    version.state.name if version.state else None
                                                ),
                                                "protection_level": (
                                                    version.protection_level.name
                                                    if version.protection_level
                                                    else None
                                                ),
                                                "algorithm": (
                                                    version.algorithm.name
                                                    if version.algorithm
                                                    else None
                                                ),
                                                "create_time": (
                                                    version.create_time.isoformat()
                                                    if version.create_time
                                                    else None
                                                ),
                                            }
                                        )
                                    key_dict["versions"] = versions
                                except Exception as e:
                                    logger.warning(
                                        "Error collecting versions for key %s: %s",
                                        crypto_key.name,
                                        e,
                                    )
                                    key_dict["versions"] = []

                                crypto_keys.append(key_dict)

                        except Exception as e:
                            logger.warning(
                                "Error collecting crypto keys in key ring %s: %s", key_ring.name, e
                            )

                except Exception as e:
                    logger.debug("No crypto keys in location %s: %s", location, e)

            logger.info("Collected %d crypto keys", len(crypto_keys))
        except Exception as e:
            logger.error("Error collecting crypto keys: %s", e)

        return crypto_keys
