"""AWS EC2 evidence collector for auditly.

Collects EC2 evidence including:
- Instances (configuration, security groups, EBS volumes)
- Security groups (ingress/egress rules)
- EBS volumes (encryption, snapshots)
- Key pairs
- VPC and networking configuration
"""

from __future__ import annotations

import logging
from typing import Any

from ..common import finalize_evidence
from .client import AWSClient

logger = logging.getLogger(__name__)

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception  # type: ignore


class EC2Collector:
    """Collector for AWS EC2 evidence."""

    def __init__(self, client: AWSClient):
        """Initialize EC2 collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.ec2 = client.get_client("ec2")

    def collect_all(self) -> dict[str, Any]:
        """Collect all EC2 evidence.

        Returns:
            Dictionary containing EC2 evidence
        """
        logger.info("Starting AWS EC2 evidence collection")

        data = {
            "instances": self.collect_instances(),
            "security_groups": self.collect_security_groups(),
            "volumes": self.collect_volumes(),
            "snapshots": self.collect_snapshots(),
            "key_pairs": self.collect_key_pairs(),
            "vpcs": self.collect_vpcs(),
            "subnets": self.collect_subnets(),
            "network_acls": self.collect_network_acls(),
        }
        evidence = finalize_evidence(
            data,
            collector="aws-ec2",
            account_id=self.client.get_account_id(),
            region=self.client.region,
        )

        logger.info(
            "EC2 collection complete: %d instances, %d security groups, %d volumes",
            len(evidence["instances"]),
            len(evidence["security_groups"]),
            len(evidence["volumes"]),
        )

        return evidence

    def collect_instances(self) -> list[dict[str, Any]]:
        """Collect EC2 instances with security configuration."""
        instances = []

        try:
            paginator = self.ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        instances.append(
                            {
                                "instance_id": instance["InstanceId"],
                                "instance_type": instance["InstanceType"],
                                "state": instance["State"]["Name"],
                                "key_name": instance.get("KeyName"),
                                "security_groups": [
                                    sg["GroupId"] for sg in instance.get("SecurityGroups", [])
                                ],
                                "public_ip": instance.get("PublicIpAddress"),
                                "private_ip": instance.get("PrivateIpAddress"),
                                "vpc_id": instance.get("VpcId"),
                                "subnet_id": instance.get("SubnetId"),
                                "launch_time": instance["LaunchTime"].isoformat(),
                                "monitoring_enabled": instance.get("Monitoring", {}).get("State")
                                == "enabled",
                                "source_dest_check": instance.get("SourceDestCheck"),
                                "ebs_optimized": instance.get("EbsOptimized"),
                                "detailed_monitoring": instance.get("Monitoring", {}).get("State")
                                == "enabled",
                                "iam_instance_profile": instance.get("IamInstanceProfile"),
                                "tags": {t["Key"]: t["Value"] for t in instance.get("Tags", [])},
                                "block_device_mappings": [
                                    {
                                        "device_name": bdm.get("DeviceName"),
                                        "ebs": {
                                            "volume_id": bdm.get("Ebs", {}).get("VolumeId"),
                                            "delete_on_termination": bdm.get("Ebs", {}).get(
                                                "DeleteOnTermination"
                                            ),
                                        },
                                    }
                                    for bdm in instance.get("BlockDeviceMappings", [])
                                ],
                            }
                        )

            logger.debug("Collected %d EC2 instances", len(instances))
        except ClientError as e:
            logger.error("Failed to collect EC2 instances: %s", e)

        return instances

    def collect_security_groups(self) -> list[dict[str, Any]]:
        """Collect security groups with ingress/egress rules."""
        security_groups = []

        try:
            paginator = self.ec2.get_paginator("describe_security_groups")
            for page in paginator.paginate():
                for sg in page["SecurityGroups"]:
                    security_groups.append(
                        {
                            "group_id": sg["GroupId"],
                            "group_name": sg["GroupName"],
                            "vpc_id": sg.get("VpcId"),
                            "description": sg.get("Description"),
                            "ingress_rules": [
                                self._format_rule(rule) for rule in sg.get("IpPermissions", [])
                            ],
                            "egress_rules": [
                                self._format_rule(rule)
                                for rule in sg.get("IpPermissionsEgress", [])
                            ],
                            "tags": {t["Key"]: t["Value"] for t in sg.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d security groups", len(security_groups))
        except ClientError as e:
            logger.error("Failed to collect security groups: %s", e)

        return security_groups

    def collect_volumes(self) -> list[dict[str, Any]]:
        """Collect EBS volumes with encryption status."""
        volumes = []

        try:
            paginator = self.ec2.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page["Volumes"]:
                    volumes.append(
                        {
                            "volume_id": volume["VolumeId"],
                            "size": volume["Size"],
                            "volume_type": volume["VolumeType"],
                            "state": volume["State"],
                            "availability_zone": volume["AvailabilityZone"],
                            "encrypted": volume["Encrypted"],
                            "iops": volume.get("Iops"),
                            "throughput": volume.get("Throughput"),
                            "kms_key_id": volume.get("KmsKeyId"),
                            "attachments": [
                                {
                                    "instance_id": att["InstanceId"],
                                    "device": att["Device"],
                                    "state": att["State"],
                                }
                                for att in volume.get("Attachments", [])
                            ],
                            "tags": {t["Key"]: t["Value"] for t in volume.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d EBS volumes", len(volumes))
        except ClientError as e:
            logger.error("Failed to collect EBS volumes: %s", e)

        return volumes

    def collect_snapshots(self) -> list[dict[str, Any]]:
        """Collect EBS snapshots owned by account."""
        snapshots = []

        try:
            paginator = self.ec2.get_paginator("describe_snapshots")
            for page in paginator.paginate(OwnerIds=["self"]):
                for snapshot in page["Snapshots"]:
                    snapshots.append(
                        {
                            "snapshot_id": snapshot["SnapshotId"],
                            "volume_id": snapshot.get("VolumeId"),
                            "state": snapshot["State"],
                            "start_time": snapshot["StartTime"].isoformat(),
                            "size": snapshot["VolumeSize"],
                            "encrypted": snapshot["Encrypted"],
                            "progress": snapshot.get("Progress"),
                            "description": snapshot.get("Description"),
                            "public": snapshot.get("Public", False),
                            "tags": {t["Key"]: t["Value"] for t in snapshot.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d EBS snapshots", len(snapshots))
        except ClientError as e:
            logger.error("Failed to collect EBS snapshots: %s", e)

        return snapshots

    def collect_key_pairs(self) -> list[dict[str, Any]]:
        """Collect EC2 key pair metadata."""
        key_pairs = []

        try:
            response = self.ec2.describe_key_pairs()
            for kp in response.get("KeyPairs", []):
                key_pairs.append(
                    {
                        "key_name": kp["KeyName"],
                        "key_fingerprint": kp.get("KeyFingerprint"),
                        "key_type": kp.get("KeyType"),
                        "create_time": kp.get("CreateTime", "").isoformat()
                        if kp.get("CreateTime")
                        else None,
                        "tags": {t["Key"]: t["Value"] for t in kp.get("Tags", [])},
                    }
                )

            logger.debug("Collected %d key pairs", len(key_pairs))
        except ClientError as e:
            logger.error("Failed to collect key pairs: %s", e)

        return key_pairs

    def collect_vpcs(self) -> list[dict[str, Any]]:
        """Collect VPC configurations."""
        vpcs = []

        try:
            paginator = self.ec2.get_paginator("describe_vpcs")
            for page in paginator.paginate():
                for vpc in page["Vpcs"]:
                    vpcs.append(
                        {
                            "vpc_id": vpc["VpcId"],
                            "cidr_block": vpc["CidrBlock"],
                            "state": vpc["State"],
                            "is_default": vpc["IsDefault"],
                            "dns_hostnames": vpc.get("Ipv6CidrBlockAssociationSet", []),
                            "tags": {t["Key"]: t["Value"] for t in vpc.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d VPCs", len(vpcs))
        except ClientError as e:
            logger.error("Failed to collect VPCs: %s", e)

        return vpcs

    def collect_subnets(self) -> list[dict[str, Any]]:
        """Collect VPC subnets."""
        subnets = []

        try:
            paginator = self.ec2.get_paginator("describe_subnets")
            for page in paginator.paginate():
                for subnet in page["Subnets"]:
                    subnets.append(
                        {
                            "subnet_id": subnet["SubnetId"],
                            "vpc_id": subnet["VpcId"],
                            "cidr_block": subnet["CidrBlock"],
                            "availability_zone": subnet["AvailabilityZone"],
                            "available_ip_address_count": subnet["AvailableIpAddressCount"],
                            "map_public_ip_on_launch": subnet.get("MapPublicIpOnLaunch"),
                            "tags": {t["Key"]: t["Value"] for t in subnet.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d subnets", len(subnets))
        except ClientError as e:
            logger.error("Failed to collect subnets: %s", e)

        return subnets

    def collect_network_acls(self) -> list[dict[str, Any]]:
        """Collect network ACLs."""
        nacls = []

        try:
            paginator = self.ec2.get_paginator("describe_network_acls")
            for page in paginator.paginate():
                for nacl in page["NetworkAcls"]:
                    nacls.append(
                        {
                            "network_acl_id": nacl["NetworkAclId"],
                            "vpc_id": nacl["VpcId"],
                            "is_default": nacl["IsDefault"],
                            "ingress_entries": [
                                self._format_nacl_entry(entry)
                                for entry in nacl.get("Entries", [])
                                if not entry.get("Egress", False)
                            ],
                            "egress_entries": [
                                self._format_nacl_entry(entry)
                                for entry in nacl.get("Entries", [])
                                if entry.get("Egress", False)
                            ],
                            "tags": {t["Key"]: t["Value"] for t in nacl.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d network ACLs", len(nacls))
        except ClientError as e:
            logger.error("Failed to collect network ACLs: %s", e)

        return nacls

    # Helper methods

    def _format_rule(self, rule: dict) -> dict[str, Any]:
        """Format security group rule."""
        return {
            "from_port": rule.get("FromPort"),
            "to_port": rule.get("ToPort"),
            "ip_protocol": rule.get("IpProtocol"),
            "ipv4_ranges": [
                {"cidr_ip": r["CidrIp"], "description": r.get("Description")}
                for r in rule.get("IpRanges", [])
            ],
            "ipv6_ranges": [
                {"cidr_ipv6": r["CidrIpv6"], "description": r.get("Description")}
                for r in rule.get("Ipv6Ranges", [])
            ],
            "user_id_group_pairs": [
                {"group_id": r["GroupId"], "description": r.get("Description")}
                for r in rule.get("UserIdGroupPairs", [])
            ],
        }

    def _format_nacl_entry(self, entry: dict) -> dict[str, Any]:
        """Format network ACL entry."""
        return {
            "rule_number": entry.get("RuleNumber"),
            "protocol": entry.get("Protocol"),
            "rule_action": entry.get("RuleAction"),
            "cidr_block": entry.get("CidrBlock"),
            "ipv6_cidr_block": entry.get("Ipv6CidrBlock"),
            "port_range": {
                "from": entry.get("PortRange", {}).get("From"),
                "to": entry.get("PortRange", {}).get("To"),
            },
        }
