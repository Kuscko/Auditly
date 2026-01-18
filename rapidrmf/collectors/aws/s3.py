"""AWS S3 evidence collector for RapidRMF.

Collects S3 evidence including:
- Bucket configurations (encryption, versioning, access logs)
- Bucket policies and ACLs
- Lifecycle policies
- Public access settings
- Server-side encryption
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional

from .client import AWSClient

logger = logging.getLogger(__name__)

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception  # type: ignore


class S3Collector:
    """Collector for AWS S3 evidence."""

    def __init__(self, client: AWSClient):
        """Initialize S3 collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.s3 = client.get_client("s3")

    def collect_all(self) -> dict[str, Any]:
        """Collect all S3 evidence.

        Returns:
            Dictionary containing S3 evidence
        """
        logger.info("Starting AWS S3 evidence collection")

        evidence = {
            "buckets": self.collect_buckets(),
            "metadata": {
                "collected_at": datetime.utcnow().isoformat(),
                "account_id": self.client.get_account_id(),
                "region": self.client.region,
                "collector": "aws-s3",
                "version": "1.0.0",
            },
        }

        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        logger.info("S3 collection complete: %d buckets", len(evidence["buckets"]))

        return evidence

    def collect_buckets(self) -> list[dict[str, Any]]:
        """Collect S3 buckets with detailed configuration."""
        buckets = []

        try:
            response = self.s3.list_buckets()
            for bucket in response.get("Buckets", []):
                bucket_name = bucket["Name"]
                
                bucket_config = {
                    "name": bucket_name,
                    "creation_date": bucket["CreationDate"].isoformat(),
                    "region": self._get_bucket_region(bucket_name),
                    "versioning": self._get_bucket_versioning(bucket_name),
                    "encryption": self._get_bucket_encryption(bucket_name),
                    "public_access_block": self._get_public_access_block(bucket_name),
                    "acl": self._get_bucket_acl(bucket_name),
                    "policy": self._get_bucket_policy(bucket_name),
                    "logging": self._get_bucket_logging(bucket_name),
                    "lifecycle": self._get_lifecycle_rules(bucket_name),
                    "tags": self._get_bucket_tags(bucket_name),
                }
                
                buckets.append(bucket_config)

            logger.debug("Collected %d S3 buckets", len(buckets))
        except ClientError as e:
            logger.error("Failed to collect S3 buckets: %s", e)

        return buckets

    def _get_bucket_region(self, bucket_name: str) -> Optional[str]:
        """Get bucket region."""
        try:
            response = self.s3.get_bucket_location(Bucket=bucket_name)
            return response.get("LocationConstraint") or "us-east-1"
        except ClientError:
            return None

    def _get_bucket_versioning(self, bucket_name: str) -> dict[str, Any]:
        """Get bucket versioning status."""
        try:
            response = self.s3.get_bucket_versioning(Bucket=bucket_name)
            return {
                "status": response.get("Status"),
                "mfa_delete": response.get("MFADelete"),
            }
        except ClientError:
            return {"status": "Not set", "mfa_delete": None}

    def _get_bucket_encryption(self, bucket_name: str) -> Optional[dict[str, Any]]:
        """Get bucket encryption configuration."""
        try:
            response = self.s3.get_bucket_encryption(Bucket=bucket_name)
            rules = response.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            return {
                "rules": [
                    {
                        "algorithm": rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm"),
                        "kms_key_id": rule.get("ApplyServerSideEncryptionByDefault", {}).get("KMSMasterKeyID"),
                    }
                    for rule in rules
                ]
            }
        except ClientError:
            return None

    def _get_public_access_block(self, bucket_name: str) -> dict[str, bool]:
        """Get public access block settings."""
        try:
            response = self.s3.get_public_access_block(Bucket=bucket_name)
            config = response.get("PublicAccessBlockConfiguration", {})
            return {
                "block_public_acls": config.get("BlockPublicAcls"),
                "ignore_public_acls": config.get("IgnorePublicAcls"),
                "block_public_policy": config.get("BlockPublicPolicy"),
                "restrict_public_buckets": config.get("RestrictPublicBuckets"),
            }
        except ClientError:
            return {}

    def _get_bucket_acl(self, bucket_name: str) -> Optional[dict[str, Any]]:
        """Get bucket ACL."""
        try:
            response = self.s3.get_bucket_acl(Bucket=bucket_name)
            return {
                "owner": response.get("Owner", {}).get("ID"),
                "grants": [
                    {
                        "grantee": grant.get("Grantee", {}).get("ID"),
                        "permission": grant.get("Permission"),
                    }
                    for grant in response.get("Grants", [])
                ],
            }
        except ClientError:
            return None

    def _get_bucket_policy(self, bucket_name: str) -> Optional[dict]:
        """Get bucket policy."""
        try:
            response = self.s3.get_bucket_policy(Bucket=bucket_name)
            policy_str = response.get("Policy", "{}")
            return json.loads(policy_str) if policy_str else None
        except ClientError:
            return None

    def _get_bucket_logging(self, bucket_name: str) -> Optional[dict[str, Any]]:
        """Get bucket logging configuration."""
        try:
            response = self.s3.get_bucket_logging(Bucket=bucket_name)
            logging_config = response.get("LoggingEnabled")
            if logging_config:
                return {
                    "target_bucket": logging_config.get("TargetBucket"),
                    "target_prefix": logging_config.get("TargetPrefix"),
                }
            return None
        except ClientError:
            return None

    def _get_lifecycle_rules(self, bucket_name: str) -> list[dict[str, Any]]:
        """Get bucket lifecycle rules."""
        try:
            response = self.s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            return [
                {
                    "id": rule.get("ID"),
                    "status": rule.get("Status"),
                    "prefix": rule.get("Prefix"),
                    "filter": rule.get("Filter"),
                    "expiration": rule.get("Expiration"),
                    "noncurrent_version_expiration": rule.get("NoncurrentVersionExpiration"),
                    "transition": rule.get("Transition"),
                }
                for rule in response.get("Rules", [])
            ]
        except ClientError:
            return []

    def _get_bucket_tags(self, bucket_name: str) -> dict[str, str]:
        """Get bucket tags."""
        try:
            response = self.s3.get_bucket_tagging(Bucket=bucket_name)
            return {tag["Key"]: tag["Value"] for tag in response.get("TagSet", [])}
        except ClientError:
            return {}
