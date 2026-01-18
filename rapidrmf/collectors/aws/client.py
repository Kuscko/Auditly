"""AWS client wrapper for boto3 session management."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:
    boto3 = None  # type: ignore
    BotoCoreError = Exception  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore
    logger.warning("boto3 not installed. AWS collectors will not be available.")


class AWSClient:
    """AWS client wrapper for managing boto3 sessions and clients.
    
    Handles:
    - Credential management (profile, access key, session token)
    - Multi-region support
    - Client caching for performance
    - Error handling and retries
    """

    def __init__(
        self,
        region: str = "us-east-1",
        profile_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
    ):
        """Initialize AWS client.

        Args:
            region: AWS region (default: us-east-1)
            profile_name: AWS CLI profile name (optional)
            access_key_id: AWS access key ID (optional)
            secret_access_key: AWS secret access key (optional)
            session_token: AWS session token for temporary credentials (optional)
        """
        if boto3 is None:
            raise ImportError(
                "boto3 is required for AWS collectors. Install with: pip install boto3"
            )

        self.region = region
        self.profile_name = profile_name
        self._clients: dict[str, Any] = {}

        # Create boto3 session
        if profile_name:
            self.session = boto3.Session(profile_name=profile_name, region_name=region)
        elif access_key_id and secret_access_key:
            self.session = boto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                region_name=region,
            )
        else:
            # Use default credential chain
            self.session = boto3.Session(region_name=region)

        logger.info(
            "Initialized AWS client for region=%s, profile=%s", region, profile_name
        )

    def get_client(self, service: str, region: Optional[str] = None) -> Any:
        """Get boto3 client for a service (cached).

        Args:
            service: AWS service name (e.g., 'iam', 'ec2', 's3')
            region: Override region for this client (optional)

        Returns:
            Boto3 service client

        Raises:
            NoCredentialsError: If no AWS credentials are found
            ClientError: If client creation fails
        """
        region = region or self.region
        cache_key = f"{service}:{region}"

        if cache_key not in self._clients:
            try:
                self._clients[cache_key] = self.session.client(service, region_name=region)
                logger.debug("Created boto3 client for %s in %s", service, region)
            except NoCredentialsError as e:
                logger.error("No AWS credentials found. Configure via AWS CLI or env vars.")
                raise
            except (ClientError, BotoCoreError) as e:
                logger.error("Failed to create AWS client for %s: %s", service, e)
                raise

        return self._clients[cache_key]

    def get_account_id(self) -> str:
        """Get AWS account ID using STS.

        Returns:
            AWS account ID

        Raises:
            ClientError: If unable to determine account ID
        """
        try:
            sts = self.get_client("sts")
            response = sts.get_caller_identity()
            account_id = response["Account"]
            logger.debug("AWS Account ID: %s", account_id)
            return account_id
        except ClientError as e:
            logger.error("Failed to get AWS account ID: %s", e)
            raise

    def list_regions(self, service: str = "ec2") -> list[str]:
        """List available AWS regions for a service.

        Args:
            service: AWS service name (default: ec2)

        Returns:
            List of region names
        """
        try:
            ec2 = self.get_client(service)
            response = ec2.describe_regions()
            regions = [r["RegionName"] for r in response["Regions"]]
            logger.debug("Found %d AWS regions", len(regions))
            return regions
        except ClientError as e:
            logger.warning("Failed to list AWS regions: %s", e)
            return [self.region]
