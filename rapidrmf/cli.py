from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print

from .config import AppConfig, MinioStorageConfig, S3StorageConfig
from .collectors.terraform import collect_terraform
from .collectors.github_actions import collect_github_actions
from .collectors.gitlab import collect_gitlab
from .collectors.argo import collect_argo
from .collectors.azure import collect_azure
from .evidence import ArtifactRecord
from .reporting.report import readiness_summary, write_html
from .reporting.report import control_coverage_placeholder
from .reporting.validation_reports import generate_engineer_report, generate_auditor_report
from .storage.minio_backend import MinioEvidenceVault
from .storage.s3_backend import S3EvidenceVault
from .bundles import generate_ed25519_keypair, save_keypair, load_private_key, load_public_key, create_bundle, verify_bundle
from .validators import validate_controls, CONTROL_REQUIREMENTS, FAMILY_PATTERNS, get_control_requirement
from .scanners import run_scanners
from .waivers import WaiverRegistry


app = typer.Typer(help="RapidRMF utility CLI")


def _vault_from_envcfg(envcfg):
    if isinstance(envcfg.storage, MinioStorageConfig):
        return MinioEvidenceVault(
            endpoint=envcfg.storage.endpoint,
            bucket=envcfg.storage.bucket,
            access_key=envcfg.storage.access_key,
            secret_key=envcfg.storage.secret_key,
            secure=envcfg.storage.secure,
        )
    if isinstance(envcfg.storage, S3StorageConfig):
        return S3EvidenceVault(
            bucket=envcfg.storage.bucket,
            region=envcfg.storage.region,
            profile=envcfg.storage.profile,
        )
    raise typer.BadParameter("Unsupported storage backend")


@app.command()
def init_config(out: Path = typer.Option("config.yaml", help="Output config path")):
    """Create a starter config file."""
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    if not example.exists():
        raise typer.Exit(code=1)
    out_path = Path(out)
    out_path.write_text(example.read_text())
    print(f"[green]Wrote config template to {out_path}")


collect = typer.Typer(help="Collect CI/IaC evidence into vault")
app.add_typer(collect, name="collect")


@collect.command("terraform", help="Upload Terraform plan/apply and write manifest")
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
    vault = _vault_from_envcfg(envcfg)

    # Optional metadata can be added via CLI later if needed
    md = {}

    artifacts, manifest = collect_terraform(environment=env, plan_path=plan, apply_log_path=apply, extra_metadata=md)

    uploaded: list[ArtifactRecord] = []
    for a in artifacts:
        vault.put_file(plan if a.metadata.get("kind") == "terraform-plan" else (apply or plan), a.key, a.metadata)
        uploaded.append(a)

    manifest_key = f"manifests/{env}/terraform-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    print(f"[green]Uploaded {len(uploaded)} artifact(s) and manifest: {manifest_key}")
