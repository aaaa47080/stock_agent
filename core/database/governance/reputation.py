"""
Audit Reputation Functions
Track and calculate reviewer reputation
"""

from typing import Dict

from ..connection import get_connection


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
        c.execute(
            """
            SELECT total_reviews, correct_votes, accuracy_rate, reputation_score
            FROM audit_reputation
            WHERE user_id = %s
        """,
            (user_id,),
        )

        row = c.fetchone()
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
        c.execute(
            """
            SELECT total_reviews, correct_votes FROM audit_reputation
            WHERE user_id = %s
        """,
            (user_id,),
        )

        row = c.fetchone()
        if not row:
            # Create new record
            c.execute(
                """
                INSERT INTO audit_reputation
                (user_id, total_reviews, correct_votes, accuracy_rate, reputation_score, updated_at)
                VALUES (%s, 1, %s, %s, %s, NOW())
            """,
                (
                    user_id,
                    1 if was_correct else 0,
                    1.0 if was_correct else 0.0,
                    1 if was_correct else 0,
                ),
            )

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

            c.execute(
                """
                UPDATE audit_reputation
                SET total_reviews = %s,
                    correct_votes = %s,
                    accuracy_rate = %s,
                    reputation_score = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """,
                (new_total, new_correct, new_accuracy, new_score, user_id),
            )

        conn.commit()

        return {
            "success": True,
            "total_reviews": new_total,
            "correct_votes": new_correct,
            "accuracy_rate": new_correct / new_total,
            "reputation_score": max(
                0, new_correct * 10 - (new_total - new_correct) * 5
            ),
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            conn.close()
