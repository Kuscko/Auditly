#!/usr/bin/env python3
"""
Generate RapidRMF system-config.json from Terraform outputs.
This automates the creation of system configuration for scanning Azure resources.

Usage:
    python generate_system_config.py [--terraform-dir ./] [--output system-config.json]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def get_terraform_outputs(terraform_dir: Path) -> Dict[str, Any]:
    """Run terraform output -json and parse results."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs = json.loads(result.stdout)
        # Terraform output format: {"key": {"value": "...", "type": "...", "sensitive": false}}
        return {k: v["value"] for k, v in outputs.items()}
    except subprocess.CalledProcessError as e:
        print(f"Error running terraform output: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing terraform output JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: terraform command not found. Ensure Terraform is installed and in PATH.", file=sys.stderr)
        sys.exit(1)


def generate_system_config(tf_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Terraform outputs into RapidRMF system-config format."""
    
    # Extract Azure resource details
    resource_group = tf_outputs.get("resource_group", "")
    storage_account = tf_outputs.get("storage_account", "")
    storage_blob_endpoint = tf_outputs.get("storage_blob_endpoint", "")
    storage_account_id = tf_outputs.get("storage_account_id", "")
    key_vault = tf_outputs.get("key_vault", "")
    log_analytics_workspace_id = tf_outputs.get("log_analytics_workspace_id", "")
    
    # Build system config matching scanner expectations
    config = {
        "metadata": {
            "generated_by": "terraform",
            "resource_group": resource_group,
            "description": "Azure test environment for RapidRMF validation",
        },
        
        # IAM Scanner inputs
        "iam_policies": [
            {
                "name": f"{key_vault}-rbac",
                "type": "Azure Key Vault RBAC",
                "resource": key_vault,
                "actions": ["read", "write"],  # Placeholder; update with actual RBAC
                "principals": ["system-assigned-identity"],
                "notes": "Key Vault RBAC authorization enabled",
            }
        ],
        "mfa_enforced": False,  # Update based on actual Azure AD configuration
        
        # Encryption Scanner inputs
        "rds": [],  # Azure SQL Database (none in current Terraform)
        "ebs": [],  # Azure Managed Disks (none in current Terraform)
        "storage_accounts": [
            {
                "name": storage_account,
                "id": storage_account_id,
                "storage_encrypted": True,  # Azure Storage Service Encryption always enabled
                "min_tls_version": "TLS1_2",
                "https_only": True,
                "blob_endpoint": storage_blob_endpoint,
            }
        ],
        "load_balancers": [],  # No load balancers in current config
        
        # Backup Scanner inputs
        "backup_policy": {
            "frequency_minutes": 1440,  # Daily (example)
            "retention_days": 7,
            "rto_minutes": 240,  # 4 hours (example)
            "rpo_minutes": 1440,  # Daily (example)
            "tested": False,  # Update when backup testing is implemented
        },
        
        # Additional Azure resources
        "key_vaults": [
            {
                "name": key_vault,
                "soft_delete_enabled": True,
                "purge_protection_enabled": True,
                "rbac_authorization_enabled": True,
                "public_network_access_enabled": False,
            }
        ],
        "log_analytics_workspaces": [
            {
                "id": log_analytics_workspace_id,
                "sku": "PerGB2018",
                "retention_days": 30,
            }
        ],
    }
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Generate RapidRMF system-config.json from Terraform outputs"
    )
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path("."),
        help="Path to Terraform directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("system-config.json"),
        help="Output file path (default: system-config.json)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    
    args = parser.parse_args()
    
    print(f"Reading Terraform outputs from: {args.terraform_dir}")
    tf_outputs = get_terraform_outputs(args.terraform_dir)
    
    print(f"Generating system configuration...")
    system_config = generate_system_config(tf_outputs)
    
    # Write output
    indent = 2 if args.pretty else None
    output_json = json.dumps(system_config, indent=indent)
    args.output.write_text(output_json)
    
    print(f"Generated {args.output}")
    print(f"\nNext steps:")
    print(f"  1. Review and customize {args.output} (update IAM policies, MFA status, etc.)")
    print(f"  2. Run scan: python -m rapidrmf scan system --config-file {args.output} --out-json scan-results.json")
    print(f"  3. Validate: python -m rapidrmf policy validate --system-state-file {args.output}")


if __name__ == "__main__":
    main()
