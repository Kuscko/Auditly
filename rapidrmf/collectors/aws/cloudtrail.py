"""AWS CloudTrail evidence collector for RapidRMF.

Collects CloudTrail evidence including:
- Trail configurations
- Event history (management events, data events)
- CloudTrail status
- S3 bucket logging configuration
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from .client import AWSClient

logger = logging.getLogger(__name__)

try:
    from botocore.exceptions import ClientError
except ImportError:
    ClientError = Exception  # type: ignore


class CloudTrailCollector:
    """Collector for AWS CloudTrail evidence."""

    def __init__(self, client: AWSClient):
        """Initialize CloudTrail collector.

        Args:
            client: AWSClient instance for API calls
        """
        self.client = client
        self.cloudtrail = client.get_client("cloudtrail")
        self.logs = client.get_client("logs")

    def collect_all(self) -> dict[str, Any]:
        """Collect all CloudTrail evidence.

        Returns:
            Dictionary containing CloudTrail evidence
        """
        logger.info("Starting AWS CloudTrail evidence collection")

        evidence = {
            "trails": self.collect_trails(),
            "event_history": self.collect_event_history(),
            "metadata": {
                "collected_at": datetime.utcnow().isoformat(),
                "account_id": self.client.get_account_id(),
                "region": self.client.region,
                "collector": "aws-cloudtrail",
                "version": "1.0.0",
            },
        }

        evidence_json = json.dumps(evidence, sort_keys=True, default=str)
        evidence["metadata"]["sha256"] = hashlib.sha256(evidence_json.encode()).hexdigest()

        logger.info("CloudTrail collection complete: %d trails", len(evidence["trails"]))

        return evidence

    def collect_trails(self) -> list[dict[str, Any]]:
        """Collect CloudTrail trail configurations."""
        trails = []

        try:
            response = self.cloudtrail.describe_trails(includeShadowTrails=True)
            for trail in response.get("trailList", []):
                trail_config = {
                    "trail_name": trail.get("Name"),
                    "trail_arn": trail.get("TrailARN"),
                    "s3_bucket_name": trail.get("S3BucketName"),
                    "include_global_events": trail.get("IncludeGlobalServiceEvents"),
                    "is_multi_region_trail": trail.get("IsMultiRegionTrail"),
                    "is_organization_trail": trail.get("IsOrganizationTrail"),
                    "home_region": trail.get("HomeRegion"),
                    "kms_key_id": trail.get("KMSKeyId"),
                    "enable_log_file_validation": trail.get("HasCustomEventSelectors"),
                    "sns_topic_arn": trail.get("SNSTopicARN"),
                    "cloud_watch_logs_group_arn": trail.get("CloudWatchLogsGroupArn"),
                    "cloud_watch_logs_role_arn": trail.get("CloudWatchLogsRoleArn"),
                    "is_logging": self._get_trail_status(trail.get("Name")),
                }
                
                trails.append(trail_config)

            logger.debug("Collected %d CloudTrail trails", len(trails))
        except ClientError as e:
            logger.error("Failed to collect CloudTrail trails: %s", e)

        return trails

    def collect_event_history(self, days: int = 7) -> list[dict[str, Any]]:
        """Collect recent CloudTrail events.

        Args:
            days: Number of days to look back (default: 7)

        Returns:
            List of recent CloudTrail events
        """
        events = []

        try:
            start_time = datetime.utcnow() - timedelta(days=days)
            
            paginator = self.cloudtrail.get_paginator("lookup_events")
            for page in paginator.paginate(StartTime=start_time):
                for event in page.get("Events", []):
                    events.append({
                        "event_id": event.get("EventId"),
                        "event_name": event.get("EventName"),
                        "event_time": event.get("EventTime", "").isoformat() if event.get("EventTime") else None,
                        "username": event.get("Username"),
                        "resources": [
                            {
                                "resource_type": r.get("ResourceType"),
                                "resource_name": r.get("ResourceName"),
                            }
                            for r in event.get("Resources", [])
                        ],
                        "event_source": event.get("EventSource"),
                        "access_key_id": event.get("AccessKeyId"),
                        "cloud_trail_event": event.get("CloudTrailEvent"),
                    })

            logger.debug("Collected %d CloudTrail events (last %d days)", len(events), days)
        except ClientError as e:
            logger.error("Failed to collect CloudTrail events: %s", e)

        return events

    def _get_trail_status(self, trail_name: str) -> bool:
        """Get whether a trail is currently logging."""
        try:
            response = self.cloudtrail.get_trail_status(Name=trail_name)
            return response.get("IsLogging", False)
        except ClientError:
            return False
