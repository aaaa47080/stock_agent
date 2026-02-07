"""
Community Governance Database Operations
Contains: Report management, voting, violations, audit reputation, activity logging, helpers
"""
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .connection import get_connection
from .user import get_user_membership


# ============================================================================
# Constants
# ============================================================================

# Violation levels with corresponding point values
VIOLATION_LEVELS = {
    "mild": 1,
    "medium": 3,
    "severe": 5,
    "critical": 30
}

# Valid report types
REPORT_TYPES = [
    "spam",
    "harassment",
    "misinformation",
    "scam",
    "illegal",
    "other"
]

# Violation actions based on point thresholds
VIOLATION_ACTIONS = {
    5: "warning",
    10: "suspend_3d",
    20: "suspend_7d",
    30: "suspend_30d",
    40: "permanent_ban"
}

# Suspension duration mappings
SUSPENSION_DURATIONS = {
    "warning": timedelta(days=0),
    "suspend_3d": timedelta(days=3),
    "suspend_7d": timedelta(days=7),
    "suspend_30d": timedelta(days=30),
    "suspend_permanent": timedelta(days=365 * 100)  # Effectively permanent
}

# Voting consensus thresholds
MIN_VOTES_REQUIRED = 3
CONSENSUS_APPROVE_THRESHOLD = 0.70
CONSENSUS_REJECT_THRESHOLD = 0.30

# Default daily report limits
DEFAULT_DAILY_REPORT_LIMIT = 5
PRO_DAILY_REPORT_LIMIT = 10


# ============================================================================
# Report Management
# ============================================================================

def create_report(db, reporter_user_id: str, content_type: str, content_id: int,
                 report_type: str, description: str = None) -> Dict:
    """
    Create a new content report

    Args:
        db: Database connection (optional, for testing)
        reporter_user_id: ID of user creating the report
        content_type: Type of content ('post' or 'comment')
        content_id: ID of the content being reported
        report_type: Type of violation (from REPORT_TYPES)
        description: Optional description of the violation

    Returns:
        Dict with success status and report_id or error
    """
    # Validate report type
    if report_type not in REPORT_TYPES:
        return {"success": False, "error": "invalid_report_type"}

    # Check content author (can't report own content)
    author_id = get_content_author(db, content_type, content_id)
    if not author_id:
        return {"success": False, "error": "content_not_found"}

    if author_id == reporter_user_id:
        return {"success": False, "error": "cannot_report_own_content"}

    # Check daily report limit
    limit = PRO_DAILY_REPORT_LIMIT if get_user_membership(reporter_user_id).get('is_pro') else DEFAULT_DAILY_REPORT_LIMIT
    if not check_daily_report_limit(db, reporter_user_id, limit):
        return {"success": False, "error": "daily_limit_exceeded"}

    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Check for duplicate report
        c.execute('''
            SELECT id FROM content_reports
            WHERE reporter_user_id = %s AND content_type = %s AND content_id = %s
        ''', (reporter_user_id, content_type, content_id))

        if c.fetchone():
            return {"success": False, "error": "duplicate_report"}

        # Create the report
        c.execute('''
            INSERT INTO content_reports
            (content_type, content_id, reporter_user_id, report_type, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        ''', (content_type, content_id, reporter_user_id, report_type, description))

        report_id = c.fetchone()[0]
        conn.commit()

        # Log the activity
        log_activity(
            db, reporter_user_id, 'report_submitted', 'report', report_id,
            {"content_type": content_type, "content_id": content_id, "report_type": report_type}
        )

        return {"success": True, "report_id": report_id}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


