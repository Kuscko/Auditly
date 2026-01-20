"""GCP evidence collectors for RapidRMF compliance automation.

This package provides collectors for Google Cloud Platform services including:
- IAM (users, service accounts, roles, policies)
- Compute Engine (instances, disks, snapshots, firewalls)
- Cloud Storage (buckets, IAM policies, lifecycle)
- Cloud SQL (instances, backups, SSL configuration)
- VPC (networks, subnets, firewall rules, VPN)
- Cloud KMS (keys, key rings, rotation)
- Cloud Logging (sinks, metrics, audit logs)
"""

from .client import GCPClient
from .compute import ComputeCollector
from .iam import IAMCollector
from .kms import KMSCollector
from .logging import LoggingCollector
from .sql import CloudSQLCollector
from .storage import StorageCollector
from .vpc import VPCCollector

__all__ = [
    "GCPClient",
    "IAMCollector",
    "ComputeCollector",
    "StorageCollector",
    "CloudSQLCollector",
    "VPCCollector",
    "KMSCollector",
    "LoggingCollector",
]
