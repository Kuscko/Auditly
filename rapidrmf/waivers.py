from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import yaml


@dataclass
class Waiver:
    """Represents an approved exception to a control."""
    control_id: str
    reason: str
    compensating_controls: List[str] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_date: Optional[str] = None
    expires: Optional[str] = None  # ISO date
    notes: Optional[str] = None

    def is_expired(self) -> bool:
        if not self.expires:
            return False
        exp_date = datetime.fromisoformat(self.expires)
        return datetime.now() > exp_date

    def days_until_expiry(self) -> Optional[int]:
        if not self.expires:
            return None
        exp_date = datetime.fromisoformat(self.expires)
        delta = exp_date - datetime.now()
        return delta.days


class WaiverRegistry:
    """Track approved exceptions and compensating controls."""

    def __init__(self):
        self.waivers: Dict[str, Waiver] = {}

    @staticmethod
    def from_yaml(path: Path | str) -> "WaiverRegistry":
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

    def get_waiver(self, control_id: str) -> Optional[Waiver]:
        """Get waiver for a control, or None."""
        waiver = self.waivers.get(control_id)
        if waiver and waiver.is_expired():
            return None  # Expired waivers don't count
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

    def summary(self) -> Dict[str, Any]:
        """Get summary of waivers."""
        active = {k: w for k, w in self.waivers.items() if not w.is_expired()}
        expired = {k: w for k, w in self.waivers.items() if w.is_expired()}
        expiring_soon = {
            k: w for k, w in active.items()
            if w.days_until_expiry() is not None and w.days_until_expiry() < 30
        }

        return {
            "total": len(self.waivers),
            "active": len(active),
            "expired": len(expired),
            "expiring_soon": len(expiring_soon),
            "expiring_soon_ids": list(expiring_soon.keys()),
        }
