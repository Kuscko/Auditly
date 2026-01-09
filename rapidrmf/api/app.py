"""FastAPI application for RapidRMF REST API."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import logging

from .models import (
    CollectRequest,
    CollectResponse,
    ValidateRequest,
    ValidateResponse,
    ValidationResultResponse,
    ReportRequest,
    ReportResponse,
)
from .operations import collect_evidence, validate_evidence, generate_report

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RapidRMF API",
    description="REST API for RapidRMF compliance automation - collection, validation, and reporting",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/", tags=["health"])
def root():
    """Health check endpoint."""
    return {
        "service": "RapidRMF API",
        "version": "0.2.0",
        "status": "healthy",
        "endpoints": ["/collect", "/validate", "/report"],
    }


@app.post("/collect", response_model=CollectResponse, tags=["evidence"])
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
        logger.info(f"Collecting evidence: environment={request.environment}, provider={request.provider}")
        
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
            **provider_params
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


@app.post("/validate", response_model=ValidateResponse, tags=["validation"])
def validate(request: ValidateRequest):
    """
    Validate controls against collected evidence.
    
    Validates control requirements from OSCAL catalogs against available evidence.
    Returns validation status for each control with remediation guidance.
    
    **Example:**
    ```json
    {
        "environment": "production",
        "control_ids": ["AC-2", "CM-2", "SC-7"]
    }
    ```
    
    If control_ids is omitted, validates all controls from configured catalogs.
    """
    try:
        logger.info(f"Validating: environment={request.environment}, controls={len(request.control_ids or [])}")
        
        results_dict, summary = validate_evidence(
            config_path=request.config_path,
            environment=request.environment,
            control_ids=request.control_ids,
            evidence_dict=request.evidence_dict,
        )
        
        # Convert to response models
        results_response = {}
        for cid, result in results_dict.items():
            results_response[cid] = ValidationResultResponse(**result)
        
        logger.info(f"Validation complete: {summary['passed']} passed, {summary['failed']} failed, {summary['insufficient']} insufficient")
        
        return ValidateResponse(
            success=True,
            environment=request.environment,
            controls_validated=len(results_dict),
            results=results_response,
            summary=summary,
            message=f"Validated {len(results_dict)} controls",
        )
        
    except ValueError as e:
        logger.error(f"Validation error in validate: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Validation failed: {e}")
        return ValidateResponse(
            success=False,
            environment=request.environment,
            controls_validated=0,
            results={},
            summary={"passed": 0, "failed": 0, "insufficient": 0, "unknown": 0},
            error=str(e),
        )


@app.post("/report", response_model=ReportResponse, tags=["reporting"])
def report(request: ReportRequest):
    """
    Generate compliance reports.
    
    Report types:
    - **readiness**: Full compliance readiness with control coverage and validation results
    - **engineer**: Engineer-focused validation report with technical remediation guidance
    - **auditor**: Auditor-focused validation report with compliance status
    
    **Example - Readiness Report:**
    ```json
    {
        "environment": "production",
        "report_type": "readiness"
    }
    ```
    
    **Example - Engineer Report:**
    ```json
    {
        "environment": "production",
        "report_type": "engineer",
        "control_ids": ["AC-2", "CM-2", "SC-7"]
    }
    ```
    
    Returns HTML report that can be viewed in a browser or saved to a file.
    """
    try:
        logger.info(f"Generating report: environment={request.environment}, type={request.report_type}")
        
        report_path, report_html, summary = generate_report(
            config_path=request.config_path,
            environment=request.environment,
            report_type=request.report_type,
            control_ids=request.control_ids,
            evidence_dict=request.evidence_dict,
        )
        
        logger.info(f"Report generated: {report_path}")
        
        return ReportResponse(
            success=True,
            environment=request.environment,
            report_type=request.report_type,
            report_path=report_path,
            report_html=report_html,
            summary=summary,
            message=f"Generated {request.report_type} report",
        )
        
    except ValueError as e:
        logger.error(f"Validation error in report: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return ReportResponse(
            success=False,
            environment=request.environment,
            report_type=request.report_type,
            error=str(e),
        )


@app.get("/report/html", response_class=HTMLResponse, tags=["reporting"])
def report_html(
    environment: str,
    report_type: str = "readiness",
    config_path: str = "config.yaml"
):
    """
    Generate and return HTML report directly (for browser viewing).
    
    Query parameters:
    - environment: Environment key
    - report_type: readiness, engineer, or auditor (default: readiness)
    - config_path: Path to config file (default: config.yaml)
    
    Example: `/report/html?environment=production&report_type=readiness`
    """
    try:
        _, report_html, _ = generate_report(
            config_path=config_path,
            environment=environment,
            report_type=report_type,
        )
        return HTMLResponse(content=report_html)
    except Exception as e:
        logger.exception(f"Report HTML generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
