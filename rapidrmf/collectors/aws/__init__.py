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
from .ec2 import EC2Collector
from .s3 import S3Collector
from .cloudtrail import CloudTrailCollector
from .vpc import VPCCollector
from .rds import RDSCollector
from .kms import KMSCollector

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
