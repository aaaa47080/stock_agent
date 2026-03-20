"""
Activity Logging Functions
Log and retrieve user activities
"""

import json
from typing import Dict, List

from ..connection import get_connection


def log_activity(
    db,
    user_id: str,
    activity_type: str,
    resource_type: str = None,
    resource_id: int = None,
    metadata: Dict = None,
    success: bool = True,
    error_message: str = None,
    ip_address: str = None,
    user_agent: str = None,
) -> Dict:
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

        c.execute(
            """
            INSERT INTO user_activity_logs
            (user_id, activity_type, resource_type, resource_id, metadata,
             success, error_message, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """,
            (
                user_id,
                activity_type,
                resource_type,
                resource_id,
                metadata_json,
                success,
                error_message,
                ip_address,
                user_agent,
            ),
        )

        log_id = c.fetchone()[0]
        conn.commit()

        return {"success": True, "log_id": log_id}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()


def get_user_activity_logs(
    db, user_id: str, activity_type: str = None, limit: int = 50, offset: int = 0
) -> List[Dict]:
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
        query = """
            SELECT id, activity_type, resource_type, resource_id,
                   metadata, success, error_message, created_at
            FROM user_activity_logs
            WHERE user_id = %s
        """
        params = [user_id]

        if activity_type:
            query += " AND activity_type = %s"
            params.append(activity_type)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[7]
            if created_at:
                created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")

            result.append(
                {
                    "id": r[0],
                    "activity_type": r[1],
                    "resource_type": r[2],
                    "resource_id": r[3],
                    "metadata": json.loads(r[4]) if r[4] else None,
                    "success": r[5],
                    "error_message": r[6],
                    "created_at": created_at,
                }
            )

        return result
    finally:
        if not db:
            conn.close()
