"""GCP client wrapper for Google Cloud SDK management."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from google.auth import default as google_auth_default
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import compute_v1, iam_credentials_v1, resourcemanager_v3, storage
    from google.oauth2 import service_account

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    logger.warning("google-cloud libraries not installed. GCP collectors will not be available.")


class GCPClient:
    """GCP client wrapper for managing Google Cloud API clients.

    Handles:
    - Credential management (service account, application default credentials)
    - Project and organization context
    - Client caching for performance
    - Error handling and retries
    """

    def __init__(
        self,
        project_id: str | None = None,
        credentials_path: str | None = None,
        organization_id: str | None = None,
    ):
        """Initialize GCP client.

        Args:
            project_id: GCP project ID (optional, will auto-detect if not provided)
            credentials_path: Path to service account JSON file (optional)
            organization_id: GCP organization ID for org-level resources (optional)
        """
        if not GCP_AVAILABLE:
            raise ImportError(
                "google-cloud libraries required for GCP collectors. "
                "Install with: pip install google-cloud-compute google-cloud-storage "
                "google-cloud-iam google-cloud-logging google-cloud-sql google-cloud-kms"
            )

        self.project_id = project_id
        self.organization_id = organization_id
        self._clients: dict[str, Any] = {}
        self.credentials = None

        # Load credentials
        if credentials_path:
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            if not project_id and hasattr(self.credentials, "project_id"):
                self.project_id = self.credentials.project_id
        else:
            try:
                self.credentials, detected_project = google_auth_default()
                if not project_id:
                    self.project_id = detected_project
            except DefaultCredentialsError:
                logger.error(
                    "No GCP credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
                    "or provide credentials_path."
                )
                raise

        logger.info(
            "Initialized GCP client for project=%s, org=%s",
            self.project_id,
            self.organization_id,
        )

    def get_compute_client(self) -> Any:
        """Get Compute Engine client (cached).

        Returns:
            Compute Engine client
        """
        if "compute" not in self._clients:
            self._clients["compute"] = compute_v1.InstancesClient(credentials=self.credentials)
            logger.debug("Created Compute Engine client")
        return self._clients["compute"]

    def get_storage_client(self) -> Any:
        """Get Cloud Storage client (cached).

        Returns:
            Cloud Storage client
        """
        if "storage" not in self._clients:
            self._clients["storage"] = storage.Client(
                project=self.project_id,
                credentials=self.credentials,
            )
            logger.debug("Created Cloud Storage client")
        return self._clients["storage"]

    def get_iam_client(self) -> Any:
        """Get IAM client (cached).

        Returns:
            IAM client
        """
        if "iam" not in self._clients:
            self._clients["iam"] = iam_credentials_v1.IAMCredentialsClient(
                credentials=self.credentials
            )
            logger.debug("Created IAM client")
        return self._clients["iam"]

    def get_resource_manager_client(self) -> Any:
        """Get Resource Manager client for project/org queries (cached).

        Returns:
            Resource Manager client
        """
        if "resource_manager" not in self._clients:
            self._clients["resource_manager"] = resourcemanager_v3.ProjectsClient(
                credentials=self.credentials
            )
            logger.debug("Created Resource Manager client")
        return self._clients["resource_manager"]

    def get_project_number(self) -> str:
        """Get GCP project number.

        Returns:
            GCP project number as string

        Raises:
            Exception: If unable to determine project number
        """
        try:
            client = self.get_resource_manager_client()
            project = client.get_project(name=f"projects/{self.project_id}")
            project_number = project.name.split("/")[-1]
            logger.debug("GCP Project Number: %s", project_number)
            return project_number
        except Exception as e:
            logger.error("Failed to get GCP project number: %s", e)
            raise

    def list_projects(self) -> list[dict[str, Any]]:
        """List all accessible GCP projects.

        Returns:
            List of project dictionaries
        """
        try:
            client = self.get_resource_manager_client()
            projects = []
            for project in client.search_projects():
                projects.append(
                    {
                        "project_id": project.project_id,
                        "name": project.display_name,
                        "state": project.state.name,
                    }
                )
            logger.debug("Found %d GCP projects", len(projects))
            return projects
        except Exception as e:
            logger.warning("Failed to list GCP projects: %s", e)
            return [{"project_id": self.project_id, "name": "Current Project"}]
