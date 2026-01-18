"""GCP Cloud SQL evidence collector for RapidRMF compliance automation.

Collects evidence about:
- Cloud SQL instances (configuration, backups, SSL)
- Database flags and settings
- Backup configuration
- SSL/TLS certificates
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from google.cloud.sql_v1 import SqlInstancesServiceClient
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class CloudSQLCollector:
    """Collector for GCP Cloud SQL evidence.
    
    Compliance Controls Mapped:
    - SC-8: Transmission Confidentiality (SSL/TLS configuration)
    - SC-12: Cryptographic Key Establishment (encryption keys)
    - SC-13: Cryptographic Protection (encryption)
    - SC-28: Protection of Information at Rest (encryption at rest)
    - SI-4: Information System Monitoring (audit logging)
    - CP-9: Information System Backup (backup configuration)
    """

    def __init__(self, client: Any):
        """Initialize Cloud SQL collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id
        
        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-sql required for Cloud SQL collector")

    def collect_all(self) -> dict[str, Any]:
        """Collect all Cloud SQL evidence.

        Returns:
            Dictionary containing all Cloud SQL evidence types
        """
        evidence = {
            "instances": self.collect_instances(),
            "metadata": {
                "collector": "GCPCloudSQLCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(
            evidence_json.encode()
        ).hexdigest()

        return evidence

    def collect_instances(self) -> list[dict[str, Any]]:
        """Collect Cloud SQL instances with security configuration.

        Returns:
            List of Cloud SQL instance dictionaries
        """
        instances = []

        try:
            sql_client = SqlInstancesServiceClient(credentials=self.client.credentials)
            
            request = {"project": f"projects/{self.project_id}"}
            
            for instance in sql_client.list(request=request):
                instance_dict = {
                    "name": instance.name,
                    "database_version": instance.database_version.name if instance.database_version else None,
                    "region": instance.region,
                    "state": instance.state.name if instance.state else None,
                    "connection_name": instance.connection_name,
                    "backend_type": instance.backend_type.name if instance.backend_type else None,
                    "instance_type": instance.instance_type.name if instance.instance_type else None,
                    "settings": {
                        "tier": instance.settings.tier if instance.settings else None,
                        "availability_type": instance.settings.availability_type.name if instance.settings and instance.settings.availability_type else None,
                        "pricing_plan": instance.settings.pricing_plan.name if instance.settings and instance.settings.pricing_plan else None,
                        "storage_auto_resize": instance.settings.storage_auto_resize if instance.settings else None,
                        "data_disk_size_gb": instance.settings.data_disk_size_gb if instance.settings else None,
                        "data_disk_type": instance.settings.data_disk_type.name if instance.settings and instance.settings.data_disk_type else None,
                        "backup_configuration": {
                            "enabled": instance.settings.backup_configuration.enabled if instance.settings and instance.settings.backup_configuration else False,
                            "start_time": instance.settings.backup_configuration.start_time if instance.settings and instance.settings.backup_configuration else None,
                            "binary_log_enabled": instance.settings.backup_configuration.binary_log_enabled if instance.settings and instance.settings.backup_configuration else False,
                            "transaction_log_retention_days": instance.settings.backup_configuration.transaction_log_retention_days if instance.settings and instance.settings.backup_configuration else None,
                        } if instance.settings and instance.settings.backup_configuration else {},
                        "ip_configuration": {
                            "ipv4_enabled": instance.settings.ip_configuration.ipv4_enabled if instance.settings and instance.settings.ip_configuration else False,
                            "private_network": instance.settings.ip_configuration.private_network if instance.settings and instance.settings.ip_configuration else None,
                            "require_ssl": instance.settings.ip_configuration.require_ssl if instance.settings and instance.settings.ip_configuration else False,
                            "authorized_networks": [
                                {
                                    "value": net.value,
                                    "name": net.name,
                                }
                                for net in instance.settings.ip_configuration.authorized_networks
                            ] if instance.settings and instance.settings.ip_configuration and instance.settings.ip_configuration.authorized_networks else [],
                        } if instance.settings and instance.settings.ip_configuration else {},
                        "database_flags": [
                            {
                                "name": flag.name,
                                "value": flag.value,
                            }
                            for flag in instance.settings.database_flags
                        ] if instance.settings and instance.settings.database_flags else [],
                    } if instance.settings else {},
                    "disk_encryption_configuration": {
                        "kms_key_name": instance.disk_encryption_configuration.kms_key_name if instance.disk_encryption_configuration else None,
                    } if instance.disk_encryption_configuration else None,
                }
                
                instances.append(instance_dict)
                
            logger.info("Collected %d Cloud SQL instances", len(instances))
        except Exception as e:
            logger.error("Error collecting Cloud SQL instances: %s", e)

        return instances
