"""API request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


# Request models
class CollectRequest(BaseModel):
    """Request to collect evidence from a provider."""

    config_path: str = Field(default="config.yaml", description="Path to config.yaml file")
    environment: str = Field(..., description="Environment key (e.g., 'production', 'staging')")
    provider: str = Field(..., description="Provider type: terraform, github, gitlab, argo, azure")

    # Provider-specific parameters
    terraform_plan_path: str | None = Field(None, description="Path to Terraform plan file")
    terraform_apply_path: str | None = Field(None, description="Path to Terraform apply log")

    github_repo: str | None = Field(None, description="GitHub repo 'owner/name'")
    github_token: str | None = Field(None, description="GitHub API token")
    github_run_id: int | None = Field(None, description="Specific GitHub Actions run ID")
    github_branch: str | None = Field(None, description="GitHub branch filter")

    gitlab_base_url: str = Field(default="https://gitlab.com", description="GitLab instance URL")
    gitlab_project_id: str | None = Field(
        None, description="GitLab project ID or 'namespace/project'"
    )
    gitlab_token: str | None = Field(None, description="GitLab API token")
    gitlab_pipeline_id: int | None = Field(None, description="Specific GitLab pipeline ID")
    gitlab_ref: str | None = Field(None, description="GitLab ref (branch/tag) filter")

    argo_base_url: str | None = Field(None, description="Argo Workflows API base URL")
    argo_namespace: str | None = Field(None, description="Argo namespace")
    argo_workflow_name: str | None = Field(None, description="Argo workflow name")
    argo_token: str | None = Field(None, description="Argo auth token")

    azure_subscription_id: str | None = Field(None, description="Azure subscription ID")
    azure_resource_group: str | None = Field(None, description="Azure resource group")


class CollectBatchRequest(BaseModel):
    """Batch request for collecting evidence from multiple providers concurrently."""

    requests: list[CollectRequest] = Field(..., description="List of collection requests")
    timeout_seconds: int = Field(300, description="Overall timeout per request in seconds")


class ValidateRequest(BaseModel):
    """Request to validate controls against evidence."""

    config_path: str = Field(default="config.yaml", description="Path to config.yaml file")
    environment: str = Field(..., description="Environment key")
    control_ids: list[str] | None = Field(
        None, description="Specific control IDs to validate (default: all from catalogs)"
    )
    evidence_dict: dict[str, object] | None = Field(
        None, description="Override evidence dict (default: fetch from DB)"
    )


class ReportRequest(BaseModel):
    """Request to generate a compliance report."""

    config_path: str = Field(default="config.yaml", description="Path to config.yaml file")
    environment: str = Field(..., description="Environment key")
    report_type: str = Field(
        default="readiness", description="Report type: readiness, engineer, auditor"
    )
    control_ids: list[str] | None = Field(
        None, description="Specific control IDs for engineer/auditor reports"
    )
    evidence_dict: dict[str, object] | None = Field(
        None, description="Override evidence dict for engineer/auditor reports"
    )


# Response models
class CollectResponse(BaseModel):
    """Response from evidence collection."""

    success: bool
    artifacts_uploaded: int
    manifest_key: str
    environment: str
    provider: str
    message: str | None = None
    error: str | None = None


class CollectBatchResponse(BaseModel):
    """Response from batch evidence collection."""

    success: bool
    results: dict[str, object]
    errors: dict[str, object]
    succeeded: int
    failed: int
    message: str | None = None


class ValidationResultResponse(BaseModel):
    """Single validation result."""

    control_id: str
    status: str  # pass, fail, insufficient_evidence, unknown
    message: str
    evidence_keys: list[str]
    metadata: dict[str, object]
    remediation: str | None = None


class ValidateResponse(BaseModel):
    """Response from validation."""

    success: bool
    environment: str
    controls_validated: int
    results: dict[str, ValidationResultResponse]
    summary: dict[str, int]  # {"passed": 10, "failed": 5, "insufficient": 3}
    message: str | None = None
    error: str | None = None


class ReportResponse(BaseModel):
    """Response from report generation."""

    success: bool
    environment: str
    report_type: str
    report_path: str | None = None
    report_html: str | None = None  # For inline HTML return
    summary: dict[str, object] | None = None
    message: str | None = None
    error: str | None = None
