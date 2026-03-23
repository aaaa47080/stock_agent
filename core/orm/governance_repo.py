"""
Async ORM repository for community governance operations.

Consolidates all functions from the 6 legacy files in
core.database.governance into a single ``GovernanceRepository`` class:

- **reports.py**: create_report, get_pending_reports, get_report_by_id,
  get_user_reports, check_daily_report_limit, get_daily_report_usage
- **voting.py**: vote_on_report, get_report_votes, check_report_consensus,
  finalize_report
- **violations.py**: add_violation_points, get_user_violation_points,
  get_user_violations, determine_suspension_action, apply_suspension,
  check_user_suspension
- **reputation.py**: get_audit_reputation, calculate_vote_weight,
  update_audit_reputation
- **activity.py**: log_activity, get_user_activity_logs
- **helpers.py**: get_content_author, get_report_statistics, get_top_reviewers

Usage::

    from core.orm.governance_repo import governance_repo

    report = await governance_repo.create_report(...)
    pending = await governance_repo.get_pending_reports(...)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import (
    and_,
    case,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AuditReputation,
    ContentReport,
    ForumComment,
    Post,
    ReportReviewVote,
    User,
    UserActivityLog,
    UserViolation,
    UserViolationPoints,
)
from .session import using_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Governance constants (mirrored from core.database.governance.constants)
# ---------------------------------------------------------------------------

VIOLATION_LEVELS: Dict[str, int] = {
    "mild": 1,
    "medium": 3,
    "severe": 5,
    "critical": 30,
}

REPORT_TYPES: List[str] = [
    "spam",
    "harassment",
    "misinformation",
    "scam",
    "illegal",
    "other",
]

VIOLATION_ACTIONS: Dict[int, str] = {
    5: "warning",
    10: "suspend_3d",
    20: "suspend_7d",
    30: "suspend_30d",
    40: "permanent_ban",
}

SUSPENSION_DURATIONS: Dict[str, timedelta] = {
    "warning": timedelta(days=0),
    "suspend_3d": timedelta(days=3),
    "suspend_7d": timedelta(days=7),
    "suspend_30d": timedelta(days=30),
    "suspend_permanent": timedelta(days=365 * 100),
}

MIN_VOTES_REQUIRED: int = 3
CONSENSUS_APPROVE_THRESHOLD: float = 0.70
CONSENSUS_REJECT_THRESHOLD: float = 0.30

DEFAULT_DAILY_REPORT_LIMIT: int = 5
PRO_DAILY_REPORT_LIMIT: int = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt(dt: datetime | None) -> str | None:
    """Format a datetime to the legacy string format or return None."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GovernanceRepository
# ---------------------------------------------------------------------------


