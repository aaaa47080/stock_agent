"""
論壇功能相關資料庫操作
包含：看板、文章、回覆、打賞、標籤

Refactored to use DatabaseBase for unified CRUD operations.
"""
import json
from typing import List, Dict, Optional
from datetime import datetime

from .base import DatabaseBase
from .connection import get_connection
from .user import get_user_membership
from .system_config import get_limits


# ============================================================================
# 看板 (Boards)
# ============================================================================

def get_boards(active_only: bool = True) -> List[Dict]:
    """獲取看板列表"""
    if active_only:
        results = DatabaseBase.query_all(
            'SELECT id, name, slug, description, post_count, is_active FROM boards WHERE is_active = 1'
        )
    else:
        results = DatabaseBase.query_all(
            'SELECT id, name, slug, description, post_count, is_active FROM boards'
        )
    # Convert is_active to bool for consistency
    return [{**r, "is_active": bool(r["is_active"])} for r in results]


def get_board_by_slug(slug: str) -> Optional[Dict]:
    """根據 slug 獲取看板詳情"""
    result = DatabaseBase.query_one(
        'SELECT id, name, slug, description, post_count, is_active FROM boards WHERE slug = %s',
        (slug,)
    )
    if result:
        result["is_active"] = bool(result["is_active"])
    return result


# ============================================================================
# 文章 (Posts)
# ============================================================================

