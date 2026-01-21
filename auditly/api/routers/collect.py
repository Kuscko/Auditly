"""Collection endpoint router."""

import logging

from fastapi import APIRouter, HTTPException

from ..models import CollectBatchRequest, CollectBatchResponse, CollectRequest, CollectResponse
from ..operations import collect_evidence, collect_evidence_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collect", tags=["evidence"])


@router.post("/batch", response_model=CollectBatchResponse)
def collect_batch(request: CollectBatchRequest):
    """Collect evidence from multiple providers concurrently.

    Each entry in `requests` mirrors the single-provider payload. Results/errors are keyed by
    request index or provided name (if passed in the request object).
    """
    try:
        batch_payload = []
        for idx, r in enumerate(request.requests):
            # Build kwargs for operations.collect_evidence
            provider_params = r.dict(exclude_none=True)
            provider_params.pop("provider", None)
            provider_params.pop("environment", None)
            provider_params.pop("config_path", None)

            batch_payload.append(
                {
                    "name": f"req-{idx}-{r.provider}",
                    "config_path": r.config_path,
                    "environment": r.environment,
                    "provider": r.provider,
                    **provider_params,
                }
            )

        result = collect_evidence_batch(batch_payload, timeout=request.timeout_seconds)

        return CollectBatchResponse(
            success=True,
            results=result.get("results", {}),
            errors=result.get("errors", {}),
            succeeded=result.get("success", 0),
            failed=result.get("failed", 0),
            message="Batch collection completed",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Batch collection failed: {e}")
        return CollectBatchResponse(
            success=False,
            results={},
            errors={"__batch__": str(e)},
            succeeded=0,
            failed=len(request.requests),
            message="Batch collection failed",
        )


@router.post("", response_model=CollectResponse)
def collect(request: CollectRequest):
    """
    Collect evidence from cloud providers or CI/CD systems.

    Supported providers: terraform, github, gitlab, argo, azure

    **Example - Terraform:**
    ```json
    {
        "environment": "production",
        "provider": "terraform",
        "terraform_plan_path": "/path/to/plan.json",
        "terraform_apply_path": "/path/to/apply.log"
    }
    ```

    **Example - GitHub Actions:**
    ```json
    {
        "environment": "production",
        "provider": "github",
        "github_repo": "owner/repo",
        "github_token": "ghp_...",
        "github_run_id": 12345
    }
    ```
    """
    try:
        logger.info(
            f"Collecting evidence: environment={request.environment}, provider={request.provider}"
        )

        # Extract provider-specific params
        provider_params = {}
        if request.provider == "terraform":
            provider_params["terraform_plan_path"] = request.terraform_plan_path
            provider_params["terraform_apply_path"] = request.terraform_apply_path
        elif request.provider == "github":
            provider_params["github_repo"] = request.github_repo
            provider_params["github_token"] = request.github_token
            provider_params["github_run_id"] = request.github_run_id
            provider_params["github_branch"] = request.github_branch
        elif request.provider == "gitlab":
            provider_params["gitlab_base_url"] = request.gitlab_base_url
            provider_params["gitlab_project_id"] = request.gitlab_project_id
            provider_params["gitlab_token"] = request.gitlab_token
            provider_params["gitlab_pipeline_id"] = request.gitlab_pipeline_id
            provider_params["gitlab_ref"] = request.gitlab_ref
        elif request.provider == "argo":
            provider_params["argo_base_url"] = request.argo_base_url
            provider_params["argo_namespace"] = request.argo_namespace
            provider_params["argo_workflow_name"] = request.argo_workflow_name
            provider_params["argo_token"] = request.argo_token
        elif request.provider == "azure":
            provider_params["azure_subscription_id"] = request.azure_subscription_id
            provider_params["azure_resource_group"] = request.azure_resource_group

        artifacts_count, manifest_key, message = collect_evidence(
            config_path=request.config_path,
            environment=request.environment,
            provider=request.provider,
            **provider_params,
        )

        logger.info(f"Collection successful: {artifacts_count} artifacts, manifest: {manifest_key}")

        return CollectResponse(
            success=True,
            artifacts_uploaded=artifacts_count,
            manifest_key=manifest_key,
            environment=request.environment,
            provider=request.provider,
            message=message,
        )

    except ValueError as e:
        logger.error(f"Validation error in collect: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Collection failed: {e}")
        return CollectResponse(
            success=False,
            artifacts_uploaded=0,
            manifest_key="",
            environment=request.environment,
            provider=request.provider,
            error=str(e),
        )
