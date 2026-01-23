from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

"""GCP Cloud Logging evidence collector for auditly compliance automation.

Collects evidence about:
- Log sinks and exports
- Audit logs configuration
- Log-based metrics
- Retention policies
"""

logger = logging.getLogger(__name__)


# Predeclare for type checkers
import types

logging_v2: types.ModuleType | None = None
ConfigServiceV2Client: type | None = None
MetricsServiceV2Client: type | None = None
LoggingServiceV2Client: type | None = None
GCP_AVAILABLE = False
try:
    import google.cloud.logging_v2 as _logging_v2
    from google.cloud.logging_v2.services.config_service_v2 import (
        ConfigServiceV2Client as _ConfigServiceV2Client,
    )
    from google.cloud.logging_v2.services.logging_service_v2 import (
        LoggingServiceV2Client as _LoggingServiceV2Client,
    )
    from google.cloud.logging_v2.services.metrics_service_v2 import (
        MetricsServiceV2Client as _MetricsServiceV2Client,
    )

    logging_v2 = _logging_v2
    ConfigServiceV2Client = _ConfigServiceV2Client
    MetricsServiceV2Client = _MetricsServiceV2Client
    LoggingServiceV2Client = _LoggingServiceV2Client
    GCP_AVAILABLE = True
except ImportError:
    pass


class LoggingCollector:
    """Collector for GCP Cloud Logging evidence.

    Compliance Controls Mapped:
    - AU-2: Audit Events (audit log types)
    - AU-3: Content of Audit Records (log entry content)
    - AU-4: Audit Storage Capacity (log sink destinations)
    - AU-6: Audit Review, Analysis, and Reporting (log-based metrics)
    - AU-9: Protection of Audit Information (log sink permissions)
    - AU-12: Audit Generation (audit logs enabled)
    """

    def __init__(self, client: Any):
        """Initialize Logging collector.

        Args:
            client: GCPClient instance
        """
        self.client = client
        self.project_id = client.project_id

        if (
            not GCP_AVAILABLE
            or not logging_v2
            or not ConfigServiceV2Client
            or not MetricsServiceV2Client
            or not LoggingServiceV2Client
        ):
            raise ImportError("google-cloud-logging required for Logging collector")

        # Use the high-level client for logs, ConfigServiceV2Client for sinks, MetricsServiceV2Client for metrics
        self.logging_client = logging_v2.Client(
            project=self.project_id, credentials=client.credentials
        )
        self.sinks_client = ConfigServiceV2Client(credentials=client.credentials)
        self.metrics_client = MetricsServiceV2Client(credentials=client.credentials)
        self.logging_service_client = LoggingServiceV2Client(credentials=client.credentials)

    def collect_all(self) -> dict[str, Any]:
        """Collect all Cloud Logging evidence.

        Returns:
            Dictionary containing all Logging evidence types
        """
        evidence: dict[str, Any] = {
            "sinks": self.collect_sinks(),
            "metrics": self.collect_metrics(),
            "logs_summary": self.collect_logs_summary(),
            "metadata": {
                "collector": "GCPLoggingCollector",
                "collected_at": datetime.utcnow().isoformat(),
                "project_id": self.project_id,
            },
        }

        # Compute evidence checksum
        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        return evidence

    def collect_sinks(self) -> list[dict[str, Any]]:
        """Collect log sinks (exports)."""
        sinks = []
        try:
            parent = f"projects/{self.project_id}"
            for sink in self.sinks_client.list_sinks(parent=parent):
                sink_dict = {
                    "name": sink.name,
                    "destination": sink.destination,
                    "filter": getattr(sink, "filter", None),
                    "description": getattr(sink, "description", None),
                    "disabled": getattr(sink, "disabled", None),
                    "output_version_format": getattr(sink, "output_version_format", None),
                    "writer_identity": getattr(sink, "writer_identity", None),
                    "include_children": getattr(sink, "include_children", None),
                }
                sinks.append(sink_dict)
            logger.info("Collected %d log sinks", len(sinks))
        except Exception as e:
            logger.error("Error collecting log sinks: %s", e)
        return sinks

    def collect_metrics(self) -> list[dict[str, Any]]:
        """Collect log-based metrics."""
        metrics = []
        try:
            parent = f"projects/{self.project_id}"
            for metric in self.metrics_client.list_log_metrics(parent=parent):
                metric_dict = {
                    "name": metric.name,
                    "description": getattr(metric, "description", None),
                    "filter": getattr(metric, "filter", None),
                    "metric_descriptor": str(getattr(metric, "metric_descriptor", None)),
                    "label_extractors": dict(getattr(metric, "label_extractors", {})),
                }
                metrics.append(metric_dict)
            logger.info("Collected %d log-based metrics", len(metrics))
        except Exception as e:
            logger.error("Error collecting log-based metrics: %s", e)
        return metrics

    def collect_logs_summary(self) -> dict[str, Any]:
        """Collect summary information about available logs."""
        summary = {
            "admin_activity_logs": False,
            "data_access_logs": False,
            "system_event_logs": False,
            "policy_denied_logs": False,
            "log_types": [],
        }
        try:
            parent = f"projects/{self.project_id}"
            log_names = []
            request = {"parent": parent}
            for log_name in self.logging_service_client.list_logs(request=request):
                log_names.append(log_name)
                # Check for audit log types
                if "cloudaudit.googleapis.com/activity" in log_name:
                    summary["admin_activity_logs"] = True
                elif "cloudaudit.googleapis.com/data_access" in log_name:
                    summary["data_access_logs"] = True
                elif "cloudaudit.googleapis.com/system_event" in log_name:
                    summary["system_event_logs"] = True
                elif "cloudaudit.googleapis.com/policy" in log_name:
                    summary["policy_denied_logs"] = True
            summary["log_types"] = log_names[:50]  # Limit to first 50
            summary["total_log_types"] = len(log_names)
            logger.info("Collected logs summary: %d log types", len(log_names))
        except Exception as e:
            logger.error("Error collecting logs summary: %s", e)
        return summary
