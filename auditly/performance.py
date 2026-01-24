"""Performance optimization: caching, parallel collection, incremental validation."""

from __future__ import annotations

import asyncio
import fnmatch
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class CacheEntry:
    """Cached entry with TTL."""

    key: str
    value: object
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 3600  # 1 hour default

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        # ttl_seconds <= 0 means expire immediately
        if self.ttl_seconds <= 0:
            return True
        age = datetime.utcnow() - self.created_at
        return age > timedelta(seconds=self.ttl_seconds)


class ValidationResultCache:
    """Cache for validation results with TTL support."""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            default_ttl: Default TTL in seconds (3600 = 1 hour)
        """
        self.cache: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> object | None:
        """Get cached value if not expired."""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        if entry.is_expired():
            del self.cache[key]
            return None

        return entry.value

    def set(self, key: str, value: object, ttl: int | None = None):
        """Cache a value."""
        ttl = self.default_ttl if ttl is None else ttl
        self.cache[key] = CacheEntry(key=key, value=value, ttl_seconds=ttl)

    def invalidate(self, pattern: str | None = None):
        """
        Invalidate cache entries.

        Args:
            pattern: Wildcard pattern (e.g., "system-123-*") or None to clear all
        """
        if pattern is None:
            self.cache.clear()
        else:
            # Simple wildcard matching

            keys_to_delete = [k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_delete:
                del self.cache[k]

    def invalidate_control(self, control_id: str):
        """Invalidate cache for a specific control."""
        # Match keys that contain the control id anywhere in the string
        self.invalidate(f"*control-{control_id.lower()}*")

    def invalidate_system(self, system_id: int):
        """Invalidate cache for a specific system."""
        self.invalidate(f"system-{system_id}-*")

    def make_key(self, *parts: str) -> str:
        """Create cache key from parts."""
        return "-".join(str(p).lower() for p in parts)

    def stats(self) -> dict[str, object]:
        """Get cache statistics."""
        expired = sum(1 for e in self.cache.values() if e.is_expired())
        return {
            "entries": len(self.cache),
            "expired": expired,
            "active": len(self.cache) - expired,
        }


class EvidenceDependencyGraph:
    """Track which controls depend on which evidence types."""

    def __init__(self) -> None:
        """Initialize EvidenceDependencyGraph with empty mappings."""
        self.evidence_to_controls: dict[str, set[str]] = {}
        self.control_to_evidence: dict[str, set[str]] = {}

    def add_dependency(self, control_id: str, evidence_types: list[str]):
        """Register evidence types for a control."""
        control_upper = control_id.upper()
        self.control_to_evidence[control_upper] = set(evidence_types)

        for ev_type in evidence_types:
            if ev_type not in self.evidence_to_controls:
                self.evidence_to_controls[ev_type] = set()
            self.evidence_to_controls[ev_type].add(control_upper)

    def get_affected_controls(self, evidence_types: list[str]) -> set[str]:
        """
        Get controls affected by changes to specific evidence types.

        Args:
            evidence_types: List of evidence types that changed

        Returns:
            Set of control IDs that depend on these evidence types
        """
        affected = set()
        for ev_type in evidence_types:
            controls = self.evidence_to_controls.get(ev_type, set())
            affected.update(controls)
        return affected

    def get_evidence_for_control(self, control_id: str) -> set[str]:
        """Get evidence types needed for a control."""
        return self.control_to_evidence.get(control_id.upper(), set())


class IncrementalValidator:
    """Validates only controls affected by evidence changes."""

    def __init__(self) -> None:
        """Initialize IncrementalValidator with evidence graph and snapshots."""
        self.evidence_graph = EvidenceDependencyGraph()
        self.last_validation: dict[str, object] = {}
        self.evidence_snapshots: dict[str, dict[str, object]] = {}

    def register_evidence_types(self, control_id: str, evidence_types: list[str]):
        """Register what evidence types affect a control."""
        self.evidence_graph.add_dependency(control_id, evidence_types)

    def get_controls_needing_validation(
        self,
        all_controls: list[str],
        current_evidence: dict[str, object],
        previous_evidence: dict[str, object] | None = None,
    ) -> list[str]:
        """
        Determine which controls need re-validation.

        Args:
            all_controls: List of all control IDs
            current_evidence: Current evidence dict
            previous_evidence: Previous evidence dict (from last validation)

        Returns:
            List of control IDs that need re-validation
        """
        if previous_evidence is None:
            # No previous state - validate all
            return all_controls

        # Find changed evidence types
        changed_evidence = set()

        # Check for new or modified evidence
        for ev_type, ev_data in current_evidence.items():
            if ev_type not in previous_evidence:
                changed_evidence.add(ev_type)
            elif ev_data != previous_evidence.get(ev_type):
                changed_evidence.add(ev_type)

        # Check for removed evidence
        for ev_type in previous_evidence.keys():
            if ev_type not in current_evidence:
                changed_evidence.add(ev_type)

        if not changed_evidence:
            # No changes - no validation needed
            return []

        # Get controls affected by changed evidence
        affected = self.evidence_graph.get_affected_controls(list(changed_evidence))

        # Return intersection with requested controls
        return [c for c in all_controls if c.upper() in affected]

    def snapshot_evidence(self, evidence: dict[str, object]):
        """Store evidence snapshot for comparison next time."""
        # Use JSON serialization to handle complex types
        self.evidence_snapshots["last"] = json.loads(json.dumps(evidence, default=str))


class ParallelCollector:
    """Enables parallel evidence collection across services."""

    def __init__(self, max_concurrent: int = 5) -> None:
        """Initialize ParallelCollector with concurrency limit."""
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def collect_parallel(
        self, collectors: dict[str, asyncio.Future], timeout: int = 300
    ) -> dict[str, object]:
        """
        Run collectors in parallel with concurrency limit.

        Args:
            collectors: Dict of {service_name: collector_coro}
            timeout: Timeout in seconds for entire collection

        Returns:
            Dict of {service_name: collected_evidence}
        """
        results = {}
        errors = {}

        async def collect_service(name: str, coro):
            async with self.semaphore:
                try:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                    results[name] = result
                except asyncio.TimeoutError:
                    errors[name] = f"Timeout after {timeout}s"
                except Exception as e:
                    errors[name] = str(e)

        # Create tasks for all collectors
        tasks = [collect_service(name, coro) for name, coro in collectors.items()]

        # Run all tasks
        await asyncio.gather(*tasks)

        return {
            "results": results,
            "errors": errors,
            "success": len(results),
            "failed": len(errors),
        }

    async def collect_with_fallback(
        self,
        primary_collectors: dict[str, asyncio.Future],
        fallback_collectors: dict[str, asyncio.Future] | None = None,
        timeout: int = 60,
    ) -> dict[str, object]:
        """
        Run primary collectors, with fallback if needed.

        Args:
            primary_collectors: Primary data sources
            fallback_collectors: Fallback sources (run only if primary fails)
            timeout: Timeout in seconds

        Returns:
            Combined evidence from both sources
        """
        primary = await self.collect_parallel(primary_collectors, timeout)

        if fallback_collectors and isinstance(primary["failed"], int) and primary["failed"] > 0:
            # Try fallback for services that failed
            fallback = await self.collect_parallel(fallback_collectors, timeout)

            # Merge: fallback fills in missing results
            if isinstance(fallback["results"], dict):
                for service, evidence in fallback["results"].items():
                    if isinstance(primary["results"], dict):
                        if service not in primary["results"]:
                            primary["results"][service] = evidence

        return primary


class Metrics:
    """Container for performance metric fields."""

    def __getitem__(self, key: str) -> object:
        """Get a metric value by key (dict-like access)."""
        return getattr(self, key)

    def __setitem__(self, key: str, value: object) -> None:
        """Set a metric value by key (dict-like access)."""
        setattr(self, key, value)

    def __init__(self) -> None:
        """Initialize all metric fields to default values."""
        self.total_validations: int = 0
        self.cached_validations: int = 0
        self.parallel_collections: int = 0
        self.incremental_validations: int = 0
        self.avg_validation_time: float = 0.0
        self.collection_times: dict[str, list[float]] = {}
        self.cache_hit_rate: float = 0.0


class PerformanceMetrics:
    """Track validation performance metrics."""

    def __init__(self) -> None:
        """Initialize PerformanceMetrics with default metrics and timings."""
        self.metrics = Metrics()
        self.timings: list[float] = []

    def record_validation(self, duration: float, cached: bool = False):
        """Record a validation run."""
        self.metrics.total_validations += 1
        if cached:
            self.metrics.cached_validations += 1

        self.timings.append(duration)
        self.metrics.avg_validation_time = sum(self.timings) / len(self.timings)
        self.metrics.cache_hit_rate = (
            (self.metrics.cached_validations / self.metrics.total_validations)
            if self.metrics.total_validations > 0
            else 0.0
        )

    def record_collection(self, service: str, duration: float):
        """Record collection timing for a service."""
        if service not in self.metrics.collection_times:
            self.metrics.collection_times[service] = []
        self.metrics.collection_times[service].append(duration)

    def record_incremental_validation(self):
        """Record an incremental validation."""
        self.metrics.incremental_validations += 1

    def record_parallel_collection(self):
        """Record a parallel collection."""
        self.metrics.parallel_collections += 1

    def get_report(self) -> dict[str, object]:
        """Get metrics report."""
        avg_times = {}
        for service, times in self.metrics.collection_times.items():
            avg_times[service] = sum(times) / len(times) if times else 0.0

        return {
            "total_validations": self.metrics.total_validations,
            "cached_validations": self.metrics.cached_validations,
            "parallel_collections": self.metrics.parallel_collections,
            "incremental_validations": self.metrics.incremental_validations,
            "avg_validation_time": self.metrics.avg_validation_time,
            "collection_times": self.metrics.collection_times,
            "cache_hit_rate": self.metrics.cache_hit_rate,
            "avg_collection_times": avg_times,
        }


# Global instances
validation_cache = ValidationResultCache()
incremental_validator = IncrementalValidator()
parallel_collector = ParallelCollector()
performance_metrics = PerformanceMetrics()
