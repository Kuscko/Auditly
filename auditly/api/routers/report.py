"""Reporting endpoint router."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..models import ReportRequest, ReportResponse
from ..operations import generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["reporting"])


@router.post("", response_model=ReportResponse)
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
        logger.info(
            f"Generating report: environment={request.environment}, type={request.report_type}"
        )

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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}") from e


@router.get("/html", response_class=HTMLResponse)
def report_html(environment: str, report_type: str = "readiness", config_path: str = "config.yaml"):
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
        raise HTTPException(status_code=500, detail=f"Report HTML generation failed: {e}") from e
