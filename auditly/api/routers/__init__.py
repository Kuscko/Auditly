"""API routers package."""

from .collect import router as collect_router
from .evidence import router as evidence_router
from .report import router as report_router
from .validate import router as validate_router
from .webhook import router as webhook_router

__all__ = [
    "collect_router",
    "validate_router",
    "report_router",
    "evidence_router",
    "webhook_router",
]
