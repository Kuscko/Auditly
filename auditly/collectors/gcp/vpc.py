"""GCP VPC evidence collector for auditly compliance automation.

Collects evidence about:
- VPC networks and subnetworks
- VPN tunnels and gateways
- Cloud Router configuration
- Network peering
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


class VPCCollector:
    """Collector for GCP VPC evidence.

    Compliance Controls Mapped:
    - SC-7: Boundary Protection (network segmentation, VPN)
    - SC-8: Transmission Confidentiality (VPN encryption)
    - SC-12: Cryptographic Key Establishment (VPN keys)
    - SI-4: Information System Monitoring (VPC flow logs)
    """

    def __init__(self, client: Any):
        """Initialize VPC collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-compute required for VPC collector")

    def collect_all(self) -> dict[str, Any]:
        """Collect all VPC evidence.

        Returns:
            Dictionary containing all VPC evidence types
        """
        evidence = {
            "networks": self.collect_networks(),
            "subnetworks": self.collect_subnetworks(),
            "vpn_tunnels": self.collect_vpn_tunnels(),
            "routers": self.collect_routers(),
            "metadata": {
                "collector": "GCPVPCCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_networks(self) -> list[dict[str, Any]]:
        """Collect VPC networks.

        Returns:
            List of network dictionaries
        """
        networks = []

        try:
            networks_client = compute_v1.NetworksClient(credentials=self.client.credentials)

            request = compute_v1.ListNetworksRequest(project=self.project_id)

            for network in networks_client.list(request=request):
                network_dict = {
                    "name": network.name,
                    "id": network.id,
                    "description": network.description,
                    "auto_create_subnetworks": network.auto_create_subnetworks,
                    "routing_mode": network.routing_config.routing_mode
                    if network.routing_config
                    else None,
                    "mtu": network.mtu,
                    "creation_timestamp": network.creation_timestamp,
                }
                networks.append(network_dict)

            logger.info("Collected %d networks", len(networks))
        except Exception as e:
            logger.error("Error collecting networks: %s", e)

        return networks

    def collect_subnetworks(self) -> list[dict[str, Any]]:
        """Collect VPC subnetworks.

        Returns:
            List of subnetwork dictionaries
        """
        subnetworks = []

        try:
            subnetworks_client = compute_v1.SubnetworksClient(credentials=self.client.credentials)

            # Aggregate subnetworks across all regions
            aggregated_request = compute_v1.AggregatedListSubnetworksRequest(
                project=self.project_id
            )

            for region, response in subnetworks_client.aggregated_list(request=aggregated_request):
                if not response.subnetworks:
                    continue

                for subnetwork in response.subnetworks:
                    subnetwork_dict = {
                        "name": subnetwork.name,
                        "id": subnetwork.id,
                        "region": region,
                        "network": subnetwork.network.split("/")[-1]
                        if subnetwork.network
                        else None,
                        "ip_cidr_range": subnetwork.ip_cidr_range,
                        "gateway_address": subnetwork.gateway_address,
                        "private_ip_google_access": subnetwork.private_ip_google_access,
                        "enable_flow_logs": subnetwork.enable_flow_logs
                        if hasattr(subnetwork, "enable_flow_logs")
                        else False,
                        "log_config": {
                            "enable": subnetwork.log_config.enable
                            if subnetwork.log_config
                            else False,
                            "flow_sampling": subnetwork.log_config.flow_sampling
                            if subnetwork.log_config
                            else None,
                            "aggregation_interval": subnetwork.log_config.aggregation_interval
                            if subnetwork.log_config
                            else None,
                        }
                        if subnetwork.log_config
                        else {},
                        "purpose": subnetwork.purpose if hasattr(subnetwork, "purpose") else None,
                    }
                    subnetworks.append(subnetwork_dict)

            logger.info("Collected %d subnetworks", len(subnetworks))
        except Exception as e:
            logger.error("Error collecting subnetworks: %s", e)

        return subnetworks

    def collect_vpn_tunnels(self) -> list[dict[str, Any]]:
        """Collect VPN tunnels.

        Returns:
            List of VPN tunnel dictionaries
        """
        vpn_tunnels = []

        try:
            vpn_tunnels_client = compute_v1.VpnTunnelsClient(credentials=self.client.credentials)

            # Aggregate VPN tunnels across all regions
            aggregated_request = compute_v1.AggregatedListVpnTunnelsRequest(project=self.project_id)

            for region, response in vpn_tunnels_client.aggregated_list(request=aggregated_request):
                if not response.vpn_tunnels:
                    continue

                for tunnel in response.vpn_tunnels:
                    tunnel_dict = {
                        "name": tunnel.name,
                        "id": tunnel.id,
                        "region": region,
                        "description": tunnel.description,
                        "status": tunnel.status,
                        "peer_ip": tunnel.peer_ip,
                        "ike_version": tunnel.ike_version,
                        "shared_secret_hash": tunnel.shared_secret_hash,
                        "target_vpn_gateway": tunnel.target_vpn_gateway.split("/")[-1]
                        if tunnel.target_vpn_gateway
                        else None,
                        "vpn_gateway": tunnel.vpn_gateway.split("/")[-1]
                        if tunnel.vpn_gateway
                        else None,
                        "creation_timestamp": tunnel.creation_timestamp,
                    }
                    vpn_tunnels.append(tunnel_dict)

            logger.info("Collected %d VPN tunnels", len(vpn_tunnels))
        except Exception as e:
            logger.error("Error collecting VPN tunnels: %s", e)

        return vpn_tunnels

    def collect_routers(self) -> list[dict[str, Any]]:
        """Collect Cloud Routers.

        Returns:
            List of router dictionaries
        """
        routers = []

        try:
            routers_client = compute_v1.RoutersClient(credentials=self.client.credentials)

            # Aggregate routers across all regions
            aggregated_request = compute_v1.AggregatedListRoutersRequest(project=self.project_id)

            for region, response in routers_client.aggregated_list(request=aggregated_request):
                if not response.routers:
                    continue

                for router in response.routers:
                    router_dict = {
                        "name": router.name,
                        "id": router.id,
                        "region": region,
                        "description": router.description,
                        "network": router.network.split("/")[-1] if router.network else None,
                        "bgp": {
                            "asn": router.bgp.asn if router.bgp else None,
                            "advertise_mode": router.bgp.advertise_mode if router.bgp else None,
                        }
                        if router.bgp
                        else {},
                        "creation_timestamp": router.creation_timestamp,
                    }
                    routers.append(router_dict)

            logger.info("Collected %d routers", len(routers))
        except Exception as e:
            logger.error("Error collecting routers: %s", e)

        return routers