def get_pending_reports(db, limit: int = 20, offset: int = 0,
                        exclude_user_id: str = None) -> List[Dict]:
    """
    Get pending reports for review

    Args:
        db: Database connection (optional)
        limit: Maximum number of reports to return
        offset: Pagination offset
        exclude_user_id: Exclude reports from this user

    Returns:
        List of report dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT cr.id, cr.content_type, cr.content_id, cr.reporter_user_id,
                   cr.report_type, cr.description, cr.review_status, cr.violation_level,
                   cr.approve_count, cr.reject_count, cr.created_at, cr.updated_at,
                   u.username as reporter_username
            FROM content_reports cr
            LEFT JOIN users u ON cr.reporter_user_id = u.user_id
            WHERE cr.review_status = 'pending'
        '''
        params = []

        if exclude_user_id:
            query += ' AND cr.reporter_user_id != %s'
            params.append(exclude_user_id)

        query += ' ORDER BY cr.created_at ASC LIMIT %s OFFSET %s'
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[10]
            updated_at = r[11]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            if updated_at and not isinstance(updated_at, str):
                updated_at = updated_at.strftime('%Y-%m-%d %H:%M:%S')

            result.append({
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
                "created_at": created_at,
                "updated_at": updated_at,
                "reporter_username": r[12]
            })

        return result
    finally:
        if not db:
            conn.close()


def get_report_by_id(db, report_id: int) -> Optional[Dict]:
    """
    Get a report by its ID

    Args:
        db: Database connection (optional)
        report_id: Report ID

    Returns:
        Report dictionary or None
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT cr.id, cr.content_type, cr.content_id, cr.reporter_user_id,
                   cr.report_type, cr.description, cr.review_status, cr.violation_level,
                   cr.approve_count, cr.reject_count, cr.created_at, cr.updated_at,
                   u.username as reporter_username
            FROM content_reports cr
            LEFT JOIN users u ON cr.reporter_user_id = u.user_id
            WHERE cr.id = %s
        ''', (report_id,))

        row = c.fetchone()
        if not row:
            return None

        created_at = row[10]
        updated_at = row[11]
        if created_at and not isinstance(created_at, str):
            created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
        if updated_at and not isinstance(updated_at, str):
            updated_at = updated_at.strftime('%Y-%m-%d %H:%M:%S')

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
            "created_at": created_at,
            "updated_at": updated_at,
            "reporter_username": row[12]
        }
    finally:
        if not db:
            conn.close()


def get_user_reports(db, user_id: str, status: str = None, limit: int = 20) -> List[Dict]:
    """
    Get reports submitted by a user

    Args:
        db: Database connection (optional)
        user_id: User ID
        status: Filter by status (pending, approved, rejected)
        limit: Maximum number of reports

    Returns:
        List of report dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT cr.id, cr.content_type, cr.content_id, cr.report_type,
                   cr.description, cr.review_status, cr.violation_level,
                   cr.approve_count, cr.reject_count, cr.created_at
            FROM content_reports cr
            WHERE cr.reporter_user_id = %s
        '''
        params = [user_id]

        if status:
            query += ' AND cr.review_status = %s'
            params.append(status)

        query += ' ORDER BY cr.created_at DESC LIMIT %s'
        params.append(limit)

        c.execute(query, params)
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[9]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')

            result.append({
                "id": r[0],
                "content_type": r[1],
                "content_id": r[2],
                "report_type": r[3],
                "description": r[4],
                "review_status": r[5],
                "violation_level": r[6],
                "approve_count": r[7],
                "reject_count": r[8],
                "created_at": created_at
            })

        return result
    finally:
        if not db:
            conn.close()


def check_daily_report_limit(db, user_id: str, daily_limit: int) -> bool:
    """
    Check if user has exceeded daily report limit

    Args:
        db: Database connection (optional)
        user_id: User ID
        daily_limit: Maximum reports allowed per day

    Returns:
        True if under limit, False if exceeded
    """
    if daily_limit is None:
        return True

    conn = db or get_connection()
    c = conn.cursor()
    try:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        c.execute('''
            SELECT COUNT(*) FROM content_reports
            WHERE reporter_user_id = %s
            AND DATE(created_at) = %s
        ''', (user_id, today))

        count = c.fetchone()[0]
        return count < daily_limit
    finally:
        if not db:
            conn.close()


# ============================================================================
# Voting
# ============================================================================

