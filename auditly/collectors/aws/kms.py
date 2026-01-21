"""AWS KMS evidence collector for auditly.

Collects KMS evidence including:
- CMK (Customer Master Key) configurations
- Key policies and key grants
- Key rotation status
- Aliases
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..common import finalize_evidence
from .client import AWSClient

logger = logging.getLogger(__name__)

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception  # type: ignore


class KMSCollector:
    """Collector for AWS KMS evidence."""

    def __init__(self, client: AWSClient):
        """Initialize KMS collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.kms = client.get_client("kms")

    def collect_all(self) -> dict[str, Any]:
        """Collect all KMS evidence.

        Returns:
            Dictionary containing KMS evidence
        """
        logger.info("Starting AWS KMS evidence collection")

        data = {
            "keys": self.collect_keys(),
            "aliases": self.collect_aliases(),
        }
        evidence = finalize_evidence(
            data,
            collector="aws-kms",
            account_id=self.client.get_account_id(),
            region=self.client.region,
        )

        logger.info("KMS collection complete: %d keys", len(evidence["keys"]))

        return evidence

    def collect_keys(self) -> list[dict[str, Any]]:
        """Collect KMS key configurations."""
        keys = []

        try:
            paginator = self.kms.get_paginator("list_keys")
            for page in paginator.paginate():
                for key_id in [k.get("KeyId") for k in page.get("Keys", [])]:
                    key_metadata = self._get_key_metadata(key_id)
                    if key_metadata:
                        keys.append(key_metadata)

            logger.debug("Collected %d KMS keys", len(keys))
        except ClientError as e:
            logger.error("Failed to collect KMS keys: %s", e)

        return keys

    def _get_key_metadata(self, key_id: str) -> dict[str, Any] | None:
        """Get detailed metadata for a KMS key."""
        try:
            desc_response = self.kms.describe_key(KeyId=key_id)
            key_metadata = desc_response.get("KeyMetadata", {})

            # Get key policy
            policy_response = self.kms.get_key_policy(KeyId=key_id, PolicyName="default")
            policy = json.loads(policy_response.get("Policy", "{}"))

            # Get key rotation status
            rotation_response = self.kms.get_key_rotation_status(KeyId=key_id)
            rotation_enabled = rotation_response.get("KeyRotationEnabled")

            # Get grants
            grants = self._get_key_grants(key_id)

            return {
                "key_id": key_metadata.get("KeyId"),
                "key_arn": key_metadata.get("Arn"),
                "description": key_metadata.get("Description"),
                "key_state": key_metadata.get("KeyState"),
                "key_usage": key_metadata.get("KeyUsage"),
                "key_spec": key_metadata.get("KeySpec"),
                "multi_region": key_metadata.get("MultiRegion", False),
                "creation_date": key_metadata.get("CreationDate", "").isoformat()
                if key_metadata.get("CreationDate")
                else None,
                "customer_master_key_spec": key_metadata.get("CustomerMasterKeySpec"),
                "encryption_algorithms": key_metadata.get("EncryptionAlgorithms", []),
                "signing_algorithms": key_metadata.get("SigningAlgorithms", []),
                "rotation_enabled": rotation_enabled,
                "policy": policy,
                "grants": grants,
            }
        except ClientError as e:
            logger.warning("Failed to get metadata for key %s: %s", key_id, e)
            return None

    def _get_key_grants(self, key_id: str) -> list[dict[str, Any]]:
        """Get grants for a KMS key."""
        grants = []

        try:
            paginator = self.kms.get_paginator("list_grants")
            for page in paginator.paginate(KeyId=key_id):
                for grant in page.get("Grants", []):
                    grants.append(
                        {
                            "grant_id": grant.get("GrantId"),
                            "grantee_principal": grant.get("GranteePrincipal"),
                            "operations": grant.get("Operations", []),
                            "creation_date": grant.get("CreationDate", "").isoformat()
                            if grant.get("CreationDate")
                            else None,
                            "retiring_principal": grant.get("RetiringPrincipal"),
                            "constraints": grant.get("Constraints", {}),
                        }
                    )
        except ClientError as e:
            logger.warning("Failed to get grants for key %s: %s", key_id, e)

        return grants

    def collect_aliases(self) -> list[dict[str, str]]:
        """Collect KMS key aliases."""
        aliases = []

        try:
            paginator = self.kms.get_paginator("list_aliases")
            for page in paginator.paginate():
                for alias in page.get("Aliases", []):
                    if not alias.get("AliasName", "").startswith("alias/aws/"):
                        aliases.append(
                            {
                                "alias_name": alias.get("AliasName"),
                                "target_key_id": alias.get("TargetKeyId"),
                            }
                        )

            logger.debug("Collected %d KMS aliases", len(aliases))
        except ClientError as e:
            logger.error("Failed to collect KMS aliases: %s", e)

        return aliases
