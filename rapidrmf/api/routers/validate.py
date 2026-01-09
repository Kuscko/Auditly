"""Validation endpoint router."""

from fastapi import APIRouter, HTTPException
import logging

from ..models import ValidateRequest, ValidateResponse, ValidationResultResponse
from ..operations import validate_evidence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validate", tags=["validation"])


@router.post("", response_model=ValidateResponse)
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
