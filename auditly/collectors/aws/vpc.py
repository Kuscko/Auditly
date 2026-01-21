"""AWS VPC evidence collector for auditly.

Collects VPC evidence including:
- VPC Flow Logs configuration
- Route tables
- NAT Gateways and NAT Instances
- VPN connections
- Endpoints
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


class VPCCollector:
    """Collector for AWS VPC evidence."""

    def __init__(self, client: AWSClient):
        """Initialize VPC collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.ec2 = client.get_client("ec2")

    def collect_all(self) -> dict[str, Any]:
        """Collect all VPC evidence.

        Returns:
            Dictionary containing VPC evidence
        """
        logger.info("Starting AWS VPC evidence collection")

        data = {
            "flow_logs": self.collect_flow_logs(),
            "route_tables": self.collect_route_tables(),
            "nat_gateways": self.collect_nat_gateways(),
            "vpn_connections": self.collect_vpn_connections(),
            "vpc_endpoints": self.collect_vpc_endpoints(),
        }
        evidence = finalize_evidence(
            data,
            collector="aws-vpc",
            account_id=self.client.get_account_id(),
            region=self.client.region,
        )

        logger.info("VPC collection complete")

        return evidence

    def collect_flow_logs(self) -> list[dict[str, Any]]:
        """Collect VPC Flow Logs configurations."""
        flow_logs = []

        try:
            paginator = self.ec2.get_paginator("describe_flow_logs")
            for page in paginator.paginate():
                for log in page.get("FlowLogs", []):
                    flow_logs.append(
                        {
                            "flow_log_id": log.get("FlowLogId"),
                            "flow_log_status": log.get("FlowLogStatus"),
                            "resource_id": log.get("ResourceId"),
                            "resource_type": log.get("ResourceType"),
                            "traffic_type": log.get("TrafficType"),
                            "log_destination": log.get("LogDestination"),
                            "log_destination_type": log.get("LogDestinationType"),
                            "log_group_name": log.get("LogGroupName"),
                            "delivery_status": log.get("DeliveryStatus"),
                            "creation_time": log.get("CreationTime", "").isoformat()
                            if log.get("CreationTime")
                            else None,
                            "tags": {t.get("Key"): t.get("Value") for t in log.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d VPC Flow Logs", len(flow_logs))
        except ClientError as e:
            logger.error("Failed to collect VPC Flow Logs: %s", e)

        return flow_logs

    def collect_route_tables(self) -> list[dict[str, Any]]:
        """Collect route table configurations."""
        route_tables = []

        try:
            paginator = self.ec2.get_paginator("describe_route_tables")
            for page in paginator.paginate():
                for rt in page.get("RouteTables", []):
                    route_tables.append(
                        {
                            "route_table_id": rt.get("RouteTableId"),
                            "vpc_id": rt.get("VpcId"),
                            "routes": [
                                {
                                    "destination_cidr_block": r.get("DestinationCidrBlock"),
                                    "destination_ipv6_cidr_block": r.get(
                                        "DestinationIpv6CidrBlock"
                                    ),
                                    "gateway_id": r.get("GatewayId"),
                                    "nat_gateway_id": r.get("NatGatewayId"),
                                    "target": r.get("Target"),
                                    "state": r.get("State"),
                                }
                                for r in rt.get("Routes", [])
                            ],
                            "associations": [
                                {
                                    "route_table_association_id": a.get("RouteTableAssociationId"),
                                    "subnet_id": a.get("SubnetId"),
                                    "main": a.get("Main"),
                                }
                                for a in rt.get("Associations", [])
                            ],
                            "tags": {t.get("Key"): t.get("Value") for t in rt.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d route tables", len(route_tables))
        except ClientError as e:
            logger.error("Failed to collect route tables: %s", e)

        return route_tables

    def collect_nat_gateways(self) -> list[dict[str, Any]]:
        """Collect NAT Gateway configurations."""
        nat_gateways = []

        try:
            paginator = self.ec2.get_paginator("describe_nat_gateways")
            for page in paginator.paginate():
                for nat in page.get("NatGateways", []):
                    nat_gateways.append(
                        {
                            "nat_gateway_id": nat.get("NatGatewayId"),
                            "state": nat.get("State"),
                            "vpc_id": nat.get("VpcId"),
                            "subnet_id": nat.get("SubnetId"),
                            "allocation_id": nat.get("NatGatewayAddresses", [{}])[0].get(
                                "AllocationId"
                            ),
                            "public_ip": nat.get("NatGatewayAddresses", [{}])[0].get("PublicIp"),
                            "create_time": nat.get("CreateTime", "").isoformat()
                            if nat.get("CreateTime")
                            else None,
                            "tags": {t.get("Key"): t.get("Value") for t in nat.get("Tags", [])},
                        }
                    )

            logger.debug("Collected %d NAT Gateways", len(nat_gateways))
        except ClientError as e:
            logger.error("Failed to collect NAT Gateways: %s", e)

        return nat_gateways

    def collect_vpn_connections(self) -> list[dict[str, Any]]:
        """Collect VPN connection configurations."""
        vpn_connections = []

        try:
            response = self.ec2.describe_vpn_connections()
            for vpn in response.get("VpnConnections", []):
                vpn_connections.append(
                    {
                        "vpn_connection_id": vpn.get("VpnConnectionId"),
                        "state": vpn.get("State"),
                        "vpn_gateway_id": vpn.get("VpnGatewayId"),
                        "customer_gateway_id": vpn.get("CustomerGatewayId"),
                        "type": vpn.get("Type"),
                        "static_routes_only": vpn.get("Options", {}).get("StaticRoutesOnly"),
                        "tunnels": [
                            {
                                "outside_ip_address": t.get("OutsideIpAddress"),
                                "status": t.get("Status"),
                            }
                            for t in vpn.get("VgwTelemetry", [])
                        ],
                    }
                )

            logger.debug("Collected %d VPN connections", len(vpn_connections))
        except ClientError as e:
            logger.error("Failed to collect VPN connections: %s", e)

        return vpn_connections

    def collect_vpc_endpoints(self) -> list[dict[str, Any]]:
        """Collect VPC endpoint configurations."""
        endpoints = []

        try:
            paginator = self.ec2.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                for endpoint in page.get("VpcEndpoints", []):
                    endpoints.append(
                        {
                            "vpc_endpoint_id": endpoint.get("VpcEndpointId"),
                            "vpc_id": endpoint.get("VpcId"),
                            "service_name": endpoint.get("ServiceName"),
                            "state": endpoint.get("State"),
                            "vpc_endpoint_type": endpoint.get("VpcEndpointType"),
                            "route_table_ids": endpoint.get("RouteTableIds", []),
                            "subnet_ids": endpoint.get("SubnetIds", []),
                            "security_group_ids": [
                                sg.get("GroupId") for sg in endpoint.get("Groups", [])
                            ],
                            "policy_document": endpoint.get("PolicyDocument"),
                            "private_dns_enabled": endpoint.get("PrivateDnsEnabled"),
                            "tags": {
                                t.get("Key"): t.get("Value") for t in endpoint.get("Tags", [])
                            },
                        }
                    )

            logger.debug("Collected %d VPC endpoints", len(endpoints))
        except ClientError as e:
            logger.error("Failed to collect VPC endpoints: %s", e)

        return endpoints
