"""
Report Management Functions
Create, retrieve, and manage content reports
"""
from typing import Dict, List, Optional
from datetime import datetime

from ..connection import get_connection
from ..user import get_user_membership
from .constants import REPORT_TYPES, DEFAULT_DAILY_REPORT_LIMIT, PRO_DAILY_REPORT_LIMIT
from .activity import log_activity
from .helpers import get_content_author


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
                        exclude_user_id: str = None, viewer_user_id: str = None) -> List[Dict]:
    """
    Get pending reports for review

    Args:
        db: Database connection (optional)
        limit: Maximum number of reports to return
        offset: Pagination offset
        exclude_user_id: Exclude reports from this user
        viewer_user_id: ID of user viewing the reports (to check for existing votes)

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
                   u.username as reporter_username,
                   rrv.vote_type as viewer_vote
            FROM content_reports cr
            LEFT JOIN users u ON cr.reporter_user_id = u.user_id
            LEFT JOIN report_review_votes rrv ON cr.id = rrv.report_id AND rrv.reviewer_user_id = %s
            WHERE cr.review_status = 'pending'
        '''
        params = [viewer_user_id]

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
                "reporter_username": r[12],
                "viewer_vote": r[13] # Will be 'approve', 'reject', or None
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


def get_daily_report_usage(db, user_id: str) -> int:
    """
    Get the number of reports a user has submitted today

    Args:
        db: Database connection (optional)
        user_id: User ID

    Returns:
        Number of reports submitted today
    """
    conn = db or get_connection()
    c = conn.cursor()
    try:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        c.execute('''
            SELECT COUNT(*) FROM content_reports
            WHERE reporter_user_id = %s
            AND DATE(created_at) = %s
        ''', (user_id, today))
        return c.fetchone()[0]
    finally:
        if not db:
            conn.close()
