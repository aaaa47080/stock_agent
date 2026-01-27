"""
好友功能資料庫操作
包含：用戶搜尋、好友請求、好友管理、封鎖功能
"""
from typing import List, Dict, Optional

from .connection import get_connection


# ============================================================================
# 用戶搜尋 / 發現
# ============================================================================

def search_users(query: str, limit: int = 20, exclude_user_id: str = None) -> List[Dict]:
    """
    以用戶名搜尋用戶（部分匹配）
    用於尋找要加為好友的用戶
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        sql = '''
            SELECT user_id, username, pi_username, membership_tier, created_at
            FROM users
            WHERE username LIKE ?
        '''
        params = [f'%{query}%']

        if exclude_user_id:
            sql += ' AND user_id != ?'
            params.append(exclude_user_id)

        sql += ' ORDER BY username ASC LIMIT ?'
        params.append(limit)

        c.execute(sql, params)
        rows = c.fetchall()

        return [
            {
                "user_id": r[0],
                "username": r[1],
                "pi_username": r[2],
                "membership_tier": r[3] or 'free',
                "member_since": r[4]
            } for r in rows
        ]
    finally:
        conn.close()


def get_public_user_profile(user_id: str, viewer_user_id: str = None) -> Optional[Dict]:
    """
    取得用戶的公開資料
    如果查看者是好友，會返回更多資訊
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 取得基本用戶資訊
        c.execute('''
            SELECT user_id, username, pi_username, membership_tier, created_at
            FROM users
            WHERE user_id = ?
        ''', (user_id,))
        row = c.fetchone()

        if not row:
            return None

        profile = {
            "user_id": row[0],
            "username": row[1],
            "pi_username": row[2],
            "membership_tier": row[3] or 'free',
            "member_since": row[4],
            "is_friend": False,
            "friend_status": None
        }

        # 如果有查看者，檢查好友狀態
        if viewer_user_id and viewer_user_id != user_id:
            friendship = get_friendship_status(viewer_user_id, user_id)
            profile["friend_status"] = friendship.get("status") if friendship else None
            profile["is_friend"] = friendship.get("status") == "accepted" if friendship else False

        # 取得論壇統計（公開）
        c.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND is_hidden = 0', (user_id,))
        profile["post_count"] = c.fetchone()[0]

        c.execute('SELECT COALESCE(SUM(push_count), 0) FROM posts WHERE user_id = ?', (user_id,))
        profile["total_pushes"] = c.fetchone()[0]

        return profile
    finally:
        conn.close()


# ============================================================================
# 好友請求
# ============================================================================

