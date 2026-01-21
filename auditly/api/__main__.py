"""Development server for auditly API."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("auditly.api.app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
