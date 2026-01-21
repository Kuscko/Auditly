"""AWS evidence collectors for auditly compliance automation.

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
from .cloudtrail import CloudTrailCollector
from .ec2 import EC2Collector
from .iam import IAMCollector
from .kms import KMSCollector
from .rds import RDSCollector
from .s3 import S3Collector
from .vpc import VPCCollector

__all__ = [
    "AWSClient",
    "IAMCollector",
    "EC2Collector",
    "S3Collector",
    "CloudTrailCollector",
    "VPCCollector",
    "RDSCollector",
    "KMSCollector",
]
