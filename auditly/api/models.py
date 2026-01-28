"""API request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Shared Constants ---
ENV_PRODUCTION = "production"
PROVIDER_TERRAFORM = "terraform"
CONFIG_YAML = "config.yaml"
CONFIG_PATH_DESC = "Path to config.yaml file."
REPORT_TYPE_READINESS = "readiness"
ENVIRONMENT_KEY_DESC = "Environment key (e.g., 'production', 'staging')."
EVIDENCE_PROVIDER_DESC = "Evidence provider type (e.g., 'terraform', 'github')."
EVIDENCE_DATA_DESC = "Evidence data payload (arbitrary key-value structure)."
CONTROL_STATUS_COUNTS_DESC = "Summary of control status counts (e.g., {'passed': 10, 'failed': 2})."
COLLECT_PROVIDER_DESC = "Provider type: terraform, github, gitlab, argo, azure."
REPORT_TYPE_DESC = "Report type: readiness, engineer, auditor."
REPORT_PATH_DESC = "Path to the generated report file."
REPORT_HTML_DESC = "Inline HTML report content (if requested)."
REPORT_SUMMARY_DESC = "Summary of report results."

# --- Evidence CRUD Models ---


class Evidence(BaseModel):
    """
    Evidence record model.

    Represents a single evidence item collected for compliance validation.
    """

    id: str = Field(..., description="Unique evidence ID.", examples=["abc123"])
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    provider: str = Field(..., description=EVIDENCE_PROVIDER_DESC, examples=[PROVIDER_TERRAFORM])
    data: dict = Field(..., description=EVIDENCE_DATA_DESC, examples=[{"resource_count": 5}])
    created_at: str | None = Field(
        None,
        description="Timestamp when evidence was created (ISO 8601).",
        examples=["2024-01-01T12:00:00Z"],
    )
    updated_at: str | None = Field(
        None,
        description="Timestamp when evidence was last updated (ISO 8601).",
        examples=["2024-01-02T09:00:00Z"],
    )


class EvidenceCreate(BaseModel):
    """
    Model for creating new evidence.

    Used in POST /evidence requests.
    """

    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    provider: str = Field(..., description=EVIDENCE_PROVIDER_DESC, examples=[PROVIDER_TERRAFORM])
    data: dict = Field(..., description=EVIDENCE_DATA_DESC, examples=[{"resource_count": 5}])


class EvidenceUpdate(BaseModel):
    """
    Model for updating evidence data.

    Used in PUT /evidence/{evidence_id} requests.
    """

    data: dict = Field(
        ..., description="Updated evidence data payload.", examples=[{"resource_count": 6}]
    )


class ControlStatusResponse(BaseModel):
    """
    Response model for control status summary.

    Returned by GET /evidence/control-status.
    """

    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    status_summary: dict[str, int] = Field(
        ..., description=CONTROL_STATUS_COUNTS_DESC, examples=[{"passed": 10, "failed": 2}]
    )
    details: list[dict] | None = Field(
        None,
        description="Optional detailed control status breakdown.",
        examples=[[{"control_id": "AC-2", "status": "passed"}]],
    )


# Request models
class CollectRequest(BaseModel):
    """
    Request to collect evidence from a provider.

    Used in POST /collect requests. Supports multiple provider types and parameters.
    """

    config_path: str = Field(
        default=CONFIG_YAML, description=CONFIG_PATH_DESC, examples=[CONFIG_YAML]
    )
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    provider: str = Field(..., description=COLLECT_PROVIDER_DESC, examples=[PROVIDER_TERRAFORM])

    # Provider-specific parameters
    terraform_plan_path: str | None = Field(
        None, description="Path to Terraform plan file.", examples=["/path/to/plan.json"]
    )
    terraform_apply_path: str | None = Field(
        None, description="Path to Terraform apply log.", examples=["/path/to/apply.log"]
    )

    github_repo: str | None = Field(
        None, description="GitHub repo 'owner/name'", examples=["myorg/myrepo"]
    )
    github_token: str | None = Field(None, description="GitHub API token", examples=["ghp_..."])
    github_run_id: int | None = Field(
        None, description="Specific GitHub Actions run ID", examples=[123456789]
    )
    github_branch: str | None = Field(None, description="GitHub branch filter", examples=["main"])

    gitlab_base_url: str = Field(
        default="https://gitlab.com",
        description="GitLab instance URL",
        examples=["https://gitlab.com"],
    )
    gitlab_project_id: str | None = Field(
        None, description="GitLab project ID or 'namespace/project'", examples=["mygroup/myproject"]
    )
    gitlab_token: str | None = Field(None, description="GitLab API token", examples=["glpat-..."])
    gitlab_pipeline_id: int | None = Field(
        None, description="Specific GitLab pipeline ID", examples=[987654321]
    )
    gitlab_ref: str | None = Field(
        None, description="GitLab ref (branch/tag) filter", examples=["main"]
    )

    argo_base_url: str | None = Field(
        None, description="Argo Workflows API base URL", examples=["https://argo.example.com"]
    )
    argo_namespace: str | None = Field(None, description="Argo namespace", examples=["default"])
    argo_workflow_name: str | None = Field(
        None, description="Argo workflow name", examples=["compliance-check"]
    )
    argo_token: str | None = Field(None, description="Argo auth token", examples=["argo-token-..."])

    azure_subscription_id: str | None = Field(
        None, description="Azure subscription ID", examples=["00000000-0000-0000-0000-000000000000"]
    )
    azure_resource_group: str | None = Field(
        None, description="Azure resource group", examples=["auditly-prod"]
    )


class CollectBatchRequest(BaseModel):
    """
    Batch request for collecting evidence from multiple providers concurrently.

    Used in POST /collect/batch requests.
    """

    requests: list[CollectRequest] = Field(
        ...,
        description="List of collection requests.",
        examples=[
            [
                {
                    "environment": ENV_PRODUCTION,
                    "provider": PROVIDER_TERRAFORM,
                    "terraform_plan_path": "/path/to/plan.json",
                }
            ]
        ],
    )
    timeout_seconds: int = Field(
        300,
        description="Overall timeout per request in seconds.",
        examples=[300],
    )


class ValidateRequest(BaseModel):
    """
    Request to validate controls against evidence.

    Used in POST /validate requests.
    """

    config_path: str = Field(
        default=CONFIG_YAML, description=CONFIG_PATH_DESC, examples=[CONFIG_YAML]
    )
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    control_ids: list[str] | None = Field(
        None,
        description="Specific control IDs to validate (default: all from catalogs).",
        examples=[["AC-2", "CM-2"]],
    )
    evidence_dict: dict[str, object] | None = Field(
        None,
        description="Override evidence dict (default: fetch from DB).",
        examples=[{"artifact_count": 42}],
    )


class ReportRequest(BaseModel):
    """
    Request to generate a compliance report.

    Used in POST /report requests. Supports readiness, engineer, and auditor report types.
    """

    config_path: str = Field(
        default=CONFIG_YAML, description=CONFIG_PATH_DESC, examples=[CONFIG_YAML]
    )
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    report_type: str = Field(
        default=REPORT_TYPE_READINESS,
        description=REPORT_TYPE_DESC,
        examples=[REPORT_TYPE_READINESS],
    )
    control_ids: list[str] | None = Field(
        None,
        description="Specific control IDs for engineer/auditor reports.",
        examples=[["AC-2", "CM-2"]],
    )
    evidence_dict: dict[str, object] | None = Field(
        None,
        description="Override evidence dict for engineer/auditor reports.",
        examples=[{"artifact_count": 42}],
    )


# Response models
class CollectResponse(BaseModel):
    """
    Response from evidence collection.

    Returned by POST /collect endpoint.
    """

    success: bool = Field(
        ..., description="Whether the collection was successful.", examples=[True]
    )
    artifacts_uploaded: int = Field(..., description="Number of artifacts uploaded.", examples=[3])
    manifest_key: str = Field(
        ...,
        description="Key or path to the evidence manifest.",
        examples=["manifests/prod-20240101.json"],
    )
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    provider: str = Field(..., description="Provider type.", examples=[PROVIDER_TERRAFORM])
    message: str | None = Field(
        None, description="Optional informational message.", examples=["Collection completed."]
    )
    error: str | None = Field(
        None,
        description="Optional error message if collection failed.",
        examples=["Provider not found."],
    )


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
    """
    Response from report generation.

    Returned by POST /report endpoint.
    """

    success: bool = Field(
        ..., description="Whether the report was generated successfully.", examples=[True]
    )
    environment: str = Field(..., description=ENVIRONMENT_KEY_DESC, examples=[ENV_PRODUCTION])
    report_type: str = Field(
        ..., description="Type of report generated.", examples=[REPORT_TYPE_READINESS]
    )
    report_path: str | None = Field(
        None, description=REPORT_PATH_DESC, examples=["reports/prod-readiness-20240101.html"]
    )
    report_html: str | None = Field(
        None, description=REPORT_HTML_DESC, examples=["<html>...</html>"]
    )
    summary: dict[str, object] | None = Field(
        None,
        description=REPORT_SUMMARY_DESC,
        examples=[{"artifacts": 42, "validation": {"passed": 35, "failed": 2}}],
    )
    message: str | None = Field(
        None, description="Optional informational message.", examples=["Report generated."]
    )
    error: str | None = Field(
        None,
        description="Optional error message if report generation failed.",
        examples=["No evidence found."],
    )
