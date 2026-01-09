"""API routers package."""

from .collect import router as collect_router
from .validate import router as validate_router
from .report import router as report_router

__all__ = ["collect_router", "validate_router", "report_router"]
