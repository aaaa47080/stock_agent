"""
私訊訊息限制
"""
from typing import Dict
from datetime import date

from ..connection import get_connection
from .config import _get_message_config


def check_message_limit(user_id: str, is_pro: bool) -> Dict:
    """
    檢查用戶是否超過每日訊息限制
    返回: {"can_send": bool, "remaining": int, "limit": int}
    """
    # Pro 會員：檢查是否有限制
    if is_pro:
        pro_limit = _get_message_config('limit_daily_message_premium', None)
        if pro_limit is None:
            return {"can_send": True, "remaining": -1, "limit": -1}  # -1 表示無限

    # 從資料庫讀取限制配置
    daily_limit = _get_message_config('limit_daily_message_free', 20)
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT message_count FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, today))
        row = c.fetchone()

        current_count = row[0] if row else 0
        remaining = daily_limit - current_count

        return {
            "can_send": remaining > 0,
            "remaining": max(0, remaining),
            "limit": daily_limit,
            "used": current_count
        }
    finally:
        conn.close()


def increment_message_count(user_id: str) -> None:
    """
    增加用戶的每日訊息計數
    """
    today = date.today().isoformat()

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO user_message_limits (user_id, date, message_count)
            VALUES (%s, %s, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET message_count = user_message_limits.message_count + 1
        ''', (user_id, today))
        conn.commit()
    finally:
        conn.close()


def check_greeting_limit(user_id: str, is_pro: bool) -> Dict:
    """
    檢查 Pro 用戶的每月打招呼限制
    返回: {"can_send": bool, "remaining": int, "limit": int}
    """
    if not is_pro:
        return {"can_send": False, "remaining": 0, "limit": 0, "error": "pro_only"}

    # 從資料庫讀取限制配置
    monthly_limit = _get_message_config('limit_monthly_greeting', 5)
    current_month = date.today().strftime('%Y-%m')

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT greeting_count, greeting_month FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, date.today().isoformat()))
        row = c.fetchone()

        if row and row[1] == current_month:
            current_count = row[0]
        else:
            current_count = 0

        remaining = monthly_limit - current_count

        return {
            "can_send": remaining > 0,
            "remaining": max(0, remaining),
            "limit": monthly_limit,
            "used": current_count
        }
    finally:
        conn.close()


def increment_greeting_count(user_id: str) -> None:
    """
    增加用戶的每月打招呼計數
    """
    today = date.today().isoformat()
    current_month = date.today().strftime('%Y-%m')

    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查是否需要重置（新月份）
        c.execute('''
            SELECT greeting_month FROM user_message_limits
            WHERE user_id = %s AND date = %s
        ''', (user_id, today))
        row = c.fetchone()

        if row and row[0] != current_month:
            # 新月份，重置計數
            c.execute('''
                UPDATE user_message_limits
                SET greeting_count = 1, greeting_month = %s
                WHERE user_id = %s AND date = %s
            ''', (current_month, user_id, today))
        else:
            c.execute('''
                INSERT INTO user_message_limits (user_id, date, greeting_count, greeting_month)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    greeting_count = CASE
                        WHEN user_message_limits.greeting_month = %s THEN user_message_limits.greeting_count + 1
                        ELSE 1
                    END,
                    greeting_month = %s
            ''', (user_id, today, current_month, current_month, current_month))

        conn.commit()
    finally:
        conn.close()