def vote_on_report(db, report_id: int, reviewer_user_id: str, vote_type: str) -> Dict:
    """
    Cast a vote on a report (PRO members only)

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

    # Check PRO membership
    membership = get_user_membership(reviewer_user_id)
    if not membership.get('is_pro'):
        return {"success": False, "error": "pro_membership_required"}

    # Get reputation for vote weight
    reputation = get_audit_reputation(db, reviewer_user_id)
    vote_weight = calculate_vote_weight(reputation)

    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Check report status
        c.execute('SELECT review_status FROM content_reports WHERE id = %s', (report_id,))
        row = c.fetchone()
        if not row:
            return {"success": False, "error": "report_not_found"}
        if row[0] != 'pending':
            return {"success": False, "error": "report_not_pending"}

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


# ============================================================================
# Violations
# ============================================================================

def add_violation_points(db, user_id: str, points: int, violation_level: str,
                         violation_type: str, source_type: str, source_id: int = None,
                         processed_by: str = None) -> Dict:
    """
    Add violation points to a user

    Args:
        db: Database connection (optional)
        user_id: User ID
        points: Points to add
        violation_level: Level of violation
        violation_type: Type of violation
        source_type: Source of violation ('report' or 'admin_action')
        source_id: ID of source
        processed_by: User ID of processor

    Returns:
        Dict with success status
    """
    if violation_level not in VIOLATION_LEVELS:
        return {"success": False, "error": "invalid_violation_level"}

    action_taken = determine_suspension_action(points)
    suspended_until = None

    if action_taken and action_taken in SUSPENSION_DURATIONS:
        duration = SUSPENSION_DURATIONS[action_taken]
        if duration.total_seconds() > 0:
            suspended_until = datetime.utcnow() + duration

    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Create violation record
        c.execute('''
            INSERT INTO user_violations
            (user_id, violation_level, violation_type, points, source_type,
             source_id, action_taken, suspended_until, processed_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        ''', (user_id, violation_level, violation_type, points, source_type,
              source_id, action_taken, suspended_until, processed_by))

        violation_id = c.fetchone()[0]

        # Update violation points
        c.execute('''
            INSERT INTO user_violation_points
            (user_id, points, total_violations, last_violation_at, suspension_count, updated_at)
            VALUES (%s, %s, 1, NOW(), %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                points = user_violation_points.points + EXCLUDED.points,
                total_violations = user_violation_points.total_violations + 1,
                last_violation_at = EXCLUDED.last_violation_at,
                suspension_count = user_violation_points.suspension_count +
                    CASE WHEN %s > 0 THEN 1 ELSE 0 END,
                updated_at = NOW()
        ''', (user_id, points, 1 if action_taken and action_taken != 'warning' else 0,
              1 if action_taken and action_taken != 'warning' else 0))

        conn.commit()

        # Log the activity
        log_activity(
            db, processed_by or 'system', 'violation_added', 'user', user_id,
            {"violation_level": violation_level, "points": points, "action_taken": action_taken}
        )

        return {
            "success": True,
            "violation_id": violation_id,
            "action_taken": action_taken,
            "suspended_until": suspended_until.strftime('%Y-%m-%d %H:%M:%S') if suspended_until else None
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


def get_user_violation_points(db, user_id: str) -> Dict:
    """
    Get user's current violation points

    Args:
        db: Database connection (optional)
        user_id: User ID

    Returns:
        Dict with violation point details
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT points, total_violations, suspension_count, last_violation_at
            FROM user_violation_points
            WHERE user_id = %s
        ''', (user_id,))

        row = c.fetchone()
        if not row:
            return {
                "points": 0,
                "total_violations": 0,
                "suspension_count": 0,
                "last_violation_at": None
            }

        last_violation_at = row[3]
        if last_violation_at and not isinstance(last_violation_at, str):
            last_violation_at = last_violation_at.strftime('%Y-%m-%d %H:%M:%S')

        return {
            "points": row[0],
            "total_violations": row[1],
            "suspension_count": row[2],
            "last_violation_at": last_violation_at
        }
    finally:
        if not db:
            conn.close()


def get_user_violations(db, user_id: str, limit: int = 20) -> List[Dict]:
    """
    Get user's violation history

    Args:
        db: Database connection (optional)
        user_id: User ID
        limit: Maximum number of violations

    Returns:
        List of violation dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT id, violation_level, violation_type, points, source_type,
                   action_taken, suspended_until, created_at, processed_by
            FROM user_violations
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))

        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[7]
            suspended_until = r[6]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            if suspended_until and not isinstance(suspended_until, str):
                suspended_until = suspended_until.strftime('%Y-%m-%d %H:%M:%S')

            result.append({
                "id": r[0],
                "violation_level": r[1],
                "violation_type": r[2],
                "points": r[3],
                "source_type": r[4],
                "action_taken": r[5],
                "suspended_until": suspended_until,
                "created_at": created_at,
                "processed_by": r[8]
            })

        return result
    finally:
        if not db:
            conn.close()


def determine_suspension_action(points: int) -> Optional[str]:
    """
    Determine suspension action based on total points

    Args:
        points: Total violation points

    Returns:
        Action string or None
    """
    # Sort thresholds by value (ascending)
    sorted_thresholds = sorted(VIOLATION_ACTIONS.items())

    last_action = None
    for threshold, action in sorted_thresholds:
        if points >= threshold:
            last_action = action
        else:
            break

    return last_action


def apply_suspension(db, user_id: str, action: str) -> bool:
    """
    Apply suspension action to user

    Args:
        db: Database connection (optional)
        user_id: User ID
        action: Suspension action

    Returns:
        True if successful
    """
    if action not in SUSPENSION_DURATIONS:
        return False

    conn = db or get_connection()
    c = conn.cursor()
    try:
        duration = SUSPENSION_DURATIONS[action]
        if duration.total_seconds() == 0:
            # Warning only, no actual suspension
            return True

        suspended_until = datetime.utcnow() + duration

        c.execute('''
            UPDATE user_violations
            SET suspended_until = %s
            WHERE user_id = %s AND suspended_until IS NULL
        ''', (suspended_until, user_id))

        conn.commit()
        return c.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        if not db:
            conn.close()


def check_user_suspension(db, user_id: str) -> Dict:
    """
    Check if user is currently suspended

    Args:
        db: Database connection (optional)
        user_id: User ID

    Returns:
        Dict with suspension status
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT action_taken, suspended_until, id
            FROM user_violations
            WHERE user_id = %s AND suspended_until IS NOT NULL
            ORDER BY suspended_until DESC
            LIMIT 1
        ''', (user_id,))

        row = c.fetchone()
        if not row:
            return {"is_suspended": False, "action": None, "suspended_until": None}

        suspended_until = row[1]
        if suspended_until and not isinstance(suspended_until, str):
            suspended_until = suspended_until.strftime('%Y-%m-%d %H:%M:%S')

        return {
            "is_suspended": True,
            "action": row[0],
            "suspended_until": suspended_until,
            "violation_id": row[2]
        }
    finally:
        if not db:
            conn.close()


