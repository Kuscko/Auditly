# AWS Evidence Collectors

Comprehensive AWS evidence collection for compliance automation and control validation.

## Features

### IAM Evidence Collection ✅
- **Users**: MFA status, access keys, password policy compliance, attached policies, group membership
- **Roles**: Trust policies, attached policies, inline policies, assume role configuration
- **Policies**: Managed and inline policies with full policy documents
- **Groups**: Group membership, attached policies
- **Password Policy**: Account-level password requirements
- **Account Summary**: Resource counts and MFA status

### Coming Soon
- **EC2**: Instances, security groups, EBS encryption, snapshots
- **S3**: Bucket policies, encryption, versioning, access logs
- **CloudTrail**: Event history, management events, data events
- **VPC**: Flow logs, network ACLs, route tables, NAT gateways
- **RDS**: Instance configs, encryption, backup retention
- **KMS**: Key policies, rotation status, usage audit

## Installation

Ensure boto3 is installed:
```bash
pip install boto3
```

## Usage

### CLI Command

```bash
# Collect IAM evidence
rapidrmf collect aws \
  --config config.yaml \
  --env production \
  --region us-east-1 \
  --profile my-aws-profile \
  --services iam \
  --output-dir ./evidence

# Multiple services (when implemented)
rapidrmf collect aws \
  --config config.yaml \
  --env production \
  --services iam,ec2,s3,cloudtrail
```

### Python API

```python
from rapidrmf.collectors.aws import AWSClient, IAMCollector

# Initialize client
client = AWSClient(
    region="us-east-1",
    profile_name="my-profile"  # or use access_key_id/secret_access_key
)

# Collect IAM evidence
iam_collector = IAMCollector(client)
evidence = iam_collector.collect_all()

# Evidence structure
print(f"Collected {len(evidence['users'])} users")
print(f"Collected {len(evidence['roles'])} roles")
print(f"Collected {len(evidence['policies'])} policies")
```

## Authentication

The AWS collector supports multiple authentication methods:

### 1. AWS CLI Profile (Recommended)
```bash
aws configure --profile my-profile
rapidrmf collect aws --profile my-profile
```

### 2. Environment Variables
```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."  # Optional for temporary credentials
rapidrmf collect aws
```

### 3. Programmatic Credentials
```python
client = AWSClient(
    region="us-east-1",
    access_key_id="AKIA...",
    secret_access_key="...",
    session_token="..."  # Optional
)
```

### 4. Default Credential Chain
Uses boto3's default credential resolution:
- Environment variables
- AWS credentials file (~/.aws/credentials)
- IAM role (when running on EC2/ECS/Lambda)

## Evidence Schema

### IAM Evidence Structure

