"""FastAPI application for auditly REST API."""

import logging

from fastapi import FastAPI

from .routers import collect_router, evidence_router, report_router, validate_router, webhook_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app

# Custom OpenAPI description with branding and authentication note
app = FastAPI(
    title="auditly API",
    description=(
        "REST API for auditly compliance automation.\n\n"
        "**Features:**\n"
        "- Evidence collection, validation, and reporting endpoints.\n"
        "- Rich OpenAPI/Swagger UI with field descriptions and examples.\n"
        "- Designed for integration with CI/CD, cloud, and compliance workflows.\n\n"
        "**Authentication:**\n"
        "This API does not include built-in authentication. For production, deploy behind an API gateway, reverse proxy, or add JWT/OAuth2 middleware.\n\n"
        "**Branding:**\n"
        "auditly \U0001f512 | Compliance Automation Platform."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Register routers

app.include_router(collect_router)
app.include_router(validate_router)
app.include_router(report_router)
app.include_router(evidence_router)
app.include_router(webhook_router)


@app.get("/", tags=["health"])
def root():
    """Health check endpoint."""
    return {
        "service": "auditly API",
        "version": "0.2.0",
        "status": "healthy",
        "endpoints": ["/collect", "/validate", "/report", "/evidence", "/webhook"],
    }