def check_daily_post_limit(user_id: str) -> Dict:
    """
    檢查用戶是否達到每日發文上限
    返回: {"allowed": bool, "count": int, "limit": int|None, "remaining": int|None}
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        membership = get_user_membership(user_id)
        is_premium = membership['is_pro']

        # 獲取對應的限制（從數據庫動態讀取）
        limits = get_limits()
        limit = limits["daily_post_premium"] if is_premium else limits["daily_post_free"]

        # 如果無限制，直接返回允許
        if limit is None:
            return {"allowed": True, "count": 0, "limit": None, "remaining": None}

        # 查詢今日發文數
        today = datetime.utcnow().strftime('%Y-%m-%d')
        c.execute('''
            SELECT post_count FROM user_daily_posts
            WHERE user_id = %s AND date = %s
        ''', (user_id, today))
        row = c.fetchone()
        current_count = row[0] if row else 0

        return {
            "allowed": current_count < limit,
            "count": current_count,
            "limit": limit,
            "remaining": max(0, limit - current_count)
        }
    finally:
        conn.close()


def create_post(board_id: int, user_id: str, category: str, title: str, content: str,
                tags: List[str] = None, payment_tx_hash: str = None,
                skip_limit_check: bool = False) -> Dict:
    """
    創建新文章
    返回: {"success": bool, "post_id": int} 或 {"success": False, "error": str, ...}

    skip_limit_check: 跳過限制檢查（用於 PRO 會員等特殊情況）
    """
    # 內容長度限制
    MAX_TITLE_LENGTH = 200
    MAX_CONTENT_LENGTH = 10000
    # 標籤數量上限
    MAX_TAGS_PER_POST = 5

    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查標題長度
        if not title or len(title.strip()) == 0:
            return {"success": False, "error": "title_required"}
        if len(title) > MAX_TITLE_LENGTH:
            return {
                "success": False,
                "error": "title_too_long",
                "max_length": MAX_TITLE_LENGTH,
                "current_length": len(title)
            }

        # 檢查內容長度
        if not content or len(content.strip()) == 0:
            return {"success": False, "error": "content_required"}
        if len(content) > MAX_CONTENT_LENGTH:
            return {
                "success": False,
                "error": "content_too_long",
                "max_length": MAX_CONTENT_LENGTH,
                "current_length": len(content)
            }

        # 檢查標籤數量
        if tags and len(tags) > MAX_TAGS_PER_POST:
            return {
                "success": False,
                "error": "too_many_tags",
                "max_tags": MAX_TAGS_PER_POST,
                "provided": len(tags)
            }

        # 檢查每日發文限制（免費會員）
        if not skip_limit_check:
            limit_check = check_daily_post_limit(user_id)
            if not limit_check["allowed"]:
                return {
                    "success": False,
                    "error": "daily_post_limit_reached",
                    "limit": limit_check["limit"],
                    "count": limit_check["count"]
                }

        # ===== 以下所有操作在單一事務中 =====

        # 1. 創建文章
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        c.execute('''
            INSERT INTO posts (board_id, user_id, category, title, content, tags, payment_tx_hash, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        ''', (board_id, user_id, category, title, content, tags_json, payment_tx_hash))

        post_id = c.fetchone()[0]

        # 2. 更新看板文章數
        c.execute('UPDATE boards SET post_count = post_count + 1 WHERE id = %s', (board_id,))

        # 3. 處理標籤
        if tags:
            for tag_name in tags:
                tag_name = tag_name.strip().upper()
                if not tag_name:
                    continue
                # 創建或更新標籤
                c.execute('''
                    INSERT INTO tags (name, post_count, last_used_at, created_at)
                    VALUES (%s, 1, NOW(), NOW())
                    ON CONFLICT(name) DO UPDATE SET
                        post_count = tags.post_count + 1,
                        last_used_at = NOW()
                ''', (tag_name,))
                # 獲取標籤 ID
                c.execute('SELECT id FROM tags WHERE name = %s', (tag_name,))
                tag_id = c.fetchone()[0]
                # 建立關聯
                c.execute('INSERT INTO post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (post_id, tag_id))

        # 4. 更新每日發文計數（關鍵：必須在同一事務中）
        today = datetime.utcnow().strftime('%Y-%m-%d')
        c.execute('''
            INSERT INTO user_daily_posts (user_id, date, post_count)
            VALUES (%s, %s, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET post_count = user_daily_posts.post_count + 1
        ''', (user_id, today))

        # 全部成功才提交
        conn.commit()
        return {"success": True, "post_id": post_id}
    except Exception as e:
        print(f"Create post error: {e}")
        conn.rollback()  # 全部回滾，確保數據一致性
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_posts(board_id: int = None, category: str = None, tag: str = None,
              limit: int = 20, offset: int = 0, include_hidden: bool = False) -> List[Dict]:
    """獲取文章列表"""
    conn = get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT p.id, p.board_id, p.user_id, p.category, p.title,
                   p.push_count, p.boo_count, p.comment_count, p.tips_total, p.view_count,
                   p.is_pinned, p.is_hidden, p.created_at,
                   u.username, b.name as board_name, b.slug as board_slug
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.user_id
            LEFT JOIN boards b ON p.board_id = b.id
            WHERE 1=1
        '''
        params = []

        if board_id:
            query += ' AND p.board_id = %s'
            params.append(board_id)

        if category:
            query += ' AND p.category = %s'
            params.append(category)

        if not include_hidden:
            query += ' AND p.is_hidden = 0'

        if tag:
            query += '''
                AND p.id IN (
                    SELECT pt.post_id FROM post_tags pt
                    JOIN tags t ON pt.tag_id = t.id
                    WHERE t.name = %s
                )
            '''
            params.append(tag.upper())

        query += ' ORDER BY p.is_pinned DESC, p.created_at DESC LIMIT %s OFFSET %s'
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[12]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "id": r[0],
                "board_id": r[1],
                "user_id": r[2],
                "category": r[3],
                "title": r[4],
                "push_count": r[5],
                "boo_count": r[6],
                "comment_count": r[7],
                "tips_total": r[8],
                "view_count": r[9],
                "is_pinned": bool(r[10]),
                "is_hidden": bool(r[11]),
                "created_at": created_at,
                "username": r[13],
                "board_name": r[14],
                "board_slug": r[15],
                "net_votes": r[5] - r[6]
            })
        return result
    finally:
        conn.close()


def get_post_by_id(post_id: int, increment_view: bool = True, viewer_user_id: str = None) -> Optional[Dict]:
    """獲取文章詳情"""
    conn = get_connection()
    c = conn.cursor()
    try:
        if increment_view:
            c.execute('UPDATE posts SET view_count = view_count + 1 WHERE id = %s', (post_id,))
            conn.commit()

        c.execute('''
            SELECT p.id, p.board_id, p.user_id, p.category, p.title, p.content, p.tags,
                   p.push_count, p.boo_count, p.comment_count, p.tips_total, p.view_count,
                   p.payment_tx_hash, p.is_pinned, p.is_hidden, p.created_at, p.updated_at,
                   u.username, b.name as board_name, b.slug as board_slug
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.user_id
            LEFT JOIN boards b ON p.board_id = b.id
            WHERE p.id = %s
        ''', (post_id,))
        row = c.fetchone()

        if row:
            tags = json.loads(row[6]) if row[6] else []
            created_at = row[15]
            updated_at = row[16]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            if updated_at and not isinstance(updated_at, str):
                updated_at = updated_at.strftime('%Y-%m-%d %H:%M:%S')

            post_data = {
                "id": row[0],
                "board_id": row[1],
                "user_id": row[2],
                "category": row[3],
                "title": row[4],
                "content": row[5],
                "tags": tags,
                "push_count": row[7],
                "boo_count": row[8],
                "comment_count": row[9],
                "tips_total": row[10],
                "view_count": row[11],
                "payment_tx_hash": row[12],
                "is_pinned": bool(row[13]),
                "is_hidden": bool(row[14]),
                "created_at": created_at,
                "updated_at": updated_at,
                "username": row[17],
                "board_name": row[18],
                "board_slug": row[19],
                "net_votes": row[7] - row[8],
                "viewer_vote": None
            }

            # 如果有提供 viewer_user_id，檢查投票狀態
            if viewer_user_id:
                c.execute('''
                    SELECT type FROM forum_comments
                    WHERE post_id = %s AND user_id = %s AND type IN ('push', 'boo')
                    LIMIT 1
                ''', (post_id, viewer_user_id))
                vote_row = c.fetchone()
                if vote_row:
                    post_data["viewer_vote"] = vote_row[0]

            return post_data
        return None
    finally:
        conn.close()


def update_post(post_id: int, user_id: str, title: str = None, content: str = None,
                category: str = None) -> bool:
    """更新文章（只有作者可以更新）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id FROM posts WHERE id = %s', (post_id,))
        row = c.fetchone()
        if not row or row[0] != user_id:
            return False

        updates = []
        params = []

        if title is not None:
            updates.append('title = %s')
            params.append(title)
        if content is not None:
            updates.append('content = %s')
            params.append(content)
        if category is not None:
            updates.append('category = %s')
            params.append(category)

        if updates:
            updates.append('updated_at = NOW()')
            params.append(post_id)
            c.execute(f'UPDATE posts SET {", ".join(updates)} WHERE id = %s', params)
            conn.commit()
            return c.rowcount > 0
        return False
    finally:
        conn.close()


