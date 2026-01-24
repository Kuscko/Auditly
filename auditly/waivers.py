"""Waiver management module for approved exceptions and compensating controls."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# type: ignore[import-untyped]
import yaml


@dataclass
class Waiver:
    """Represents an approved exception to a control."""

    control_id: str
    reason: str
    compensating_controls: list[str] = field(default_factory=list)
    approved_by: str | None = None
    approved_date: str | None = None
    expires: str | None = None  # ISO date
    notes: str | None = None

    def is_expired(self) -> bool:
        """Return True if the waiver is expired."""
        if not self.expires:
            return False
        exp_date = datetime.fromisoformat(self.expires)
        return datetime.now() > exp_date

    def days_until_expiry(self) -> int | None:
        """Return the number of days until expiry, or None if not set."""
        if not self.expires:
            return None
        exp_date = datetime.fromisoformat(self.expires)
        delta = exp_date - datetime.now()
        return delta.days


class WaiverRegistry:
    """Track approved exceptions and compensating controls."""

    def __init__(self) -> None:
        """Initialize the WaiverRegistry."""
        self.waivers: dict[str, Waiver] = {}

    @staticmethod
    def from_yaml(path: Path | str) -> WaiverRegistry:
        """Load waivers from YAML file."""
        reg = WaiverRegistry()
        p = Path(path)
        if not p.exists():
            return reg

        data = yaml.safe_load(p.read_text())
        for item in data.get("waivers", []):
            waiver = Waiver(
                control_id=item["control_id"],
                reason=item["reason"],
                compensating_controls=item.get("compensating_controls", []),
                approved_by=item.get("approved_by"),
                approved_date=item.get("approved_date"),
                expires=item.get("expires"),
                notes=item.get("notes"),
            )
            reg.waivers[waiver.control_id] = waiver
        return reg

    def add_waiver(self, waiver: Waiver) -> None:
        """Add a waiver."""
        self.waivers[waiver.control_id] = waiver

    def get_waiver(self, control_id: str) -> Waiver | None:
        """Get waiver for a control, or None."""
        waiver = self.waivers.get(control_id)
        if waiver and waiver.is_expired():
            return None  # Expired waivers do not count
        return waiver

    def save(self, path: Path | str) -> None:
        """Save waivers to YAML file."""
        p = Path(path)
        data = {
            "waivers": [
                {
                    "control_id": w.control_id,
                    "reason": w.reason,
                    "compensating_controls": w.compensating_controls,
                    "approved_by": w.approved_by,
                    "approved_date": w.approved_date,
                    "expires": w.expires,
                    "notes": w.notes,
                }
                for w in self.waivers.values()
            ]
        }
        p.write_text(yaml.safe_dump(data, sort_keys=False))

    def summary(self) -> dict[str, Any]:
        """Get summary of waivers."""
        active = {k: w for k, w in self.waivers.items() if not w.is_expired()}
        expired = {k: w for k, w in self.waivers.items() if w.is_expired()}
        expiring_soon = {}
        for k, w in active.items():
            days = w.days_until_expiry()
            if days is not None and days < 30:
                expiring_soon[k] = w

        return {
            "total": len(self.waivers),
            "active": len(active),
            "expired": len(expired),
            "expiring_soon": len(expiring_soon),
            "expiring_soon_ids": list(expiring_soon.keys()),
        }
