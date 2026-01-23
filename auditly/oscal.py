"""OSCAL catalog and profile utilities for auditly."""

from __future__ import annotations

import json
from pathlib import Path


class OscalCatalog:
    """Represents an OSCAL catalog containing control definitions."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize an OscalCatalog from a data dictionary."""
        self.data = data
        self.catalog = data.get("catalog", {})
        self.catalog = data.get("catalog", {})

    def control_ids(self) -> list[str]:
        """Extract all control IDs from the catalog."""
        controls = []
        for group in self.catalog.get("groups", []):
            controls.extend(self._extract_control_ids_from_group(group))
        return controls

    def _extract_control_ids_from_group(self, group: dict[str, Any]) -> list[str]:
        """Recursively extract control IDs from a group and its subgroups."""
        ids = []
        for ctl in group.get("controls", []):
            if cid := ctl.get("id"):
                ids.append(cid)
        for subgroup in group.get("groups", []):
            ids.extend(self._extract_control_ids_from_group(subgroup))
        return ids

    def get_control(self, control_id: str) -> dict[str, Any] | None:
        """Retrieve a specific control by ID."""
        for group in self.catalog.get("groups", []):
            if control := self._find_control_in_group(group, control_id):
                return control
        return None

    def _find_control_in_group(
        self, group: dict[str, Any], control_id: str
    ) -> dict[str, Any] | None:
        """Recursively search for a control in a group."""
        for ctl in group.get("controls", []):
            if ctl.get("id") == control_id:
                return ctl
        for subgroup in group.get("groups", []):
            if control := self._find_control_in_group(subgroup, control_id):
                return control
        return None

    def metadata(self) -> dict[str, Any]:
        """Get catalog metadata."""
        return self.catalog.get("metadata", {})


class OscalProfile:
    """Represents an OSCAL profile (baseline) that imports and tailors controls from catalogs."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize an OscalProfile from a data dictionary."""
        self.data = data
        self.profile = data.get("profile", {})

    def imported_control_ids(self) -> list[str]:
        """Extract all control IDs that are imported/included in this profile."""
        control_ids = []
        for import_def in self.profile.get("imports", []):
            # Check include-controls
            for include in import_def.get("include-controls", []):
                # with-ids section lists specific controls
                for with_id in include.get("with-ids", []):
                    control_ids.append(with_id)

                # matching section can specify controls by criteria
                matching = include.get("matching", [])
                if matching:
                    # These would need catalog resolution to expand
                    pass

        return control_ids

    def import_hrefs(self) -> list[str]:
        """Get the hrefs of imported catalogs/profiles."""
        hrefs = []
        for import_def in self.profile.get("imports", []):
            if href := import_def.get("href"):
                hrefs.append(href)
        return hrefs

    def metadata(self) -> dict[str, Any]:
        """Get profile metadata."""
        return self.profile.get("metadata", {})

    def title(self) -> str | None:
        """Get the profile title."""
        return self.metadata().get("title")


def load_oscal_catalog(path: Path | str) -> OscalCatalog | None:
    """Load an OSCAL catalog from a JSON file."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if "catalog" not in data:
        return None
    return OscalCatalog(data)


def load_oscal_profile(path: Path | str) -> OscalProfile | None:
    """Load an OSCAL profile from a JSON file."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if "profile" not in data:
        return None
    return OscalProfile(data)


def load_oscal(path: Path | str) -> OscalCatalog | OscalProfile | None:
    """Auto-detect and load either an OSCAL catalog or profile."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))

    if "catalog" in data:
        return OscalCatalog(data)
    elif "profile" in data:
        return OscalProfile(data)

    return None


from typing import Any