def delete_post(post_id: int, user_id: str) -> bool:
    """刪除文章（軟刪除，設為隱藏）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 執行軟刪除
        c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s', (post_id, user_id))
        success = c.rowcount > 0

        # 如果刪除成功，更新標籤統計與記錄審計日誌
        if success:
            # 1. 更新標籤統計 (Decrement tag counts)
            try:
                # 獲取該文章的標籤
                c.execute('SELECT tag_id FROM post_tags WHERE post_id = %s', (post_id,))
                tag_rows = c.fetchall()
                if tag_rows:
                    for (tag_id,) in tag_rows:
                        # 減少標籤的使用計數
                        c.execute('UPDATE tags SET post_count = GREATEST(0, post_count - 1) WHERE id = %s', (tag_id,))
            except Exception as e:
                print(f"⚠️ 更新標籤統計失敗: {e}")
                # 不影響刪除主流程

            # 2. 記錄審計日誌
            try:
                c.execute('''
                    INSERT INTO audit_logs (
                        user_id, action, resource_type, resource_id,
                        endpoint, method, success
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (user_id, 'DELETE_POST', 'post', str(post_id), '/api/forum/posts/{id}', 'DELETE', True))
            except Exception as e:
                # 審計日誌失敗不應該影響主操作
                print(f"⚠️ 審計日誌記錄失敗: {e}")

        conn.commit()
        return success
    except Exception as e:
        conn.rollback()
        # 記錄失敗的審計日誌
        try:
            c.execute('''
                INSERT INTO audit_logs (
                    user_id, action, resource_type, resource_id,
                    endpoint, method, success, error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (user_id, 'DELETE_POST', 'post', str(post_id), '/api/forum/posts/{id}', 'DELETE', False, str(e)))
            conn.commit()
        except:
            pass
        raise
    finally:
        conn.close()


def get_user_posts(user_id: str, limit: int = 20, offset: int = 0) -> List[Dict]:
    """獲取用戶的文章列表"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT p.id, p.board_id, p.category, p.title,
                   p.push_count, p.boo_count, p.comment_count, p.tips_total, p.view_count,
                   p.is_pinned, p.is_hidden, p.created_at,
                   b.name as board_name, b.slug as board_slug
            FROM posts p
            LEFT JOIN boards b ON p.board_id = b.id
            WHERE p.user_id = %s AND p.is_hidden = 0
            ORDER BY p.created_at DESC
            LIMIT %s OFFSET %s
        ''', (user_id, limit, offset))
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[11]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "id": r[0],
                "board_id": r[1],
                "category": r[2],
                "title": r[3],
                "push_count": r[4],
                "boo_count": r[5],
                "comment_count": r[6],
                "tips_total": r[7],
                "view_count": r[8],
                "is_pinned": bool(r[9]),
                "is_hidden": bool(r[10]),
                "created_at": created_at,
                "board_name": r[12],
                "board_slug": r[13],
                "net_votes": r[4] - r[5]
            })
        return result
    finally:
        conn.close()


# ============================================================================
# 回覆 (Comments)
# ============================================================================

def add_comment(post_id: int, user_id: str, comment_type: str, content: str = None,
                parent_id: int = None) -> Dict:
    """
    新增回覆
    comment_type: 'push' / 'boo' / 'comment'
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查每日回覆限制（免費會員）- 僅針對實際留言，推噓不計入
        if comment_type == 'comment':
            membership = get_user_membership(user_id)
            limits = get_limits()
            limit = limits["daily_comment_premium"] if membership['is_pro'] else limits["daily_comment_free"]

            # 如果有限制，檢查是否超過
            if limit is not None:
                today = datetime.utcnow().strftime('%Y-%m-%d')
                c.execute('''
                    SELECT comment_count FROM user_daily_comments
                    WHERE user_id = %s AND date = %s
                ''', (user_id, today))
                row = c.fetchone()
                current_count = row[0] if row else 0

                if current_count >= limit:
                    return {"success": False, "error": "daily_limit_reached", "limit": limit}

        # 檢查是否重複推噓 (同一篇文章只能推/噓一次) - 實作 Toggle 邏輯
        if comment_type in ['push', 'boo']:
            c.execute('''
                SELECT id, type FROM forum_comments
                WHERE post_id = %s AND user_id = %s AND type IN ('push', 'boo')
            ''', (post_id, user_id))
            existing_vote = c.fetchone()

            if existing_vote:
                vote_id, v_type = existing_vote

                # 如果點擊的是同一種類型 -> 取消 (Toggle Off)
                if v_type == comment_type:
                    c.execute('DELETE FROM forum_comments WHERE id = %s', (vote_id,))
                    # push/boo 不影響 comment_count，只更新各自的計數
                    if v_type == 'push':
                        c.execute('UPDATE posts SET push_count = GREATEST(0, push_count - 1) WHERE id = %s', (post_id,))
                    else:
                        c.execute('UPDATE posts SET boo_count = GREATEST(0, boo_count - 1) WHERE id = %s', (post_id,))
                    conn.commit()
                    return {"success": True, "action": "cancelled"}

                # 如果點擊的是不同類型 -> 切換 (Switch)
                else:
                    # 先刪除舊的
                    c.execute('DELETE FROM forum_comments WHERE id = %s', (vote_id,))
                    # push/boo 不影響 comment_count，只更新各自的計數
                    if v_type == 'push':
                        c.execute('UPDATE posts SET push_count = GREATEST(0, push_count - 1) WHERE id = %s', (post_id,))
                    else:
                        c.execute('UPDATE posts SET boo_count = GREATEST(0, boo_count - 1) WHERE id = %s', (post_id,))
                    # 接下來會繼續執行下面的 INSERT

        # 新增回覆
        c.execute('''
            INSERT INTO forum_comments (post_id, user_id, parent_id, type, content, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        ''', (post_id, user_id, parent_id, comment_type, content))

        comment_id = c.fetchone()[0]

        # 更新文章統計
        # 注意：comment_count 只統計真正的留言，push/boo 只更新各自的計數
        if comment_type == 'push':
            c.execute('UPDATE posts SET push_count = push_count + 1 WHERE id = %s', (post_id,))
        elif comment_type == 'boo':
            c.execute('UPDATE posts SET boo_count = boo_count + 1 WHERE id = %s', (post_id,))
        else:
            c.execute('UPDATE posts SET comment_count = comment_count + 1 WHERE id = %s', (post_id,))

        # 更新每日回覆計數 (僅針對實際留言)
        if comment_type == 'comment':
            today = datetime.utcnow().strftime('%Y-%m-%d')
            c.execute('''
                INSERT INTO user_daily_comments (user_id, date, comment_count)
                VALUES (%s, %s, 1)
                ON CONFLICT(user_id, date) DO UPDATE SET comment_count = user_daily_comments.comment_count + 1
            ''', (user_id, today))

        conn.commit()
        return {"success": True, "comment_id": comment_id}
    except Exception as e:
        print(f"Add comment error: {e}")
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_comments(post_id: int, include_hidden: bool = False) -> List[Dict]:
    """獲取文章的回覆列表"""
    conn = get_connection()
    c = conn.cursor()
    try:
        query = '''
            SELECT c.id, c.post_id, c.user_id, c.parent_id, c.type, c.content,
                   c.is_hidden, c.created_at, u.username
            FROM forum_comments c
            LEFT JOIN users u ON c.user_id = u.user_id
            WHERE c.post_id = %s
        '''
        if not include_hidden:
            query += ' AND c.is_hidden = 0'
        query += ' ORDER BY c.created_at ASC'

        c.execute(query, (post_id,))
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[7]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "id": r[0],
                "post_id": r[1],
                "user_id": r[2],
                "parent_id": r[3],
                "type": r[4],
                "content": r[5],
                "is_hidden": bool(r[6]),
                "created_at": created_at,
                "username": r[8]
            })
        return result
    finally:
        conn.close()


def get_daily_comment_count(user_id: str) -> Dict:
    """獲取用戶今日回覆數"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    row = DatabaseBase.query_one(
        'SELECT comment_count FROM user_daily_comments WHERE user_id = %s AND date = %s',
        (user_id, today)
    )
    count = row['comment_count'] if row else 0

    membership = get_user_membership(user_id)
    limits = get_limits()
    limit = limits["daily_comment_premium"] if membership['is_pro'] else limits["daily_comment_free"]

    return {
        "count": count,
        "limit": limit,
        "remaining": None if limit is None else max(0, limit - count)
    }


def get_daily_post_count(user_id: str) -> Dict:
    """獲取用戶今日發文數"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    row = DatabaseBase.query_one(
        'SELECT post_count FROM user_daily_posts WHERE user_id = %s AND date = %s',
        (user_id, today)
    )
    count = row['post_count'] if row else 0

    membership = get_user_membership(user_id)
    limits = get_limits()
    limit = limits["daily_post_premium"] if membership['is_pro'] else limits["daily_post_free"]

    return {
        "count": count,
        "limit": limit,
        "remaining": None if limit is None else max(0, limit - count)
    }


# ============================================================================
# 打賞 (Tips)
# ============================================================================

def create_tip(post_id: int, from_user_id: str, to_user_id: str, amount: float, tx_hash: str) -> int:
    """創建打賞記錄"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO tips (post_id, from_user_id, to_user_id, amount, tx_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        ''', (post_id, from_user_id, to_user_id, amount, tx_hash))

        tip_id = c.fetchone()[0]

        # 更新文章累計打賞
        c.execute('UPDATE posts SET tips_total = tips_total + %s WHERE id = %s', (amount, post_id))

        conn.commit()
        return tip_id
    except Exception as e:
        print(f"Create tip error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_tips_sent(user_id: str, limit: int = 50) -> List[Dict]:
    """獲取用戶送出的打賞記錄"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT t.id, t.post_id, t.to_user_id, t.amount, t.tx_hash, t.created_at,
                   p.title, u.username as to_username
            FROM tips t
            LEFT JOIN posts p ON t.post_id = p.id
            LEFT JOIN users u ON t.to_user_id = u.user_id
            WHERE t.from_user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[5]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "id": r[0],
                "post_id": r[1],
                "to_user_id": r[2],
                "amount": r[3],
                "tx_hash": r[4],
                "created_at": created_at,
                "post_title": r[6],
                "to_username": r[7]
            })
        return result
    finally:
        conn.close()


def get_tips_received(user_id: str, limit: int = 50) -> List[Dict]:
    """獲取用戶收到的打賞記錄"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT t.id, t.post_id, t.from_user_id, t.amount, t.tx_hash, t.created_at,
                   p.title, u.username as from_username
            FROM tips t
            LEFT JOIN posts p ON t.post_id = p.id
            LEFT JOIN users u ON t.from_user_id = u.user_id
            WHERE t.to_user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        rows = c.fetchall()

        result = []
        for r in rows:
            created_at = r[5]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            result.append({
                "id": r[0],
                "post_id": r[1],
                "from_user_id": r[2],
                "amount": r[3],
                "tx_hash": r[4],
                "created_at": created_at,
                "post_title": r[6],
                "from_username": r[7]
            })
        return result
    finally:
        conn.close()


def get_tips_total_received(user_id: str) -> float:
    """獲取用戶累計收到的打賞總額"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT COALESCE(SUM(amount), 0) FROM tips WHERE to_user_id = %s', (user_id,))
        return c.fetchone()[0]
    finally:
        conn.close()


# ============================================================================
# 標籤 (Tags)
# ============================================================================

def get_trending_tags(limit: int = 10) -> List[Dict]:
    """獲取熱門標籤（按最近使用頻率）"""
    results = DatabaseBase.query_all('''
        SELECT id, name, post_count, last_used_at
        FROM tags
        WHERE last_used_at > NOW() - INTERVAL '7 days'
        ORDER BY post_count DESC
        LIMIT %s
    ''', (limit,))

    # Format datetime fields
    for r in results:
        last_used_at = r.get("last_used_at")
        if last_used_at and not isinstance(last_used_at, str):
            r["last_used_at"] = last_used_at.strftime('%Y-%m-%d %H:%M:%S')
    return results


def get_posts_by_tag(tag_name: str, limit: int = 20, offset: int = 0) -> List[Dict]:
    """根據標籤獲取文章列表"""
    return get_posts(tag=tag_name, limit=limit, offset=offset)


def search_tags(query: str, limit: int = 10) -> List[Dict]:
    """搜尋標籤"""
    return DatabaseBase.query_all('''
        SELECT id, name, post_count
        FROM tags
        WHERE name LIKE %s
        ORDER BY post_count DESC
        LIMIT %s
    ''', (f'%{query.upper()}%', limit))


# ============================================================================
# 用戶論壇統計
# ============================================================================

def get_user_forum_stats(user_id: str) -> Dict:
    """獲取用戶論壇統計資料"""
    with DatabaseBase() as db:
        # 文章數
        c = db.connection.cursor()
        c.execute('SELECT COUNT(*) FROM posts WHERE user_id = %s AND is_hidden = 0', (user_id,))
        post_count = c.fetchone()[0]

        # 回覆數
        c.execute('SELECT COUNT(*) FROM forum_comments WHERE user_id = %s AND is_hidden = 0', (user_id,))
        comment_count = c.fetchone()[0]

        # 獲得的推數
        c.execute('SELECT COALESCE(SUM(push_count), 0) FROM posts WHERE user_id = %s', (user_id,))
        total_pushes = c.fetchone()[0]

        # 收到的打賞總額
        tips_total = get_tips_total_received(user_id)

        return {
            "post_count": post_count,
            "comment_count": comment_count,
            "total_pushes": total_pushes,
            "tips_received": tips_total
        }


def get_user_payment_history(user_id: str, limit: int = 50) -> List[Dict]:
    """獲取用戶的所有付款記錄（包含發文費和會員費）"""
    # 使用 UNION（自動去重）合併發文紀錄和會員購買紀錄
    # 避免同一個 tx_hash 出現兩次
    query = '''
        SELECT type, id, title, amount, tx_hash, created_at FROM (
            -- 文章支付紀錄
            SELECT
                'post' as type,
                id,
                title,
                1.0 as amount,
                payment_tx_hash as tx_hash,
                created_at
            FROM posts
            WHERE user_id = %s AND payment_tx_hash IS NOT NULL AND payment_tx_hash != 'pro_member_free'

            UNION

            -- 會員購買紀錄
            SELECT
                'membership' as type,
                id,
                'Premium Membership (' || months || ' Month)' as title,
                amount,
                tx_hash,
                created_at
            FROM membership_payments
            WHERE user_id = %s
        ) AS combined
        ORDER BY created_at DESC
        LIMIT %s
    '''

    results = DatabaseBase.query_all(query, (user_id, user_id, limit))

    # Format datetime fields
    for r in results:
        created_at = r.get("created_at")
        if created_at and not isinstance(created_at, str):
            r["created_at"] = created_at.strftime('%Y-%m-%d %H:%M:%S')
        # Rename 'id' to 'ref_id' for clarity
        r["ref_id"] = r.pop("id")

    return results
