# GCP Evidence Collectors

Automated evidence collection for Google Cloud Platform (GCP) services to support compliance and security assessments.

## Overview

The GCP collectors package provides automated evidence gathering for key GCP services, with built-in NIST 800-53 control mappings and comprehensive security configuration documentation.

## Supported Services

| Service | Collector | Evidence Types |
|---------|-----------|----------------|
| **IAM** | `IAMCollector` | Service accounts, custom roles, IAM policies, SA keys |
| **Compute Engine** | `ComputeCollector` | Instances, disks, firewall rules, snapshots |
| **Cloud Storage** | `StorageCollector` | Buckets, IAM policies, lifecycle rules, encryption |
| **Cloud SQL** | `CloudSQLCollector` | Database instances, backups, SSL configuration |
| **VPC** | `VPCCollector` | Networks, subnets, VPN tunnels, routers |
| **Cloud KMS** | `KMSCollector` | Key rings, crypto keys, key versions, rotation |
| **Cloud Logging** | `LoggingCollector` | Log sinks, metrics, audit log configuration |

## Installation

```bash
pip install google-cloud-compute google-cloud-storage google-cloud-iam \
            google-cloud-logging google-cloud-sql google-cloud-kms \
            google-cloud-resource-manager
```

## Authentication

### Application Default Credentials (Recommended)

```bash
gcloud auth application-default login
```

### Service Account JSON

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

Or pass directly to GCPClient:

```python
from rapidrmf.collectors.gcp import GCPClient

client = GCPClient(credentials_path="/path/to/service-account-key.json")
```

## Required IAM Permissions

### IAM Collector
- `iam.serviceAccounts.list`
- `iam.serviceAccounts.get`
- `iam.roles.list`
- `iam.roles.get`
- `iam.serviceAccountKeys.list`
- `resourcemanager.projects.getIamPolicy`

### Compute Engine Collector
- `compute.instances.list`
- `compute.disks.list`
- `compute.firewalls.list`
- `compute.snapshots.list`

### Cloud Storage Collector
- `storage.buckets.list`
- `storage.buckets.get`
- `storage.buckets.getIamPolicy`

### Cloud SQL Collector
- `cloudsql.instances.list`
- `cloudsql.instances.get`

### VPC Collector
- `compute.networks.list`
- `compute.subnetworks.list`
- `compute.vpnTunnels.list`
- `compute.routers.list`

### Cloud KMS Collector
- `cloudkms.keyRings.list`
- `cloudkms.cryptoKeys.list`
- `cloudkms.cryptoKeyVersions.list`

### Cloud Logging Collector
- `logging.sinks.list`
- `logging.logMetrics.list`

## Usage Examples

### CLI Usage

```bash
# Collect all GCP evidence
rapidrmf collect gcp --config config.yaml --env production \
  --project-id my-project

# Specific services only
rapidrmf collect gcp --config config.yaml --env production \
  --project-id my-project \
  --services iam,compute,storage

# Using service account credentials
rapidrmf collect gcp --config config.yaml --env production \
  --project-id my-project \
  --credentials-path service-account.json

# Save evidence files locally
rapidrmf collect gcp --config config.yaml --env production \
  --project-id my-project \
  --output-dir ./evidence
```

### Python API Usage

#### Basic Collection

```python
from rapidrmf.collectors.gcp import GCPClient, IAMCollector

# Initialize client
client = GCPClient(project_id="my-project")

# Collect IAM evidence
collector = IAMCollector(client)
evidence = collector.collect_all()

print(f"Found {len(evidence['service_accounts'])} service accounts")
print(f"Evidence checksum: {evidence['metadata']['sha256']}")
```

#### Multi-Service Collection

```python
from rapidrmf.collectors.gcp import (
    GCPClient,
    IAMCollector,
    ComputeCollector,
    StorageCollector,
)

client = GCPClient(project_id="my-project")

collectors = [
    ("iam", IAMCollector(client)),
    ("compute", ComputeCollector(client)),
    ("storage", StorageCollector(client)),
]

for name, collector in collectors:
    evidence = collector.collect_all()
    print(f"{name}: {len(evidence)} evidence types collected")
```

#### Advanced: Organization-Level Collection

```python
from rapidrmf.collectors.gcp import GCPClient, IAMCollector

client = GCPClient()

# List all projects in organization
projects = client.list_projects()

for project in projects:
    project_id = project.project_id
    print(f"Collecting from project: {project_id}")
    
    # Create client for this project
    project_client = GCPClient(project_id=project_id)
    collector = IAMCollector(project_client)
    
    evidence = collector.collect_all()
    # Process evidence...
```

## Evidence Schema

All collectors return evidence in this structure:

