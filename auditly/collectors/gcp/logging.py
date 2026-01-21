"""GCP Cloud Logging evidence collector for auditly compliance automation.

Collects evidence about:
- Log sinks and exports
- Audit logs configuration
- Log-based metrics
- Retention policies
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from google.cloud import logging_v2

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


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

        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-logging required for Logging collector")

        self.logging_client = logging_v2.LoggingServiceV2Client(credentials=client.credentials)
        self.sinks_client = logging_v2.ConfigServiceV2Client(credentials=client.credentials)
        self.metrics_client = logging_v2.MetricsServiceV2Client(credentials=client.credentials)

    def collect_all(self) -> dict[str, Any]:
        """Collect all Cloud Logging evidence.

        Returns:
            Dictionary containing all Logging evidence types
        """
        evidence = {
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
        """Collect log sinks (exports).

        Returns:
            List of log sink dictionaries
        """
        sinks = []

        try:
            parent = f"projects/{self.project_id}"
            request = logging_v2.ListSinksRequest(parent=parent)

            for sink in self.sinks_client.list_sinks(request=request):
                sink_dict = {
                    "name": sink.name,
                    "destination": sink.destination,
                    "filter": sink.filter,
                    "description": sink.description,
                    "disabled": sink.disabled,
                    "output_version_format": sink.output_version_format.name
                    if sink.output_version_format
                    else None,
                    "writer_identity": sink.writer_identity,
                    "include_children": sink.include_children,
                }
                sinks.append(sink_dict)

            logger.info("Collected %d log sinks", len(sinks))
        except Exception as e:
            logger.error("Error collecting log sinks: %s", e)

        return sinks

    def collect_metrics(self) -> list[dict[str, Any]]:
        """Collect log-based metrics.

        Returns:
            List of log-based metric dictionaries
        """
        metrics = []

        try:
            parent = f"projects/{self.project_id}"
            request = logging_v2.ListLogMetricsRequest(parent=parent)

            for metric in self.metrics_client.list_log_metrics(request=request):
                metric_dict = {
                    "name": metric.name,
                    "description": metric.description,
                    "filter": metric.filter,
                    "metric_descriptor": {
                        "metric_kind": metric.metric_descriptor.metric_kind.name
                        if metric.metric_descriptor and metric.metric_descriptor.metric_kind
                        else None,
                        "value_type": metric.metric_descriptor.value_type.name
                        if metric.metric_descriptor and metric.metric_descriptor.value_type
                        else None,
                        "unit": metric.metric_descriptor.unit if metric.metric_descriptor else None,
                    }
                    if metric.metric_descriptor
                    else {},
                    "label_extractors": dict(metric.label_extractors)
                    if metric.label_extractors
                    else {},
                }
                metrics.append(metric_dict)

            logger.info("Collected %d log-based metrics", len(metrics))
        except Exception as e:
            logger.error("Error collecting log-based metrics: %s", e)

        return metrics

    def collect_logs_summary(self) -> dict[str, Any]:
        """Collect summary information about available logs.

        Returns:
            Dictionary with log summary information
        """
        summary = {
            "admin_activity_logs": False,
            "data_access_logs": False,
            "system_event_logs": False,
            "policy_denied_logs": False,
            "log_types": [],
        }

        try:
            parent = f"projects/{self.project_id}"

            # List logs to see what's available
            request = logging_v2.ListLogsRequest(parent=parent)

            log_names = []
            for log_name in self.logging_client.list_logs(request=request):
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
