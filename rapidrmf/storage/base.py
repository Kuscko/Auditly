from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class EvidenceVault(ABC):
    @abstractmethod
    def put_file(self, src_path: Path | str, dest_key: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def put_json(self, dest_key: str, data: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def exists(self, dest_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, key: str, out_path: Path | str) -> None:
        raise NotImplementedError
