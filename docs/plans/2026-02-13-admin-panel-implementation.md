# Admin Panel P0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add admin panel with broadcast notifications and user management to the existing SPA.

**Architecture:** Role-based auth (`role` column on users table), independent module (`admin.js` + `admin_panel.py`) embedded as a new SPA tab visible only to admin users. Reuses existing notification infrastructure for broadcast.

**Tech Stack:** FastAPI, PostgreSQL, Vanilla JS, Tailwind CSS, Lucide icons, existing WebSocket notification system.

---

### Task 1: DB Schema — Add role, is_active columns + admin_broadcasts table

**Files:**
- Modify: `core/database/connection.py:452-466` (users CREATE TABLE)
- Modify: `core/database/user.py:86` (get_user_by_id SELECT)

**Step 1: Add `role` and `is_active` to users CREATE TABLE**

In `core/database/connection.py`, find the users table creation (line ~452) and add two columns:

```python
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email TEXT UNIQUE,
            auth_method TEXT DEFAULT 'password',
            pi_uid TEXT UNIQUE,
            pi_username TEXT,
            last_active_at TIMESTAMP,
            membership_tier TEXT DEFAULT 'free',
            membership_expires_at TIMESTAMP,
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
```

**Step 2: Add ALTER TABLE for existing databases**

After the users CREATE TABLE block, add migration ALTERs (safe to re-run):

```python
    # Migration: add role and is_active columns if missing
    for col, default in [("role", "'user'"), ("is_active", "TRUE")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}" if col == "role"
                      else f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT {default}")
        except Exception:
            pass  # Column already exists
```

**Step 3: Add admin_broadcasts table**

After the users-related tables section, add:

```python
    # 管理員廣播紀錄表
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_broadcasts (
            id SERIAL PRIMARY KEY,
            admin_user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            type TEXT DEFAULT 'announcement',
            recipient_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    ''')
```

**Step 4: Update get_user_by_id to return role and is_active**

In `core/database/user.py:86`, change:

```python
# Before:
c.execute('SELECT user_id, username, email, auth_method FROM users WHERE user_id = %s', (user_id,))
row = c.fetchone()
if row:
    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "auth_method": row[3]
    }

# After:
c.execute('SELECT user_id, username, email, auth_method, role, is_active, membership_tier, membership_expires_at, created_at FROM users WHERE user_id = %s', (user_id,))
row = c.fetchone()
if row:
    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "auth_method": row[3],
        "role": row[4] or "user",
        "is_active": row[5] if row[5] is not None else True,
        "membership_tier": row[6] or "free",
        "membership_expires_at": row[7].isoformat() if row[7] else None,
        "created_at": row[8].isoformat() if row[8] else None
    }
```

**Step 5: Commit**

```bash
git add core/database/connection.py core/database/user.py
git commit -m "feat: add role, is_active columns to users + admin_broadcasts table"
```

---

### Task 2: require_admin middleware

**Files:**
- Modify: `api/deps.py:125-191` (after get_current_user)

**Step 1: Add require_admin dependency**

At the end of `api/deps.py`, add:

```python
async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Require admin role. Use as dependency on admin-only endpoints.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    return current_user
```

**Step 2: Also add is_active check in get_current_user**

In `get_current_user`, after fetching the user from DB (line ~170 `if user: return user`), add an active check:

```python
            if user:
                if not user.get("is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account has been suspended"
                    )
                return user
```

**Step 3: Commit**

```bash
git add api/deps.py
git commit -m "feat: add require_admin middleware + is_active check"
```

---

### Task 3: Admin Panel API — Broadcast Notifications

**Files:**
- Create: `api/routers/admin_panel.py`
- Modify: `api_server.py` (register router)

**Step 1: Create admin_panel.py with broadcast endpoints**

Create `api/routers/admin_panel.py`:

```python
"""
管理後台 API（獨立模組）
- 廣播通知
- 用戶管理
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
from functools import partial
import logging

from api.deps import require_admin
from core.database.connection import get_connection
from core.database.notifications import create_notification
from api.routers.notifications import push_notification_to_user, notification_manager

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
    notification_type = request.type
    sent_count = 0

    def _create_notifications_batch():
        nonlocal sent_count
        conn = get_connection()
        try:
            with conn.cursor() as c:
                from psycopg2.extras import Json
                import uuid
                for uid in user_ids:
                    nid = f"notif_{uuid.uuid4().hex[:12]}"
                    c.execute("""
                        INSERT INTO notifications (id, user_id, type, title, body, data, is_read, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
                    """, (nid, uid, notification_type, request.title, request.body,
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
                    "type": notification_type,
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
                      f'{{"title":"{request.title}","type":"{request.type}","recipients":{sent_count}}}',
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
```

**Step 2: Register router in api_server.py**

After the existing `admin_router` include:

```python
from api.routers.admin_panel import router as admin_panel_router
# ...
app.include_router(admin_panel_router)  # 管理後台 API（廣播+用戶管理）
```

**Step 3: Commit**

```bash
git add api/routers/admin_panel.py api_server.py
git commit -m "feat: admin broadcast notification API + history"
```

---

### Task 4: Admin Panel API — User Management

**Files:**
- Modify: `api/routers/admin_panel.py` (append user management endpoints)

**Step 1: Add user management endpoints**

Append to `admin_panel.py`:

```python
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
                # Get old role
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
            success = await loop.run_in_executor(
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
```

