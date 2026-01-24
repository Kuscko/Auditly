"""Evidence CRUD and control status API router."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..models import ControlStatusResponse, Evidence, EvidenceCreate, EvidenceUpdate
from ..operations import (
    create_evidence,
    delete_evidence,
    get_control_status,
    get_evidence,
    list_evidence,
    update_evidence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", response_model=Evidence)
def create_evidence_endpoint(evidence: EvidenceCreate):
    """Create new evidence item."""
    try:
        return create_evidence(evidence)
    except Exception as e:
        logger.error(f"Create evidence failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{evidence_id}", response_model=Evidence)
def get_evidence_endpoint(evidence_id: str = Path(...)):
    """Get evidence by ID."""
    try:
        return get_evidence(evidence_id)
    except Exception as e:
        logger.error(f"Get evidence failed: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{evidence_id}", response_model=Evidence)
def update_evidence_endpoint(evidence_id: str, evidence: EvidenceUpdate):
    """Update evidence by ID."""
    try:
        return update_evidence(evidence_id, evidence)
    except Exception as e:
        logger.error(f"Update evidence failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{evidence_id}")
def delete_evidence_endpoint(evidence_id: str):
    """Delete evidence by ID."""
    try:
        delete_evidence(evidence_id)
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Delete evidence failed: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("", response_model=List[Evidence])
def list_evidence_endpoint(environment: Optional[str] = Query(None)):
    """List all evidence (optionally filter by environment)."""
    try:
        return list_evidence(environment=environment)
    except Exception as e:
        logger.error(f"List evidence failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/control-status", response_model=ControlStatusResponse)
def control_status_endpoint(environment: str = Query(...)):
    """Get control status summary for an environment."""
    try:
        return get_control_status(environment)
    except Exception as e:
        logger.error(f"Control status failed: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
