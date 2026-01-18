from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .config import AppConfig
from .collectors.terraform import collect_terraform
from .collectors.github_actions import collect_github_actions
from .collectors.gitlab import collect_gitlab
from .collectors.argo import collect_argo
from .collectors.azure import collect_azure
from .evidence import ArtifactRecord
from .cli_common import vault_from_envcfg, persist_if_db

# Import AWS collectors
try:
    from .collectors.aws import (
        AWSClient,
        IAMCollector,
        EC2Collector,
        S3Collector,
        CloudTrailCollector,
        VPCCollector,
        RDSCollector,
        KMSCollector,
    )
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

# Import GCP collectors
try:
    from .collectors.gcp import (
        GCPClient,
        IAMCollector as GCPIAMCollector,
        ComputeCollector,
        StorageCollector,
        CloudSQLCollector,
        VPCCollector as GCPVPCCollector,
        KMSCollector as GCPKMSCollector,
        LoggingCollector,
    )
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

collect_app = typer.Typer(help="Collect CI/IaC evidence into vault")


@collect_app.command("terraform", help="Upload Terraform plan/apply and write manifest")
def collect_terraform_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    plan: Path = typer.Option(..., exists=True, help="Path to terraform plan artifact"),
    apply: Optional[Path] = typer.Option(None, exists=True, help="Path to terraform apply log"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)

    md = {}
    artifacts, manifest = collect_terraform(environment=env, plan_path=plan, apply_log_path=apply, extra_metadata=md)

    uploaded: list[ArtifactRecord] = []
    for a in artifacts:
        vault.put_file(plan if a.metadata.get("kind") == "terraform-plan" else (apply or plan), a.key, a.metadata)
        uploaded.append(a)

    manifest_key = f"manifests/{env}/terraform-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    persist_if_db(envcfg, env, manifest, uploaded)
    typer.echo(f"Uploaded {len(uploaded)} artifact(s) and manifest: {manifest_key}")


