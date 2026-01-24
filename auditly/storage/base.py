"""Abstract base class for evidence vault backends in auditly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class EvidenceVault(ABC):
    """Abstract base class for evidence vault storage backends."""

    @abstractmethod
    def put_file(
        self, src_path: Path | str, dest_key: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Upload a file to the evidence vault."""
        raise NotImplementedError

    @abstractmethod
    def put_json(
        self, dest_key: str, data: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Upload a JSON string as an object to the evidence vault."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, dest_key: str) -> bool:
        """Check if an object exists in the evidence vault."""
        raise NotImplementedError

    @abstractmethod
    def list(self, prefix: str) -> list[str]:
        """List object keys in the evidence vault with the given prefix."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, key: str, out_path: Path | str) -> None:
        """Download an object from the evidence vault to a local path."""
        raise NotImplementedError

    @abstractmethod
    def get_json(self, key: str) -> dict[str, Any]:
        """Fetch JSON evidence and return as dict."""
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for an evidence artifact."""
        raise NotImplementedError
