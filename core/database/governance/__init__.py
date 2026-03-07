"""
Community Governance Database Operations
Contains: Report management, voting, violations, audit reputation, activity logging, helpers

This module is split into submodules for better organization:
- constants: Governance thresholds and limits
- reports: Report creation and management
- voting: Vote casting and consensus
- violations: Violation points and suspensions
- reputation: Audit reputation tracking
- activity: Activity logging
- helpers: Utility functions
"""

from .constants import (
    VIOLATION_LEVELS,
    REPORT_TYPES,
    VIOLATION_ACTIONS,
    SUSPENSION_DURATIONS,
    MIN_VOTES_REQUIRED,
    CONSENSUS_APPROVE_THRESHOLD,
    CONSENSUS_REJECT_THRESHOLD,
    DEFAULT_DAILY_REPORT_LIMIT,
    PRO_DAILY_REPORT_LIMIT,
)

from .reports import (
    create_report,
    get_pending_reports,
    get_report_by_id,
    get_user_reports,
    check_daily_report_limit,
    get_daily_report_usage,
)

from .voting import (
    vote_on_report,
    get_report_votes,
    check_report_consensus,
    finalize_report,
)

from .violations import (
    add_violation_points,
    get_user_violation_points,
    get_user_violations,
    determine_suspension_action,
    apply_suspension,
    check_user_suspension,
)

from .reputation import (
    get_audit_reputation,
    calculate_vote_weight,
    update_audit_reputation,
)

from .activity import (
    log_activity,
    get_user_activity_logs,
)

from .helpers import (
    get_content_author,
    get_report_statistics,
    get_top_reviewers,
)


__all__ = [
    # Constants
    "VIOLATION_LEVELS",
    "REPORT_TYPES",
    "VIOLATION_ACTIONS",
    "SUSPENSION_DURATIONS",
    "MIN_VOTES_REQUIRED",
    "CONSENSUS_APPROVE_THRESHOLD",
    "CONSENSUS_REJECT_THRESHOLD",
    "DEFAULT_DAILY_REPORT_LIMIT",
    "PRO_DAILY_REPORT_LIMIT",
    # Reports
    "create_report",
    "get_pending_reports",
    "get_report_by_id",
    "get_user_reports",
    "check_daily_report_limit",
    "get_daily_report_usage",
    # Voting
    "vote_on_report",
    "get_report_votes",
    "check_report_consensus",
    "finalize_report",
    # Violations
    "add_violation_points",
    "get_user_violation_points",
    "get_user_violations",
    "determine_suspension_action",
    "apply_suspension",
    "check_user_suspension",
    # Reputation
    "get_audit_reputation",
    "calculate_vote_weight",
    "update_audit_reputation",
    # Activity
    "log_activity",
    "get_user_activity_logs",
    # Helpers
    "get_content_author",
    "get_report_statistics",
    "get_top_reviewers",
]