def send_friend_request(from_user_id: str, to_user_id: str) -> Dict:
    """
    發送好友請求
    返回: {"success": bool, "message": str, "request_id": int}
    """
    if from_user_id == to_user_id:
        return {"success": False, "error": "cannot_add_self"}

    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查是否已存在任何關係
        c.execute('''
            SELECT id, status, user_id FROM friendships
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (from_user_id, to_user_id, to_user_id, from_user_id))
        existing = c.fetchone()

        if existing:
            status = existing[1]
            requester_id = existing[2]

            if status == 'accepted':
                return {"success": False, "error": "already_friends"}
            elif status == 'pending':
                # 檢查方向 - 如果對方已經發送請求給我們，自動接受
                if requester_id == to_user_id:
                    # 對方發送請求給我們，自動接受
                    c.execute('''
                        UPDATE friendships
                        SET status = 'accepted', updated_at = datetime('now')
                        WHERE user_id = ? AND friend_id = ?
                    ''', (to_user_id, from_user_id))
                    conn.commit()
                    return {"success": True, "message": "friend_added", "auto_accepted": True}
                return {"success": False, "error": "request_pending"}
            elif status == 'blocked':
                # 檢查是誰封鎖誰
                if requester_id == to_user_id:
                    return {"success": False, "error": "user_blocked_you"}
                return {"success": False, "error": "you_blocked_user"}
            elif status == 'rejected':
                # 允許在拒絕後重新發送（更新現有記錄）
                c.execute('''
                    UPDATE friendships
                    SET status = 'pending', updated_at = datetime('now')
                    WHERE user_id = ? AND friend_id = ?
                ''', (from_user_id, to_user_id))
                conn.commit()
                return {"success": True, "message": "request_resent", "request_id": existing[0]}

        # 建立新的好友請求
        c.execute('''
            INSERT INTO friendships (user_id, friend_id, status, created_at, updated_at)
            VALUES (?, ?, 'pending', datetime('now'), datetime('now'))
        ''', (from_user_id, to_user_id))
        conn.commit()

        return {"success": True, "message": "request_sent", "request_id": c.lastrowid}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def accept_friend_request(user_id: str, requester_id: str) -> Dict:
    """
    接受好友請求
    user_id: 接受請求的用戶
    requester_id: 發送請求的用戶
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE friendships
            SET status = 'accepted', updated_at = datetime('now')
            WHERE user_id = ? AND friend_id = ? AND status = 'pending'
        ''', (requester_id, user_id))

        if c.rowcount == 0:
            return {"success": False, "error": "request_not_found"}

        conn.commit()
        return {"success": True, "message": "friend_added"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def reject_friend_request(user_id: str, requester_id: str) -> Dict:
    """拒絕好友請求"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE friendships
            SET status = 'rejected', updated_at = datetime('now')
            WHERE user_id = ? AND friend_id = ? AND status = 'pending'
        ''', (requester_id, user_id))

        if c.rowcount == 0:
            return {"success": False, "error": "request_not_found"}

        conn.commit()
        return {"success": True, "message": "request_rejected"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def cancel_friend_request(user_id: str, target_user_id: str) -> Dict:
    """取消已發送的好友請求"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            DELETE FROM friendships
            WHERE user_id = ? AND friend_id = ? AND status = 'pending'
        ''', (user_id, target_user_id))

        if c.rowcount == 0:
            return {"success": False, "error": "request_not_found"}

        conn.commit()
        return {"success": True, "message": "request_cancelled"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def remove_friend(user_id: str, friend_id: str) -> Dict:
    """移除好友（解除好友關係）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 刪除雙向的好友記錄
        c.execute('''
            DELETE FROM friendships
            WHERE ((user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?))
            AND status = 'accepted'
        ''', (user_id, friend_id, friend_id, user_id))

        if c.rowcount == 0:
            return {"success": False, "error": "not_friends"}

        conn.commit()
        return {"success": True, "message": "friend_removed"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ============================================================================
# 封鎖功能
# ============================================================================

def block_user(user_id: str, blocked_user_id: str) -> Dict:
    """封鎖用戶（阻止好友請求和互動）"""
    if user_id == blocked_user_id:
        return {"success": False, "error": "cannot_block_self"}

    conn = get_connection()
    c = conn.cursor()
    try:
        # 移除任何現有的好友關係/請求
        c.execute('''
            DELETE FROM friendships
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (user_id, blocked_user_id, blocked_user_id, user_id))

        # 建立封鎖記錄
        c.execute('''
            INSERT INTO friendships (user_id, friend_id, status, created_at, updated_at)
            VALUES (?, ?, 'blocked', datetime('now'), datetime('now'))
        ''', (user_id, blocked_user_id))

        conn.commit()
        return {"success": True, "message": "user_blocked"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def unblock_user(user_id: str, blocked_user_id: str) -> Dict:
    """解除封鎖"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            DELETE FROM friendships
            WHERE user_id = ? AND friend_id = ? AND status = 'blocked'
        ''', (user_id, blocked_user_id))

        if c.rowcount == 0:
            return {"success": False, "error": "user_not_blocked"}

        conn.commit()
        return {"success": True, "message": "user_unblocked"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_blocked_users(user_id: str) -> List[Dict]:
    """取得封鎖名單"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT u.user_id, u.username, u.pi_username, f.created_at as blocked_at
            FROM friendships f
            JOIN users u ON f.friend_id = u.user_id
            WHERE f.user_id = ? AND f.status = 'blocked'
            ORDER BY f.created_at DESC
        ''', (user_id,))

        rows = c.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "pi_username": r[2],
                "blocked_at": r[3]
            } for r in rows
        ]
    finally:
        conn.close()


# ============================================================================
# 好友列表與查詢
# ============================================================================

def get_friends_list(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
    """取得已接受的好友列表"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT u.user_id, u.username, u.pi_username, u.membership_tier,
                   f.updated_at as friends_since
            FROM friendships f
            JOIN users u ON (
                CASE
                    WHEN f.user_id = ? THEN f.friend_id = u.user_id
                    ELSE f.user_id = u.user_id
                END
            )
            WHERE (f.user_id = ? OR f.friend_id = ?)
            AND f.status = 'accepted'
            AND u.user_id != ?
            ORDER BY f.updated_at DESC
            LIMIT ? OFFSET ?
        ''', (user_id, user_id, user_id, user_id, limit, offset))

        rows = c.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "pi_username": r[2],
                "membership_tier": r[3] or 'free',
                "friends_since": r[4]
            } for r in rows
        ]
    finally:
        conn.close()


