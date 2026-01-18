"""AWS RDS evidence collector for RapidRMF.

Collects RDS evidence including:
- DB instances (configuration, encryption, backups)
- DB clusters
- Parameter groups
- Subnet groups
- Snapshot configurations
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


class RDSCollector:
    """Collector for AWS RDS evidence."""

    def __init__(self, client: AWSClient):
        """Initialize RDS collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.rds = client.get_client("rds")

    def collect_all(self) -> dict[str, Any]:
        """Collect all RDS evidence.

        Returns:
            Dictionary containing RDS evidence
        """
        logger.info("Starting AWS RDS evidence collection")

        evidence = {
            "db_instances": self.collect_db_instances(),
            "db_clusters": self.collect_db_clusters(),
            "parameter_groups": self.collect_parameter_groups(),
            "subnet_groups": self.collect_subnet_groups(),
            "metadata": {
                "collected_at": datetime.utcnow().isoformat(),
                "account_id": self.client.get_account_id(),
                "region": self.client.region,
                "collector": "aws-rds",
                "version": "1.0.0",
            },
        }

        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        logger.info("RDS collection complete: %d instances", len(evidence["db_instances"]))

        return evidence

    def collect_db_instances(self) -> list[dict[str, Any]]:
        """Collect RDS DB instance configurations."""
        instances = []

        try:
            paginator = self.rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page.get("DBInstances", []):
                    instances.append({
                        "db_instance_identifier": instance.get("DBInstanceIdentifier"),
                        "db_instance_class": instance.get("DBInstanceClass"),
                        "engine": instance.get("Engine"),
                        "engine_version": instance.get("EngineVersion"),
                        "db_instance_status": instance.get("DBInstanceStatus"),
                        "allocated_storage": instance.get("AllocatedStorage"),
                        "storage_type": instance.get("StorageType"),
                        "storage_encrypted": instance.get("StorageEncrypted"),
                        "kms_key_id": instance.get("KmsKeyId"),
                        "iops": instance.get("Iops"),
                        "publicly_accessible": instance.get("PubliclyAccessible"),
                        "multi_az": instance.get("MultiAZ"),
                        "auto_minor_version_upgrade": instance.get("AutoMinorVersionUpgrade"),
                        "backup_retention_period": instance.get("BackupRetentionPeriod"),
                        "preferred_backup_window": instance.get("PreferredBackupWindow"),
                        "preferred_maintenance_window": instance.get("PreferredMaintenanceWindow"),
                        "enable_cloudwatch_logs_exports": instance.get("EnableCloudwatchLogsExports", []),
                        "db_parameter_group": instance.get("DBParameterGroups", [{}])[0].get("DBParameterGroupName"),
                        "vpc_security_groups": [sg.get("VpcSecurityGroupId") for sg in instance.get("VpcSecurityGroups", [])],
                        "db_subnet_group": instance.get("DBSubnetGroup", {}).get("DBSubnetGroupName"),
                        "enable_iam_database_authentication": instance.get("IAMDatabaseAuthenticationEnabled"),
                        "deletion_protection": instance.get("DeletionProtection"),
                        "enhanced_monitoring_resource_arn": instance.get("EnhancedMonitoringResourceArn"),
                        "performance_insights_enabled": instance.get("PerformanceInsightsEnabled"),
                        "performance_insights_kms_key_id": instance.get("PerformanceInsightsKMSKeyId"),
                    })

            logger.debug("Collected %d RDS instances", len(instances))
        except ClientError as e:
            logger.error("Failed to collect RDS instances: %s", e)

        return instances

    def collect_db_clusters(self) -> list[dict[str, Any]]:
        """Collect RDS DB cluster configurations."""
        clusters = []

        try:
            paginator = self.rds.get_paginator("describe_db_clusters")
            for page in paginator.paginate():
                for cluster in page.get("DBClusters", []):
                    clusters.append({
                        "db_cluster_identifier": cluster.get("DBClusterIdentifier"),
                        "engine": cluster.get("Engine"),
                        "engine_version": cluster.get("EngineVersion"),
                        "status": cluster.get("Status"),
                        "backup_retention_period": cluster.get("BackupRetentionPeriod"),
                        "storage_encrypted": cluster.get("StorageEncrypted"),
                        "kms_key_id": cluster.get("KmsKeyId"),
                        "preferred_backup_window": cluster.get("PreferredBackupWindow"),
                        "preferred_maintenance_window": cluster.get("PreferredMaintenanceWindow"),
                        "enabled_cloudwatch_logs_exports": cluster.get("EnabledCloudwatchLogsExports", []),
                        "db_cluster_members": [
                            {
                                "db_instance_identifier": m.get("DBInstanceIdentifier"),
                                "is_cluster_writer": m.get("IsClusterWriter"),
                            }
                            for m in cluster.get("DBClusterMembers", [])
                        ],
                        "vpc_security_groups": [sg.get("VpcSecurityGroupId") for sg in cluster.get("VpcSecurityGroups", [])],
                        "db_subnet_group": cluster.get("DBSubnetGroup"),
                        "iam_database_authentication_enabled": cluster.get("IAMDatabaseAuthenticationEnabled"),
                        "deletion_protection": cluster.get("DeletionProtection"),
                    })

            logger.debug("Collected %d RDS clusters", len(clusters))
        except ClientError as e:
            logger.error("Failed to collect RDS clusters: %s", e)

        return clusters

    def collect_parameter_groups(self) -> list[dict[str, Any]]:
        """Collect RDS parameter group configurations."""
        param_groups = []

        try:
            paginator = self.rds.get_paginator("describe_db_parameter_groups")
            for page in paginator.paginate():
                for pg in page.get("DBParameterGroups", []):
                    param_groups.append({
                        "db_parameter_group_name": pg.get("DBParameterGroupName"),
                        "db_parameter_group_family": pg.get("DBParameterGroupFamily"),
                        "description": pg.get("Description"),
                        "arn": pg.get("DBParameterGroupArn"),
                    })

            logger.debug("Collected %d RDS parameter groups", len(param_groups))
        except ClientError as e:
            logger.error("Failed to collect RDS parameter groups: %s", e)

        return param_groups

    def collect_subnet_groups(self) -> list[dict[str, Any]]:
        """Collect RDS subnet group configurations."""
        subnet_groups = []

        try:
            paginator = self.rds.get_paginator("describe_db_subnet_groups")
            for page in paginator.paginate():
                for sg in page.get("DBSubnetGroups", []):
                    subnet_groups.append({
                        "db_subnet_group_name": sg.get("DBSubnetGroupName"),
                        "description": sg.get("DBSubnetGroupDescription"),
                        "vpc_id": sg.get("VpcId"),
                        "status": sg.get("SubnetGroupStatus"),
                        "subnets": [
                            {
                                "subnet_id": s.get("SubnetIdentifier"),
                                "availability_zone": s.get("SubnetAvailabilityZone", {}).get("Name"),
                                "subnet_status": s.get("SubnetStatus"),
                            }
                            for s in sg.get("Subnets", [])
                        ],
                        "arn": sg.get("DBSubnetGroupArn"),
                    })

            logger.debug("Collected %d RDS subnet groups", len(subnet_groups))
        except ClientError as e:
            logger.error("Failed to collect RDS subnet groups: %s", e)

        return subnet_groups
