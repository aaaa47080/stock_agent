"""
管理後台 API（獨立模組）
- 廣播通知
- 用戶管理
- 論壇管理 (P1)
- 系統設定 (P1)
- 統計儀表板 (P2)
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import asyncio
import os
from functools import partial
from datetime import datetime, timedelta
import logging
import json
import uuid

from api.deps import require_admin, get_current_user
from core.database.connection import get_connection
from core.database.notifications import create_notification
from api.routers.notifications import push_notification_to_user, notification_manager
from core.database.system_config import list_all_configs_with_metadata, set_config
from core.database.governance import finalize_report, get_report_by_id
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])


# ============================================================================
# Request Models
# ============================================================================

class BroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    type: str = Field(default="announcement", pattern="^(announcement|system_update)$")


class SetRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


class SetMembershipRequest(BaseModel):
    tier: str = Field(..., pattern="^(pro|free)$")
    months: int = Field(default=1, ge=1, le=12)


class SetStatusRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


class PostVisibilityRequest(BaseModel):
    is_hidden: bool


class PostPinRequest(BaseModel):
    is_pinned: bool


class ResolveReportRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    violation_level: Optional[str] = Field(None, pattern="^(mild|medium|severe|critical)$")


class UpdateConfigRequest(BaseModel):
    value: str


# ============================================================================
# Broadcast Notifications
# ============================================================================

@router.post("/notifications/broadcast")
async def broadcast_notification(
    request: BroadcastRequest,
    admin_user: dict = Depends(require_admin)
):
    """發送廣播通知給所有活躍用戶"""
    loop = asyncio.get_running_loop()

    # 1. 查所有活躍用戶
    def _get_active_user_ids():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT user_id FROM users WHERE is_active = TRUE OR is_active IS NULL")
                return [row[0] for row in c.fetchall()]
        finally:
            conn.close()

    user_ids = await loop.run_in_executor(None, _get_active_user_ids)

    if not user_ids:
        return {"success": True, "sent_count": 0, "online_count": 0}

    # 2. 批量建通知
    sent_count = 0

    def _create_notifications_batch():
        nonlocal sent_count
        conn = get_connection()
        try:
            with conn.cursor() as c:
                for uid in user_ids:
                    nid = f"notif_{uuid.uuid4().hex[:12]}"
                    c.execute("""
                        INSERT INTO notifications (id, user_id, type, title, body, data, is_read, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
                    """, (nid, uid, request.type, request.title, request.body,
                          Json({"admin_user_id": admin_user["user_id"]})))
                    sent_count += 1
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    await loop.run_in_executor(None, _create_notifications_batch)

    # 3. WebSocket push 在線用戶
    online_count = 0
    for uid in user_ids:
        if uid in notification_manager.active_connections:
            try:
                await push_notification_to_user(uid, {
                    "type": request.type,
                    "title": request.title,
                    "body": request.body
                })
                online_count += 1
            except Exception:
                pass

    # 4. 寫廣播紀錄
    def _save_broadcast_record():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO admin_broadcasts (admin_user_id, title, body, type, recipient_count)
                    VALUES (%s, %s, %s, %s, %s)
                """, (admin_user["user_id"], request.title, request.body, request.type, sent_count))
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.warning(f"Failed to save broadcast record: {e}")
        finally:
            conn.close()

    await loop.run_in_executor(None, _save_broadcast_record)

    # 5. 審計紀錄
    def _write_audit():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, ("broadcast", None,
                      json.dumps({"title": request.title, "type": request.type, "recipients": sent_count}),
                      admin_user["user_id"]))
                conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    await loop.run_in_executor(None, _write_audit)

    return {
        "success": True,
        "sent_count": sent_count,
        "online_count": online_count
    }