# ============================================================================
# Audit Reputation
# ============================================================================

def get_audit_reputation(db, user_id: str) -> Dict:
    """
    Get user's audit reputation

    Args:
        db: Database connection (optional)
        user_id: User ID

    Returns:
        Dict with reputation details
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT total_reviews, correct_votes, accuracy_rate, reputation_score
            FROM audit_reputation
            WHERE user_id = %s
        ''', (user_id,))

        row = c.fetchone()
        if not row:
            return {
                "total_reviews": 0,
                "correct_votes": 0,
                "accuracy_rate": 1.0,
                "reputation_score": 0
            }

        return {
            "total_reviews": row[0],
            "correct_votes": row[1],
            "accuracy_rate": row[2],
            "reputation_score": row[3]
        }
    finally:
        if not db:
            conn.close()


def calculate_vote_weight(reputation: Dict) -> float:
    """
    Calculate vote weight based on reputation

    Args:
        reputation: Reputation dict

    Returns:
        Vote weight multiplier
    """
    score = reputation.get("reputation_score", 0)
    total_reviews = reputation.get("total_reviews", 0)

    # Base weight is 1.0
    weight = 1.0

    # Increase weight based on reputation score
    if score >= 80 and total_reviews >= 20:
        weight = 2.0  # Top reviewers get 2x weight
    elif score >= 50 and total_reviews >= 10:
        weight = 1.5  # Experienced reviewers get 1.5x weight

    return weight


def update_audit_reputation(db, user_id: str, was_correct: bool) -> Dict:
    """
    Update audit reputation after a vote is validated

    Args:
        db: Database connection (optional)
        user_id: User ID
        was_correct: Whether the vote was correct

    Returns:
        Dict with updated reputation
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        # Get current stats
        c.execute('''
            SELECT total_reviews, correct_votes FROM audit_reputation
            WHERE user_id = %s
        ''', (user_id,))

        row = c.fetchone()
        if not row:
            # Create new record
            c.execute('''
                INSERT INTO audit_reputation
                (user_id, total_reviews, correct_votes, accuracy_rate, reputation_score, updated_at)
                VALUES (%s, 1, %s, %s, %s, NOW())
            ''', (user_id, 1 if was_correct else 0, 1.0 if was_correct else 0.0, 1 if was_correct else 0))

            new_total = 1
            new_correct = 1 if was_correct else 0
        else:
            total_reviews, correct_votes = row
            new_total = total_reviews + 1
            new_correct = correct_votes + (1 if was_correct else 0)

            # Calculate new accuracy rate
            new_accuracy = new_correct / new_total if new_total > 0 else 0

            # Calculate reputation score (simple formula: correct * 10 - incorrect * 5)
            new_score = max(0, new_correct * 10 - (new_total - new_correct) * 5)

            c.execute('''
                UPDATE audit_reputation
                SET total_reviews = %s,
                    correct_votes = %s,
                    accuracy_rate = %s,
                    reputation_score = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (new_total, new_correct, new_accuracy, new_score, user_id))

        conn.commit()

        return {
            "success": True,
            "total_reviews": new_total,
            "correct_votes": new_correct,
            "accuracy_rate": new_correct / new_total,
            "reputation_score": max(0, new_correct * 10 - (new_total - new_correct) * 5)
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


# ============================================================================
# Activity Logging
# ============================================================================

def log_activity(db, user_id: str, activity_type: str, resource_type: str = None,
                 resource_id: int = None, metadata: Dict = None, success: bool = True,
                 error_message: str = None, ip_address: str = None,
                 user_agent: str = None) -> Dict:
    """
    Log user activity

    Args:
        db: Database connection (optional)
        user_id: User ID
        activity_type: Type of activity
        resource_type: Type of resource
        resource_id: ID of resource
        metadata: Additional metadata (will be JSON encoded)
        success: Whether activity was successful
        error_message: Error message if failed
        ip_address: IP address
        user_agent: User agent string

    Returns:
        Dict with success status
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        metadata_json = json.dumps(metadata) if metadata else None

        c.execute('''
            INSERT INTO user_activity_logs
            (user_id, activity_type, resource_type, resource_id, metadata,
             success, error_message, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        ''', (user_id, activity_type, resource_type, resource_id, metadata_json,
              success, error_message, ip_address, user_agent))

        log_id = c.fetchone()[0]
        conn.commit()

        return {"success": True, "log_id": log_id}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


def get_user_activity_logs(db, user_id: str, activity_type: str = None,
                           limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    Get user activity logs

    Args:
        db: Database connection (optional)
        user_id: User ID
        activity_type: Filter by activity type
        limit: Maximum number of logs
        offset: Pagination offset

    Returns:
        List of activity log dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT id, activity_type, resource_type, resource_id,
                   metadata, success, error_message, created_at
            FROM user_activity_logs
            WHERE user_id = %s
        '''
        params = [user_id]

        if activity_type:
            query += ' AND activity_type = %s'
            params.append(activity_type)

        query += ' ORDER BY created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[7]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')

            result.append({
                "id": r[0],
                "activity_type": r[1],
                "resource_type": r[2],
                "resource_id": r[3],
                "metadata": json.loads(r[4]) if r[4] else None,
                "success": r[5],
                "error_message": r[6],
                "created_at": created_at
            })

        return result
    finally:
        if not db:
            conn.close()


# ============================================================================
# Helpers
# ============================================================================

def get_content_author(db, content_type: str, content_id: int) -> Optional[str]:
    """
    Get the author of content (post or comment)

    Args:
        db: Database connection (optional)
        content_type: 'post' or 'comment'
        content_id: Content ID

    Returns:
        User ID of author or None
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        if content_type == 'post':
            c.execute('SELECT user_id FROM posts WHERE id = %s', (content_id,))
        elif content_type == 'comment':
            c.execute('SELECT user_id FROM forum_comments WHERE id = %s', (content_id,))
        else:
            return None

        row = c.fetchone()
        return row[0] if row else None
    finally:
        if not db:
            conn.close()


def get_report_statistics(db, days: int = 30) -> Dict:
    """
    Get report statistics for the specified period

    Args:
        db: Database connection (optional)
        days: Number of days to look back

    Returns:
        Dict with statistics
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        since_date = datetime.utcnow() - timedelta(days=days)

        c.execute('''
            SELECT
                COUNT(*) as total_reports,
                SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) as approved_reports,
                SUM(CASE WHEN review_status = 'rejected' THEN 1 ELSE 0 END) as rejected_reports,
                SUM(CASE WHEN review_status = 'pending' THEN 1 ELSE 0 END) as pending_reports,
                SUM(approve_count + reject_count) as total_votes
            FROM content_reports
            WHERE created_at >= %s
        ''', (since_date,))

        row = c.fetchone()

        return {
            "total_reports": row[0] or 0,
            "approved_reports": row[1] or 0,
            "rejected_reports": row[2] or 0,
            "pending_reports": row[3] or 0,
            "total_votes": row[4] or 0
        }
    finally:
        if not db:
            conn.close()


def get_top_reviewers(db, limit: int = 10) -> List[Dict]:
    """
    Get top reviewers by reputation

    Args:
        db: Database connection (optional)
        limit: Maximum number of reviewers

    Returns:
        List of reviewer dictionaries
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT ar.user_id, u.username, ar.total_reviews, ar.correct_votes,
                   ar.accuracy_rate, ar.reputation_score
            FROM audit_reputation ar
            LEFT JOIN users u ON ar.user_id = u.user_id
            WHERE ar.total_reviews >= 5
            ORDER BY ar.reputation_score DESC, ar.total_reviews DESC
            LIMIT %s
        ''', (limit,))

        rows = c.fetchall()

        result = []
        for r in rows:
            result.append({
                "user_id": r[0],
                "username": r[1],
                "total_reviews": r[2],
                "correct_votes": r[3],
                "accuracy_rate": r[4],
                "reputation_score": r[5]
            })

        return result
    finally:
        if not db:
            conn.close()
