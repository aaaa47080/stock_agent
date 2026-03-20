"""
Violation Functions
Add points, track violations, and apply suspensions
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..connection import get_connection
from .activity import log_activity
from .constants import SUSPENSION_DURATIONS, VIOLATION_ACTIONS, VIOLATION_LEVELS


def add_violation_points(
    db,
    user_id: str,
    points: int,
    violation_level: str,
    violation_type: str,
    source_type: str,
    source_id: int = None,
    processed_by: str = None,
) -> Dict:
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
        c.execute(
            """
            INSERT INTO user_violations
            (user_id, violation_level, violation_type, points, source_type,
             source_id, action_taken, suspended_until, processed_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """,
            (
                user_id,
                violation_level,
                violation_type,
                points,
                source_type,
                source_id,
                action_taken,
                suspended_until,
                processed_by,
            ),
        )

        violation_id = c.fetchone()[0]

        # Update violation points
        c.execute(
            """
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
        """,
            (
                user_id,
                points,
                1 if action_taken and action_taken != "warning" else 0,
                1 if action_taken and action_taken != "warning" else 0,
            ),
        )

        conn.commit()

        # Log the activity
        log_activity(
            db,
            processed_by or "system",
            "violation_added",
            "user",
            user_id,
            {
                "violation_level": violation_level,
                "points": points,
                "action_taken": action_taken,
            },
        )

        return {
            "success": True,
            "violation_id": violation_id,
            "action_taken": action_taken,
            "suspended_until": suspended_until.strftime("%Y-%m-%d %H:%M:%S")
            if suspended_until
            else None,
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
        c.execute(
            """
            SELECT points, total_violations, suspension_count, last_violation_at
            FROM user_violation_points
            WHERE user_id = %s
        """,
            (user_id,),
        )

        row = c.fetchone()
        if not row:
            return {
                "points": 0,
                "total_violations": 0,
                "suspension_count": 0,
                "last_violation_at": None,
            }

        last_violation_at = row[3]
        if last_violation_at:
            last_violation_at = last_violation_at.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "points": row[0],
            "total_violations": row[1],
            "suspension_count": row[2],
            "last_violation_at": last_violation_at,
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
        c.execute(
            """
            SELECT id, violation_level, violation_type, points, source_type,
                   action_taken, suspended_until, created_at, processed_by
            FROM user_violations
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """,
            (user_id, limit),
        )

        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[7]
            suspended_until = r[6]
            if created_at:
                created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
            if suspended_until:
                suspended_until = suspended_until.strftime("%Y-%m-%d %H:%M:%S")

            result.append(
                {
                    "id": r[0],
                    "violation_level": r[1],
                    "violation_type": r[2],
                    "points": r[3],
                    "source_type": r[4],
                    "action_taken": r[5],
                    "suspended_until": suspended_until,
                    "created_at": created_at,
                    "processed_by": r[8],
                }
            )

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

        c.execute(
            """
            UPDATE user_violations
            SET suspended_until = %s
            WHERE user_id = %s AND suspended_until IS NULL
        """,
            (suspended_until, user_id),
        )

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
        c.execute(
            """
            SELECT action_taken, suspended_until, id
            FROM user_violations
            WHERE user_id = %s AND suspended_until IS NOT NULL
            ORDER BY suspended_until DESC
            LIMIT 1
        """,
            (user_id,),
        )

        row = c.fetchone()
        if not row:
            return {"is_suspended": False, "action": None, "suspended_until": None}

        suspended_until = row[1]
        if suspended_until:
            suspended_until = suspended_until.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "is_suspended": True,
            "action": row[0],
            "suspended_until": suspended_until,
            "violation_id": row[2],
        }
    finally:
        if not db:
            conn.close()
