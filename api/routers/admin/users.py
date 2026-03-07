"""
Admin User Management
User listing, role, membership, and status management endpoints
"""
import asyncio
import logging
from functools import partial
from fastapi import APIRouter, Depends, Query, HTTPException

from api.deps import require_admin, get_current_user
from core.database.connection import get_connection
from api.routers.notifications import notification_manager
from .schemas import SetRoleRequest, SetMembershipRequest, SetStatusRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Users"])


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
# Bootstrap (one-time admin setup)
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
    import os

    # 1. 環境開關
    if os.getenv("ALLOW_ADMIN_BOOTSTRAP", "true").lower() == "false":
        raise HTTPException(status_code=403, detail="Admin bootstrap is disabled")

    loop = asyncio.get_running_loop()

    def _check_and_set():
        conn = get_connection()
        try:
            with conn.cursor() as c:
                # Check existing admins
                c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                admin_count = c.fetchone()[0]

                if admin_count > 0:
                    # Already has admin, check if current user is admin
                    if current_user.get("role") != "admin":
                        raise PermissionError("Only admins can create new admins")
                    # Current user is admin, allow setting new admin
                    c.execute("UPDATE users SET role = 'admin' WHERE user_id = %s", (user_id,))
                else:
                    # No admin yet, allow self-promotion
                    c.execute("UPDATE users SET role = 'admin' WHERE user_id = %s", (user_id,))

                # Audit log
                c.execute("""
                    INSERT INTO config_audit_log (config_key, old_value, new_value, changed_by)
                    VALUES (%s, %s, %s, %s)
                """, ("bootstrap_admin", None, user_id, current_user["user_id"]))

                conn.commit()
                return True
        except PermissionError as e:
            conn.rollback()
            raise e
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    try:
        await loop.run_in_executor(None, _check_and_set)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"success": True, "message": f"User {user_id} is now an admin"}
