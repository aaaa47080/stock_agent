"""
Security Monitoring System (Stage 4 Security)

Logs and tracks security events for monitoring and alerting.
Events are stored in a JSONL file for easy parsing and rotation.

Security Event Types:
- BRUTE_FORCE_ATTEMPT: Multiple failed login attempts
- RATE_LIMIT_EXCEEDED: API rate limit exceeded
- SUSPICIOUS_LOGIN: Login from unusual location/IP
- TOKEN_THEFT: Token used from multiple IPs simultaneously
- UNUSUAL_ACTIVITY: Anomalous user behavior
- FAILED_VERIFICATION: Authentication verification failures
- ADMIN_ACCESS: Admin operations performed
- KEY_ROTATION: JWT key rotation events
- TEST_MODE_ENABLED: Development mode enabled
"""
import json
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from api.utils import logger


class SecurityEventType(Enum):
    """Types of security events"""
    BRUTE_FORCE_ATTEMPT = "brute_force"
    RATE_LIMIT_EXCEEDED = "rate_limit"
    SUSPICIOUS_LOGIN = "suspicious_login"
    TOKEN_THEFT = "token_theft"
    UNUSUAL_ACTIVITY = "unusual_activity"
    FAILED_VERIFICATION = "failed_verification"
    ADMIN_ACCESS = "admin_access"
    KEY_ROTATION = "key_rotation"
    TEST_MODE_ENABLED = "test_mode"
    PERMISSION_ESCALATION = "permission_escalation"
    SQL_INJECTION_ATTEMPT = "sql_injection"
    XSS_ATTEMPT = "xss_attempt"


class SeverityLevel(Enum):
    """Severity levels for security events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_type: SecurityEventType
    severity: SeverityLevel
    title: str
    description: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[Dict] = None
    timestamp: datetime = None
    resolved: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enums to values
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        # Convert datetime to ISO format
        if isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class SecurityMonitor:
    """
    Security event monitoring and logging system.

    Stores events in JSONL format for easy parsing and rotation.
    Provides querying and statistics functionality.
    """

    def __init__(self, storage_path: str = "data/security_events.jsonl"):
        """
        Initialize the security monitor.

        Args:
            storage_path: Path to the event log file (JSONL format)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load alert dispatcher
        try:
            from core.alert_dispatcher import AlertDispatcher
            self.alert_dispatcher = AlertDispatcher()
        except ImportError:
            logger.warning("⚠️ Alert dispatcher not available")
            self.alert_dispatcher = None

    def log_event(self, event: SecurityEvent) -> Dict[str, Any]:
        """
        Log a security event to storage and trigger alerts if needed.

        Args:
            event: SecurityEvent to log

        Returns:
            Dictionary representation of the logged event
        """
        event_data = event.to_dict()

        # Append to JSONL file
        try:
            with open(self.storage_path, "a") as f:
                f.write(json.dumps(event_data) + "\n")
        except IOError as e:
            logger.error(f"Failed to write security event: {e}")

        # Check if alert is needed
        self._check_alerts(event)

        # Log to application logger
        level_map = {
            SeverityLevel.LOW: "info",
            SeverityLevel.MEDIUM: "warning",
            SeverityLevel.HIGH: "warning",
            SeverityLevel.CRITICAL: "error"
        }
        log_level = level_map.get(event.severity, "info")
        log_func = getattr(logger, log_level, logger.info)
        log_func(
            f"[SECURITY] {event.event_type.value}: {event.title} "
            f"(user={event.user_id}, ip={event.ip_address})"
        )

        return event_data

    def _check_alerts(self, event: SecurityEvent):
        """
        Check if event requires alert dispatch.

        High and critical severity events trigger alerts.
        """
        if self.alert_dispatcher is None:
            return

        if event.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]:
            try:
                self.alert_dispatcher.send(
                    channel="telegram",
                    severity=event.severity.value,
                    title=event.title,
                    message=f"{event.description}\n\n"
                           f"User: {event.user_id or 'N/A'}\n"
                           f"IP: {event.ip_address or 'N/A'}\n"
                           f"Time: {event.timestamp.isoformat()}"
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")

    def get_recent_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get security events from the last N hours.

        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            List of event dictionaries, sorted by timestamp (newest first)
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        events = []

        if not self.storage_path.exists():
            return events

        try:
            with open(self.storage_path, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])
                        if event_time >= cutoff:
                            events.append(event)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
        except IOError:
            return []

        return sorted(events, key=lambda e: e["timestamp"], reverse=True)

    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get security statistics for the last N days.

        Args:
            days: Number of days to analyze (default: 7)

        Returns:
            Dictionary with statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        events_by_type = {}
        events_by_severity = {}
        total_events = 0
        unresolved_events = 0

        if not self.storage_path.exists():
            return {
                "total_events": 0,
                "unresolved_events": 0,
                "by_type": {},
                "by_severity": {},
                "period_days": days
            }

        try:
            with open(self.storage_path, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])

                        if event_time < cutoff:
                            continue

                        total_events += 1

                        # Count by type
                        event_type = event.get("event_type", "unknown")
                        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

                        # Count by severity
                        severity = event.get("severity", "unknown")
                        events_by_severity[severity] = events_by_severity.get(severity, 0) + 1

                        # Count unresolved
                        if not event.get("resolved", True):
                            unresolved_events += 1

                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
        except IOError:
            pass

        return {
            "total_events": total_events,
            "unresolved_events": unresolved_events,
            "by_type": events_by_type,
            "by_severity": events_by_severity,
            "period_days": days
        }

    def cleanup_old_events(self, days_to_keep: int = 90):
        """
        Remove security events older than specified days.

        Args:
            days_to_keep: Number of days of events to retain (default: 90)

        Returns:
            Number of events removed
        """
        if not self.storage_path.exists():
            return 0

        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        remaining_events = []
        removed_count = 0

        try:
            with open(self.storage_path, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])

                        if event_time >= cutoff:
                            remaining_events.append(line.strip())
                        else:
                            removed_count += 1
                    except (json.JSONDecodeError, ValueError, KeyError):
                        # Keep malformed lines
                        remaining_events.append(line.strip())

            # Write back filtered events
            with open(self.storage_path, "w") as f:
                for event_line in remaining_events:
                    f.write(event_line + "\n")

            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old security events (older than {days_to_keep} days)")

        except IOError as e:
            logger.error(f"Failed to cleanup security events: {e}")
            return 0

        return removed_count


# ============================================================================
# Convenience Functions
# ============================================================================

_global_monitor: Optional[SecurityMonitor] = None


def get_security_monitor() -> SecurityMonitor:
    """Get the global security monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SecurityMonitor()
    return _global_monitor


def log_security_event(
    event_type: SecurityEventType,
    severity: SeverityLevel,
    title: str,
    description: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Convenience function to log a security event.

    Args:
        event_type: Type of security event
        severity: Severity level
        title: Event title
        description: Event description
        user_id: Associated user ID (optional)
        ip_address: Associated IP address (optional)
        metadata: Additional metadata (optional)

    Returns:
        Dictionary representation of the logged event
    """
    monitor = get_security_monitor()
    event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        title=title,
        description=description,
        user_id=user_id,
        ip_address=ip_address,
        metadata=metadata
    )
    return monitor.log_event(event)