```json
{
  "users": [
    {
      "user_name": "john.doe",
      "user_id": "AIDAI...",
      "arn": "arn:aws:iam::123456789012:user/john.doe",
      "create_date": "2024-01-01T00:00:00",
      "password_last_used": "2026-01-17T00:00:00",
      "mfa_enabled": true,
      "mfa_devices": [
        {
          "serial_number": "arn:aws:iam::123456789012:mfa/john.doe",
          "enable_date": "2024-01-01T00:00:00"
        }
      ],
      "access_keys": [
        {
          "access_key_id": "AKIA...",
          "status": "Active",
          "create_date": "2024-01-01T00:00:00"
        }
      ],
      "attached_policies": [
        {
          "policy_name": "ReadOnlyAccess",
          "policy_arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"
        }
      ],
      "inline_policies": [],
      "groups": ["Developers"]
    }
  ],
  "roles": [
    {
      "role_name": "EC2-S3-Access",
      "role_id": "AROAI...",
      "arn": "arn:aws:iam::123456789012:role/EC2-S3-Access",
      "create_date": "2024-01-01T00:00:00",
      "assume_role_policy": { /* trust policy document */ },
      "max_session_duration": 3600,
      "attached_policies": [],
      "inline_policies": []
    }
  ],
  "policies": [
    {
      "policy_name": "CustomPolicy",
      "policy_id": "ANPAI...",
      "arn": "arn:aws:iam::123456789012:policy/CustomPolicy",
      "create_date": "2024-01-01T00:00:00",
      "update_date": "2024-06-01T00:00:00",
      "attachment_count": 2,
      "is_attachable": true,
      "default_version_id": "v1",
      "policy_document": { /* policy document */ }
    }
  ],
  "groups": [
    {
      "group_name": "Developers",
      "group_id": "AGPAI...",
      "arn": "arn:aws:iam::123456789012:group/Developers",
      "create_date": "2024-01-01T00:00:00",
      "members": ["john.doe", "jane.smith"],
      "attached_policies": [],
      "inline_policies": []
    }
  ],
  "password_policy": {
    "minimum_password_length": 14,
    "require_symbols": true,
    "require_numbers": true,
    "require_uppercase": true,
    "require_lowercase": true,
    "allow_users_to_change": true,
    "expire_passwords": true,
    "max_password_age": 90,
    "password_reuse_prevention": 24,
    "hard_expiry": false
  },
  "account_summary": {
    "users": 42,
    "groups": 5,
    "roles": 18,
    "policies": 23,
    "mfa_devices": 38,
    "account_mfa_enabled": 0
  },
  "metadata": {
    "collected_at": "2026-01-17T00:00:00",
    "account_id": "123456789012",
    "region": "us-east-1",
    "collector": "aws-iam",
    "version": "1.0.0",
    "sha256": "abc123..."
  }
}
```

## Control Mapping

IAM evidence supports validation of NIST 800-53 controls including:

- **AC-2 (Account Management)**: User creation, MFA status, access keys
- **AC-3 (Access Enforcement)**: IAM policies, role permissions
- **AC-6 (Least Privilege)**: Policy analysis, role trust policies
- **IA-2 (Identification and Authentication)**: MFA requirements
- **IA-4 (Identifier Management)**: User lifecycle management
- **IA-5 (Authenticator Management)**: Password policy, access key rotation

## Performance

- **IAM Collection**: ~5-10 seconds for typical account (100 users, 50 roles)
- **Pagination**: Automatic handling of large result sets
- **Caching**: Client reuse for multiple service calls
- **Rate Limiting**: Automatic backoff for API throttling

## Error Handling

The collector handles:
- Missing credentials → Clear error message with authentication options
- Insufficient permissions → Logs warning, continues with available data
- API throttling → Automatic retry with exponential backoff
- Service unavailable → Logs error, continues with other services

## Security

- **No credential storage**: Uses boto3's secure credential chain
- **Least privilege**: Only requires read permissions (e.g., `iam:List*`, `iam:Get*`)
- **Encryption**: Evidence encrypted in transit (TLS) and at rest (vault)
- **Audit trail**: All collections logged with timestamps and account IDs

## IAM Permissions Required

Minimal IAM policy for evidence collection:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:ListUsers",
        "iam:GetUser",
        "iam:ListMFADevices",
        "iam:ListAccessKeys",
        "iam:ListAttachedUserPolicies",
        "iam:ListUserPolicies",
        "iam:ListGroupsForUser",
        "iam:ListRoles",
        "iam:GetRole",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:ListPolicies",
        "iam:GetPolicy",
        "iam:GetPolicyVersion",
        "iam:ListGroups",
        "iam:GetGroup",
        "iam:ListAttachedGroupPolicies",
        "iam:ListGroupPolicies",
        "iam:GetAccountPasswordPolicy",
        "iam:GetAccountSummary",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

## Testing

```bash
# Run IAM collector tests
pytest tests/test_aws_iam_collector.py

# Integration test with real AWS account (requires credentials)
pytest tests/integration/test_aws_collection.py --aws-profile my-profile
```

## Next Steps

See [V0.3_CORE_ROADMAP.md](../../V0.3_CORE_ROADMAP.md) for upcoming AWS collectors:
- EC2 (Week 5)
- S3 (Week 5)
- CloudTrail (Week 6)
- VPC (Week 6)
- RDS (Week 6)
- KMS (Week 6)