**Step 2: Commit**

```bash
git add api/routers/admin_panel.py
git commit -m "feat: admin user management API (list, role, membership, status)"
```

---

### Task 5: Frontend — admin.js module

**Files:**
- Create: `web/js/admin.js`

**Step 1: Create the full AdminPanel module**

Create `web/js/admin.js` with:
- `AdminPanel` object with `init()`, `switchSubPage()`, `_getAuthHeaders()`
- `BroadcastManager` sub-object: form render, send, history
- `UserManager` sub-object: search, list, role/membership/status actions
- Tailwind dark theme styling consistent with existing app
- Uses Lucide icons

This file should be self-contained. The HTML templates are inline in the JS (same pattern as `ForumApp` in `forum.js`).

Key patterns to follow:
- Auth headers: `AuthManager.currentUser.accessToken` (same as forum.js `_getAuthHeaders`)
- Toast messages: `showToast(message, type)` for success/error feedback
- Lucide icon refresh: `if (window.lucide) lucide.createIcons()` after DOM changes

**Step 2: Commit**

```bash
git add web/js/admin.js
git commit -m "feat: admin.js frontend module (broadcast + user management UI)"
```

---

### Task 6: SPA Integration — Register Admin tab

**Files:**
- Modify: `web/js/nav-config.js:6-16` (NAV_ITEMS array)
- Modify: `web/js/components.js` (add admin template + injection list)
- Modify: `web/index.html` (add tab div, script tag, executeTabSwitch, validTabs)

**Step 1: Add Admin item to NAV_ITEMS**

In `nav-config.js`, add before the settings entry:

```javascript
{ id: 'admin', icon: 'shield', label: 'Admin', i18nKey: 'nav.admin', defaultEnabled: true, locked: true },
```

Also bump `PREFERENCES_VERSION` from 2 to 3 so existing users get the new tab via migration.

Note: The `visible` check will be done at render time in the nav builder, not in NAV_ITEMS itself. The admin tab will be filtered out for non-admin users in the nav rendering logic.

**Step 2: Add admin template to components.js**

Add to the `Components` templates object:

```javascript
admin: () => `
    <div id="admin-content" class="p-4">
        <!-- AdminPanel.init() will populate this -->
        <div class="text-center text-textMuted py-12">Loading admin panel...</div>
    </div>
`
```

Add `'admin'` to the injection list (the array in `Components.inject` that checks which tabs to inject).

**Step 3: Add admin tab div to index.html**

After the settings-tab div, add:

```html
<div id="admin-tab" class="tab-content hidden"></div>
```

**Step 4: Add script tag for admin.js**

In the script section of index.html:

```html
<script src="/static/js/admin.js?v=1"></script>
```

**Step 5: Update executeTabSwitch in index.html**

1. Add `'admin'` to the `validTabs` array (line ~1143)
2. Add `'admin'` to the dynamic injection list (line ~1194)
3. Add admin init call:

```javascript
if (tabId === 'admin') {
    if (window.AdminPanel) AdminPanel.init();
}
```

**Step 6: Add admin tab visibility filter**

In the nav rendering logic (where nav buttons are built from NAV_ITEMS), add a filter:
- If `item.id === 'admin'` and `AuthManager.currentUser?.role !== 'admin'`, skip rendering this nav button.

This ensures non-admin users never see the Admin tab.

**Step 7: Bump cache versions**

Update all modified JS file version params in index.html:
- `nav-config.js` → bump `?v=`
- `components.js` → bump `?v=`

**Step 8: Commit**

```bash
git add web/js/nav-config.js web/js/components.js web/index.html web/js/admin.js
git commit -m "feat: integrate Admin tab into SPA (nav, components, routing)"
```

---

### Task 7: Set admin account + smoke test

**Files:**
- No new files

**Step 1: Set your account as admin via SQL**

The developer should identify their user_id and run:

```sql
UPDATE users SET role = 'admin' WHERE user_id = '<your-user-id>';
```

Or, provide a one-time endpoint in admin_panel.py that uses the existing `X-Admin-Key` from the old admin.py to bootstrap the first admin:

```python
@router.post("/bootstrap-admin")
async def bootstrap_admin(
    user_id: str = Query(...),
    admin_key: str = Depends(verify_admin_key)  # Uses existing API key auth
):
    """One-time: set a user as admin using the legacy API key."""
    # ... UPDATE users SET role = 'admin' WHERE user_id = ...
```

**Step 2: Smoke test checklist**

1. Login as admin user → Admin tab appears in nav
2. Login as normal user → Admin tab does NOT appear
3. Admin > Broadcast → Fill form → Send → Check notification bell on another test account
4. Admin > Users → Search → Results appear
5. Admin > Users → Set Pro → Verify membership changed
6. Admin > Users → Suspend → Verify user gets force-logout
7. Non-admin user tries `GET /api/admin/users` → 403

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: admin panel P0 complete (broadcast + user management)"
```

---

## Task Dependency Order

```
Task 1 (DB schema)
  → Task 2 (middleware)
    → Task 3 (broadcast API)
    → Task 4 (user mgmt API)
      → Task 5 (admin.js frontend)
        → Task 6 (SPA integration)
          → Task 7 (set admin + smoke test)
```

Tasks 3 and 4 can be done together since they're in the same file. Task 5 depends on both 3 and 4 being done so the frontend knows the API shape.