class GovernanceRepository:
    """Single async repository that replaces all 6 governance modules."""

    # ===================================================================
    # Activity Log  (core.database.governance.activity)
    # ===================================================================

    async def log_activity(
        self,
        user_id: str,
        activity_type: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Log user activity.

        Returns ``{"success": True, "log_id": <int>}`` on success.
        """
        log_entry = UserActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        async with using_session(session) as s:
            s.add(log_entry)
            await s.flush()
            return {"success": True, "log_id": log_entry.id}

    async def get_user_activity_logs(
        self,
        user_id: str,
        activity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get paginated activity logs for a user."""
        stmt = (
            select(
                UserActivityLog.id,
                UserActivityLog.activity_type,
                UserActivityLog.resource_type,
                UserActivityLog.resource_id,
                UserActivityLog.metadata_,
                UserActivityLog.success,
                UserActivityLog.error_message,
                UserActivityLog.created_at,
            )
            .where(UserActivityLog.user_id == user_id)
            .order_by(UserActivityLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if activity_type is not None:
            stmt = stmt.where(UserActivityLog.activity_type == activity_type)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "activity_type": r[1],
                    "resource_type": r[2],
                    "resource_id": r[3],
                    "metadata": r[4],  # JSONB is already a dict
                    "success": r[5],
                    "error_message": r[6],
                    "created_at": _fmt(r[7]),
                }
                for r in rows
            ]

    # ===================================================================
    # Helpers  (core.database.governance.helpers)
    # ===================================================================

    async def get_content_author(
        self,
        content_type: str,
        content_id: int,
        session: AsyncSession | None = None,
    ) -> Optional[str]:
        """Return the user_id of the author of a post or comment."""
        if content_type == "post":
            stmt = select(Post.user_id).where(Post.id == content_id)
        elif content_type == "comment":
            stmt = select(ForumComment.user_id).where(
                ForumComment.id == content_id
            )
        else:
            return None

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            return row[0] if row else None

    async def get_report_statistics(
        self,
        days: int = 30,
        session: AsyncSession | None = None,
    ) -> dict:
        """Get report statistics for the specified period."""
        since_date = _utcnow() - timedelta(days=days)

        total_reports = func.count(ContentReport.id).label("total_reports")
        approved_reports = func.coalesce(
            func.sum(
                case(
                    (ContentReport.review_status == "approved", 1),
                    else_=0,
                )
            ),
            0,
        ).label("approved_reports")
        rejected_reports = func.coalesce(
            func.sum(
                case(
                    (ContentReport.review_status == "rejected", 1),
                    else_=0,
                )
            ),
            0,
        ).label("rejected_reports")
        pending_reports = func.coalesce(
            func.sum(
                case(
                    (ContentReport.review_status == "pending", 1),
                    else_=0,
                )
            ),
            0,
        ).label("pending_reports")
        total_votes = func.coalesce(
            func.sum(ContentReport.approve_count + ContentReport.reject_count), 0
        ).label("total_votes")

        stmt = (
            select(
                total_reports,
                approved_reports,
                rejected_reports,
                pending_reports,
                total_votes,
            )
            .where(ContentReport.created_at >= since_date)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            return {
                "total_reports": row[0] or 0,
                "approved_reports": row[1] or 0,
                "rejected_reports": row[2] or 0,
                "pending_reports": row[3] or 0,
                "total_votes": row[4] or 0,
            }

    async def get_top_reviewers(
        self,
        limit: int = 10,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get top reviewers by reputation score."""
        stmt = (
            select(
                AuditReputation.user_id,
                User.username,
                AuditReputation.total_reviews,
                AuditReputation.correct_votes,
                AuditReputation.accuracy_rate,
                AuditReputation.reputation_score,
            )
            .outerjoin(User, AuditReputation.user_id == User.user_id)
            .where(AuditReputation.total_reviews >= 5)
            .order_by(
                AuditReputation.reputation_score.desc(),
                AuditReputation.total_reviews.desc(),
            )
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "total_reviews": r[2],
                    "correct_votes": r[3],
                    "accuracy_rate": r[4],
                    "reputation_score": r[5],
                }
                for r in rows
            ]

    # ===================================================================
    # Reports  (core.database.governance.reports)
    # ===================================================================

    async def create_report(
        self,
        reporter_user_id: str,
        content_type: str,
        content_id: int,
        report_type: str,
        description: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Create a new content report.

        Performs validation (report_type, duplicate, daily limit) and
        logs the activity.  Returns ``{"success": True, "report_id": <int>}``
        or ``{"success": False, "error": "<reason>"}``.
        """
        if report_type not in REPORT_TYPES:
            return {"success": False, "error": "invalid_report_type"}

        async with using_session(session) as s:
            # Check content author — cannot report own content
            author_id = await self._get_content_author_tx(s, content_type, content_id)
            if not author_id:
                return {"success": False, "error": "content_not_found"}
            if author_id == reporter_user_id:
                return {"success": False, "error": "cannot_report_own_content"}

            # Check daily report limit (always uses DEFAULT for now;
            # premium check can be layered by the caller)
            limit = DEFAULT_DAILY_REPORT_LIMIT
            if not await self._check_daily_report_limit_tx(s, reporter_user_id, limit):
                return {"success": False, "error": "daily_limit_exceeded"}

            # Check for duplicate report
            dup_stmt = select(ContentReport.id).where(
                and_(
                    ContentReport.reporter_user_id == reporter_user_id,
                    ContentReport.content_type == content_type,
                    ContentReport.content_id == content_id,
                )
            )
            dup_result = await s.execute(dup_stmt)
            if dup_result.fetchone():
                return {"success": False, "error": "duplicate_report"}

            # Create the report
            now = _utcnow()
            report = ContentReport(
                content_type=content_type,
                content_id=content_id,
                reporter_user_id=reporter_user_id,
                report_type=report_type,
                description=description,
                created_at=now,
                updated_at=now,
            )
            s.add(report)
            await s.flush()

            # Log the activity
            log_entry = UserActivityLog(
                user_id=reporter_user_id,
                activity_type="report_submitted",
                resource_type="report",
                resource_id=report.id,
                metadata_={
                    "content_type": content_type,
                    "content_id": content_id,
                    "report_type": report_type,
                },
            )
            s.add(log_entry)

            return {"success": True, "report_id": report.id}

    async def get_pending_reports(
        self,
        limit: int = 20,
        offset: int = 0,
        exclude_user_id: Optional[str] = None,
        viewer_user_id: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get pending reports for review, optionally filtered."""
        stmt = (
            select(
                ContentReport.id,
                ContentReport.content_type,
                ContentReport.content_id,
                ContentReport.reporter_user_id,
                ContentReport.report_type,
                ContentReport.description,
                ContentReport.review_status,
                ContentReport.violation_level,
                ContentReport.approve_count,
                ContentReport.reject_count,
                ContentReport.created_at,
                ContentReport.updated_at,
                User.username,
                ReportReviewVote.vote_type,
            )
            .outerjoin(User, ContentReport.reporter_user_id == User.user_id)
            .outerjoin(
                ReportReviewVote,
                and_(
                    ContentReport.id == ReportReviewVote.report_id,
                    ReportReviewVote.reviewer_user_id == viewer_user_id,
                ),
            )
            .where(ContentReport.review_status == "pending")
        )

        if exclude_user_id is not None:
            stmt = stmt.where(
                ContentReport.reporter_user_id != exclude_user_id
            )

        stmt = (
            stmt.order_by(ContentReport.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "content_type": r[1],
                    "content_id": r[2],
                    "reporter_user_id": r[3],
                    "report_type": r[4],
                    "description": r[5],
                    "review_status": r[6],
                    "violation_level": r[7],
                    "approve_count": r[8],
                    "reject_count": r[9],
                    "created_at": _fmt(r[10]),
                    "updated_at": _fmt(r[11]),
                    "reporter_username": r[12],
                    "viewer_vote": r[13],
                }
                for r in rows
            ]

    async def get_report_by_id(
        self,
        report_id: int,
        session: AsyncSession | None = None,
    ) -> Optional[dict]:
        """Get a single report by ID with reporter username."""
        stmt = (
            select(
                ContentReport.id,
                ContentReport.content_type,
                ContentReport.content_id,
                ContentReport.reporter_user_id,
                ContentReport.report_type,
                ContentReport.description,
                ContentReport.review_status,
                ContentReport.violation_level,
                ContentReport.approve_count,
                ContentReport.reject_count,
                ContentReport.created_at,
                ContentReport.updated_at,
                User.username,
            )
            .outerjoin(User, ContentReport.reporter_user_id == User.user_id)
            .where(ContentReport.id == report_id)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "content_type": row[1],
                "content_id": row[2],
                "reporter_user_id": row[3],
                "report_type": row[4],
                "description": row[5],
                "review_status": row[6],
                "violation_level": row[7],
                "approve_count": row[8],
                "reject_count": row[9],
                "created_at": _fmt(row[10]),
                "updated_at": _fmt(row[11]),
                "reporter_username": row[12],
            }

    async def get_user_reports(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get reports submitted by a specific user."""
        stmt = (
            select(
                ContentReport.id,
                ContentReport.content_type,
                ContentReport.content_id,
                ContentReport.report_type,
                ContentReport.description,
                ContentReport.review_status,
                ContentReport.violation_level,
                ContentReport.approve_count,
                ContentReport.reject_count,
                ContentReport.created_at,
            )
            .where(ContentReport.reporter_user_id == user_id)
            .order_by(ContentReport.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(ContentReport.review_status == status)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "content_type": r[1],
                    "content_id": r[2],
                    "report_type": r[3],
                    "description": r[4],
                    "review_status": r[5],
                    "violation_level": r[6],
                    "approve_count": r[7],
                    "reject_count": r[8],
                    "created_at": _fmt(r[9]),
                }
                for r in rows
            ]

    async def check_daily_report_limit(
        self,
        user_id: str,
        daily_limit: Optional[int] = None,
        session: AsyncSession | None = None,
    ) -> bool:
        """Return True if the user is under their daily report limit."""
        if daily_limit is None:
            return True

        async with using_session(session) as s:
            return await self._check_daily_report_limit_tx(s, user_id, daily_limit)

    async def get_daily_report_usage(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """Return the number of reports submitted by the user today."""
        today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.count(ContentReport.id))
            .where(
                and_(
                    ContentReport.reporter_user_id == user_id,
                    ContentReport.created_at >= today_start,
                )
            )
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            return result.scalar() or 0

    # ===================================================================
    # Voting  (core.database.governance.voting)
    # ===================================================================

    async def vote_on_report(
        self,
        report_id: int,
        reviewer_user_id: str,
        vote_type: str,
        is_premium: bool = False,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Cast a vote on a report (premium members only).

        Returns ``{"success": True, "vote_id": <int>}`` on success.
        """
        if vote_type not in ("approve", "reject"):
            return {"success": False, "error": "invalid_vote_type"}

        if not is_premium:
            return {"success": False, "error": "premium_membership_required"}

        async with using_session(session) as s:
            # Check report status
            report_stmt = select(
                ContentReport.review_status,
                ContentReport.reporter_user_id,
            ).where(ContentReport.id == report_id)
            result = await s.execute(report_stmt)
            row = result.fetchone()
            if not row:
                return {"success": False, "error": "report_not_found"}

            review_status, reporter_user_id = row

            if review_status != "pending":
                return {"success": False, "error": "report_not_pending"}

            if reviewer_user_id == reporter_user_id:
                return {"success": False, "error": "cannot_vote_on_own_report"}

            # Check for existing vote
            dup_stmt = select(ReportReviewVote.id, ReportReviewVote.vote_type).where(
                and_(
                    ReportReviewVote.report_id == report_id,
                    ReportReviewVote.reviewer_user_id == reviewer_user_id,
                )
            )
            dup_result = await s.execute(dup_stmt)
            existing = dup_result.fetchone()
            if existing:
                return {
                    "success": False,
                    "error": "already_voted",
                    "existing_vote": existing[1],
                }

            # Get reputation for vote weight
            reputation = await self._get_audit_reputation_tx(s, reviewer_user_id)
            vote_weight = self.calculate_vote_weight(reputation)

            # Record the vote
            vote = ReportReviewVote(
                report_id=report_id,
                reviewer_user_id=reviewer_user_id,
                vote_type=vote_type,
                vote_weight=vote_weight,
            )
            s.add(vote)
            await s.flush()

            # Update report vote counts
            if vote_type == "approve":
                await s.execute(
                    update(ContentReport)
                    .where(ContentReport.id == report_id)
                    .values(
                        approve_count=ContentReport.approve_count + 1,
                        updated_at=_utcnow(),
                    )
                )
            else:
                await s.execute(
                    update(ContentReport)
                    .where(ContentReport.id == report_id)
                    .values(
                        reject_count=ContentReport.reject_count + 1,
                        updated_at=_utcnow(),
                    )
                )

            # Log activity
            log_entry = UserActivityLog(
                user_id=reviewer_user_id,
                activity_type="review_vote",
                resource_type="report",
                resource_id=report_id,
                metadata_={"vote_type": vote_type, "vote_weight": vote_weight},
            )
            s.add(log_entry)

            return {"success": True, "vote_id": vote.id}

    async def get_report_votes(
        self,
        report_id: int,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get all votes for a report with reviewer username."""
        stmt = (
            select(
                ReportReviewVote.id,
                ReportReviewVote.reviewer_user_id,
                ReportReviewVote.vote_type,
                ReportReviewVote.vote_weight,
                ReportReviewVote.created_at,
                User.username,
            )
            .outerjoin(User, ReportReviewVote.reviewer_user_id == User.user_id)
            .where(ReportReviewVote.report_id == report_id)
            .order_by(ReportReviewVote.created_at.asc())
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "reviewer_user_id": r[1],
                    "vote_type": r[2],
                    "vote_weight": r[3],
                    "created_at": _fmt(r[4]),
                    "reviewer_username": r[5],
                }
                for r in rows
            ]

    async def check_report_consensus(
        self,
        report_id: int,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Check if a report has reached voting consensus.

        Returns a dict with ``has_consensus``, ``decision``, vote counts, etc.
        """
        stmt = select(
            (ContentReport.approve_count + ContentReport.reject_count).label(
                "total_votes"
            ),
            ContentReport.approve_count,
            ContentReport.reject_count,
        ).where(ContentReport.id == report_id)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if not row:
                return {"has_consensus": False, "error": "report_not_found"}

            total_votes, approve_count, reject_count = (
                row[0],
                row[1],
                row[2],
            )

            if total_votes < MIN_VOTES_REQUIRED:
                return {
                    "has_consensus": False,
                    "total_votes": total_votes,
                    "minimum_votes": MIN_VOTES_REQUIRED,
                    "reason": "insufficient_votes",
                }

            approve_rate = approve_count / total_votes if total_votes > 0 else 0

            if approve_rate >= CONSENSUS_APPROVE_THRESHOLD:
                return {
                    "has_consensus": True,
                    "decision": "approved",
                    "total_votes": total_votes,
                    "approve_count": approve_count,
                    "reject_count": reject_count,
                    "approve_rate": approve_rate,
                }
            elif approve_rate <= CONSENSUS_REJECT_THRESHOLD:
                return {
                    "has_consensus": True,
                    "decision": "rejected",
                    "total_votes": total_votes,
                    "approve_count": approve_count,
                    "reject_count": reject_count,
                    "approve_rate": approve_rate,
                }
            else:
                return {
                    "has_consensus": False,
                    "total_votes": total_votes,
                    "approve_count": approve_count,
                    "reject_count": reject_count,
                    "approve_rate": approve_rate,
                    "reason": "no_clear_consensus",
                }

    async def finalize_report(
        self,
        report_id: int,
        decision: str,
        violation_level: Optional[str] = None,
        processed_by: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Finalize a report with a decision.

        If *decision* is ``"approved"`` and *violation_level* is set,
        violation points are applied and reviewer reputations are updated.
        """
        if decision not in ("approved", "rejected"):
            return {"success": False, "error": "invalid_decision"}

        async with using_session(session) as s:
            # Get report details
            report_stmt = select(
                ContentReport.reporter_user_id,
                ContentReport.content_type,
                ContentReport.content_id,
            ).where(ContentReport.id == report_id)
            result = await s.execute(report_stmt)
            row = result.fetchone()
            if not row:
                return {"success": False, "error": "report_not_found"}

            reporter_user_id, content_type, content_id = row

            # Get content author
            author_id = await self._get_content_author_tx(
                s, content_type, content_id
            )

            points = 0
            action_taken = None

            if decision == "approved" and violation_level:
                points = VIOLATION_LEVELS.get(violation_level, 0)
                # Calculate total points after adding
                current_pts = await self._get_user_violation_points_tx(s, author_id)
                total_after = current_pts + points
                action_taken = self.determine_suspension_action(total_after)

                # Add violation points
                await self._add_violation_points_tx(
                    s,
                    author_id=author_id,
                    points=points,
                    violation_level=violation_level,
                    violation_type="report",
                    source_type="report",
                    source_id=report_id,
                    processed_by=processed_by,
                    action_taken=action_taken,
                )

                # Apply suspension if needed
                if action_taken and action_taken != "warning":
                    await self._apply_suspension_tx(s, author_id, action_taken)

            # Update report status
            await s.execute(
                update(ContentReport)
                .where(ContentReport.id == report_id)
                .values(
                    review_status=decision,
                    violation_level=violation_level,
                    points_assigned=points,
                    action_taken=action_taken,
                    processed_by=processed_by,
                    updated_at=_utcnow(),
                )
            )

            # Update reviewer reputations
            votes = await self._get_report_votes_tx(s, report_id)
            for vote in votes:
                was_correct = (
                    (vote["vote_type"] == "approve")
                    if decision == "approved"
                    else (vote["vote_type"] == "reject")
                )
                await self._update_audit_reputation_tx(
                    s, vote["reviewer_user_id"], was_correct
                )

            return {
                "success": True,
                "decision": decision,
                "violation_level": violation_level,
                "points_assigned": points,
                "action_taken": action_taken,
            }

    # ===================================================================
    # Violations  (core.database.governance.violations)
    # ===================================================================

    async def add_violation_points(
        self,
        user_id: str,
        points: int,
        violation_level: str,
        violation_type: str,
        source_type: str,
        source_id: Optional[int] = None,
        processed_by: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Add violation points to a user.

        Returns ``{"success": True, "violation_id": <int>, "action_taken": ..., "suspended_until": ...}``.
        """
        if violation_level not in VIOLATION_LEVELS:
            return {"success": False, "error": "invalid_violation_level"}

        action_taken = self.determine_suspension_action(points)
        suspended_until: Optional[datetime] = None

        if action_taken and action_taken in SUSPENSION_DURATIONS:
            duration = SUSPENSION_DURATIONS[action_taken]
            if duration.total_seconds() > 0:
                suspended_until = _utcnow() + duration

        async with using_session(session) as s:
            await self._add_violation_points_tx(
                s,
                user_id=user_id,
                points=points,
                violation_level=violation_level,
                violation_type=violation_type,
                source_type=source_type,
                source_id=source_id,
                processed_by=processed_by,
                action_taken=action_taken,
            )

            # Log activity
            log_entry = UserActivityLog(
                user_id=processed_by or "system",
                activity_type="violation_added",
                resource_type="user",
                resource_id=user_id,
                metadata_={
                    "violation_level": violation_level,
                    "points": points,
                    "action_taken": action_taken,
                },
            )
            s.add(log_entry)

            return {
                "success": True,
                "violation_id": s.info.get("last_violation_id"),  # set by _tx helper
                "action_taken": action_taken,
                "suspended_until": _fmt(suspended_until),
            }

    async def get_user_violation_points(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        """Get user's current violation points summary."""
        async with using_session(session) as s:
            pts = await self._get_user_violation_points_tx(s, user_id)
            return {
                "points": pts,
                "total_violations": 0,  # populated below
                "suspension_count": 0,
                "last_violation_at": None,
            }

        # For full detail, query the aggregate row
        stmt = select(
            UserViolationPoints.points,
            UserViolationPoints.total_violations,
            UserViolationPoints.suspension_count,
            UserViolationPoints.last_violation_at,
        ).where(UserViolationPoints.user_id == user_id)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if not row:
                return {
                    "points": 0,
                    "total_violations": 0,
                    "suspension_count": 0,
                    "last_violation_at": None,
                }
            return {
                "points": row[0],
                "total_violations": row[1],
                "suspension_count": row[2],
                "last_violation_at": _fmt(row[3]),
            }

    async def get_user_violations(
        self,
        user_id: str,
        limit: int = 20,
        session: AsyncSession | None = None,
    ) -> List[dict]:
        """Get user's violation history."""
        stmt = (
            select(
                UserViolation.id,
                UserViolation.violation_level,
                UserViolation.violation_type,
                UserViolation.points,
                UserViolation.source_type,
                UserViolation.action_taken,
                UserViolation.suspended_until,
                UserViolation.created_at,
                UserViolation.processed_by,
            )
            .where(UserViolation.user_id == user_id)
            .order_by(UserViolation.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "violation_level": r[1],
                    "violation_type": r[2],
                    "points": r[3],
                    "source_type": r[4],
                    "action_taken": r[5],
                    "suspended_until": _fmt(r[6]),
                    "created_at": _fmt(r[7]),
                    "processed_by": r[8],
                }
                for r in rows
            ]

    @staticmethod
    def determine_suspension_action(points: int) -> Optional[str]:
        """Determine suspension action based on cumulative points."""
        sorted_thresholds = sorted(VIOLATION_ACTIONS.items())
        last_action: Optional[str] = None
        for threshold, action in sorted_thresholds:
            if points >= threshold:
                last_action = action
            else:
                break
        return last_action

    async def apply_suspension(
        self,
        user_id: str,
        action: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Apply a suspension action to a user's active violations."""
        if action not in SUSPENSION_DURATIONS:
            return False

        async with using_session(session) as s:
            return await self._apply_suspension_tx(s, user_id, action)

    async def check_user_suspension(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        """Check if user is currently suspended."""
        stmt = (
            select(
                UserViolation.action_taken,
                UserViolation.suspended_until,
                UserViolation.id,
            )
            .where(
                and_(
                    UserViolation.user_id == user_id,
                    UserViolation.suspended_until.isnot(None),
                )
            )
            .order_by(UserViolation.suspended_until.desc())
            .limit(1)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if not row:
                return {
                    "is_suspended": False,
                    "action": None,
                    "suspended_until": None,
                }
            return {
                "is_suspended": True,
                "action": row[0],
                "suspended_until": _fmt(row[1]),
                "violation_id": row[2],
            }

    # ===================================================================
    # Reputation  (core.database.governance.reputation)
    # ===================================================================

    async def get_audit_reputation(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> dict:
        """Get user's audit reputation summary."""
        async with using_session(session) as s:
            return await self._get_audit_reputation_tx(s, user_id)

    @staticmethod
    def calculate_vote_weight(reputation: dict) -> float:
        """Calculate vote weight multiplier based on reputation."""
        score = reputation.get("reputation_score", 0)
        total_reviews = reputation.get("total_reviews", 0)

        weight = 1.0
        if score >= 80 and total_reviews >= 20:
            weight = 2.0
        elif score >= 50 and total_reviews >= 10:
            weight = 1.5
        return weight

    async def update_audit_reputation(
        self,
        user_id: str,
        was_correct: bool,
        session: AsyncSession | None = None,
    ) -> dict:
        """
        Update audit reputation after a vote is validated.

        Returns ``{"success": True, "total_reviews": ..., "correct_votes": ..., ...}``.
        """
        async with using_session(session) as s:
            return await self._update_audit_reputation_tx(
                s, user_id, was_correct
            )

    # ===================================================================
    # Internal transaction helpers  (_tx suffix = use existing session)
    # ===================================================================

    @staticmethod
    async def _get_content_author_tx(
        s: AsyncSession,
        content_type: str,
        content_id: int,
    ) -> Optional[str]:
        if content_type == "post":
            stmt = select(Post.user_id).where(Post.id == content_id)
        elif content_type == "comment":
            stmt = select(ForumComment.user_id).where(
                ForumComment.id == content_id
            )
        else:
            return None
        result = await s.execute(stmt)
        row = result.fetchone()
        return row[0] if row else None

    @staticmethod
    async def _check_daily_report_limit_tx(
        s: AsyncSession,
        user_id: str,
        daily_limit: int,
    ) -> bool:
        today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(ContentReport.id)).where(
            and_(
                ContentReport.reporter_user_id == user_id,
                ContentReport.created_at >= today_start,
            )
        )
        result = await s.execute(stmt)
        count = result.scalar() or 0
        return count < daily_limit

    @staticmethod
    async def _get_audit_reputation_tx(s: AsyncSession, user_id: str) -> dict:
        stmt = select(
            AuditReputation.total_reviews,
            AuditReputation.correct_votes,
            AuditReputation.accuracy_rate,
            AuditReputation.reputation_score,
        ).where(AuditReputation.user_id == user_id)
        result = await s.execute(stmt)
        row = result.fetchone()
        if not row:
            return {
                "total_reviews": 0,
                "correct_votes": 0,
                "accuracy_rate": 1.0,
                "reputation_score": 0,
            }
        return {
            "total_reviews": row[0],
            "correct_votes": row[1],
            "accuracy_rate": row[2],
            "reputation_score": row[3],
        }

    @staticmethod
    async def _update_audit_reputation_tx(
        s: AsyncSession,
        user_id: str,
        was_correct: bool,
    ) -> dict:
        """Insert-or-update reputation row inside an existing transaction."""
        stmt = select(
            AuditReputation.total_reviews,
            AuditReputation.correct_votes,
        ).where(AuditReputation.user_id == user_id)
        result = await s.execute(stmt)
        row = result.fetchone()

        if not row:
            correct = 1 if was_correct else 0
            rep = AuditReputation(
                user_id=user_id,
                total_reviews=1,
                correct_votes=correct,
                accuracy_rate=1.0 if was_correct else 0.0,
                reputation_score=1 if was_correct else 0,
            )
            s.add(rep)
            new_total = 1
            new_correct = correct
        else:
            total_reviews, correct_votes = row
            new_total = total_reviews + 1
            new_correct = correct_votes + (1 if was_correct else 0)

            new_accuracy = new_correct / new_total if new_total > 0 else 0
            new_score = max(0, new_correct * 10 - (new_total - new_correct) * 5)

            await s.execute(
                update(AuditReputation)
                .where(AuditReputation.user_id == user_id)
                .values(
                    total_reviews=new_total,
                    correct_votes=new_correct,
                    accuracy_rate=new_accuracy,
                    reputation_score=new_score,
                    updated_at=_utcnow(),
                )
            )

        return {
            "success": True,
            "total_reviews": new_total,
            "correct_votes": new_correct,
            "accuracy_rate": new_correct / new_total if new_total > 0 else 0,
            "reputation_score": max(
                0, new_correct * 10 - (new_total - new_correct) * 5
            ),
        }

    @staticmethod
    async def _get_user_violation_points_tx(
        s: AsyncSession,
        user_id: str,
    ) -> int:
        stmt = select(func.coalesce(UserViolationPoints.points, 0)).where(
            UserViolationPoints.user_id == user_id
        )
        result = await s.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def _add_violation_points_tx(
        s: AsyncSession,
        *,
        user_id: str,
        points: int,
        violation_level: str,
        violation_type: str,
        source_type: str,
        source_id: Optional[int] = None,
        processed_by: Optional[str] = None,
        action_taken: Optional[str] = None,
    ) -> int:
        """
        Insert a UserViolation row + upsert UserViolationPoints.
        Returns the new violation id.
        """
        # Determine suspension end
        suspended_until: Optional[datetime] = None
        if action_taken and action_taken in SUSPENSION_DURATIONS:
            duration = SUSPENSION_DURATIONS[action_taken]
            if duration.total_seconds() > 0:
                suspended_until = _utcnow() + duration

        violation = UserViolation(
            user_id=user_id,
            violation_level=violation_level,
            violation_type=violation_type,
            points=points,
            source_type=source_type,
            source_id=source_id,
            action_taken=action_taken,
            suspended_until=suspended_until,
            processed_by=processed_by,
            created_at=_utcnow(),
        )
        s.add(violation)
        await s.flush()

        is_real_suspension = (
            action_taken is not None and action_taken != "warning"
        )
        inc_susp = 1 if is_real_suspension else 0

        # Upsert violation points via PostgreSQL ON CONFLICT
        stmt = (
            pg_insert(UserViolationPoints)
            .values(
                user_id=user_id,
                points=points,
                total_violations=1,
                last_violation_at=_utcnow(),
                suspension_count=inc_susp,
                updated_at=_utcnow(),
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "points": UserViolationPoints.points + points,
                    "total_violations": UserViolationPoints.total_violations + 1,
                    "last_violation_at": _utcnow(),
                    "suspension_count": UserViolationPoints.suspension_count
                    + inc_susp,
                    "updated_at": _utcnow(),
                },
            )
        )
        await s.execute(stmt)

        return violation.id

    @staticmethod
    async def _apply_suspension_tx(
        s: AsyncSession,
        user_id: str,
        action: str,
    ) -> bool:
        """Apply suspension to active (non-expired) violations."""
        if action not in SUSPENSION_DURATIONS:
            return False

        duration = SUSPENSION_DURATIONS[action]
        if duration.total_seconds() == 0:
            return True

        suspended_until = _utcnow() + duration
        stmt = (
            update(UserViolation)
            .where(
                and_(
                    UserViolation.user_id == user_id,
                    UserViolation.suspended_until.is_(None),
                )
            )
            .values(suspended_until=suspended_until)
        )
        result = await s.execute(stmt)
        return result.rowcount > 0

    @staticmethod
    async def _get_report_votes_tx(
        s: AsyncSession,
        report_id: int,
    ) -> List[dict]:
        stmt = (
            select(
                ReportReviewVote.id,
                ReportReviewVote.reviewer_user_id,
                ReportReviewVote.vote_type,
                ReportReviewVote.vote_weight,
                ReportReviewVote.created_at,
                User.username,
            )
            .outerjoin(User, ReportReviewVote.reviewer_user_id == User.user_id)
            .where(ReportReviewVote.report_id == report_id)
            .order_by(ReportReviewVote.created_at.asc())
        )
        result = await s.execute(stmt)
        rows = result.fetchall()
        return [
            {
                "id": r[0],
                "reviewer_user_id": r[1],
                "vote_type": r[2],
                "vote_weight": r[3],
                "created_at": r[4],
                "reviewer_username": r[5],
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

governance_repo = GovernanceRepository()
