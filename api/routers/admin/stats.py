"""
Admin Statistics Dashboard
Overview and trend statistics endpoints
"""
import asyncio
from fastapi import APIRouter, Depends, Query

from api.deps import require_admin
from core.database.connection import get_connection

router = APIRouter(tags=["Admin - Stats"])


@router.get("/stats/overview")
async def admin_stats_overview(
    admin_user: dict = Depends(require_admin)
):
    """概覽統計數據"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                stats = {}
                c.execute("SELECT COUNT(*) FROM users")
                stats["total_users"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE")
                stats["new_users_today"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM users WHERE last_active_at > NOW() - INTERVAL '24 hours'")
                stats["active_today"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM users WHERE membership_tier IN ('pro', 'premium') AND (membership_expires_at IS NULL OR membership_expires_at > NOW())")
                premium_users = c.fetchone()[0]
                stats["premium_users"] = premium_users

                c.execute("SELECT COUNT(*) FROM posts WHERE is_hidden = 0")
                stats["total_posts"] = c.fetchone()[0]

                c.execute("SELECT COUNT(*) FROM forum_comments WHERE is_hidden = 0 AND type = 'comment'")
                stats["total_comments"] = c.fetchone()[0]

                c.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM tips")
                row = c.fetchone()
                stats["total_tips_amount"] = float(row[0])
                stats["total_tips_count"] = row[1]

                c.execute("SELECT COUNT(*) FROM content_reports WHERE review_status = 'pending'")
                stats["pending_reports"] = c.fetchone()[0]

                return stats
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.get("/stats/users")
async def admin_stats_users(
    days: int = Query(30, ge=7, le=90),
    admin_user: dict = Depends(require_admin)
):
    """用戶增長趨勢"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= NOW() - INTERVAL %s
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """, (f"{days} days",))
                rows = c.fetchall()
                return [{"date": r[0].isoformat(), "count": r[1]} for r in rows]
        finally:
            conn.close()

    data = await loop.run_in_executor(None, _query)
    return {"success": True, "data": data, "days": days}


@router.get("/stats/forum")
async def admin_stats_forum(
    days: int = Query(30, ge=7, le=90),
    admin_user: dict = Depends(require_admin)
):
    """論壇活動趨勢"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM posts
                    WHERE created_at >= NOW() - INTERVAL %s
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """, (f"{days} days",))
                posts = [{"date": r[0].isoformat(), "count": r[1]} for r in c.fetchall()]

                c.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM forum_comments
                    WHERE created_at >= NOW() - INTERVAL %s AND type = 'comment'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """, (f"{days} days",))
                comments = [{"date": r[0].isoformat(), "count": r[1]} for r in c.fetchall()]

                return {"posts": posts, "comments": comments}
        finally:
            conn.close()

    data = await loop.run_in_executor(None, _query)
    return {"success": True, **data, "days": days}


@router.get("/stats/revenue")
async def admin_stats_revenue(
    days: int = Query(30, ge=7, le=90),
    admin_user: dict = Depends(require_admin)
):
    """收入趨勢"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT DATE(created_at) as date, SUM(amount) as total, COUNT(*) as count
                    FROM membership_payments
                    WHERE created_at >= NOW() - INTERVAL %s
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """, (f"{days} days",))
                rows = c.fetchall()
                return [{
                    "date": r[0].isoformat(),
                    "total_pi": float(r[1]),
                    "payment_count": r[2]
                } for r in rows]
        finally:
            conn.close()

    data = await loop.run_in_executor(None, _query)
    return {"success": True, "data": data, "days": days}
