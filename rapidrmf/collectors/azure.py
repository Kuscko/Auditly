from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence import ArtifactRecord, EvidenceManifest, sha256_file


def _run_az_command(cmd: List[str]) -> str:
    """Run Azure CLI command and return JSON output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Azure CLI command failed: {e.stderr}")


def _create_json_file(data: Any, path: Path) -> Path:
    """Create a JSON file and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def collect_azure(
    environment: str,
    subscription_id: str,
    resource_group: str,
    storage_account: str,
    key_vault: str,
    output_dir: Optional[Path | str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    key_prefix: str = "azure",
) -> (List[ArtifactRecord], EvidenceManifest):
    """
    Collect Azure resources evidence (storage, Key Vault, IAM, activity log, MFA).

    Args:
        environment: Environment name (e.g., 'edge', 'prod')
        subscription_id: Azure subscription ID
        resource_group: Azure resource group name
        storage_account: Storage account name
        key_vault: Key Vault name
        output_dir: Directory to store collected evidence
        extra_metadata: Additional metadata to include in manifest
        key_prefix: Prefix for artifact keys in vault

    Returns:
        Tuple of (artifacts, manifest)
    """
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / "azure-evidence"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: List[ArtifactRecord] = []

    # Ensure subscription is set
    _run_az_command(["az", "account", "set", "--subscription", subscription_id])

    # 1. Collect Storage Account details
    print(f"Collecting storage account {storage_account}...")
    storage_json = _run_az_command(
        [
            "az",
            "storage",
            "account",
            "show",
            "--name",
            storage_account,
            "--resource-group",
            resource_group,
        ]
    )
    storage_data = json.loads(storage_json)
    storage_path = _create_json_file(storage_data, output_dir / "storage-account.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/storage/{storage_path.name}",
            filename=storage_path.name,
            sha256=sha256_file(storage_path),
            size=storage_path.stat().st_size,
            metadata={
                "kind": "azure-storage-account",
                "resource": storage_account,
                **(extra_metadata or {}),
            },
        )
    )

    # 2. Collect Storage Account role assignments
    print("Collecting storage account roles...")
    storage_scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}"
    storage_roles_json = _run_az_command(
        ["az", "role", "assignment", "list", "--scope", storage_scope]
    )
    storage_roles_data = json.loads(storage_roles_json) if storage_roles_json else []
    storage_roles_path = _create_json_file(
        storage_roles_data, output_dir / "storage-role-assignments.json"
    )
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/roles/{storage_roles_path.name}",
            filename=storage_roles_path.name,
            sha256=sha256_file(storage_roles_path),
            size=storage_roles_path.stat().st_size,
            metadata={
                "kind": "azure-role-assignments",
                "resource": storage_account,
                **(extra_metadata or {}),
            },
        )
    )

    # 3. Collect Key Vault details
    print(f"Collecting Key Vault {key_vault}...")
    kv_json = _run_az_command(
        ["az", "keyvault", "show", "--name", key_vault, "--resource-group", resource_group]
    )
    kv_data = json.loads(kv_json)
    kv_path = _create_json_file(kv_data, output_dir / "keyvault.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/keyvault/{kv_path.name}",
            filename=kv_path.name,
            sha256=sha256_file(kv_path),
            size=kv_path.stat().st_size,
            metadata={"kind": "azure-keyvault", "resource": key_vault, **(extra_metadata or {})},
        )
    )

    # 4. Collect Key Vault role assignments
    print("Collecting Key Vault roles...")
    kv_scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.KeyVault/vaults/{key_vault}"
    kv_roles_json = _run_az_command(["az", "role", "assignment", "list", "--scope", kv_scope])
    kv_roles_data = json.loads(kv_roles_json) if kv_roles_json else []
    kv_roles_path = _create_json_file(kv_roles_data, output_dir / "keyvault-role-assignments.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/roles/{kv_roles_path.name}",
            filename=kv_roles_path.name,
            sha256=sha256_file(kv_roles_path),
            size=kv_roles_path.stat().st_size,
            metadata={
                "kind": "azure-role-assignments",
                "resource": key_vault,
                **(extra_metadata or {}),
            },
        )
    )

    # 5. Collect Activity Log (24h)
    print("Collecting activity log...")
    activity_json = _run_az_command(
        [
            "az",
            "monitor",
            "activity-log",
            "list",
            "--resource-group",
            resource_group,
            "--offset",
            "24h",
        ]
    )
    activity_data = json.loads(activity_json) if activity_json else []
    activity_path = _create_json_file(activity_data, output_dir / "activity-log.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/audit/{activity_path.name}",
            filename=activity_path.name,
            sha256=sha256_file(activity_path),
            size=activity_path.stat().st_size,
            metadata={"kind": "azure-activity-log", "lookback": "24h", **(extra_metadata or {})},
        )
    )

    # 6. Collect Conditional Access policies (MFA config)
    print("Collecting conditional access policies...")
    try:
        ca_json = _run_az_command(
            [
                "az",
                "rest",
                "--method",
                "GET",
                "--url",
                "https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies",
            ]
        )
        ca_data = json.loads(ca_json) if ca_json else {"value": []}
    except RuntimeError as e:
        # Graph permissions may not be available
        print(f"Warning: Could not fetch conditional access policies: {e}")
        ca_data = {"value": [], "error": "insufficient_permissions"}

    ca_path = _create_json_file(ca_data, output_dir / "conditional-access-policies.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/mfa/{ca_path.name}",
            filename=ca_path.name,
            sha256=sha256_file(ca_path),
            size=ca_path.stat().st_size,
            metadata={"kind": "azure-conditional-access", **(extra_metadata or {})},
        )
    )

    # 7. Create consolidated evidence summary
    print("Creating evidence summary...")
    evidence_summary = {
        "encryption-config": {
            "path": str(storage_path.absolute()),
            "type": "encryption-configuration",
            "sources": [
                {"type": "storage-account", "file": str(storage_path.absolute())},
                {"type": "key-vault", "file": str(kv_path.absolute())},
            ],
        },
        "iam-policy": {
            "path": str(storage_roles_path.absolute()),
            "type": "identity-access-management",
            "sources": [
                {"type": "storage-roles", "file": str(storage_roles_path.absolute())},
                {"type": "keyvault-roles", "file": str(kv_roles_path.absolute())},
            ],
        },
        "audit-trail": {
            "path": str(activity_path.absolute()),
            "type": "audit-trail",
            "sources": [{"type": "activity-log", "file": str(activity_path.absolute())}],
        },
        "mfa-config": {
            "path": str(ca_path.absolute()),
            "type": "multi-factor-authentication",
            "sources": [{"type": "conditional-access", "file": str(ca_path.absolute())}],
        },
    }

    evidence_path = _create_json_file(evidence_summary, output_dir / "evidence.json")
    artifacts.append(
        ArtifactRecord(
            key=f"{key_prefix}/manifest/{evidence_path.name}",
            filename=evidence_path.name,
            sha256=sha256_file(evidence_path),
            size=evidence_path.stat().st_size,
            metadata={"kind": "evidence-manifest", **(extra_metadata or {})},
        )
    )

    manifest = EvidenceManifest.create(
        environment=environment,
        artifacts=artifacts,
        notes=f"azure collection: {resource_group} ({len(artifacts)} artifacts)",
    )

    return artifacts, manifest
