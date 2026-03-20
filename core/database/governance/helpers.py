"""
Helper Functions
Utility functions for governance operations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..connection import get_connection


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
        if content_type == "post":
            c.execute("SELECT user_id FROM posts WHERE id = %s", (content_id,))
        elif content_type == "comment":
            c.execute("SELECT user_id FROM forum_comments WHERE id = %s", (content_id,))
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

        c.execute(
            """
            SELECT
                COUNT(*) as total_reports,
                SUM(CASE WHEN review_status = 'approved' THEN 1 ELSE 0 END) as approved_reports,
                SUM(CASE WHEN review_status = 'rejected' THEN 1 ELSE 0 END) as rejected_reports,
                SUM(CASE WHEN review_status = 'pending' THEN 1 ELSE 0 END) as pending_reports,
                SUM(approve_count + reject_count) as total_votes
            FROM content_reports
            WHERE created_at >= %s
        """,
            (since_date,),
        )

        row = c.fetchone()

        return {
            "total_reports": row[0] or 0,
            "approved_reports": row[1] or 0,
            "rejected_reports": row[2] or 0,
            "pending_reports": row[3] or 0,
            "total_votes": row[4] or 0,
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
        c.execute(
            """
            SELECT ar.user_id, u.username, ar.total_reviews, ar.correct_votes,
                   ar.accuracy_rate, ar.reputation_score
            FROM audit_reputation ar
            LEFT JOIN users u ON ar.user_id = u.user_id
            WHERE ar.total_reviews >= 5
            ORDER BY ar.reputation_score DESC, ar.total_reviews DESC
            LIMIT %s
        """,
            (limit,),
        )

        rows = c.fetchall()

        result = []
        for r in rows:
            result.append(
                {
                    "user_id": r[0],
                    "username": r[1],
                    "total_reviews": r[2],
                    "correct_votes": r[3],
                    "accuracy_rate": r[4],
                    "reputation_score": r[5],
                }
            )

        return result
    finally:
        if not db:
            conn.close()