```python
{
    "metadata": {
        "evidence": "gcp-<service>",
        "service": "<service>",
        "project_id": "my-project",
        "collected_at": "2024-01-15T10:30:00Z",
        "sha256": "abc123...",
        "controls": ["AC-2", "AC-3", ...]
    },
    "<evidence_type_1>": [...],
    "<evidence_type_2>": [...],
    ...
}
```

### IAM Evidence Schema

```python
{
    "metadata": {...},
    "service_accounts": [
        {
            "name": "projects/my-project/serviceAccounts/sa@project.iam.gserviceaccount.com",
            "email": "sa@project.iam.gserviceaccount.com",
            "display_name": "My Service Account",
            "disabled": false,
            "description": "Service account for..."
        }
    ],
    "custom_roles": [
        {
            "name": "projects/my-project/roles/customRole",
            "title": "Custom Role",
            "permissions": ["compute.instances.get", ...],
            "stage": "GA"
        }
    ],
    "iam_policies": [
        {
            "bindings": [
                {
                    "role": "roles/owner",
                    "members": ["user:alice@example.com"],
                    "condition": {...}
                }
            ]
        }
    ],
    "service_account_keys": [
        {
            "name": "projects/my-project/serviceAccounts/.../keys/...",
            "key_type": "USER_MANAGED",
            "valid_after_time": "2024-01-01T00:00:00Z",
            "valid_before_time": "9999-12-31T23:59:59Z",
            "key_age_days": 45,
            "needs_rotation": false
        }
    ]
}
```

### Compute Engine Evidence Schema

```python
{
    "metadata": {...},
    "instances": [
        {
            "id": "1234567890",
            "name": "instance-1",
            "zone": "us-central1-a",
            "machine_type": "n1-standard-1",
            "status": "RUNNING",
            "deletion_protection": true,
            "disks": [...],
            "network_interfaces": [...],
            "service_accounts": [...],
            "metadata": {...}
        }
    ],
    "disks": [
        {
            "id": "9876543210",
            "name": "disk-1",
            "zone": "us-central1-a",
            "type": "pd-standard",
            "size_gb": 100,
            "status": "READY",
            "source_image": "projects/debian-cloud/global/images/debian-11...",
            "disk_encryption_key": {...}
        }
    ],
    "firewalls": [...],
    "snapshots": [...]
}
```

### Cloud Storage Evidence Schema

```python
{
    "metadata": {...},
    "buckets": [
        {
            "id": "bucket-id",
            "name": "my-bucket",
            "location": "US",
            "storage_class": "STANDARD",
            "versioning_enabled": true,
            "lifecycle_rules": [...],
            "iam_configuration": {
                "uniform_bucket_level_access": {
                    "enabled": true
                },
                "public_access_prevention": "enforced"
            },
            "encryption": {
                "default_kms_key_name": "projects/.../locations/.../keyRings/.../cryptoKeys/..."
            },
            "cors": [...],
            "retention_policy": {...}
        }
    ]
}
```

### Cloud SQL Evidence Schema

```python
{
    "metadata": {...},
    "instances": [
        {
            "name": "my-database",
            "database_version": "POSTGRES_14",
            "region": "us-central1",
            "state": "RUNNABLE",
            "settings": {
                "tier": "db-n1-standard-1",
                "availability_type": "REGIONAL",
                "backup_configuration": {
                    "enabled": true,
                    "start_time": "03:00",
                    "point_in_time_recovery_enabled": true,
                    "binary_log_enabled": true,
                    "transaction_log_retention_days": 7
                },
                "ip_configuration": {
                    "ipv4_enabled": true,
                    "require_ssl": true,
                    "private_network": "projects/.../global/networks/default"
                },
                "database_flags": [...]
            },
            "disk_encryption_configuration": {...}
        }
    ]
}
```

### VPC Evidence Schema

```python
{
    "metadata": {...},
    "networks": [
        {
            "id": "12345",
            "name": "default",
            "auto_create_subnetworks": false,
            "routing_config": {
                "routing_mode": "REGIONAL"
            },
            "mtu": 1460
        }
    ],
    "subnetworks": [
        {
            "id": "67890",
            "name": "subnet-1",
            "region": "us-central1",
            "network": "projects/my-project/global/networks/default",
            "ip_cidr_range": "10.0.1.0/24",
            "private_ip_google_access": true,
            "log_config": {
                "enable": true,
                "flow_sampling": 0.5
            }
        }
    ],
    "vpn_tunnels": [...],
    "routers": [...]
}
```

### Cloud KMS Evidence Schema