def get_pending_requests_received(user_id: str) -> List[Dict]:
    """取得收到的待處理好友請求"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT u.user_id, u.username, u.pi_username, u.membership_tier,
                   f.id as request_id, f.created_at
            FROM friendships f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.friend_id = ? AND f.status = 'pending'
            ORDER BY f.created_at DESC
        ''', (user_id,))

        rows = c.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "pi_username": r[2],
                "membership_tier": r[3] or 'free',
                "request_id": r[4],
                "requested_at": r[5]
            } for r in rows
        ]
    finally:
        conn.close()


def get_pending_requests_sent(user_id: str) -> List[Dict]:
    """取得已發送的待處理好友請求"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT u.user_id, u.username, u.pi_username, u.membership_tier,
                   f.id as request_id, f.created_at
            FROM friendships f
            JOIN users u ON f.friend_id = u.user_id
            WHERE f.user_id = ? AND f.status = 'pending'
            ORDER BY f.created_at DESC
        ''', (user_id,))

        rows = c.fetchall()
        return [
            {
                "user_id": r[0],
                "username": r[1],
                "pi_username": r[2],
                "membership_tier": r[3] or 'free',
                "request_id": r[4],
                "sent_at": r[5]
            } for r in rows
        ]
    finally:
        conn.close()


def get_friendship_status(user_id: str, other_user_id: str) -> Optional[Dict]:
    """取得兩個用戶之間的好友狀態"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT id, user_id, friend_id, status, created_at, updated_at
            FROM friendships
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (user_id, other_user_id, other_user_id, user_id))

        row = c.fetchone()
        if row:
            return {
                "id": row[0],
                "requester_id": row[1],
                "target_id": row[2],
                "status": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "is_requester": row[1] == user_id
            }
        return None
    finally:
        conn.close()


def get_friends_count(user_id: str) -> int:
    """取得好友數量"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT COUNT(*) FROM friendships
            WHERE (user_id = ? OR friend_id = ?) AND status = 'accepted'
        ''', (user_id, user_id))
        return c.fetchone()[0]
    finally:
        conn.close()


def get_pending_count(user_id: str) -> int:
    """取得收到的待處理好友請求數量"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT COUNT(*) FROM friendships
            WHERE friend_id = ? AND status = 'pending'
        ''', (user_id,))
        return c.fetchone()[0]
    finally:
        conn.close()


def is_blocked(user_id: str, other_user_id: str) -> bool:
    """檢查是否有任一方封鎖對方"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT 1 FROM friendships
            WHERE ((user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?))
            AND status = 'blocked'
        ''', (user_id, other_user_id, other_user_id, user_id))
        return c.fetchone() is not None
    finally:
        conn.close()


def is_friend(user_id: str, other_user_id: str) -> bool:
    """檢查兩個用戶是否為好友"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT 1 FROM friendships
            WHERE ((user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?))
            AND status = 'accepted'
        ''', (user_id, other_user_id, other_user_id, user_id))
        return c.fetchone() is not None
    finally:
        conn.close()
