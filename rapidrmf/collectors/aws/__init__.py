"""AWS evidence collectors for RapidRMF compliance automation.

This package provides collectors for AWS services including:
- IAM (users, roles, policies, MFA status)
- EC2 (instances, security groups, EBS encryption)
- S3 (bucket policies, encryption, versioning)
- CloudTrail (event history, management events)
- VPC (flow logs, network ACLs, route tables)
- RDS (instance configs, encryption, backups)
- KMS (key policies, rotation status)
"""

from .client import AWSClient
from .iam import IAMCollector

__all__ = ["AWSClient", "IAMCollector"]
