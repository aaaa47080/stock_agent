"""
Voting Functions
Cast votes, check consensus, and finalize reports
"""
from typing import Dict, List

from ..connection import get_connection
from ..user import get_user_membership
from .constants import (
    MIN_VOTES_REQUIRED, CONSENSUS_APPROVE_THRESHOLD, CONSENSUS_REJECT_THRESHOLD,
    VIOLATION_LEVELS
)
from .activity import log_activity
from .reputation import get_audit_reputation, calculate_vote_weight, update_audit_reputation
from .violations import (
    add_violation_points, get_user_violation_points,
    determine_suspension_action, apply_suspension
)
from .helpers import get_content_author


def vote_on_report(db, report_id: int, reviewer_user_id: str, vote_type: str) -> Dict:
    """
    Cast a vote on a report (Premium members only)

    Args:
        db: Database connection (optional)
        report_id: Report ID
        reviewer_user_id: User ID of the reviewer
        vote_type: 'approve' or 'reject'

    Returns:
        Dict with success status
    """
    if vote_type not in ['approve', 'reject']:
        return {"success": False, "error": "invalid_vote_type"}

    # Check premium membership
    membership = get_user_membership(reviewer_user_id)
    if not membership.get('is_premium', membership.get('is_pro')):
        return {"success": False, "error": "pro_membership_required"}

    # Get reputation for vote weight
    reputation = get_audit_reputation(db, reviewer_user_id)
    vote_weight = calculate_vote_weight(reputation)

    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Check report status
        c.execute('SELECT review_status, reporter_user_id FROM content_reports WHERE id = %s', (report_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "report_not_found"}

        review_status, reporter_user_id = row

        if review_status != 'pending':
            return {"success": False, "error": "report_not_pending"}

        # Prevent reporter from voting on their own report
        if reviewer_user_id == reporter_user_id:
            return {"success": False, "error": "cannot_vote_on_own_report"}

        # Check for existing vote
        c.execute('''
            SELECT id, vote_type FROM report_review_votes
            WHERE report_id = %s AND reviewer_user_id = %s
        ''', (report_id, reviewer_user_id))

        existing = c.fetchone()
        if existing:
            return {"success": False, "error": "already_voted", "existing_vote": existing[1]}

        # Record the vote
        c.execute('''
            INSERT INTO report_review_votes
            (report_id, reviewer_user_id, vote_type, vote_weight, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id
        ''', (report_id, reviewer_user_id, vote_type, vote_weight))

        vote_id = c.fetchone()[0]

        # Update report vote counts
        if vote_type == 'approve':
            c.execute('''
                UPDATE content_reports
                SET approve_count = approve_count + 1, updated_at = NOW()
                WHERE id = %s
            ''', (report_id,))
        else:
            c.execute('''
                UPDATE content_reports
                SET reject_count = reject_count + 1, updated_at = NOW()
                WHERE id = %s
            ''', (report_id,))

        conn.commit()

        # Log the activity
        log_activity(
            db, reviewer_user_id, 'review_vote', 'report', report_id,
            {"vote_type": vote_type, "vote_weight": vote_weight}
        )

        return {"success": True, "vote_id": vote_id}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


def get_report_votes(db, report_id: int) -> List[Dict]:
    """
    Get all votes for a report

    Args:
        db: Database connection (optional)
        report_id: Report ID

    Returns:
        List of vote dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT rrv.id, rrv.reviewer_user_id, rrv.vote_type,
                   rrv.vote_weight, rrv.created_at, u.username
            FROM report_review_votes rrv
            LEFT JOIN users u ON rrv.reviewer_user_id = u.user_id
            WHERE rrv.report_id = %s
            ORDER BY rrv.created_at ASC
        ''', (report_id,))

        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[4]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')

            result.append({
                "id": r[0],
                "reviewer_user_id": r[1],
                "vote_type": r[2],
                "vote_weight": r[3],
                "created_at": created_at,
                "reviewer_username": r[5]
            })

        return result
    finally:
        if not db:
            conn.close()


def check_report_consensus(db, report_id: int) -> Dict:
    """
    Check if a report has reached consensus

    Args:
        db: Database connection (optional)
        report_id: Report ID

    Returns:
        Dict with consensus status and decision
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT
                (approve_count + reject_count) as total_votes,
                approve_count,
                reject_count
            FROM content_reports
            WHERE id = %s
        ''', (report_id,))

        row = c.fetchone()
        if not row:
            return {"has_consensus": False, "error": "report_not_found"}

        total_votes, approve_count, reject_count = row

        # Check minimum votes threshold
        if total_votes < MIN_VOTES_REQUIRED:
            return {
                "has_consensus": False,
                "total_votes": total_votes,
                "minimum_votes": MIN_VOTES_REQUIRED,
                "reason": "insufficient_votes"
            }

        # Calculate approve rate
        approve_rate = approve_count / total_votes if total_votes > 0 else 0

        # Check for consensus
        if approve_rate >= CONSENSUS_APPROVE_THRESHOLD:
            return {
                "has_consensus": True,
                "decision": "approved",
                "total_votes": total_votes,
                "approve_count": approve_count,
                "reject_count": reject_count,
                "approve_rate": approve_rate
            }
        elif approve_rate <= CONSENSUS_REJECT_THRESHOLD:
            return {
                "has_consensus": True,
                "decision": "rejected",
                "total_votes": total_votes,
                "approve_count": approve_count,
                "reject_count": reject_count,
                "approve_rate": approve_rate
            }
        else:
            return {
                "has_consensus": False,
                "total_votes": total_votes,
                "approve_count": approve_count,
                "reject_count": reject_count,
                "approve_rate": approve_rate,
                "reason": "no_clear_consensus"
            }
    finally:
        if not db:
            conn.close()


def finalize_report(db, report_id: int, decision: str, violation_level: str = None,
                    processed_by: str = None) -> Dict:
    """
    Finalize a report with a decision

    Args:
        db: Database connection (optional)
        report_id: Report ID
        decision: 'approved' or 'rejected'
        violation_level: Level of violation (if approved)
        processed_by: User ID of processor

    Returns:
        Dict with success status
    """
    if decision not in ['approved', 'rejected']:
        return {"success": False, "error": "invalid_decision"}

    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Get report details
        c.execute('''
            SELECT reporter_user_id, content_type, content_id
            FROM content_reports WHERE id = %s
        ''', (report_id,))

        row = c.fetchone()
        if not row:
            return {"success": False, "error": "report_not_found"}

        reporter_user_id, content_type, content_id = row

        # Get content author
        author_id = get_content_author(conn, content_type, content_id)

        points = 0
        action_taken = None

        if decision == 'approved' and violation_level:
            points = VIOLATION_LEVELS.get(violation_level, 0)
            action_taken = determine_suspension_action(
                get_user_violation_points(conn, author_id).get('points', 0) + points
            )

            # Add violation points
            add_violation_points(
                conn, author_id, points, violation_level,
                'report', report_id, processed_by
            )

            # Apply suspension if needed
            if action_taken and action_taken != 'warning':
                apply_suspension(conn, author_id, action_taken)

        # Update report status
        c.execute('''
            UPDATE content_reports
            SET review_status = %s,
                violation_level = %s,
                points_assigned = %s,
                action_taken = %s,
                processed_by = %s,
                updated_at = NOW()
            WHERE id = %s
        ''', (decision, violation_level, points, action_taken, processed_by, report_id))

        conn.commit()

        # Update reviewer reputations
        votes = get_report_votes(conn, report_id)
        for vote in votes:
            was_correct = (vote['vote_type'] == 'approve') if decision == 'approved' else (vote['vote_type'] == 'reject')
            update_audit_reputation(conn, vote['reviewer_user_id'], was_correct)

        return {
            "success": True,
            "decision": decision,
            "violation_level": violation_level,
            "points_assigned": points,
            "action_taken": action_taken
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()
