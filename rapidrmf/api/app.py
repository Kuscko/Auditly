"""FastAPI application for RapidRMF REST API."""

import logging

from fastapi import FastAPI

from .routers import collect_router, report_router, validate_router

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

# Register routers
app.include_router(collect_router)
app.include_router(validate_router)
app.include_router(report_router)


@app.get("/", tags=["health"])
def root():
    """Health check endpoint."""
    return {
        "service": "RapidRMF API",
        "version": "0.2.0",
        "status": "healthy",
        "endpoints": ["/collect", "/validate", "/report"],
    }