@router.get("/notifications/history")
async def get_broadcast_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """獲取廣播歷史紀錄"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT id, admin_user_id, title, body, type, recipient_count, created_at
                    FROM admin_broadcasts
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                rows = c.fetchall()

                c.execute("SELECT COUNT(*) FROM admin_broadcasts")
                total = c.fetchone()[0]

                return {
                    "broadcasts": [{
                        "id": r[0], "admin_user_id": r[1], "title": r[2],
                        "body": r[3], "type": r[4], "recipient_count": r[5],
                        "created_at": r[6].isoformat() if r[6] else None
                    } for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit
                }
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


# ============================================================================
# User Management
# ============================================================================

@router.get("/users")
async def list_users(
    search: str = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """搜尋/列出用戶"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                if search:
                    like = f"%{search}%"
                    c.execute("""
                        SELECT user_id, username, email, auth_method, role, is_active,
                               membership_tier, membership_expires_at, created_at, last_active_at
                        FROM users
                        WHERE username ILIKE %s OR user_id ILIKE %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (like, like, limit, offset))
                    rows = c.fetchall()

                    c.execute("""
                        SELECT COUNT(*) FROM users
                        WHERE username ILIKE %s OR user_id ILIKE %s
                    """, (like, like))
                else:
                    c.execute("""
                        SELECT user_id, username, email, auth_method, role, is_active,
                               membership_tier, membership_expires_at, created_at, last_active_at
                        FROM users
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                    rows = c.fetchall()

                    c.execute("SELECT COUNT(*) FROM users")

                total = c.fetchone()[0]

                return {
                    "users": [{
                        "user_id": r[0], "username": r[1], "email": r[2],
                        "auth_method": r[3], "role": r[4] or "user",
                        "is_active": r[5] if r[5] is not None else True,
                        "membership_tier": r[6] or "free",
                        "membership_expires_at": r[7].isoformat() if r[7] else None,
                        "created_at": r[8].isoformat() if r[8] else None,
                        "last_active_at": r[9].isoformat() if r[9] else None
                    } for r in rows],
                    "total": total,
                    "page": page,
                    "limit": limit
                }
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    admin_user: dict = Depends(require_admin)
):
    """獲取單一用戶詳情"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT user_id, username, email, auth_method, role, is_active,
                           membership_tier, membership_expires_at, created_at, last_active_at,
                           pi_uid, pi_username
                    FROM users WHERE user_id = %s
                """, (user_id,))
                r = c.fetchone()
                if not r:
                    return None
                return {
                    "user_id": r[0], "username": r[1], "email": r[2],
                    "auth_method": r[3], "role": r[4] or "user",
                    "is_active": r[5] if r[5] is not None else True,
                    "membership_tier": r[6] or "free",
                    "membership_expires_at": r[7].isoformat() if r[7] else None,
                    "created_at": r[8].isoformat() if r[8] else None,
                    "last_active_at": r[9].isoformat() if r[9] else None,
                    "pi_uid": r[10], "pi_username": r[11]
                }
        finally:
            conn.close()

    user = await loop.run_in_executor(None, _query)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user": user}


@router.put("/users/{user_id}/role")
async def set_user_role(
    user_id: str,
    request: SetRoleRequest,
    admin_user: dict = Depends(require_admin)
):
    """設定用戶角色"""
    loop = asyncio.get_running_loop()

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
                row = c.fetchone()
                if not row:
                    return None
                old_role = row[0] or "user"

                c.execute("UPDATE users SET role = %s WHERE user_id = %s", (request.role, user_id))

                # Audit log
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"user_role:{user_id}", old_role, request.role, admin_user["user_id"]))

                conn.commit()
                return {"old_role": old_role, "new_role": request.role}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, **result}


