"""
Governance Constants
Violation levels, report types, thresholds, and limits
"""

from datetime import timedelta

# Violation levels with corresponding point values
VIOLATION_LEVELS = {"mild": 1, "medium": 3, "severe": 5, "critical": 30}

# Valid report types
REPORT_TYPES = ["spam", "harassment", "misinformation", "scam", "illegal", "other"]

# Violation actions based on point thresholds
VIOLATION_ACTIONS = {
    5: "warning",
    10: "suspend_3d",
    20: "suspend_7d",
    30: "suspend_30d",
    40: "permanent_ban",
}

# Suspension duration mappings
SUSPENSION_DURATIONS = {
    "warning": timedelta(days=0),
    "suspend_3d": timedelta(days=3),
    "suspend_7d": timedelta(days=7),
    "suspend_30d": timedelta(days=30),
    "suspend_permanent": timedelta(days=365 * 100),  # Effectively permanent
}

# Voting consensus thresholds
MIN_VOTES_REQUIRED = 3
CONSENSUS_APPROVE_THRESHOLD = 0.70
CONSENSUS_REJECT_THRESHOLD = 0.30

# Default daily report limits
DEFAULT_DAILY_REPORT_LIMIT = 5
PRO_DAILY_REPORT_LIMIT = 10
