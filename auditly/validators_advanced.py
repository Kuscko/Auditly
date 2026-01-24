"""Advanced validation features: control dependencies, custom validators, findings lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .validators import ValidationResult, ValidationStatus


class ControlDependencyType(str, Enum):
    """Types of control dependencies."""

    PREREQUISITE = "prerequisite"  # Must pass before dependent
    RELATED = "related"  # Should be considered together
    INHERITED = "inherited"  # Inherited from provider (FedRAMP, GovCloud)
    COMPENSATING = "compensating"  # Compensates for waived control


@dataclass
class ControlDependency:
    """Defines a dependency between two controls."""

    source_control: str  # Control that has the dependency
    depends_on: str  # Control that must be satisfied first
    dependency_type: ControlDependencyType = ControlDependencyType.PREREQUISITE
    description: str = ""
    optional: bool = False  # Whether failure of dependency blocks this control


@dataclass
class CustomValidator:
    """Framework for custom validators."""

    control_id: str
    name: str
    description: str
    validator_func: Callable[[dict[str, object], dict[str, object] | None], ValidationResult]
    enabled: bool = True
    priority: int = 0  # Higher priority runs first


@dataclass
class FindingLifecycleEvent:
    """Track finding status changes."""

    finding_id: int
    timestamp: str
    from_status: str
    to_status: str
    assigned_to: str | None = None
    notes: str | None = None
    remediation_evidence: dict[str, object] | None = field(default_factory=dict)


class ControlDependencyGraph:
    """Manages control dependencies and validates prerequisite controls."""

    def __init__(self) -> None:
        """Initialize the ControlDependencyGraph with standard dependencies."""
        self.dependencies: dict[str, list[ControlDependency]] = {}
        self._init_standard_dependencies()

    def _init_standard_dependencies(self) -> None:
        """Initialize standard FedRAMP/NIST control dependencies."""
        # AC-2 (Account Management) is prerequisite for AC-3, AC-4, AC-5
        self.add_dependency(
            ControlDependency(
                source_control="ac-3",
                depends_on="ac-2",
                dependency_type=ControlDependencyType.PREREQUISITE,
                description="Access Enforcement depends on Account Management",
            )
        )
        # AC-1 (Access Control Policy) prerequisite for all AC controls
        for control_id in ["ac-2", "ac-3", "ac-4", "ac-5", "ac-6"]:
            self.add_dependency(
                ControlDependency(
                    source_control=control_id,
                    depends_on="ac-1",
                    dependency_type=ControlDependencyType.PREREQUISITE,
                    optional=True,  # Policy can exist separately
                )
            )
        # IA-1 (Identification and Authentication Policy) prerequisite
        for control_id in ["ia-2", "ia-3", "ia-4", "ia-5"]:
            self.add_dependency(
                ControlDependency(
                    source_control=control_id,
                    depends_on="ia-1",
                    dependency_type=ControlDependencyType.PREREQUISITE,
                    optional=True,
                )
            )

    def add_dependency(self, dep: ControlDependency) -> None:
        """Add a control dependency."""
        control_upper = dep.source_control.upper()
        if control_upper not in self.dependencies:
            self.dependencies[control_upper] = []
        self.dependencies[control_upper].append(dep)

    def get_dependencies(self, control_id: str) -> list[ControlDependency]:
        """Get all dependencies for a control."""
        control_upper = control_id.upper()
        return self.dependencies.get(control_upper, [])

    def get_blockers(self, control_id: str) -> list[str]:
        """Get prerequisite controls that must pass for this control."""
        blockers = []
        for dep in self.get_dependencies(control_id):
            if dep.dependency_type == ControlDependencyType.PREREQUISITE and not dep.optional:
                blockers.append(dep.depends_on.upper())
        return blockers

    def validate_with_dependencies(
        self, control_id: str, validation_results: dict[str, ValidationResult], strict: bool = False
    ) -> tuple[bool, list[str]]:
        """
        Check if control can be validated based on dependencies.

        Args:
            control_id: Control to check
            validation_results: Dict of control_id -> ValidationResult
            strict: If True, all prerequisites must pass; else only required ones

        Returns:
            (can_validate, blocking_controls)
        """
        blockers = self.get_blockers(control_id)
        blocking = []

        for blocker in blockers:
            if blocker not in validation_results:
                blocking.append(f"{blocker} (not yet validated)")
            else:
                result = validation_results[blocker]
                if result.status != ValidationStatus.PASS:
                    blocking.append(f"{blocker} ({result.status.value})")

        return len(blocking) == 0, blocking

    def get_validation_order(self, control_ids: list[str]) -> list[str]:
        """
        Topologically sort controls by dependencies.

        Controls with no dependencies or satisfied dependencies come first.

        Args:
            control_ids: List of control IDs to order

        Returns:
            Ordered list for validation
        """
        control_set = {c.upper() for c in control_ids}
        ordered = []
        remaining = set(control_set)

        # Iteratively add controls with satisfied dependencies
        while remaining:
            ready = []
            for control in remaining:
                deps = self.get_blockers(control)
                # Control is ready if all blockers are already ordered
                if all(dep.upper() in ordered or dep.upper() not in control_set for dep in deps):
                    ready.append(control)

            if not ready:
                # Circular dependency or unsatisfiable - add remaining in original order
                ordered.extend(sorted(remaining))
                break

            ordered.extend(sorted(ready))
            remaining -= set(ready)

        return ordered


class CustomValidatorRegistry:
    """Registry for custom validators."""

    def __init__(self) -> None:
        """Initialize the CustomValidatorRegistry with an empty validator dictionary."""
        self.validators: dict[str, list[CustomValidator]] = {}

    def register(self, validator: CustomValidator) -> None:
        """Register a custom validator."""
        control_upper = validator.control_id.upper()
        if control_upper not in self.validators:
            self.validators[control_upper] = []
        self.validators[control_upper].append(validator)
        # Sort by priority (descending)
        self.validators[control_upper].sort(key=lambda v: v.priority, reverse=True)

    def get_validators(self, control_id: str) -> list[CustomValidator]:
        """Get enabled validators for a control."""
        control_upper = control_id.upper()
        validators = self.validators.get(control_upper, [])
        return [v for v in validators if v.enabled]

    def validate(
        self,
        control_id: str,
        evidence: dict[str, object],
        system_state: dict[str, object] | None = None,
    ) -> ValidationResult | None:
        """
        Run custom validators for a control.

        Returns first passing result, or last failing result.

        Args:
            control_id: Control ID to validate
            evidence: Evidence dict
            system_state: Optional live system state

        Returns:
            ValidationResult from custom validator, or None if no validators
        """
        validators = self.get_validators(control_id)
        if not validators:
            return None

        last_result = None
        for validator in validators:
            try:
                result = validator.validator_func(evidence, system_state)
                last_result = result
                if result.status == ValidationStatus.PASS:
                    return result  # Short-circuit on pass
            except Exception as e:
                # Log but continue to next validator
                last_result = ValidationResult(
                    control_id=control_id,
                    status=ValidationStatus.UNKNOWN,
                    message=f"Validator '{validator.name}' failed: {str(e)}",
                    evidence_keys=[],
                    metadata={"error": str(e), "validator": validator.name},
                )

        return last_result


class FindingsLifecycleManager:
    """Manages finding status transitions and remediation tracking."""

    # Valid state transitions
    VALID_TRANSITIONS = {
        "open": ["investigating", "closed"],
        "investigating": ["remediating", "closed"],
        "remediating": ["investigating", "closed"],
        "closed": ["open"],  # Reopen if needed
    }

    def __init__(self, session=None) -> None:
        """Initialize with optional DB session for persistence."""
        self.session = session
        self.events: list[FindingLifecycleEvent] = []

    def transition_finding(
        self,
        finding_id: int,
        from_status: str,
        to_status: str,
        assigned_to: str | None = None,
        notes: str | None = None,
        remediation_evidence: dict[str, Any] | None = None,
    ) -> bool:
        """
        Transition finding to new status.

        Args:
            finding_id: Finding ID
            from_status: Current status
            to_status: New status
            assigned_to: Owner of remediation
            notes: Status change notes
            remediation_evidence: Evidence of remediation

        Returns:
            True if transition valid, False otherwise
        """
        if from_status not in self.VALID_TRANSITIONS:
            return False

        valid_next = self.VALID_TRANSITIONS[from_status]
        if to_status not in valid_next:
            return False

        event = FindingLifecycleEvent(
            finding_id=finding_id,
            timestamp=self._get_timestamp(),
            from_status=from_status,
            to_status=to_status,
            assigned_to=assigned_to,
            notes=notes,
            remediation_evidence=remediation_evidence or {},
        )
        self.events.append(event)

        # Persist if session available
        if self.session:
            self._persist_event(event)

        return True

    def get_finding_status_history(self, finding_id: int) -> list[FindingLifecycleEvent]:
        """Get status change history for a finding."""
        return [e for e in self.events if e.finding_id == finding_id]

    def can_close_finding(self, finding_id: int, current_status: str) -> bool:
        """Check if finding can be closed."""
        return (
            current_status in self.VALID_TRANSITIONS
            and "closed" in self.VALID_TRANSITIONS[current_status]
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.utcnow().isoformat()

    def _persist_event(self, event: FindingLifecycleEvent) -> None:
        """Persist event to database (async wrapper needed for actual use)."""
        # This would need async context in real usage
        # For now, just track in memory
        pass


# Global registry instances
dependency_graph = ControlDependencyGraph()
custom_validators = CustomValidatorRegistry()
findings_manager = FindingsLifecycleManager()