@collect_app.command("github", help="Fetch GitHub Actions logs/artifacts to vault")
def collect_github_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    repo: str = typer.Option(..., help="GitHub repo 'owner/name'"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN", help="GitHub token or env GITHUB_TOKEN"),
    run_id: Optional[int] = typer.Option(None, help="Specific run id; if not set, uses latest (optionally by branch)"),
    branch: Optional[str] = typer.Option(None, help="Branch to filter latest run"),
):
    if not token:
        raise typer.BadParameter("GitHub token required (use --token or set GITHUB_TOKEN)")
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)

    artifacts, manifest, run = collect_github_actions(environment=env, repo=repo, token=token, run_id=run_id, branch=branch)

    uploaded = 0
    for a in artifacts:
        local_path = a.metadata.get("_local_path")
        if not local_path:
            continue
        vault.put_file(local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"})
        uploaded += 1

    manifest_key = f"manifests/{env}/github-run-{run.id}.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    persist_if_db(envcfg, env, manifest, artifacts)
    typer.echo(f"Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect_app.command("gitlab", help="Fetch GitLab pipeline logs/artifacts to vault")
def collect_gitlab_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    base_url: str = typer.Option("https://gitlab.com", help="GitLab instance URL"),
    project_id: str = typer.Option(..., help="GitLab project ID or 'namespace/project'"),
    token: Optional[str] = typer.Option(None, envvar="GITLAB_TOKEN", help="GitLab token or env GITLAB_TOKEN"),
    pipeline_id: Optional[int] = typer.Option(None, help="Specific pipeline id; if not set, uses latest (optionally by ref)"),
    ref: Optional[str] = typer.Option(None, help="Ref (branch/tag) to filter latest pipeline"),
):
    if not token:
        raise typer.BadParameter("GitLab token required (use --token or set GITLAB_TOKEN)")
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)

    artifacts, manifest, pipeline = collect_gitlab(
        environment=env,
        base_url=base_url,
        project_id=project_id,
        token=token,
        pipeline_id=pipeline_id,
        ref=ref,
    )

    uploaded = 0
    for a in artifacts:
        local_path = a.metadata.get("_local_path")
        if not local_path:
            continue
        vault.put_file(local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"})
        uploaded += 1

    manifest_key = f"manifests/{env}/gitlab-pipeline-{pipeline.id}.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    persist_if_db(envcfg, env, manifest, artifacts)
    typer.echo(f"Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect_app.command("argo", help="Fetch Argo Workflow logs/artifacts to vault")
def collect_argo_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    base_url: str = typer.Option(..., help="Argo Server URL (e.g., https://argo-server:2746)"),
    namespace: str = typer.Option("argo", help="Kubernetes namespace"),
    workflow_name: Optional[str] = typer.Option(None, help="Specific workflow name; if not set, uses latest"),
    token: Optional[str] = typer.Option(None, envvar="ARGO_TOKEN", help="Argo token or env ARGO_TOKEN (optional)"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)

    artifacts, manifest, workflow = collect_argo(
        environment=env,
        base_url=base_url,
        namespace=namespace,
        workflow_name=workflow_name,
        token=token,
    )

    uploaded = 0
    for a in artifacts:
        local_path = a.metadata.get("_local_path")
        if not local_path:
            continue
        vault.put_file(local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"})
        uploaded += 1

    manifest_key = f"manifests/{env}/argo-workflow-{workflow.name}.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    persist_if_db(envcfg, env, manifest, artifacts)
    typer.echo(f"Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect_app.command("azure", help="Collect Azure resources evidence (storage, Key Vault, IAM, audit log, MFA)")
def collect_azure_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    subscription_id: str = typer.Option(..., help="Azure subscription ID"),
    resource_group: str = typer.Option(..., help="Azure resource group name"),
    storage_account: str = typer.Option(..., help="Storage account name"),
    key_vault: str = typer.Option(..., help="Key Vault name"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory for collected evidence (default: temp)"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)

    artifacts, manifest = collect_azure(
        environment=env,
        subscription_id=subscription_id,
        resource_group=resource_group,
        storage_account=storage_account,
        key_vault=key_vault,
        output_dir=output_dir,
    )

    uploaded: list[ArtifactRecord] = []
    for a in artifacts:
        metadata = {k: v for k, v in a.metadata.items()}
        vault.put_json(a.key, a.metadata, metadata=metadata)
        uploaded.append(a)

    manifest_key = f"manifests/{env}/azure-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    persist_if_db(envcfg, env, manifest, artifacts)
    typer.echo(f"Collected and uploaded {len(uploaded)} Azure artifact(s)")
    typer.echo(f"Manifest: {manifest_key}")
    if output_dir:
        typer.echo(f"Evidence files: {output_dir}")


@collect_app.command("aws", help="Collect AWS evidence (IAM, EC2, S3, etc.)")
def collect_aws_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., production)"),
    region: str = typer.Option("us-east-1", help="AWS region"),
    profile: Optional[str] = typer.Option(None, help="AWS CLI profile name"),
    services: str = typer.Option("iam,ec2,s3,cloudtrail,vpc,rds,kms", help="Comma-separated services to collect"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory for evidence files"),
):
    """Collect evidence from AWS services.
    
    Supported services: iam, ec2, s3, cloudtrail, vpc, rds, kms
    """
    if not AWS_AVAILABLE:
        typer.echo("Error: boto3 not installed. Install with: pip install boto3", err=True)
        raise typer.Exit(code=1)
    
    import json
    import tempfile
    from datetime import datetime
    from .evidence import ArtifactRecord, EvidenceManifest
    
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)
    
    # Parse services
    service_list = [s.strip().lower() for s in services.split(",")]
    valid_services = ["iam", "ec2", "s3", "cloudtrail", "vpc", "rds", "kms"]
    invalid_services = [s for s in service_list if s not in valid_services]
    if invalid_services:
        typer.echo(f"Error: Invalid services {invalid_services}. Valid: {', '.join(valid_services)}", err=True)
        raise typer.Exit(code=1)
    
    # Initialize AWS client
    try:
        client = AWSClient(region=region, profile_name=profile)
        account_id = client.get_account_id()
        typer.echo(f"Connected to AWS account: {account_id} (region: {region})")
    except Exception as e:
        typer.echo(f"Error connecting to AWS: {e}", err=True)
        raise typer.Exit(code=1)
    
    # Collect evidence
    artifacts: list[ArtifactRecord] = []
    collected_at = datetime.utcnow().isoformat()
    
    for service in service_list:
        typer.echo(f"Collecting evidence from AWS {service}...")
        
        try:
            if service == "iam":
                collector = IAMCollector(client)
                evidence = collector.collect_all()
                summary = f"users={len(evidence.get('users', []))}, roles={len(evidence.get('roles', []))}, policies={len(evidence.get('policies', []))}"
                
            elif service == "ec2":
                collector = EC2Collector(client)
                evidence = collector.collect_all()
                summary = f"instances={len(evidence.get('instances', []))}, sg={len(evidence.get('security_groups', []))}, volumes={len(evidence.get('volumes', []))}"
                
            elif service == "s3":
                collector = S3Collector(client)
                evidence = collector.collect_all()
                summary = f"buckets={len(evidence.get('buckets', []))}, policies={len(evidence.get('policies', []))}"
                
            elif service == "cloudtrail":
                collector = CloudTrailCollector(client)
                evidence = collector.collect_all()
                summary = f"trails={len(evidence.get('trails', []))}, events={len(evidence.get('events', []))}"
                
            elif service == "vpc":
                collector = VPCCollector(client)
                evidence = collector.collect_all()
                summary = f"flow_logs={len(evidence.get('flow_logs', []))}, nacls={len(evidence.get('nacls', []))}"
                
            elif service == "rds":
                collector = RDSCollector(client)
                evidence = collector.collect_all()
                summary = f"instances={len(evidence.get('instances', []))}, clusters={len(evidence.get('clusters', []))}"
                
            elif service == "kms":
                collector = KMSCollector(client)
                evidence = collector.collect_all()
                summary = f"keys={len(evidence.get('keys', []))}, policies={len(evidence.get('policies', []))}"
            
            # Save evidence to temp file or output dir
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                evidence_file = output_dir / f"aws-{service}-{collected_at}.json"
                evidence_file.write_text(json.dumps(evidence, indent=2, default=str))
            else:
                evidence_file = Path(tempfile.mktemp(suffix=".json"))
                evidence_file.write_text(json.dumps(evidence, indent=2, default=str))
            
            # Create artifact record
            artifact = ArtifactRecord(
                key=f"evidence/{env}/aws-{service}-{account_id}.json",
                sha256=evidence["metadata"]["sha256"],
                size=evidence_file.stat().st_size,
                metadata={
                    "kind": f"aws-{service}",
                    "service": service,
                    "account_id": account_id,
                    "region": region,
                    "collected_at": collected_at,
                    "_local_path": str(evidence_file),
                }
            )
            artifacts.append(artifact)
            
            # Upload to vault
            vault.put_json(artifact.key, evidence, metadata=artifact.metadata)
            typer.echo(f"  ✓ {summary}")
            
        except Exception as e:
            typer.echo(f"  ✗ Error collecting {service}: {e}", err=True)
            continue
    
    if not artifacts:
        typer.echo("No evidence collected.", err=True)
        raise typer.Exit(code=1)
    
    # Create manifest
    manifest = EvidenceManifest(
        environment=env,
        artifacts=artifacts,
        overall_hash=EvidenceManifest.compute_overall_hash([a.sha256 for a in artifacts]),
        notes=f"AWS evidence collection: {', '.join(service_list)}",
        attributes={
            "account_id": account_id,
            "region": region,
            "services": service_list,
            "collected_at": collected_at,
        }
    )
    
    # Upload manifest
    manifest_key = f"manifests/{env}/aws-{'-'.join(service_list)}-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    
    # Persist to database if configured
    persist_if_db(envcfg, env, manifest, artifacts)
    
    typer.echo(f"\n✓ Collected {len(artifacts)} artifact(s) from AWS")
    typer.echo(f"✓ Manifest: {manifest_key}")
    if output_dir:
        typer.echo(f"✓ Evidence files: {output_dir}")


@collect_app.command("gcp", help="Collect GCP evidence (IAM, Compute, Storage, etc.)")
def collect_gcp_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., production)"),
    project_id: Optional[str] = typer.Option(None, help="GCP project ID (auto-detect if not provided)"),
    credentials_path: Optional[Path] = typer.Option(None, exists=True, help="Path to service account JSON"),
    services: str = typer.Option("iam,compute,storage,sql,vpc,kms,logging", help="Comma-separated services"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory for evidence files"),
):
    """Collect evidence from GCP services.
    
    Supported services: iam, compute, storage, sql, vpc, kms, logging
    """
    if not GCP_AVAILABLE:
        typer.echo("Error: google-cloud libraries not installed. Install with: "
                   "pip install google-cloud-compute google-cloud-storage google-cloud-iam "
                   "google-cloud-logging google-cloud-sql google-cloud-kms", err=True)
        raise typer.Exit(code=1)
    
    import json
    import tempfile
    from datetime import datetime
    from .evidence import ArtifactRecord, EvidenceManifest
    
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = vault_from_envcfg(envcfg)
    
    # Parse services
    service_list = [s.strip().lower() for s in services.split(",")]
    valid_services = ["iam", "compute", "storage", "sql", "vpc", "kms", "logging"]
    invalid_services = [s for s in service_list if s not in valid_services]
    if invalid_services:
        typer.echo(f"Error: Invalid services {invalid_services}. Valid: {', '.join(valid_services)}", err=True)
        raise typer.Exit(code=1)
    
    # Initialize GCP client
    try:
        client = GCPClient(
            project_id=project_id,
            credentials_path=str(credentials_path) if credentials_path else None,
        )
        project_id = client.project_id
        typer.echo(f"Connected to GCP project: {project_id}")
    except Exception as e:
        typer.echo(f"Error connecting to GCP: {e}", err=True)
        raise typer.Exit(code=1)
    
    # Collect evidence
    artifacts: list[ArtifactRecord] = []
    collected_at = datetime.utcnow().isoformat()
    
    for service in service_list:
        typer.echo(f"Collecting evidence from GCP {service}...")
        
        try:
            if service == "iam":
                collector = GCPIAMCollector(client)
                evidence = collector.collect_all()
                summary = f"service_accounts={len(evidence.get('service_accounts', []))}, roles={len(evidence.get('custom_roles', []))}"
                
            elif service == "compute":
                collector = ComputeCollector(client)
                evidence = collector.collect_all()
                summary = f"instances={len(evidence.get('instances', []))}, disks={len(evidence.get('disks', []))}, firewalls={len(evidence.get('firewalls', []))}"
                
            elif service == "storage":
                collector = StorageCollector(client)
                evidence = collector.collect_all()
                summary = f"buckets={len(evidence.get('buckets', []))}"
                
            elif service == "sql":
                collector = CloudSQLCollector(client)
                evidence = collector.collect_all()
                summary = f"instances={len(evidence.get('instances', []))}"
                
            elif service == "vpc":
                collector = GCPVPCCollector(client)
                evidence = collector.collect_all()
                summary = f"networks={len(evidence.get('networks', []))}, subnets={len(evidence.get('subnetworks', []))}"
                
            elif service == "kms":
                collector = GCPKMSCollector(client)
                evidence = collector.collect_all()
                summary = f"key_rings={len(evidence.get('key_rings', []))}, keys={len(evidence.get('crypto_keys', []))}"
                
            elif service == "logging":
                collector = LoggingCollector(client)
                evidence = collector.collect_all()
                summary = f"sinks={len(evidence.get('sinks', []))}, metrics={len(evidence.get('metrics', []))}"
            
            # Save evidence to temp file or output dir
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                evidence_file = output_dir / f"gcp-{service}-{collected_at}.json"
                evidence_file.write_text(json.dumps(evidence, indent=2, default=str))
            else:
                evidence_file = Path(tempfile.mktemp(suffix=".json"))
                evidence_file.write_text(json.dumps(evidence, indent=2, default=str))
            
            # Create artifact record
            artifact = ArtifactRecord(
                key=f"evidence/{env}/gcp-{service}-{project_id}.json",
                filename=f"gcp-{service}-{project_id}.json",
                sha256=evidence["metadata"]["sha256"],
                size=evidence_file.stat().st_size,
                metadata={
                    "kind": f"gcp-{service}",
                    "service": service,
                    "project_id": project_id,
                    "collected_at": collected_at,
                    "_local_path": str(evidence_file),
                }
            )
            artifacts.append(artifact)
            
            # Upload to vault
            vault.put_json(artifact.key, evidence, metadata=artifact.metadata)
            typer.echo(f"  ✓ {summary}")
            
        except Exception as e:
            typer.echo(f"  ✗ Error collecting {service}: {e}", err=True)
            continue
    
    if not artifacts:
        typer.echo("No evidence collected.", err=True)
        raise typer.Exit(code=1)
    
    # Create manifest
    manifest = EvidenceManifest(
        version="1.0",
        environment=env,
        created_at=datetime.utcnow().timestamp(),
        artifacts=artifacts,
        notes=f"GCP evidence collection: {', '.join(service_list)}",
    )
    
    manifest.compute_overall_hash()
    
    # Upload manifest
    manifest_key = f"manifests/{env}/gcp-{'-'.join(service_list)}-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    
    # Persist to database if configured
    persist_if_db(envcfg, env, manifest, artifacts)
    
    typer.echo(f"\n✓ Collected {len(artifacts)} artifact(s) from GCP")
    typer.echo(f"✓ Manifest: {manifest_key}")
    if output_dir:
        typer.echo(f"✓ Evidence files: {output_dir}")
