# Dockerfile for auditly API (FastAPI)
FROM python:3.12-slim

# Install pipx and set up environment
RUN pip install --no-cache-dir pipx && pipx ensurepath

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements-prod.txt .
RUN pipx install . --spec .[all] || pip install --no-cache-dir -r requirements-prod.txt

# Copy source code
COPY auditly/ auditly/
COPY config.yaml catalogs/ ./

# Expose port and run API
EXPOSE 8000

# Add a non-root user, group, and set permissions for app files
RUN addgroup --system auditly \
	&& adduser --system --ingroup auditly auditly \
	&& chown -R auditly:auditly /app /usr/local

# Switch to non-root user
USER auditly

CMD ["uvicorn", "auditly.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
