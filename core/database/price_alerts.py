"""
Price Alerts Database Module

Manages user price alerts for Crypto, TW Stock, and US Stock markets.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from .connection import get_connection

VALID_MARKETS = {"crypto", "tw_stock", "us_stock"}
VALID_CONDITIONS = {"above", "below", "change_pct_up", "change_pct_down"}


def create_price_alerts_table() -> None:
    """Create price_alerts table if it doesn't exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    market      TEXT NOT NULL,
                    condition   TEXT NOT NULL,
                    target      REAL NOT NULL,
                    repeat      INTEGER NOT NULL DEFAULT 0,
                    triggered   INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL,
                    CONSTRAINT fk_alert_user
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(triggered) WHERE triggered = 0"
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


MAX_ALERTS_PER_USER = 20


def create_alert(
    user_id: str,
    symbol: str,
    market: str,
    condition: str,
    target: float,
    repeat: bool = False,
    max_alerts: int = MAX_ALERTS_PER_USER,
) -> Dict[str, Any]:
    """Create a new price alert. Returns the created alert dict.

    Raises ValueError on invalid market/condition or if the user has reached max_alerts.
    The count check and insert are performed in a single transaction to prevent races.
    """
    if market not in VALID_MARKETS:
        raise ValueError(f"Invalid market '{market}'. Must be one of {VALID_MARKETS}")
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Invalid condition '{condition}'. Must be one of {VALID_CONDITIONS}")

    alert_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    repeat_int = 1 if repeat else 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM price_alerts WHERE user_id = %s", (user_id,))
            count = cur.fetchone()[0]
            if count >= max_alerts:
                raise ValueError(
                    f"已達警報上限（最多 {max_alerts} 個），請刪除舊警報後再試。"
                )
            cur.execute(
                """
                INSERT INTO price_alerts (id, user_id, symbol, market, condition, target, repeat, triggered, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s)
                """,
                (alert_id, user_id, symbol.upper(), market, condition, target, repeat_int, created_at),
            )
            conn.commit()
    finally:
        conn.close()

    return {
        "id": alert_id,
        "user_id": user_id,
        "symbol": symbol.upper(),
        "market": market,
        "condition": condition,
        "target": target,
        "repeat": repeat_int,
        "triggered": 0,
        "created_at": created_at,
    }


def get_user_alerts(user_id: str) -> List[Dict[str, Any]]:
    """Return all alerts for a user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, symbol, market, condition, target, repeat, triggered, created_at "
                "FROM price_alerts WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "user_id": r[1], "symbol": r[2],
                    "market": r[3], "condition": r[4], "target": r[5],
                    "repeat": r[6], "triggered": r[7], "created_at": r[8],
                }
                for r in rows
            ]
    finally:
        conn.close()


def delete_alert(alert_id: str, user_id: str) -> bool:
    """Delete an alert. Returns True if deleted, False if not found/unauthorized."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM price_alerts WHERE id = %s AND user_id = %s",
                (alert_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_active_alerts() -> List[Dict[str, Any]]:
    """Return all alerts that have not been permanently deactivated (for background task)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # one-shot: triggered=0
            # persistent (repeat=1): always active (triggered resets each cycle)
            cur.execute(
                "SELECT id, user_id, symbol, market, condition, target, repeat, triggered, created_at "
                "FROM price_alerts WHERE triggered = 0 OR repeat = 1"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "user_id": r[1], "symbol": r[2],
                    "market": r[3], "condition": r[4], "target": r[5],
                    "repeat": r[6], "triggered": r[7], "created_at": r[8],
                }
                for r in rows
            ]
    finally:
        conn.close()


def mark_alert_triggered(alert_id: str, repeat: bool) -> None:
    """
    Handle triggered alert:
    - repeat=False (one-shot): delete the alert
    - repeat=True (persistent): set triggered=1 to prevent immediate re-trigger
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not repeat:
                cur.execute("DELETE FROM price_alerts WHERE id = %s", (alert_id,))
            else:
                cur.execute(
                    "UPDATE price_alerts SET triggered = 1 WHERE id = %s",
                    (alert_id,),
                )
            conn.commit()
    finally:
        conn.close()


def count_user_alerts(user_id: str) -> int:
    """Count total alerts for a user (for limit enforcement)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM price_alerts WHERE user_id = %s", (user_id,))
            return cur.fetchone()[0]
    finally:
        conn.close()