```python
{
    "metadata": {...},
    "key_rings": [
        {
            "name": "projects/my-project/locations/us-central1/keyRings/my-keyring",
            "location": "us-central1"
        }
    ],
    "crypto_keys": [
        {
            "name": "projects/.../keyRings/my-keyring/cryptoKeys/my-key",
            "purpose": "ENCRYPT_DECRYPT",
            "rotation_period": "7776000s",
            "next_rotation_time": "2024-04-01T00:00:00Z",
            "primary": {
                "name": "projects/.../cryptoKeyVersions/1",
                "state": "ENABLED",
                "protection_level": "HSM",
                "algorithm": "GOOGLE_SYMMETRIC_ENCRYPTION"
            },
            "versions": [...]
        }
    ]
}
```

### Cloud Logging Evidence Schema

```python
{
    "metadata": {...},
    "sinks": [
        {
            "name": "projects/my-project/sinks/audit-sink",
            "destination": "storage.googleapis.com/audit-logs-bucket",
            "filter": "logName:cloudaudit.googleapis.com",
            "disabled": false,
            "output_version_format": "V2"
        }
    ],
    "metrics": [
        {
            "name": "projects/my-project/metrics/error-count",
            "filter": "severity >= ERROR",
            "metric_descriptor": {
                "metric_kind": "DELTA",
                "value_type": "INT64"
            }
        }
    ],
    "logs_summary": {
        "admin_activity": true,
        "data_access": true,
        "system_event": true,
        "policy_denied": false
    }
}
```

## NIST 800-53 Control Mappings

| Collector | Controls |
|-----------|----------|
| **IAM** | AC-2 (Account Management), AC-3 (Access Enforcement), AC-6 (Least Privilege), IA-4 (Identifier Management), IA-5 (Authenticator Management) |
| **Compute** | AC-4 (Information Flow Enforcement), SC-7 (Boundary Protection), SC-12 (Cryptographic Key Establishment), SC-13 (Cryptographic Protection), SC-28 (Protection of Information at Rest), SI-2 (Flaw Remediation) |
| **Storage** | AC-3 (Access Enforcement), AC-6 (Least Privilege), SC-7 (Boundary Protection), SC-12 (Cryptographic Key Establishment), SC-13 (Cryptographic Protection), SC-28 (Protection of Information at Rest), SI-12 (Information Handling) |
| **SQL** | SC-8 (Transmission Confidentiality), SC-12 (Cryptographic Key Establishment), SC-13 (Cryptographic Protection), SC-28 (Protection of Information at Rest), SI-4 (Information System Monitoring), CP-9 (Information System Backup) |
| **VPC** | SC-7 (Boundary Protection), SC-8 (Transmission Confidentiality), SC-12 (Cryptographic Key Establishment), SI-4 (Information System Monitoring) |
| **KMS** | SC-12 (Cryptographic Key Establishment), SC-13 (Cryptographic Protection), SI-16 (Memory Protection) |
| **Logging** | AU-2 (Audit Events), AU-3 (Content of Audit Records), AU-4 (Audit Storage Capacity), AU-6 (Audit Review), AU-9 (Protection of Audit Information), AU-12 (Audit Generation) |

## Troubleshooting

### Authentication Errors

```python
# Error: Default credentials are not available
# Solution: Set up application default credentials
$ gcloud auth application-default login

# Or use service account
$ export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### Permission Denied Errors

```python
# Error: Permission denied on resource
# Solution: Grant required IAM roles to your principal

# For read-only evidence collection:
$ gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:you@example.com" \
    --role="roles/viewer"

# For more granular permissions, create custom role with required permissions
```

### Project Not Found

```python
# Error: Project not found or not specified
# Solution: Explicitly set project ID

client = GCPClient(project_id="my-project-id")
```

### Large Project Collections

```python
# For projects with many resources, use pagination and filtering

from rapidrmf.collectors.gcp import ComputeCollector, GCPClient

client = GCPClient(project_id="large-project")
collector = ComputeCollector(client)

# Collectors automatically handle pagination
evidence = collector.collect_all()
```

## Performance Considerations

- **API Quotas**: GCP has rate limits. Collectors use exponential backoff for retries.
- **Pagination**: All collectors handle pagination automatically.
- **Parallel Collection**: Collect from multiple projects in parallel for faster results.
- **Caching**: GCPClient caches service clients to avoid repeated initialization.

## Best Practices

1. **Use Application Default Credentials** in production environments
2. **Grant minimal IAM permissions** (roles/viewer or custom read-only role)
3. **Collect regularly** (daily or weekly) for trend analysis
4. **Store evidence securely** with encryption at rest
5. **Review collected evidence** for sensitive data before sharing
6. **Monitor API usage** to avoid quota exhaustion
7. **Version evidence** using Git or dedicated versioning system

## Contributing

When adding new collectors:

1. Follow the existing collector pattern
2. Include NIST 800-53 control mappings
3. Add comprehensive error handling
4. Include docstrings with examples
5. Add integration tests
6. Update this README

## License

See main project LICENSE file.