@collect.command("github", help="Fetch GitHub Actions logs/artifacts to vault")
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
    vault = _vault_from_envcfg(envcfg)

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
    print(f"[green]Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect.command("gitlab", help="Fetch GitLab pipeline logs/artifacts to vault")
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
    vault = _vault_from_envcfg(envcfg)

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
    print(f"[green]Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect.command("argo", help="Fetch Argo Workflow logs/artifacts to vault")
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
    vault = _vault_from_envcfg(envcfg)

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
    print(f"[green]Uploaded {uploaded} artifact(s) and manifest: {manifest_key}")


@collect.command("azure", help="Collect Azure resources evidence (storage, Key Vault, IAM, audit log, MFA)")
def collect_azure_cmd(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    subscription_id: str = typer.Option(..., help="Azure subscription ID"),
    resource_group: str = typer.Option(..., help="Azure resource group name"),
    storage_account: str = typer.Option(..., help="Storage account name"),
    key_vault: str = typer.Option(..., help="Key Vault name"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory for collected evidence (default: temp)"),
):
    """
    Collect Azure infrastructure evidence and upload to vault.
    
    Collects:
    - Storage Account configuration (encryption, HTTPS, TLS)
    - Storage Account role assignments (IAM)
    - Key Vault configuration (purge protection, soft delete)
    - Key Vault role assignments (IAM)
    - Activity log (24h audit trail)
    - Conditional Access policies (MFA enforcement)
    """
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = _vault_from_envcfg(envcfg)

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
        # For Azure, all artifacts are local JSON files in output_dir
        metadata = {k: v for k, v in a.metadata.items()}
        vault.put_json(a.key, a.metadata, metadata=metadata)  # Put manifest entry
        uploaded.append(a)

    manifest_key = f"manifests/{env}/azure-manifest.json"
    vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
    print(f"[green]Collected and uploaded {len(uploaded)} Azure artifact(s)")
    print(f"[green]Manifest: {manifest_key}")
    if output_dir:
        print(f"[green]Evidence files: {output_dir}")


report = typer.Typer(help="Generate compliance readiness reports")
app.add_typer(report, name="report")


@report.command("readiness", help="Generate HTML readiness report")
def report_readiness(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Environment key (e.g., edge)"),
    out: Path = typer.Option(Path("report.html"), help="Output HTML path"),
):
    # For MVP, we can't list from storage without extra APIs; use local manifests if staged
    # In future: list and fetch manifests from vault
    staging = Path(".rapidrmf_manifests")
    staging.mkdir(exist_ok=True)
    # Placeholder: write a dummy manifest if none exists
    if not any(staging.glob(f"{env}-*.json")):
        from .evidence import EvidenceManifest, ArtifactRecord
        dummy = EvidenceManifest.create(env, [ArtifactRecord(key="noop", filename="noop", sha256="0", size=0, metadata={})])
        (staging / f"{env}-dummy.json").write_text(dummy.to_json())

    manifests = []
    for p in staging.glob(f"{env}-*.json"):
        from .evidence import EvidenceManifest
        import json as _json
        data = _json.loads(p.read_text())
        # Rehydrate minimally
        m = EvidenceManifest(
            version=data["version"],
            environment=data["environment"],
            created_at=data["created_at"],
            artifacts=[ArtifactRecord(**a) for a in data["artifacts"]],
            overall_hash=data.get("overall_hash"),
            notes=data.get("notes"),
        )
        manifests.append(m)

    summary = readiness_summary(manifests)
    # Control coverage using catalogs and mapping rules
    try:
        from .oscal import load_oscal, OscalCatalog, OscalProfile
        from .mapping import ControlMapping, match_evidence_to_controls, compute_control_coverage
        from .validators import validate_controls

        cfg = AppConfig.load(config)
        control_ids = []
        
        # Load all configured catalogs/profiles
        for name, cat_path in cfg.catalogs.get_all_catalogs().items():
            oscal_obj = load_oscal(cat_path)
            if isinstance(oscal_obj, OscalCatalog):
                control_ids.extend(oscal_obj.control_ids())
            elif isinstance(oscal_obj, OscalProfile):
                # Profiles list imported controls
                imported = oscal_obj.imported_control_ids()
                if imported:
                    control_ids.extend(imported)
        
        # Remove duplicates while preserving order
        seen = set()
        control_ids = [x for x in control_ids if not (x in seen or seen.add(x))]
        
        # Load mapping rules if present
        mapping_path = Path("mapping.yaml")
        if not mapping_path.exists():
            mapping_path = Path("mapping.example.yaml")
        
        control_evidence = {}
        if mapping_path.exists():
            mapping = ControlMapping.from_yaml(mapping_path)
            control_evidence = match_evidence_to_controls(manifests, mapping)
            summary["controls"] = compute_control_coverage(control_ids, control_evidence)
        else:
            summary["controls"] = control_coverage_placeholder(control_ids, manifests)
        
        # Validate controls against evidence
        evidence_dict = {a.metadata.get("kind", "unknown"): True for m in manifests for a in m.artifacts}
        validation_results = validate_controls(control_ids, evidence_dict)
        summary["validation"] = {
            "passed": sum(1 for r in validation_results.values() if r.status.value == "pass"),
            "failed": sum(1 for r in validation_results.values() if r.status.value == "fail"),
            "insufficient": sum(1 for r in validation_results.values() if r.status.value == "insufficient_evidence"),
        }
        
        # Load and include waivers
        waiver_file = Path("waivers.yaml")
        if waiver_file.exists():
            registry = WaiverRegistry.from_yaml(waiver_file)
            summary["waivers"] = registry.summary()
    except Exception as e:
        summary["controls"] = {"error": f"failed to compute coverage: {e}"}
        summary["validation"] = {"error": str(e)}
    write_html(summary, out)
    print(f"[green]Wrote readiness report to {out}")

policy = typer.Typer(help="Policy evaluation tools (validate, conftest, wasm)")
app.add_typer(policy, name="policy")


@policy.command("validate", help="Validate controls from evidence + system state")
def policy_validate(
    evidence_file: Optional[Path] = typer.Option(None, help="JSON file with evidence dict"),
    system_state_file: Optional[Path] = typer.Option(None, help="JSON file with live system state"),
    out_json: Optional[Path] = typer.Option(None, help="Write validation results to JSON"),
    out_engineer: Optional[Path] = typer.Option(None, help="Write engineer-focused HTML report"),
    out_auditor: Optional[Path] = typer.Option(None, help="Write auditor-focused HTML report (with evidence)"),
    control_ids: Optional[str] = typer.Option(None, help="Comma-separated control IDs (default: all families)"),
):
    import json as _json
    from rapidrmf.validators import FAMILY_PATTERNS
    
    # Generate all control IDs from family patterns if not specified
    if control_ids:
        control_list = [c.strip() for c in control_ids.split(",")]
    else:
        # Generate comprehensive list across all families (sample representative controls)
        control_list = []
        for family in FAMILY_PATTERNS.keys():
            # Generate sample controls for each family (1-25 for most families)
            # This covers the typical range; adjust as needed
            control_list.extend([f"{family}-{i}" for i in range(1, 26)])
    
    evidence = {}
    if evidence_file:
        evidence = _json.loads(evidence_file.read_text())
    
    system_state = None
    if system_state_file:
        system_state = _json.loads(system_state_file.read_text())
    
    results = validate_controls(control_list, evidence, system_state)
    
    summary = {
        "passed": sum(1 for r in results.values() if r.status.value == "pass"),
        "failed": sum(1 for r in results.values() if r.status.value == "fail"),
        "insufficient": sum(1 for r in results.values() if r.status.value == "insufficient_evidence"),
        "controls": {
            cid: {
                "status": r.status.value,
                "message": r.message,
                "evidence_keys": r.evidence_keys,
                "metadata": r.metadata,
                "remediation": r.remediation,
            }
            for cid, r in results.items()
        },
    }
    
    print(f"[cyan]Validation: {summary['passed']} passed, {summary['failed']} failed, {summary['insufficient']} insufficient")
    
    if out_json:
        out_json.write_text(_json.dumps(summary, indent=2))
        print(f"[green]Wrote validation results to {out_json}")
    
    if out_engineer:
        generate_engineer_report(results, evidence, out_engineer)
        print(f"[green]Wrote engineer report to {out_engineer}")
    
    if out_auditor:
        generate_auditor_report(results, evidence, out_auditor)
        print(f"[green]Wrote auditor report to {out_auditor}")


@policy.command("conftest", help="Run Conftest (OPA/Rego) on a target")
def policy_conftest(
    target: Path = typer.Option(..., exists=True, help="Path to IaC directory or file"),
    policy_dir: Optional[Path] = typer.Option(None, exists=True, help="Path to Rego policy dir (optional)"),
    out_json: Optional[Path] = typer.Option(None, help="Write raw JSON results to this path"),
):
    from .policy.conftest_runner import run_conftest, conftest_available
    if not conftest_available():
        raise typer.BadParameter("conftest not found in PATH; install Conftest to use this command")
    results = run_conftest(target, policy_dir)
    summary = {
        "targets": len(results),
        "failures": sum(r.failures for r in results),
        "warnings": sum(r.warnings for r in results),
        "passes": sum(r.passes for r in results),
    }
    print(f"[cyan]Conftest summary: {summary}")
    if out_json:
        import json as _json
        out_json.write_text(_json.dumps([r.raw for r in results], indent=2))
        print(f"[green]Wrote raw Conftest JSON to {out_json}")


@policy.command("wasm", help="Evaluate compiled OPA WASM policy")
def policy_wasm(
    wasm_file: Path = typer.Option(..., exists=True, help="Path to OPA WASM policy file"),
    target: Path = typer.Option(..., exists=True, help="Path to target file (JSON/YAML/text)"),
    out_json: Optional[Path] = typer.Option(None, help="Write raw JSON results to this path"),
):
    from .policy.wasm_runner import wasm_available, evaluate_wasm_policy
    import json as _json
    if not wasm_available():
        raise typer.BadParameter("wasmtime not installed; run: pip install wasmtime")
    
    # Read target
    try:
        if target.suffix in (".json", ".yaml", ".yml"):
            input_data = _json.loads(target.read_text())
        else:
            input_data = {"path": str(target), "content": target.read_text()}
    except Exception as e:
        raise typer.BadParameter(f"Failed to read target: {e}")
    
    result = evaluate_wasm_policy(wasm_file, input_data)
    print(f"[cyan]WASM policy result: allowed={result.allowed}, violations={len(result.violations)}")
    if out_json:
        out_json.write_text(_json.dumps(result.raw, indent=2))
        print(f"[green]Wrote raw WASM result to {out_json}")


scan = typer.Typer(help="Compliance scanning (system, waivers)")
app.add_typer(scan, name="scan")


@scan.command("system", help="Run IAM/encryption/backup scanners")
def scan_system(
    config_file: Path = typer.Option(..., help="System config JSON"),
    out_json: Optional[Path] = typer.Option(None, help="Write scan results to JSON"),
):
    # Default scanner types
    scanner_types = ["iam", "encryption", "backup"]
    import json as _json
    config = _json.loads(config_file.read_text())
    results = run_scanners(config, scanner_types)
    
    summary = {
        "total_findings": sum(len(r.findings) for r in results.values()),
        "high_severity": sum(len([f for f in r.findings if f.get("severity") == "high"]) for r in results.values()),
        "scanners": {k: {"status": r.status, "findings": len(r.findings)} for k, r in results.items()},
    }
    
    print(f"[cyan]Scan complete: {summary['total_findings']} findings ({summary['high_severity']} high severity)")
    
    if out_json:
        out_json.write_text(_json.dumps({k: _json.loads(v.to_json()) for k, v in results.items()}, indent=2))
        print(f"[green]Wrote scan results to {out_json}")


@scan.command("waivers", help="Summarize waiver exceptions and expiries")
def scan_waivers(
    waivers_file: Path = typer.Option(Path("waivers.yaml"), help="Waivers YAML file"),
):
    registry = WaiverRegistry.from_yaml(waivers_file)
    summary = registry.summary()
    
    print(f"[cyan]Waivers: {summary['active']} active, {summary['expired']} expired, {summary['expiring_soon']} expiring soon")
    if summary['expiring_soon_ids']:
        print(f"[yellow]Expiring soon: {', '.join(summary['expiring_soon_ids'])}")


bundle = typer.Typer(help="Air-gap bundles (keygen, create, verify, import)")
app.add_typer(bundle, name="bundle")


@bundle.command("keygen", help="Generate Ed25519 keypair for bundles")
def bundle_keygen(
    out_dir: Path = typer.Option(Path(".keys"), help="Output directory for keys"),
    name: str = typer.Option("rapidrmf", help="Key name prefix"),
):
    out_dir.mkdir(parents=True, exist_ok=True)
    sk, pk = generate_ed25519_keypair()
    priv_path = out_dir / f"{name}.ed25519"
    pub_path = out_dir / f"{name}.ed25519.pub"
    save_keypair(sk, pk, priv_path, pub_path)
    print(f"[green]Wrote keys: {priv_path}, {pub_path}")


@bundle.command("create", help="Create signed bundle from vault prefix")
def bundle_create(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Source environment key"),
    key_prefix: str = typer.Option("manifests/", help="Prefix to include from vault"),
    private_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 private key"),
    out_path: Path = typer.Option(Path("evidence-bundle.tar.gz"), help="Output tar.gz path"),
    note: str = typer.Option("", help="Optional note"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = _vault_from_envcfg(envcfg)
    keys = vault.list(key_prefix)
    if not keys:
        raise typer.BadParameter(f"No objects under prefix '{key_prefix}' in environment '{env}'")

    staging = Path(cfg.staging_dir or ".rapidrmf_staging") / "bundle"
    staging.mkdir(parents=True, exist_ok=True)
    files = []
    for k in sorted(keys):
        out_file = staging / k
        vault.fetch(k, out_file)
        files.append((out_file, k))

    sk = load_private_key(private_key_path)
    create_bundle(environment=env, files=files, out_path=out_path, private_key=sk, note=note or None)
    print(f"[green]Created bundle at {out_path} with {len(files)} file(s)")


@bundle.command("verify", help="Verify bundle signature and manifest")
def bundle_verify_cmd(
    bundle_path: Path = typer.Option(..., exists=True, help="Path to evidence-bundle.tar.gz"),
    public_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 public key"),
):
    vk = load_public_key(public_key_path)
    manifest = verify_bundle(bundle_path, vk)
    print(f"[green]Bundle OK for environment '{manifest.environment}', items: {len(manifest.items)}")


@bundle.command("import", help="Verify bundle and import into vault")
def bundle_import(
    config: Path = typer.Option(..., exists=True, help="Path to config.yaml"),
    env: str = typer.Option(..., help="Target environment key"),
    bundle_path: Path = typer.Option(..., exists=True, help="Path to evidence-bundle.tar.gz"),
    public_key_path: Path = typer.Option(..., exists=True, help="Path to Ed25519 public key"),
    dest_prefix: str = typer.Option("", help="Optional destination prefix to prepend"),
):
    cfg = AppConfig.load(config)
    if env not in cfg.environments:
        raise typer.BadParameter(f"Unknown environment: {env}")
    envcfg = cfg.environments[env]
    vault = _vault_from_envcfg(envcfg)
    vk = load_public_key(public_key_path)
    manifest = verify_bundle(bundle_path, vk)

    import tarfile

    uploaded = 0
    with tarfile.open(bundle_path, "r:gz") as tar:
        for item in manifest.items:
            f = tar.extractfile(item.key)
            if not f:
                raise typer.BadParameter(f"missing file in bundle: {item.key}")
            tmp = Path(cfg.staging_dir or ".rapidrmf_staging") / "import" / item.key
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(f.read())
            dest_key = f"{dest_prefix}{item.key}" if dest_prefix else item.key
            vault.put_file(tmp, dest_key, metadata={"imported": "true"})
            uploaded += 1
    print(f"[green]Imported {uploaded} file(s) into environment '{env}'")


@app.command()
def check_catalogs(
    config: Path = typer.Option("config.yaml", exists=True, help="Path to config.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed catalog info"),
):
    """Validate configured OSCAL catalogs and profiles."""
    from rich.table import Table
    from rich.console import Console
    from .oscal import load_oscal, OscalCatalog, OscalProfile

    console = Console()
    
    try:
        cfg = AppConfig.load(config)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(code=1)

    catalogs_dict = cfg.catalogs.get_all_catalogs()
    
    if not catalogs_dict:
        console.print("[yellow]No catalogs configured in config.yaml[/yellow]")
        return

    table = Table(title="OSCAL Catalog/Profile Validation")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Title", style="white")
    table.add_column("Controls", justify="right", style="blue")

    total_valid = 0
    total_invalid = 0

    for name, path in catalogs_dict.items():
        try:
            oscal_obj = load_oscal(path)
            if oscal_obj is None:
                table.add_row(
                    name,
                    "Unknown",
                    "[red]Invalid[/red]",
                    "Could not load",
                    "—"
                )
                total_invalid += 1
                continue

            if isinstance(oscal_obj, OscalCatalog):
                control_ids = oscal_obj.control_ids()
                title = oscal_obj.metadata().get("title", "Untitled")
                table.add_row(
                    name,
                    "Catalog",
                    "[green]✓ Valid[/green]",
                    title,
                    str(len(control_ids))
                )
                total_valid += 1
                
                if verbose:
                    console.print(f"\n[cyan]{name}[/cyan] controls: {', '.join(control_ids[:10])}" + 
                                  (f" ... (+{len(control_ids)-10} more)" if len(control_ids) > 10 else ""))

            elif isinstance(oscal_obj, OscalProfile):
                imported_ids = oscal_obj.imported_control_ids()
                title = oscal_obj.title() or "Untitled"
                import_hrefs = oscal_obj.import_hrefs()
                table.add_row(
                    name,
                    "Profile",
                    "[green]✓ Valid[/green]",
                    title,
                    str(len(imported_ids)) if imported_ids else "—"
                )
                total_valid += 1
                
                if verbose:
                    console.print(f"\n[cyan]{name}[/cyan] imports: {', '.join(import_hrefs)}")
                    if imported_ids:
                        console.print(f"  Included controls: {', '.join(imported_ids[:10])}" + 
                                      (f" ... (+{len(imported_ids)-10} more)" if len(imported_ids) > 10 else ""))

        except Exception as e:
            table.add_row(
                name,
                "Error",
                "[red]✗ Invalid[/red]",
                str(e)[:50],
                "—"
            )
            total_invalid += 1

    console.print(table)
    console.print(f"\n[green]Valid: {total_valid}[/green] | [red]Invalid: {total_invalid}[/red]")

    if total_invalid > 0:
        raise typer.Exit(code=1)


@app.command()
def list_validators(
    filter_family: Optional[str] = typer.Option(None, "--family", "-f", help="Filter by control family (e.g., CM, AC, SC)"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all families including those with only pattern-based rules"),
):
    """List available control validators and their requirements."""
    from rich.table import Table
    from rich.console import Console

    console = Console()
    
    if show_all:
        # Show family patterns
        console.print("\n[bold cyan]Control Family Patterns:[/bold cyan]")
        console.print("[dim]These patterns apply to ALL controls in a family unless overridden[/dim]\n")
        
        family_table = Table()
        family_table.add_column("Family", style="cyan", no_wrap=True)
        family_table.add_column("Description", style="white")
        family_table.add_column("Required Any", style="yellow")
        family_table.add_column("Required All", style="green")
        
        for family_code in sorted(FAMILY_PATTERNS.keys()):
            if filter_family and family_code.upper() != filter_family.upper():
                continue
            pattern = FAMILY_PATTERNS[family_code]
            family_table.add_row(
                family_code,
                pattern.description_template,
                ", ".join(pattern.required_any) if pattern.required_any else "—",
                ", ".join(pattern.required_all) if pattern.required_all else "—",
            )
        
        console.print(family_table)
        console.print(f"\n[dim]Total families: {len(FAMILY_PATTERNS)}[/dim]\n")
    
    # Show specific control overrides
    console.print("\n[bold cyan]Specific Control Overrides:[/bold cyan]")
    console.print("[dim]These controls have custom requirements beyond family patterns[/dim]\n")
    
    table = Table()
    table.add_column("Control", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Required Any", style="yellow")
    table.add_column("Required All", style="green")

    for req in sorted(CONTROL_REQUIREMENTS.values(), key=lambda x: x.control_id):
        control_upper = req.control_id.upper()
        
        # Filter by family if specified
        if filter_family:
            family = control_upper.split("-")[0] if "-" in control_upper else ""
            if family.upper() != filter_family.upper():
                continue
        
        table.add_row(
            control_upper,
            req.description,
            ", ".join(req.required_any) if req.required_any else "—",
            ", ".join(req.required_all) if req.required_all else "—",
        )
    
    console.print(table)
    console.print(f"\n[dim]Specific overrides: {len(CONTROL_REQUIREMENTS)}[/dim]")
    console.print(f"[dim]Use --all flag to see family patterns covering all controls[/dim]")


@app.command()
def check_validator_coverage(
    config: Path = typer.Option("config.yaml", exists=True, help="Path to config.yaml"),
    profile: Optional[str] = typer.Option(None, help="Specific profile to check (e.g., fedramp_high)"),
):
    """Check validator coverage across all controls in configured catalogs."""
    from rich.console import Console
    from rich.table import Table
    from .oscal import load_oscal, OscalCatalog, OscalProfile

    console = Console()
    
    try:
        cfg = AppConfig.load(config)
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(code=1)

    catalogs_dict = cfg.catalogs.get_all_catalogs()
    
    if not catalogs_dict:
        console.print("[yellow]No catalogs configured[/yellow]")
        raise typer.Exit(code=1)
    
    # If profile specified, only check that one
    if profile:
        if profile not in catalogs_dict:
            console.print(f"[red]Profile '{profile}' not found in config[/red]")
            raise typer.Exit(code=1)
        catalogs_dict = {profile: catalogs_dict[profile]}
    
    table = Table(title="Validator Coverage Report")
    table.add_column("Catalog/Profile", style="cyan")
    table.add_column("Total Controls", justify="right", style="white")
    table.add_column("Covered", justify="right", style="green")
    table.add_column("Coverage %", justify="right", style="yellow")
    table.add_column("Method", style="dim")

    for name, path in catalogs_dict.items():
        oscal_obj = load_oscal(path)
        if oscal_obj is None:
            continue
        
        if isinstance(oscal_obj, OscalCatalog):
            control_ids = oscal_obj.control_ids()
        elif isinstance(oscal_obj, OscalProfile):
            control_ids = oscal_obj.imported_control_ids()
        else:
            continue
        
        if not control_ids:
            continue
        
        # Check coverage
        specific_overrides = 0
        family_patterns = 0
        uncovered = 0
        
        for cid in control_ids:
            req = get_control_requirement(cid)
            if req:
                if cid.lower() in CONTROL_REQUIREMENTS:
                    specific_overrides += 1
                else:
                    family_patterns += 1
            else:
                uncovered += 1
        
        covered = specific_overrides + family_patterns
        total = len(control_ids)
        pct = (covered / total * 100) if total > 0 else 0
        
        method = []
        if specific_overrides > 0:
            method.append(f"{specific_overrides} override")
        if family_patterns > 0:
            method.append(f"{family_patterns} pattern")
        if uncovered > 0:
            method.append(f"[red]{uncovered} uncovered[/red]")
        
        table.add_row(
            name,
            str(total),
            str(covered),
            f"{pct:.1f}%",
            ", ".join(method) if method else "—"
        )
    
    console.print(table)
    console.print("\n[dim]Coverage methods:[/dim]")
    console.print("  [cyan]override[/cyan] = specific control requirements")
    console.print("  [yellow]pattern[/yellow] = family-based pattern matching")


@app.command()
def test_validator(
    control_id: str = typer.Argument(..., help="Control ID to test (e.g., CM-2)"),
    evidence: str = typer.Option("", help="Comma-separated evidence types (e.g., terraform-plan,change-request)"),
):
    """Test a control validator with sample evidence."""
    from rich.console import Console
    from rich.panel import Panel
    from .validators import ValidationStatus

    console = Console()
    
    control_upper = control_id.upper()
    req = get_control_requirement(control_id)
    
    if not req:
        console.print(f"[red]No validator or family pattern found for {control_upper}[/red]")
        console.print("[yellow]Run 'list-validators --all' to see available patterns[/yellow]")
        raise typer.Exit(code=1)
    
    # Parse evidence
    evidence_set = set(e.strip() for e in evidence.split(",") if e.strip())
    
    console.print(f"\n[bold]Testing {control_upper}[/bold]")
    console.print(f"Validator source: {'[cyan]Specific override[/cyan]' if control_id.lower() in CONTROL_REQUIREMENTS else '[yellow]Family pattern[/yellow]'}")
    console.print(f"Evidence provided: {', '.join(evidence_set) if evidence_set else '(none)'}\n")
    
    # Run validation
    from .validators import ComplianceValidator
    validator = ComplianceValidator(req)
    result = validator.validate(evidence_set)
    
    # Display result
    status_color = {
        ValidationStatus.PASS: "green",
        ValidationStatus.FAIL: "red",
        ValidationStatus.INSUFFICIENT_EVIDENCE: "yellow",
        ValidationStatus.UNKNOWN: "dim",
    }
    
    color = status_color.get(result.status, "white")
    panel = Panel(
        f"[bold]{result.status.value.upper()}[/bold]\n\n"
        f"{result.message}\n\n"
        + (f"[dim]Remediation: {result.remediation}[/dim]" if result.remediation else ""),
        title=f"{control_upper} Validation",
        border_style=color,
    )
    
    console.print(panel)


if __name__ == "__main__":
    app()
