"""Core API operations - reuses existing CLI/collection/validation logic."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from ..cli_common import persist_if_db, vault_from_envcfg
from ..collectors.argo import collect_argo
from ..collectors.azure import collect_azure
from ..collectors.github_actions import collect_github_actions
from ..collectors.gitlab import collect_gitlab
from ..collectors.terraform import collect_terraform
from ..config import AppConfig
from ..evidence import ArtifactRecord, EvidenceManifest
from ..mapping import ControlMapping, compute_control_coverage, match_evidence_to_controls
from ..oscal import OscalCatalog, OscalProfile, load_oscal
from ..performance import parallel_collector
from ..reporting.report import readiness_summary, write_html
from ..reporting.validation_reports import generate_auditor_report, generate_engineer_report
from ..validators import validate_controls
from ..waivers import WaiverRegistry


async def collect_evidence_parallel(
    requests: list[dict[str, Any]],
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    """Collect evidence for multiple providers in parallel.

    Each request dict should contain the arguments for ``collect_evidence``.
    Synchronous collectors run in a thread via ``asyncio.to_thread``.

    Returns the parallel collector aggregate payload containing results/errors.
    """

    async def _run(req: dict[str, Any]) -> Any:
        return await asyncio.to_thread(collect_evidence, **req)

    # mypy expects Future[Any] for collect_parallel
    tasks: dict[str, asyncio.Future[Any]] = {}
    for idx, req in enumerate(requests):
        name = req.get("name", f"request-{idx}")
        tasks[name] = asyncio.ensure_future(_run(req))

    return await parallel_collector.collect_parallel(tasks, timeout=timeout)


def collect_evidence_batch(
    requests: list[dict[str, Any]],
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    """Synchronize batch evidence collection for multiple systems."""
    return asyncio.run(collect_evidence_parallel(requests, timeout=timeout))


def collect_evidence(
    config_path: str, environment: str, provider: str, **provider_params
) -> tuple[int, str, str]:
    """
    Collect evidence from a provider (reuses CLI collection logic).

    Args:
        config_path: Path to config.yaml
        environment: Environment key
        provider: Provider type (terraform, github, gitlab, argo, azure)
        **provider_params: Provider-specific parameters

    Returns:
        Tuple of (artifacts_uploaded, manifest_key, message)

    Raises:
        ValueError: If provider is unsupported or required params missing
        Exception: Collection errors
    """
    cfg = AppConfig.load(config_path)
    if environment not in cfg.environments:
        raise ValueError(f"Unknown environment: {environment}")

    envcfg = cfg.environments[environment]
    vault = vault_from_envcfg(envcfg)

    artifacts: list[ArtifactRecord] = []
    manifest = None
    manifest_key = ""

    if provider == "terraform":
        plan_path = provider_params.get("terraform_plan_path")
        apply_path = provider_params.get("terraform_apply_path")

        if not plan_path:
            raise ValueError("terraform_plan_path is required for terraform provider")

        plan = Path(plan_path)
        apply = Path(apply_path) if apply_path else None

        if not plan.exists():
            raise ValueError(f"Terraform plan not found: {plan_path}")
        if apply and not apply.exists():
            raise ValueError(f"Terraform apply log not found: {apply_path}")

        artifacts, manifest = collect_terraform(
            environment=environment, plan_path=plan, apply_log_path=apply, extra_metadata={}
        )

        for a in artifacts:
            vault.put_file(
                plan if a.metadata.get("kind") == "terraform-plan" else (apply or plan),
                a.key,
                a.metadata,
            )

        manifest_key = f"manifests/{environment}/terraform-manifest.json"
        vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
        persist_if_db(envcfg, environment, manifest, artifacts)

    elif provider == "github":
        repo = provider_params.get("github_repo")
        token = provider_params.get("github_token")
        run_id = provider_params.get("github_run_id")
        branch = provider_params.get("github_branch")

        if not repo or not token:
            raise ValueError("github_repo and github_token are required for github provider")

        artifacts, manifest, run = collect_github_actions(
            environment=environment, repo=repo, token=token, run_id=run_id, branch=branch
        )

        uploaded = 0
        for a in artifacts:
            local_path = a.metadata.get("_local_path")
            if local_path:
                vault.put_file(
                    local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"}
                )
                uploaded += 1

        manifest_key = f"manifests/{environment}/github-run-{run.id}.json"
        vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
        persist_if_db(envcfg, environment, manifest, artifacts)

    elif provider == "gitlab":
        base_url = provider_params.get("gitlab_base_url", "https://gitlab.com")
        project_id = provider_params.get("gitlab_project_id")
        token = provider_params.get("gitlab_token")
        pipeline_id = provider_params.get("gitlab_pipeline_id")
        ref = provider_params.get("gitlab_ref")

        if not project_id or not token:
            raise ValueError("gitlab_project_id and gitlab_token are required for gitlab provider")

        artifacts, manifest, pipeline = collect_gitlab(
            environment=environment,
            base_url=base_url,
            project_id=project_id,
            token=token,
            pipeline_id=pipeline_id,
            ref=ref,
        )

        uploaded = 0
        for a in artifacts:
            local_path = a.metadata.get("_local_path")
            if local_path:
                vault.put_file(
                    local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"}
                )
                uploaded += 1

        manifest_key = f"manifests/{environment}/gitlab-pipeline-{pipeline.id}.json"
        vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
        persist_if_db(envcfg, environment, manifest, artifacts)

    elif provider == "argo":
        base_url = provider_params.get("argo_base_url")
        namespace = provider_params.get("argo_namespace")
        workflow_name = provider_params.get("argo_workflow_name")
        token = provider_params.get("argo_token")

        if not all([base_url, namespace, workflow_name]):
            raise ValueError(
                "argo_base_url, argo_namespace, and argo_workflow_name "
                "are required for argo provider"
            )

        # namespace is required as str
        artifacts, manifest, workflow = collect_argo(
            environment=environment,
            base_url=base_url,
            namespace=str(namespace),
            workflow_name=workflow_name,
            token=token,
        )

        uploaded = 0
        for a in artifacts:
            local_path = a.metadata.get("_local_path")
            if local_path:
                vault.put_file(
                    local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"}
                )
                uploaded += 1

        # workflow.name instead of workflow.metadata.name
        manifest_key = f"manifests/{environment}/argo-workflow-{workflow.name}.json"
        vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
        persist_if_db(envcfg, environment, manifest, artifacts)

    elif provider == "azure":
        subscription_id = provider_params.get("azure_subscription_id")
        resource_group = provider_params.get("azure_resource_group")
        storage_account = provider_params.get("azure_storage_account")
        key_vault = provider_params.get("azure_key_vault")

        if not subscription_id:
            raise ValueError("azure_subscription_id is required for azure provider")

        # Pass all required args, ensure resource_group is str or None
        # All arguments must be str for collect_azure
        rg: str = str(resource_group) if resource_group is not None else ""
        sa: str = str(storage_account) if storage_account is not None else ""
        kv: str = str(key_vault) if key_vault is not None else ""
        artifacts, manifest = collect_azure(
            environment=environment,
            subscription_id=subscription_id,
            resource_group=rg,
            storage_account=sa,
            key_vault=kv,
        )

        for a in artifacts:
            local_path = a.metadata.get("_local_path")
            if local_path:
                vault.put_file(
                    local_path, a.key, {k: v for k, v in a.metadata.items() if k != "_local_path"}
                )

        manifest_key = f"manifests/{environment}/azure-{subscription_id}.json"
        vault.put_json(manifest_key, manifest.to_json(), metadata={"kind": "evidence-manifest"})
        persist_if_db(envcfg, environment, manifest, artifacts)

    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return len(artifacts), manifest_key, f"Collected {len(artifacts)} artifacts from {provider}"


def validate_evidence(
    config_path: str,
    environment: str,
    control_ids: list[str] | None = None,
    evidence_dict: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """
    Validate controls against evidence (reuses CLI validation logic).

    Args:
        config_path: Path to config.yaml
        environment: Environment key
        control_ids: Specific controls to validate (default: all from catalogs)
        evidence_dict: Override evidence dict (default: build from DB or manifests)

    Returns:
        Tuple of (validation_results, summary)
    """
    cfg = AppConfig.load(config_path)
    if environment not in cfg.environments:
        raise ValueError(f"Unknown environment: {environment}")

    envcfg = cfg.environments[environment]

    # Get control IDs from catalogs if not provided
    if not control_ids:
        control_ids = []
        for cat_path in cfg.catalogs.get_all_catalogs().values():
            oscal_obj = load_oscal(cat_path)
            if isinstance(oscal_obj, OscalCatalog):
                control_ids.extend(oscal_obj.control_ids())
            elif isinstance(oscal_obj, OscalProfile):
                imported = oscal_obj.imported_control_ids()
                if imported:
                    control_ids.extend(imported)

        # Deduplicate
        seen = set()
        deduped = []
        for x in control_ids:
            if x not in seen:
                deduped.append(x)
                seen.add(x)
        control_ids = deduped

    # Build evidence dict if not provided
    evidence: dict[str, object]
    if evidence_dict is None:
        # Try to load from manifests in staging directory
        evidence = {}
        staging = Path(".auditly_manifests")
        if staging.exists():
            for p in staging.glob(f"{environment}-*.json"):
                import json as _json

                data = _json.loads(p.read_text())
                for artifact in data.get("artifacts", []):
                    meta = artifact.get("metadata", {}) or {}
                    kind = meta.get("kind", "unknown")
                    # Aggregate by kind; preserve last-seen
                    if isinstance(kind, str):
                        evidence[kind] = {
                            "key": artifact.get("key"),
                            "filename": artifact.get("filename"),
                            "sha256": artifact.get("sha256"),
                            "size": artifact.get("size"),
                            "metadata": meta,
                            "manifest": str(p),
                        }
        # else evidence remains empty
    else:
        evidence = evidence_dict  # type: ignore

    # Run validation with database_url for access logging
    database_url = getattr(envcfg, "database_url", None)
    validation_results = validate_controls(
        control_ids,
        evidence,
        database_url=database_url,
        user_id="api-validator",
    )

    # Compute summary
    summary = {
        "passed": sum(1 for r in validation_results.values() if r.status.value == "pass"),
        "failed": sum(1 for r in validation_results.values() if r.status.value == "fail"),
        "insufficient": sum(
            1 for r in validation_results.values() if r.status.value == "insufficient_evidence"
        ),
        "unknown": sum(1 for r in validation_results.values() if r.status.value == "unknown"),
    }

    # Convert to serializable dict
    results_dict = {}
    for cid, result in validation_results.items():
        results_dict[str(cid)] = {
            "control_id": result.control_id,
            "status": result.status.value,
            "message": result.message,
            "evidence_keys": result.evidence_keys,
            "metadata": result.metadata,
            "remediation": result.remediation,
        }

    return results_dict, summary


def generate_report(
    config_path: str,
    environment: str,
    report_type: str = "readiness",
    control_ids: list[str] | None = None,
    evidence_dict: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> tuple[str | None, str | None, dict[str, Any]]:
    """
    Generate compliance report (reuses CLI reporting logic).

    Args:
        config_path: Path to config.yaml
        environment: Environment key
        report_type: Report type (readiness, engineer, auditor)
        control_ids: Specific controls for engineer/auditor reports
        evidence_dict: Override evidence dict for engineer/auditor reports
        output_path: Custom output path (default: temp file)

    Returns:
        Tuple of (report_path, report_html, summary)
    """
    cfg = AppConfig.load(config_path)
    if report_type == "readiness":
        return _generate_readiness_report(cfg, environment, output_path)
    elif report_type == "engineer":
        # Always pass a dict[str, Any] for evidence_dict
        engineer_evidence_dict: dict[str, Any] = evidence_dict if evidence_dict is not None else {}
        return _generate_engineer_report(
            cfg, environment, control_ids, engineer_evidence_dict, output_path
        )
    elif report_type == "auditor":
        auditor_evidence_dict: dict[str, Any] = evidence_dict if evidence_dict is not None else {}
        return _generate_auditor_report(
            cfg, environment, control_ids, auditor_evidence_dict, output_path
        )
    else:
        raise ValueError(f"Unsupported report type: {report_type}")


def _generate_readiness_report(
    cfg: AppConfig, environment: str, output_path: str | None
) -> tuple[str, str, dict[str, Any]]:
    """Generate readiness report (CLI logic)."""
    staging = Path(".auditly_manifests")
    staging.mkdir(exist_ok=True)

    if not any(staging.glob(f"{environment}-*.json")):
        dummy = EvidenceManifest.create(
            environment,
            [ArtifactRecord(key="noop", filename="noop", sha256="0", size=0, metadata={})],
        )
        (staging / f"{environment}-dummy.json").write_text(dummy.to_json())

    manifests = []
    for p in staging.glob(f"{environment}-*.json"):
        import json as _json

        data = _json.loads(p.read_text())
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

    # Add control coverage and validation
    try:
        control_ids = []
        for cat_path in cfg.catalogs.get_all_catalogs().values():
            oscal_obj = load_oscal(cat_path)
            if isinstance(oscal_obj, OscalCatalog):
                control_ids.extend(oscal_obj.control_ids())
            elif isinstance(oscal_obj, OscalProfile):
                imported = oscal_obj.imported_control_ids()
                if imported:
                    control_ids.extend(imported)

        seen = set()
        deduped = []
        for x in control_ids:
            if x not in seen:
                deduped.append(x)
                seen.add(x)
        control_ids = deduped

        mapping_path = Path("mapping.yaml")
        if not mapping_path.exists():
            mapping_path = Path("mapping.example.yaml")

        control_evidence = {}
        if mapping_path.exists():
            mapping = ControlMapping.from_yaml(mapping_path)
            control_evidence = match_evidence_to_controls(manifests, mapping)
            summary["controls"] = compute_control_coverage(control_ids, control_evidence)

        evidence_dict2: dict[str, object] = {
            str(a.metadata.get("kind", "unknown")): True for m in manifests for a in m.artifacts
        }
        validation_results = validate_controls(control_ids, evidence_dict2)
        summary["validation"] = {
            "passed": sum(1 for r in validation_results.values() if r.status.value == "pass"),
            "failed": sum(1 for r in validation_results.values() if r.status.value == "fail"),
            "insufficient": sum(
                1 for r in validation_results.values() if r.status.value == "insufficient_evidence"
            ),
        }

        waiver_file = Path("waivers.yaml")
        if waiver_file.exists():
            registry = WaiverRegistry.from_yaml(waiver_file)
            summary["waivers"] = registry.summary()
    except Exception as e:
        summary["controls"] = {"error": f"failed to compute coverage: {e}"}
        summary["validation"] = {"error": str(e)}

    # Write HTML
    if output_path:
        out = Path(output_path)
    else:
        out = Path(tempfile.mktemp(suffix=".html", prefix="auditly-readiness-"))

    write_html(summary, out)
    html_content = out.read_text()

    return str(out), html_content, summary


def _generate_engineer_report(
    cfg: AppConfig,
    environment: str,
    control_ids: list[str] | None,
    evidence_dict: dict[str, Any] | None,
    output_path: str | None,
) -> tuple[str, str, dict[str, Any]]:
    """Generate engineer report (CLI logic)."""
    if not control_ids:
        # Use sample controls
        from ..validators import FAMILY_PATTERNS

        control_ids = []
        for family in FAMILY_PATTERNS.keys():
            control_ids.extend([f"{family}-{i}" for i in range(1, 26)])

    if not evidence_dict:
        # Try to load from staging
        staging = Path(".auditly_manifests")
        evidence_dict2: dict[str, object] = {}
        if staging.exists():
            for p in staging.glob(f"{environment}-*.json"):
                import json as _json

                data = _json.loads(p.read_text())
                for artifact in data.get("artifacts", []):
                    kind = artifact.get("metadata", {}).get("kind", "unknown")
                    if isinstance(kind, str) and kind not in evidence_dict2:
                        evidence_dict2[kind] = True
        else:
            evidence_dict2 = {}
    else:
        evidence_dict2 = evidence_dict  # type: ignore

    results = validate_controls(control_ids, evidence_dict2)

    if output_path:
        out = Path(output_path)
    else:
        out = Path(tempfile.mktemp(suffix=".html", prefix="auditly-engineer-"))

    generate_engineer_report(results, evidence_dict2, out)
    html_content = out.read_text()

    summary = {
        "controls_validated": len(results),
        "passed": sum(1 for r in results.values() if r.status.value == "pass"),
        "failed": sum(1 for r in results.values() if r.status.value == "fail"),
    }

    return str(out), html_content, summary


def _generate_auditor_report(
    cfg: AppConfig,
    environment: str,
    control_ids: list[str] | None,
    evidence_dict: dict[str, Any] | None,
    output_path: str | None,
) -> tuple[str, str, dict[str, Any]]:
    """Generate auditor report (CLI logic)."""
    if not control_ids:
        # Use sample controls
        from ..validators import FAMILY_PATTERNS

        control_ids = []
        for family in FAMILY_PATTERNS.keys():
            control_ids.extend([f"{family}-{i}" for i in range(1, 26)])

    if not evidence_dict:
        # Try to load from staging
        staging = Path(".auditly_manifests")
        evidence_dict2: dict[str, object] = {}
        if staging.exists():
            for p in staging.glob(f"{environment}-*.json"):
                import json as _json

                data = _json.loads(p.read_text())
                for artifact in data.get("artifacts", []):
                    kind = artifact.get("metadata", {}).get("kind", "unknown")
                    if kind not in evidence_dict2:
                        evidence_dict2[kind] = True
        else:
            evidence_dict2 = {}
    else:
        evidence_dict2 = evidence_dict  # type: ignore

    results = validate_controls(control_ids, evidence_dict2)

    if output_path:
        out = Path(output_path)
    else:
        out = Path(tempfile.mktemp(suffix=".html", prefix="auditly-auditor-"))

    generate_auditor_report(results, evidence_dict2, out)
    html_content = out.read_text()

    summary = {
        "controls_validated": len(results),
        "passed": sum(1 for r in results.values() if r.status.value == "pass"),
        "failed": sum(1 for r in results.values() if r.status.value == "fail"),
    }

    return str(out), html_content, summary
