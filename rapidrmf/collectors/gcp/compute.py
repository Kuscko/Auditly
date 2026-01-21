"""GCP Compute Engine evidence collector for RapidRMF compliance automation.

Collects evidence about:
- VM instances (configuration, metadata, disks)
- Disks (encryption, snapshots, type)
- Firewalls (rules, source/destination ranges)
- Snapshots (encryption, schedule)
- Instance templates
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from google.cloud import compute_v1

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class ComputeCollector:
    """Collector for GCP Compute Engine evidence.

    Compliance Controls Mapped:
    - AC-4: Information Flow Enforcement (firewall rules)
    - SC-7: Boundary Protection (firewall configuration)
    - SC-12: Cryptographic Key Establishment (disk encryption)
    - SC-13: Cryptographic Protection (encryption at rest)
    - SC-28: Protection of Information at Rest (disk encryption)
    - SI-2: Flaw Remediation (OS images, patch management)
    """

    def __init__(self, client: Any):
        """Initialize Compute collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-compute required for Compute collector")

    def collect_all(self) -> dict[str, Any]:
        """Collect all Compute Engine evidence.

        Returns:
            Dictionary containing all Compute evidence types
        """
        evidence = {
            "instances": self.collect_instances(),
            "disks": self.collect_disks(),
            "firewalls": self.collect_firewalls(),
            "snapshots": self.collect_snapshots(),
            "metadata": {
                "collector": "GCPComputeCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_instances(self) -> list[dict[str, Any]]:
        """Collect VM instances across all zones.

        Returns:
            List of instance dictionaries
        """
        instances = []

        try:
            instances_client = compute_v1.InstancesClient(credentials=self.client.credentials)

            # Get all zones
            zones_client = compute_v1.ZonesClient(credentials=self.client.credentials)
            zones = zones_client.list(project=self.project_id)

            for zone in zones:
                zone_name = zone.name

                try:
                    request = compute_v1.ListInstancesRequest(
                        project=self.project_id,
                        zone=zone_name,
                    )

                    for instance in instances_client.list(request=request):
                        instance_dict = {
                            "name": instance.name,
                            "id": instance.id,
                            "zone": zone_name,
                            "machine_type": instance.machine_type.split("/")[-1],
                            "status": instance.status,
                            "creation_timestamp": instance.creation_timestamp,
                            "disks": [
                                {
                                    "source": disk.source.split("/")[-1] if disk.source else None,
                                    "mode": disk.mode,
                                    "boot": disk.boot,
                                    "auto_delete": disk.auto_delete,
                                }
                                for disk in instance.disks
                            ],
                            "network_interfaces": [
                                {
                                    "network": ni.network.split("/")[-1] if ni.network else None,
                                    "subnet": ni.subnetwork.split("/")[-1]
                                    if ni.subnetwork
                                    else None,
                                    "internal_ip": ni.network_i_p
                                    if hasattr(ni, "network_i_p")
                                    else None,
                                    "access_configs": [
                                        {
                                            "name": ac.name,
                                            "nat_ip": ac.nat_i_p
                                            if hasattr(ac, "nat_i_p")
                                            else None,
                                        }
                                        for ac in ni.access_configs
                                    ]
                                    if ni.access_configs
                                    else [],
                                }
                                for ni in instance.network_interfaces
                            ],
                            "metadata": {item.key: item.value for item in instance.metadata.items}
                            if instance.metadata and instance.metadata.items
                            else {},
                            "service_accounts": [
                                {
                                    "email": sa.email,
                                    "scopes": list(sa.scopes),
                                }
                                for sa in instance.service_accounts
                            ]
                            if instance.service_accounts
                            else [],
                            "labels": dict(instance.labels) if instance.labels else {},
                            "deletion_protection": instance.deletion_protection,
                        }
                        instances.append(instance_dict)

                except Exception as e:
                    logger.warning("Error collecting instances in zone %s: %s", zone_name, e)

            logger.info("Collected %d instances", len(instances))
        except Exception as e:
            logger.error("Error collecting instances: %s", e)

        return instances

    def collect_disks(self) -> list[dict[str, Any]]:
        """Collect persistent disks across all zones.

        Returns:
            List of disk dictionaries
        """
        disks = []

        try:
            disks_client = compute_v1.DisksClient(credentials=self.client.credentials)
            zones_client = compute_v1.ZonesClient(credentials=self.client.credentials)
            zones = zones_client.list(project=self.project_id)

            for zone in zones:
                zone_name = zone.name

                try:
                    request = compute_v1.ListDisksRequest(
                        project=self.project_id,
                        zone=zone_name,
                    )

                    for disk in disks_client.list(request=request):
                        disk_dict = {
                            "name": disk.name,
                            "id": disk.id,
                            "zone": zone_name,
                            "size_gb": disk.size_gb,
                            "type": disk.type_.split("/")[-1] if disk.type_ else None,
                            "status": disk.status,
                            "creation_timestamp": disk.creation_timestamp,
                            "source_image": disk.source_image.split("/")[-1]
                            if disk.source_image
                            else None,
                            "source_snapshot": disk.source_snapshot.split("/")[-1]
                            if disk.source_snapshot
                            else None,
                            "users": [user.split("/")[-1] for user in disk.users]
                            if disk.users
                            else [],
                            "labels": dict(disk.labels) if disk.labels else {},
                            "disk_encryption_key": {
                                "kms_key_name": disk.disk_encryption_key.kms_key_name
                                if disk.disk_encryption_key
                                else None,
                            }
                            if disk.disk_encryption_key
                            else None,
                        }
                        disks.append(disk_dict)

                except Exception as e:
                    logger.warning("Error collecting disks in zone %s: %s", zone_name, e)

            logger.info("Collected %d disks", len(disks))
        except Exception as e:
            logger.error("Error collecting disks: %s", e)

        return disks

    def collect_firewalls(self) -> list[dict[str, Any]]:
        """Collect firewall rules.

        Returns:
            List of firewall rule dictionaries
        """
        firewalls = []

        try:
            firewalls_client = compute_v1.FirewallsClient(credentials=self.client.credentials)

            request = compute_v1.ListFirewallsRequest(project=self.project_id)

            for firewall in firewalls_client.list(request=request):
                firewall_dict = {
                    "name": firewall.name,
                    "id": firewall.id,
                    "description": firewall.description,
                    "network": firewall.network.split("/")[-1] if firewall.network else None,
                    "priority": firewall.priority,
                    "direction": firewall.direction,
                    "disabled": firewall.disabled,
                    "source_ranges": list(firewall.source_ranges) if firewall.source_ranges else [],
                    "destination_ranges": list(firewall.destination_ranges)
                    if firewall.destination_ranges
                    else [],
                    "source_tags": list(firewall.source_tags) if firewall.source_tags else [],
                    "target_tags": list(firewall.target_tags) if firewall.target_tags else [],
                    "allowed": [
                        {
                            "ip_protocol": rule.i_p_protocol,
                            "ports": list(rule.ports) if rule.ports else [],
                        }
                        for rule in firewall.allowed
                    ]
                    if firewall.allowed
                    else [],
                    "denied": [
                        {
                            "ip_protocol": rule.i_p_protocol,
                            "ports": list(rule.ports) if rule.ports else [],
                        }
                        for rule in firewall.denied
                    ]
                    if firewall.denied
                    else [],
                }
                firewalls.append(firewall_dict)

            logger.info("Collected %d firewall rules", len(firewalls))
        except Exception as e:
            logger.error("Error collecting firewalls: %s", e)

        return firewalls

    def collect_snapshots(self) -> list[dict[str, Any]]:
        """Collect disk snapshots.

        Returns:
            List of snapshot dictionaries
        """
        snapshots = []

        try:
            snapshots_client = compute_v1.SnapshotsClient(credentials=self.client.credentials)

            request = compute_v1.ListSnapshotsRequest(project=self.project_id)

            for snapshot in snapshots_client.list(request=request):
                snapshot_dict = {
                    "name": snapshot.name,
                    "id": snapshot.id,
                    "creation_timestamp": snapshot.creation_timestamp,
                    "disk_size_gb": snapshot.disk_size_gb,
                    "storage_bytes": snapshot.storage_bytes,
                    "source_disk": snapshot.source_disk.split("/")[-1]
                    if snapshot.source_disk
                    else None,
                    "status": snapshot.status,
                    "snapshot_encryption_key": {
                        "kms_key_name": snapshot.snapshot_encryption_key.kms_key_name
                        if snapshot.snapshot_encryption_key
                        else None,
                    }
                    if snapshot.snapshot_encryption_key
                    else None,
                    "labels": dict(snapshot.labels) if snapshot.labels else {},
                    "auto_created": snapshot.auto_created,
                }
                snapshots.append(snapshot_dict)

            logger.info("Collected %d snapshots", len(snapshots))
        except Exception as e:
            logger.error("Error collecting snapshots: %s", e)

        return snapshots
