"""GCP IAM evidence collector for auditly compliance automation.

Collects evidence about:
- Service accounts (keys, permissions, IAM policies)
- IAM roles (predefined and custom)
- IAM policies (bindings, conditions)
- Organization policies
- Service account keys (age, usage)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# type: ignore[import-untyped]

try:
    from google.cloud import iam_admin_v1
    from google.iam.v1 import iam_policy_pb2

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class IAMCollector:
    """Collector for GCP IAM evidence.

    Compliance Controls Mapped:
    - AC-2: Account Management (service accounts, lifecycle)
    - AC-3: Access Enforcement (IAM policies, role bindings)
    - AC-6: Least Privilege (role assignments, custom roles)
    - IA-4: Identifier Management (service account identifiers)
    - IA-5: Authenticator Management (service account keys)
    """

    def __init__(self, client: Any):
        """Initialize IAM collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if GCP_AVAILABLE:
            self.iam_client = iam_admin_v1.IAMClient(credentials=client.credentials)
        else:
            raise ImportError("google-cloud-iam required for IAM collector")

    def collect_all(self) -> dict[str, Any]:
        """Collect all IAM evidence.

        Returns:
            Dictionary containing all IAM evidence types
        """
        evidence = {
            "service_accounts": self.collect_service_accounts(),
            "custom_roles": self.collect_custom_roles(),
            "iam_policies": self.collect_iam_policies(),
            "service_account_keys": self.collect_service_account_keys(),
            "metadata": {
                "collector": "GCPIAMCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_service_accounts(self) -> list[dict[str, Any]]:
        """Collect service accounts with metadata.

        Returns:
            List of service account dictionaries
        """
        service_accounts = []

        try:
            project_name = f"projects/{self.project_id}"
            request = iam_admin_v1.ListServiceAccountsRequest(name=project_name)

            for sa in self.iam_client.list_service_accounts(request=request):
                sa_dict = {
                    "name": sa.name,
                    "email": sa.email,
                    "display_name": sa.display_name,
                    "unique_id": sa.unique_id,
                    "disabled": sa.disabled,
                    "description": sa.description,
                }
                service_accounts.append(sa_dict)

            logger.info("Collected %d service accounts", len(service_accounts))
        except Exception as e:
            logger.error("Error collecting service accounts: %s", e)

        return service_accounts

    def collect_custom_roles(self) -> list[dict[str, Any]]:
        """Collect custom IAM roles defined in the project.

        Returns:
            List of custom role dictionaries
        """
        custom_roles = []

        try:
            parent = f"projects/{self.project_id}"
            request = iam_admin_v1.ListRolesRequest(parent=parent)

            for role in self.iam_client.list_roles(request=request):
                role_dict = {
                    "name": role.name,
                    "title": role.title,
                    "description": role.description,
                    "stage": role.stage.name if role.stage else "GA",
                    "included_permissions": list(role.included_permissions),
                    "deleted": role.deleted,
                }
                custom_roles.append(role_dict)

            logger.info("Collected %d custom roles", len(custom_roles))
        except Exception as e:
            logger.error("Error collecting custom roles: %s", e)

        return custom_roles

    def collect_iam_policies(self) -> list[dict[str, Any]]:
        """Collect IAM policy bindings for the project.

        Returns:
            List of IAM policy dictionaries with bindings
        """
        policies = []

        try:
            # Get project IAM policy
            from google.cloud import resourcemanager_v3

            projects_client = resourcemanager_v3.ProjectsClient(credentials=self.client.credentials)

            project_name = f"projects/{self.project_id}"
            policy = projects_client.get_iam_policy(resource=project_name)

            bindings = []
            for binding in policy.bindings:
                binding_dict = {
                    "role": binding.role,
                    "members": list(binding.members),
                }

                # Include condition if present
                if binding.condition:
                    binding_dict["condition"] = {
                        "title": binding.condition.title,
                        "description": binding.condition.description,
                        "expression": binding.condition.expression,
                    }

                bindings.append(binding_dict)

            policies.append(
                {
                    "resource": project_name,
                    "bindings": bindings,
                    "etag": policy.etag.decode() if policy.etag else None,
                }
            )

            logger.info("Collected IAM policies with %d bindings", len(bindings))
        except Exception as e:
            logger.error("Error collecting IAM policies: %s", e)

        return policies

    def collect_service_account_keys(self) -> list[dict[str, Any]]:
        """Collect service account keys with age information.

        Returns:
            List of service account key dictionaries
        """
        keys = []

        try:
            project_name = f"projects/{self.project_id}"
            sa_request = iam_admin_v1.ListServiceAccountsRequest(name=project_name)

            for sa in self.iam_client.list_service_accounts(request=sa_request):
                # List keys for this service account
                key_request = iam_admin_v1.ListServiceAccountKeysRequest(name=sa.name)

                try:
                    key_list = self.iam_client.list_service_account_keys(request=key_request)

                    for key in key_list.keys:
                        key_dict = {
                            "service_account": sa.email,
                            "key_name": key.name,
                            "key_algorithm": key.key_algorithm.name if key.key_algorithm else None,
                            "key_type": key.key_type.name if key.key_type else None,
                            "valid_after_time": (
                                key.valid_after_time.isoformat() if key.valid_after_time else None
                            ),
                            "valid_before_time": (
                                key.valid_before_time.isoformat() if key.valid_before_time else None
                            ),
                        }

                        # Calculate key age if valid_after_time exists
                        if key.valid_after_time:
                            age_days = (
                                datetime.now(key.valid_after_time.tzinfo) - key.valid_after_time
                            ).days
                            key_dict["age_days"] = age_days
                            key_dict["age_warning"] = age_days > 90  # Flag keys older than 90 days

                        keys.append(key_dict)

                except Exception as e:
                    logger.warning("Error collecting keys for %s: %s", sa.email, e)

            logger.info("Collected %d service account keys", len(keys))
        except Exception as e:
            logger.error("Error collecting service account keys: %s", e)

        return keys
