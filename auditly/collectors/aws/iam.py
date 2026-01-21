"""AWS IAM evidence collector for auditly.

Collects IAM evidence including:
- Users (MFA status, access keys, password policy compliance)
- Roles (trust policies, attached policies)
- Policies (managed and inline policies)
- Groups (membership, attached policies)
- Password policy
- Account summary
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


class IAMCollector:
    """Collector for AWS IAM evidence."""

    def __init__(self, client: AWSClient):
        """Initialize IAM collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.iam = client.get_client("iam")

    def collect_all(self) -> dict[str, Any]:
        """Collect all IAM evidence.

        Returns:
            Dictionary containing all IAM evidence:
            {
                "users": [...],
                "roles": [...],
                "policies": [...],
                "groups": [...],
                "password_policy": {...},
                "account_summary": {...},
                "metadata": {...}
            }
        """
        logger.info("Starting AWS IAM evidence collection")

        data = {
            "users": self.collect_users(),
            "roles": self.collect_roles(),
            "policies": self.collect_policies(),
            "groups": self.collect_groups(),
            "password_policy": self.collect_password_policy(),
            "account_summary": self.collect_account_summary(),
        }
        evidence = finalize_evidence(
            data,
            collector="aws-iam",
            account_id=self.client.get_account_id(),
            region=self.client.region,
        )

        logger.info(
            "IAM collection complete: %d users, %d roles, %d policies",
            len(evidence["users"]),
            len(evidence["roles"]),
            len(evidence["policies"]),
        )

        return evidence

    def collect_users(self) -> list[dict[str, Any]]:
        """Collect IAM users with MFA status and access keys.

        Returns:
            List of user dictionaries with enhanced metadata
        """
        users = []

        try:
            paginator = self.iam.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    user_name = user["UserName"]

                    # Get MFA devices
                    mfa_devices = self._get_mfa_devices(user_name)

                    # Get access keys
                    access_keys = self._get_access_keys(user_name)

                    # Get attached policies
                    attached_policies = self._get_attached_user_policies(user_name)

                    # Get inline policies
                    inline_policies = self._get_inline_user_policies(user_name)

                    # Get groups
                    groups = self._get_user_groups(user_name)

                    users.append(
                        {
                            "user_name": user_name,
                            "user_id": user["UserId"],
                            "arn": user["Arn"],
                            "create_date": user["CreateDate"].isoformat(),
                            "password_last_used": user.get("PasswordLastUsed", "").isoformat()
                            if user.get("PasswordLastUsed")
                            else None,
                            "mfa_enabled": len(mfa_devices) > 0,
                            "mfa_devices": mfa_devices,
                            "access_keys": access_keys,
                            "attached_policies": attached_policies,
                            "inline_policies": inline_policies,
                            "groups": groups,
                        }
                    )

            logger.debug("Collected %d IAM users", len(users))
        except ClientError as e:
            logger.error("Failed to collect IAM users: %s", e)

        return users

    def collect_roles(self) -> list[dict[str, Any]]:
        """Collect IAM roles with trust policies and permissions.

        Returns:
            List of role dictionaries
        """
        roles = []

        try:
            paginator = self.iam.get_paginator("list_roles")
            for page in paginator.paginate():
                for role in page["Roles"]:
                    role_name = role["RoleName"]

                    # Get attached policies
                    attached_policies = self._get_attached_role_policies(role_name)

                    # Get inline policies
                    inline_policies = self._get_inline_role_policies(role_name)

                    roles.append(
                        {
                            "role_name": role_name,
                            "role_id": role["RoleId"],
                            "arn": role["Arn"],
                            "create_date": role["CreateDate"].isoformat(),
                            "assume_role_policy": role["AssumeRolePolicyDocument"],
                            "max_session_duration": role.get("MaxSessionDuration"),
                            "attached_policies": attached_policies,
                            "inline_policies": inline_policies,
                        }
                    )

            logger.debug("Collected %d IAM roles", len(roles))
        except ClientError as e:
            logger.error("Failed to collect IAM roles: %s", e)

        return roles

    def collect_policies(self, scope: str = "Local") -> list[dict[str, Any]]:
        """Collect IAM policies (customer managed).

        Args:
            scope: Policy scope - 'Local' for customer managed, 'AWS' for AWS managed

        Returns:
            List of policy dictionaries
        """
        policies = []

        try:
            paginator = self.iam.get_paginator("list_policies")
            for page in paginator.paginate(Scope=scope):
                for policy in page["Policies"]:
                    policy_arn = policy["Arn"]

                    # Get default policy version document
                    policy_document = self._get_policy_version(
                        policy_arn, policy["DefaultVersionId"]
                    )

                    policies.append(
                        {
                            "policy_name": policy["PolicyName"],
                            "policy_id": policy["PolicyId"],
                            "arn": policy_arn,
                            "create_date": policy["CreateDate"].isoformat(),
                            "update_date": policy["UpdateDate"].isoformat(),
                            "attachment_count": policy["AttachmentCount"],
                            "is_attachable": policy["IsAttachable"],
                            "default_version_id": policy["DefaultVersionId"],
                            "policy_document": policy_document,
                        }
                    )

            logger.debug("Collected %d IAM policies (scope=%s)", len(policies), scope)
        except ClientError as e:
            logger.error("Failed to collect IAM policies: %s", e)

        return policies

    def collect_groups(self) -> list[dict[str, Any]]:
        """Collect IAM groups with members and policies.

        Returns:
            List of group dictionaries
        """
        groups = []

        try:
            paginator = self.iam.get_paginator("list_groups")
            for page in paginator.paginate():
                for group in page["Groups"]:
                    group_name = group["GroupName"]

                    # Get group members
                    members = self._get_group_members(group_name)

                    # Get attached policies
                    attached_policies = self._get_attached_group_policies(group_name)

                    # Get inline policies
                    inline_policies = self._get_inline_group_policies(group_name)

                    groups.append(
                        {
                            "group_name": group_name,
                            "group_id": group["GroupId"],
                            "arn": group["Arn"],
                            "create_date": group["CreateDate"].isoformat(),
                            "members": members,
                            "attached_policies": attached_policies,
                            "inline_policies": inline_policies,
                        }
                    )

            logger.debug("Collected %d IAM groups", len(groups))
        except ClientError as e:
            logger.error("Failed to collect IAM groups: %s", e)

        return groups

    def collect_password_policy(self) -> dict[str, Any] | None:
        """Collect account password policy.

        Returns:
            Password policy dictionary or None if not set
        """
        try:
            response = self.iam.get_account_password_policy()
            policy = response["PasswordPolicy"]
            logger.debug("Collected IAM password policy")
            return {
                "minimum_password_length": policy.get("MinimumPasswordLength"),
                "require_symbols": policy.get("RequireSymbols"),
                "require_numbers": policy.get("RequireNumbers"),
                "require_uppercase": policy.get("RequireUppercaseCharacters"),
                "require_lowercase": policy.get("RequireLowercaseCharacters"),
                "allow_users_to_change": policy.get("AllowUsersToChangePassword"),
                "expire_passwords": policy.get("ExpirePasswords"),
                "max_password_age": policy.get("MaxPasswordAge"),
                "password_reuse_prevention": policy.get("PasswordReusePrevention"),
                "hard_expiry": policy.get("HardExpiry"),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.warning("No password policy set for account")
            else:
                logger.error("Failed to get password policy: %s", e)
            return None

    def collect_account_summary(self) -> dict[str, Any]:
        """Collect IAM account summary.

        Returns:
            Account summary with resource counts
        """
        try:
            response = self.iam.get_account_summary()
            summary = response["SummaryMap"]
            logger.debug("Collected IAM account summary")
            return {
                "users": summary.get("Users", 0),
                "groups": summary.get("Groups", 0),
                "roles": summary.get("Roles", 0),
                "policies": summary.get("Policies", 0),
                "mfa_devices": summary.get("MFADevices", 0),
                "account_mfa_enabled": summary.get("AccountMFAEnabled", 0),
            }
        except ClientError as e:
            logger.error("Failed to get account summary: %s", e)
            return {}

    # Helper methods

    def _get_mfa_devices(self, user_name: str) -> list[dict[str, str]]:
        """Get MFA devices for a user."""
        try:
            response = self.iam.list_mfa_devices(UserName=user_name)
            return [
                {
                    "serial_number": device["SerialNumber"],
                    "enable_date": device["EnableDate"].isoformat(),
                }
                for device in response.get("MFADevices", [])
            ]
        except ClientError:
            return []

    def _get_access_keys(self, user_name: str) -> list[dict[str, Any]]:
        """Get access keys for a user."""
        try:
            response = self.iam.list_access_keys(UserName=user_name)
            return [
                {
                    "access_key_id": key["AccessKeyId"],
                    "status": key["Status"],
                    "create_date": key["CreateDate"].isoformat(),
                }
                for key in response.get("AccessKeyMetadata", [])
            ]
        except ClientError:
            return []

    def _get_attached_user_policies(self, user_name: str) -> list[dict[str, str]]:
        """Get attached managed policies for a user."""
        try:
            response = self.iam.list_attached_user_policies(UserName=user_name)
            return [
                {"policy_name": p["PolicyName"], "policy_arn": p["PolicyArn"]}
                for p in response.get("AttachedPolicies", [])
            ]
        except ClientError:
            return []

    def _get_inline_user_policies(self, user_name: str) -> list[str]:
        """Get inline policy names for a user."""
        try:
            response = self.iam.list_user_policies(UserName=user_name)
            return response.get("PolicyNames", [])
        except ClientError:
            return []

    def _get_user_groups(self, user_name: str) -> list[str]:
        """Get groups for a user."""
        try:
            response = self.iam.list_groups_for_user(UserName=user_name)
            return [g["GroupName"] for g in response.get("Groups", [])]
        except ClientError:
            return []

    def _get_attached_role_policies(self, role_name: str) -> list[dict[str, str]]:
        """Get attached managed policies for a role."""
        try:
            response = self.iam.list_attached_role_policies(RoleName=role_name)
            return [
                {"policy_name": p["PolicyName"], "policy_arn": p["PolicyArn"]}
                for p in response.get("AttachedPolicies", [])
            ]
        except ClientError:
            return []

    def _get_inline_role_policies(self, role_name: str) -> list[str]:
        """Get inline policy names for a role."""
        try:
            response = self.iam.list_role_policies(RoleName=role_name)
            return response.get("PolicyNames", [])
        except ClientError:
            return []

    def _get_attached_group_policies(self, group_name: str) -> list[dict[str, str]]:
        """Get attached managed policies for a group."""
        try:
            response = self.iam.list_attached_group_policies(GroupName=group_name)
            return [
                {"policy_name": p["PolicyName"], "policy_arn": p["PolicyArn"]}
                for p in response.get("AttachedPolicies", [])
            ]
        except ClientError:
            return []

    def _get_inline_group_policies(self, group_name: str) -> list[str]:
        """Get inline policy names for a group."""
        try:
            response = self.iam.list_group_policies(GroupName=group_name)
            return response.get("PolicyNames", [])
        except ClientError:
            return []

    def _get_group_members(self, group_name: str) -> list[str]:
        """Get members of a group."""
        try:
            response = self.iam.get_group(GroupName=group_name)
            return [u["UserName"] for u in response.get("Users", [])]
        except ClientError:
            return []

    def _get_policy_version(self, policy_arn: str, version_id: str) -> dict | None:
        """Get policy version document."""
        try:
            response = self.iam.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
            return response["PolicyVersion"]["Document"]
        except ClientError:
            return None