@router.put("/users/{user_id}/membership")
async def set_user_membership(
    user_id: str,
    request: SetMembershipRequest,
    admin_user: dict = Depends(require_admin)
):
    """設定用戶會員等級"""
    loop = asyncio.get_running_loop()

    if request.tier == "pro":
        from core.database.user import upgrade_to_pro
        try:
            await loop.run_in_executor(
                None, partial(upgrade_to_pro, user_id, request.months, f"admin_grant_{admin_user['user_id']}")
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Audit log
        def _audit():
            conn = get_connection()
            try:
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                        VALUES (%s, %s, %s, %s)
                    """, (f"user_membership:{user_id}", "free", f"pro:{request.months}mo", admin_user["user_id"]))
                    conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

        await loop.run_in_executor(None, _audit)
        return {"success": True, "tier": "pro", "months": request.months}

    else:
        # Downgrade to free
        from core.database.user import expire_user_membership
        await loop.run_in_executor(None, expire_user_membership, user_id)

        def _audit():
            conn = get_connection()
            try:
                with conn.cursor() as c:
                    c.execute("""
                        INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                        VALUES (%s, %s, %s, %s)
                    """, (f"user_membership:{user_id}", "pro", "free", admin_user["user_id"]))
                    conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

        await loop.run_in_executor(None, _audit)
        return {"success": True, "tier": "free"}


@router.put("/users/{user_id}/status")
async def set_user_status(
    user_id: str,
    request: SetStatusRequest,
    admin_user: dict = Depends(require_admin)
):
    """封鎖/解封用戶"""
    loop = asyncio.get_running_loop()

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_active FROM users WHERE user_id = %s", (user_id,))
                row = c.fetchone()
                if not row:
                    return None

                old_status = "active" if row[0] else "suspended"
                new_status = "active" if request.active else "suspended"

                c.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (request.active, user_id))

                # Audit log
                reason_str = f" reason:{request.reason}" if request.reason else ""
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"user_status:{user_id}", old_status, f"{new_status}{reason_str}", admin_user["user_id"]))

                conn.commit()
                return {"old_status": old_status, "new_status": new_status}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    # If suspending, push force-logout via WebSocket
    if not request.active:
        try:
            await notification_manager.send_to_user(user_id, {
                "type": "force_logout",
                "reason": request.reason or "Account suspended by admin"
            })
        except Exception:
            pass

    return {"success": True, **result}


# ============================================================================
# Bootstrap (one-time, uses legacy API key for first admin setup)
# ============================================================================

@router.post("/bootstrap-admin")
async def bootstrap_admin(
    user_id: str = Query(..., description="要設為 admin 的 user_id"),
    current_user: dict = Depends(get_current_user)
):
    """
    設定第一個管理員（需要已登入的有效帳號）。
    如果系統中沒有任何 admin，允許任何登入用戶自我提升。
    如果已有 admin，則只有 admin 才能設定新 admin。

    安全：生產環境可設 ALLOW_ADMIN_BOOTSTRAP=false 來完全關閉此端點。
    """
    # 安全開關：生產環境設定完第一個 admin 後應關閉
    allow_bootstrap = os.getenv("ALLOW_ADMIN_BOOTSTRAP", "true").lower()
    if allow_bootstrap == "false":
        raise HTTPException(
            status_code=403,
            detail="Bootstrap endpoint is disabled. Set ALLOW_ADMIN_BOOTSTRAP=true to enable."
        )

    loop = asyncio.get_running_loop()

    def _bootstrap():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                # Check if any admin exists
                c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                admin_count = c.fetchone()[0]

                if admin_count > 0:
                    # Already has admins - only admin can add more
                    if current_user.get("role") != "admin":
                        return {"error": "forbidden"}

                # 安全：只允許用戶將自己設為 admin（防止指定他人）
                if admin_count == 0 and user_id != current_user.get("user_id"):
                    return {"error": "self_only"}

                # Verify target user exists
                c.execute("SELECT user_id, username FROM users WHERE user_id = %s", (user_id,))
                row = c.fetchone()
                if not row:
                    return {"error": "not_found"}

                c.execute("UPDATE users SET role = 'admin' WHERE user_id = %s", (user_id,))
                conn.commit()

                # 寫審計日誌
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"bootstrap_admin:{user_id}", "user", "admin", current_user.get("user_id")))
                conn.commit()

                return {"success": True, "user_id": row[0], "username": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _bootstrap)

    if result.get("error") == "forbidden":
        raise HTTPException(status_code=403, detail="Only existing admins can add new admins")
    if result.get("error") == "self_only":
        raise HTTPException(status_code=403, detail="First admin can only bootstrap themselves")
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="User not found")

    return result


# ============================================================================
# P1A: Forum Management
# ============================================================================

@router.get("/forum/posts")
async def admin_list_posts(
    search: str = Query(None, max_length=200),
    status: str = Query("all", pattern="^(all|hidden|pinned)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """管理後台 - 列出論壇貼文（含隱藏貼文）"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                where_clauses = []
                params = []

                if search:
                    where_clauses.append("(p.title ILIKE %s OR u.username ILIKE %s)")
                    like = f"%{search}%"
                    params.extend([like, like])

                if status == "hidden":
                    where_clauses.append("p.is_hidden = 1")
                elif status == "pinned":
                    where_clauses.append("p.is_pinned = 1")

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                c.execute(f"""
                    SELECT p.id, p.title, p.user_id, u.username, p.category,
                           p.is_hidden, p.is_pinned, p.comment_count, p.view_count,
                           p.push_count, p.boo_count, p.created_at
                    FROM posts p
                    LEFT JOIN users u ON p.user_id = u.user_id
                    {where_sql}
                    ORDER BY p.created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                rows = c.fetchall()

                c.execute(f"""
                    SELECT COUNT(*)
                    FROM posts p
                    LEFT JOIN users u ON p.user_id = u.user_id
                    {where_sql}
                """, params)
                total = c.fetchone()[0]

                return {
                    "posts": [{
                        "id": r[0], "title": r[1], "user_id": r[2],
                        "username": r[3] or "Unknown", "category": r[4],
                        "is_hidden": bool(r[5]), "is_pinned": bool(r[6]),
                        "comment_count": r[7] or 0, "view_count": r[8] or 0,
                        "push_count": r[9] or 0, "boo_count": r[10] or 0,
                        "created_at": r[11].isoformat() if r[11] else None
                    } for r in rows],
                    "total": total, "page": page, "limit": limit
                }
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.patch("/forum/posts/{post_id}/visibility")
async def admin_toggle_post_visibility(
    post_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin)
):
    """隱藏/顯示貼文"""
    loop = asyncio.get_running_loop()
    hidden_int = 1 if request.is_hidden else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_hidden, title FROM posts WHERE id = %s", (post_id,))
                row = c.fetchone()
                if not row:
                    return None
                old_hidden = bool(row[0])

                c.execute("UPDATE posts SET is_hidden = %s WHERE id = %s", (hidden_int, post_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:post_visibility:{post_id}",
                      "hidden" if old_hidden else "visible",
                      "hidden" if request.is_hidden else "visible",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_hidden": old_hidden, "new_hidden": request.is_hidden, "title": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True, **result}


@router.patch("/forum/posts/{post_id}/pin")
async def admin_toggle_post_pin(
    post_id: int,
    request: PostPinRequest,
    admin_user: dict = Depends(require_admin)
):
    """置頂/取消置頂貼文"""
    loop = asyncio.get_running_loop()
    pinned_int = 1 if request.is_pinned else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_pinned, title FROM posts WHERE id = %s", (post_id,))
                row = c.fetchone()
                if not row:
                    return None

                c.execute("UPDATE posts SET is_pinned = %s WHERE id = %s", (pinned_int, post_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:post_pin:{post_id}",
                      "pinned" if row[0] else "unpinned",
                      "pinned" if request.is_pinned else "unpinned",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_pinned": bool(row[0]), "new_pinned": request.is_pinned, "title": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True, **result}


@router.patch("/forum/comments/{comment_id}/visibility")
async def admin_toggle_comment_visibility(
    comment_id: int,
    request: PostVisibilityRequest,
    admin_user: dict = Depends(require_admin)
):
    """隱藏/顯示留言"""
    loop = asyncio.get_running_loop()
    hidden_int = 1 if request.is_hidden else 0

    def _update():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("SELECT is_hidden, post_id FROM forum_comments WHERE id = %s", (comment_id,))
                row = c.fetchone()
                if not row:
                    return None

                c.execute("UPDATE forum_comments SET is_hidden = %s WHERE id = %s", (hidden_int, comment_id))
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, (f"admin_forum:comment_visibility:{comment_id}",
                      "hidden" if row[0] else "visible",
                      "hidden" if request.is_hidden else "visible",
                      admin_user["user_id"]))
                conn.commit()
                return {"old_hidden": bool(row[0]), "new_hidden": request.is_hidden, "post_id": row[1]}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _update)
    if result is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"success": True, **result}


@router.get("/forum/reports")
async def admin_list_reports(
    status: str = Query("pending", pattern="^(pending|approved|rejected)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin)
):
    """列出內容舉報"""
    loop = asyncio.get_running_loop()
    offset = (page - 1) * limit

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT cr.id, cr.content_type, cr.content_id, cr.reporter_user_id,
                           u.username as reporter_username, cr.report_type, cr.description,
                           cr.review_status, cr.approve_count, cr.reject_count, cr.created_at
                    FROM content_reports cr
                    LEFT JOIN users u ON cr.reporter_user_id = u.user_id
                    WHERE cr.review_status = %s
                    ORDER BY cr.created_at DESC
                    LIMIT %s OFFSET %s
                """, (status, limit, offset))
                rows = c.fetchall()

                c.execute("SELECT COUNT(*) FROM content_reports WHERE review_status = %s", (status,))
                total = c.fetchone()[0]

                reports = []
                for r in rows:
                    report = {
                        "id": r[0], "content_type": r[1], "content_id": r[2],
                        "reporter_user_id": r[3], "reporter_username": r[4] or "Unknown",
                        "report_type": r[5], "description": r[6],
                        "review_status": r[7], "approve_count": r[8] or 0,
                        "reject_count": r[9] or 0,
                        "created_at": r[10].isoformat() if r[10] else None,
                        "content_preview": None
                    }
                    # Fetch content preview
                    if r[1] == "post":
                        c.execute("SELECT title FROM posts WHERE id = %s", (r[2],))
                    elif r[1] == "comment":
                        c.execute("SELECT content FROM forum_comments WHERE id = %s", (r[2],))
                    preview_row = c.fetchone()
                    if preview_row:
                        report["content_preview"] = (preview_row[0] or "")[:100]
                    reports.append(report)

                return {"reports": reports, "total": total, "page": page, "limit": limit}
        finally:
            conn.close()

    result = await loop.run_in_executor(None, _query)
    return {"success": True, **result}


@router.post("/forum/reports/{report_id}/resolve")
async def admin_resolve_report(
    report_id: int,
    request: ResolveReportRequest,
    admin_user: dict = Depends(require_admin)
):
    """處理舉報（批准=隱藏內容+違規記點，駁回=不處理）"""
    loop = asyncio.get_running_loop()

    # 1. Get report details
    report = await loop.run_in_executor(None, partial(get_report_by_id, None, report_id))
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.get("review_status") != "pending":
        raise HTTPException(status_code=400, detail="Report already resolved")

    # 2. Finalize via governance system
    result = await loop.run_in_executor(
        None, partial(finalize_report, None, report_id, request.decision,
                      request.violation_level, admin_user["user_id"])
    )

    # 3. If approved, auto-hide the reported content
    if request.decision == "approved":
        content_type = report.get("content_type")
        content_id = report.get("content_id")

        def _hide_content():
            conn = get_connection()
            try:
                with conn.cursor() as c:
                    if content_type == "post":
                        c.execute("UPDATE posts SET is_hidden = 1 WHERE id = %s", (content_id,))
                    elif content_type == "comment":
                        c.execute("UPDATE forum_comments SET is_hidden = 1 WHERE id = %s", (content_id,))
                    c.execute("""
                        INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                        VALUES (%s, %s, %s, %s)
                    """, (f"admin_forum:report_resolve:{report_id}",
                          "pending", f"{request.decision}:hide_{content_type}:{content_id}",
                          admin_user["user_id"]))
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to hide content for report {report_id}: {e}")
            finally:
                conn.close()

        await loop.run_in_executor(None, _hide_content)

    return {"success": True, "report_id": report_id, "decision": request.decision,
            "content_hidden": request.decision == "approved"}


# ============================================================================
# P1B: System Config Management
# ============================================================================

@router.get("/config/all")
async def admin_get_all_configs(
    admin_user: dict = Depends(require_admin)
):
    """獲取所有系統設定（依類別分組）"""
    loop = asyncio.get_running_loop()

    configs = await loop.run_in_executor(None, list_all_configs_with_metadata)

    # Group by category
    grouped = {}
    for cfg in configs:
        cat = cfg.get("category", "general")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(cfg)

    return {"success": True, "configs_by_category": grouped}


@router.put("/config/{key}")
async def admin_update_config(
    key: str,
    request: UpdateConfigRequest,
    admin_user: dict = Depends(require_admin)
):
    """更新單一設定值"""
    loop = asyncio.get_running_loop()

    success = await loop.run_in_executor(
        None, partial(set_config, key, request.value, changed_by=admin_user["user_id"])
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update config")

    return {"success": True, "key": key, "value": request.value}


@router.get("/config/audit")
async def admin_get_config_audit(
    limit: int = Query(50, ge=1, le=200),
    admin_user: dict = Depends(require_admin)
):
    """獲取設定變更歷史"""
    loop = asyncio.get_running_loop()

    def _query():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                c.execute("""
                    SELECT config_key, old_value, new_value, changed_by, changed_at
                    FROM config_audit_log
                    ORDER BY changed_at DESC
                    LIMIT %s
                """, (limit,))
                rows = c.fetchall()
                return [{
                    "key": r[0], "old_value": r[1], "new_value": r[2],
                    "changed_by": r[3],
                    "changed_at": r[4].isoformat() if r[4] else None
                } for r in rows]
        finally:
            conn.close()

    logs = await loop.run_in_executor(None, _query)
    return {"success": True, "logs": logs}


# ============================================================================
# P2: Statistics Dashboard
# ============================================================================

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

                c.execute("SELECT COUNT(*) FROM users WHERE membership_tier = 'pro' AND (membership_expires_at IS NULL OR membership_expires_at > NOW())")
                stats["pro_users"] = c.fetchone()[0]

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
                c.execute(f"""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """)
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
                c.execute(f"""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM posts
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """)
                posts = [{"date": r[0].isoformat(), "count": r[1]} for r in c.fetchall()]

                c.execute(f"""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM forum_comments
                    WHERE created_at >= NOW() - INTERVAL '{days} days' AND type = 'comment'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """)
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
                c.execute(f"""
                    SELECT DATE(created_at) as date,
                           COALESCE(SUM(amount), 0) as amount,
                           COUNT(*) as count
                    FROM tips
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """)
                tips = [{"date": r[0].isoformat(), "amount": float(r[1]), "count": r[2]}
                        for r in c.fetchall()]

                c.execute(f"""
                    SELECT DATE(created_at) as date,
                           COALESCE(SUM(amount), 0) as amount,
                           COUNT(*) as count
                    FROM membership_payments
                    WHERE created_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY DATE(created_at)
                    ORDER BY date ASC
                """)
                memberships = [{"date": r[0].isoformat(), "amount": float(r[1]), "count": r[2]}
                               for r in c.fetchall()]

                return {"tips": tips, "memberships": memberships}
        finally:
            conn.close()

    data = await loop.run_in_executor(None, _query)
    return {"success": True, **data, "days": days}
