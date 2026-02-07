"""
可疑錢包追蹤系統 - 數據庫操作層
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from .connection import get_connection
from .system_config import get_config
from .user import get_user_membership
from core.validators import (
    validate_pi_address,
    validate_pi_tx_hash,
    mask_wallet_address,
    filter_sensitive_content,
    sanitize_description
)
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 舉報管理
# ============================================================================

def create_scam_report(
    scam_wallet_address: str,
    reporter_user_id: str,
    reporter_wallet_address: str,
    scam_type: str,
    description: str,
    transaction_hash: Optional[str] = None
) -> Dict:
    """
    創建詐騙舉報

    Args:
        scam_wallet_address: 可疑錢包地址
        reporter_user_id: 舉報者用戶 ID
        reporter_wallet_address: 舉報者錢包地址
        scam_type: 詐騙類型
        description: 詐騙描述
        transaction_hash: 交易哈希（可選）

    Returns:
        {"success": bool, "report_id": int} 或 {"success": False, "error": str}
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 1. 驗證 Pi 地址格式
        valid, error = validate_pi_address(scam_wallet_address)
        if not valid:
            return {"success": False, "error": "invalid_scam_wallet", "detail": error}

        valid, error = validate_pi_address(reporter_wallet_address)
        if not valid:
            return {"success": False, "error": "invalid_reporter_wallet", "detail": error}

        # 2. 驗證交易哈希（如果提供）
        if transaction_hash:
            valid, error = validate_pi_tx_hash(transaction_hash)
            if not valid:
                return {"success": False, "error": "invalid_tx_hash", "detail": error}

        # 3. 檢查 PRO 權限
        membership = get_user_membership(reporter_user_id)
        if not membership['is_pro']:
            return {"success": False, "error": "pro_membership_required"}

        # 4. 檢查每日限額
        daily_limit = get_config('scam_report_daily_limit_pro', 5)
        today = datetime.utcnow().strftime('%Y-%m-%d')

        c.execute('''
            SELECT COUNT(*) FROM scam_reports
            WHERE reporter_user_id = %s
            AND DATE(created_at) = %s
        ''', (reporter_user_id, today))

        today_count = c.fetchone()[0]
        if today_count >= daily_limit:
            return {
                "success": False,
                "error": "daily_limit_reached",
                "limit": daily_limit,
                "used": today_count
            }

        # 5. 檢查地址是否已被舉報（去重）
        scam_wallet_upper = scam_wallet_address.upper()
        c.execute('''
            SELECT id FROM scam_reports
            WHERE scam_wallet_address = %s
        ''', (scam_wallet_upper,))

        existing = c.fetchone()
        if existing:
            return {
                "success": False,
                "error": "already_reported",
                "existing_report_id": existing[0]
            }

        # 6. 內容審核
        description_clean = sanitize_description(description)
        content_check = filter_sensitive_content(description_clean)
        if not content_check["valid"]:
            return {
                "success": False,
                "error": "content_validation_failed",
                "warnings": content_check["warnings"]
            }

        # 7. 生成遮罩錢包地址
        mask_length = get_config('scam_wallet_mask_length', 4)
        reporter_wallet_masked = mask_wallet_address(
            reporter_wallet_address, mask_length
        )

        # 8. 創建舉報
        c.execute('''
            INSERT INTO scam_reports (
                scam_wallet_address, blockchain_type,
                reporter_user_id, reporter_wallet_address, reporter_wallet_masked,
                scam_type, description, transaction_hash,
                verification_status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        ''', (
            scam_wallet_upper, 'pi_network',
            reporter_user_id, reporter_wallet_address.upper(), reporter_wallet_masked,
            scam_type, description_clean, transaction_hash,
            'pending'
        ))

        report_id = c.fetchone()[0]

        # 9. 記錄審計日誌
        try:
            c.execute('''
                INSERT INTO audit_logs (
                    user_id, action, resource_type, resource_id,
                    endpoint, method, success
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                reporter_user_id, 'CREATE_SCAM_REPORT', 'scam_report',
                str(report_id), '/api/scam-tracker/reports', 'POST', True
            ))
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        conn.commit()
        logger.info(f"Scam report created: {report_id} by {reporter_user_id}")
        return {"success": True, "report_id": report_id}

    except Exception as e:
        conn.rollback()
        logger.error(f"Create scam report failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_scam_reports(
    scam_type: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "latest",
    limit: int = 20,
    offset: int = 0
) -> List[Dict]:
    """
    獲取舉報列表

    Args:
        scam_type: 詐騙類型篩選
        status: 驗證狀態篩選 (pending/verified/disputed)
        sort_by: 排序方式 (latest/most_voted/most_viewed)
        limit: 每頁數量
        offset: 偏移量

    Returns:
        舉報列表
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        query = '''
            SELECT
                sr.id, sr.scam_wallet_address, sr.scam_type,
                sr.description, sr.verification_status,
                sr.approve_count, sr.reject_count,
                sr.comment_count, sr.view_count,
                sr.reporter_wallet_masked, sr.created_at,
                u.username
            FROM scam_reports sr
            LEFT JOIN users u ON sr.reporter_user_id = u.user_id
            WHERE 1=1
        '''
        params = []

        if scam_type:
            query += ' AND sr.scam_type = %s'
            params.append(scam_type)

        if status:
            query += ' AND sr.verification_status = %s'
            params.append(status)

        # 排序
        if sort_by == "most_voted":
            query += ' ORDER BY (sr.approve_count - sr.reject_count) DESC, sr.created_at DESC'
        elif sort_by == "most_viewed":
            query += ' ORDER BY sr.view_count DESC, sr.created_at DESC'
        else:  # latest
            query += ' ORDER BY sr.created_at DESC'

        query += ' LIMIT %s OFFSET %s'
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        results = []
        for r in rows:
            created_at = r[10]
            if created_at and not isinstance(created_at, str):
                created_at = created_at.isoformat()

            # 截斷描述
            desc = r[3]
            if len(desc) > 200:
                desc = desc[:200] + "..."

            results.append({
                "id": r[0],
                "scam_wallet_address": r[1],
                "scam_type": r[2],
                "description": desc,
                "verification_status": r[4],
                "approve_count": r[5],
                "reject_count": r[6],
                "comment_count": r[7],
                "view_count": r[8],
                "reporter_wallet_masked": r[9],
                "created_at": created_at,
                "reporter_username": r[11],
                "net_votes": r[5] - r[6]
            })

        return results

    finally:
        conn.close()


def get_scam_report_by_id(
    report_id: int,
    increment_view: bool = True,
    viewer_user_id: Optional[str] = None
) -> Optional[Dict]:
    """
    獲取舉報詳情

    Args:
        report_id: 舉報 ID
        increment_view: 是否增加瀏覽數
        viewer_user_id: 查看者用戶 ID（用於查詢投票狀態）

    Returns:
        舉報詳情或 None
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 增加瀏覽數
        if increment_view:
            c.execute('''
                UPDATE scam_reports
                SET view_count = view_count + 1,
                    updated_at = NOW()
                WHERE id = %s
            ''', (report_id,))
            conn.commit()

        # 獲取詳情
        c.execute('''
            SELECT
                sr.id, sr.scam_wallet_address, sr.scam_type,
                sr.description, sr.transaction_hash,
                sr.verification_status,
                sr.approve_count, sr.reject_count,
                sr.comment_count, sr.view_count,
                sr.reporter_wallet_masked, sr.created_at, sr.updated_at,
                u.username
            FROM scam_reports sr
            LEFT JOIN users u ON sr.reporter_user_id = u.user_id
            WHERE sr.id = %s
        ''', (report_id,))

        row = c.fetchone()
        if not row:
            return None

        created_at = row[11].isoformat() if row[11] else None
        updated_at = row[12].isoformat() if row[12] else None

        report = {
            "id": row[0],
            "scam_wallet_address": row[1],
            "scam_type": row[2],
            "description": row[3],
            "transaction_hash": row[4],
            "verification_status": row[5],
            "approve_count": row[6],
            "reject_count": row[7],
            "comment_count": row[8],
            "view_count": row[9],
            "reporter_wallet_masked": row[10],
            "created_at": created_at,
            "updated_at": updated_at,
            "reporter_username": row[13],
            "net_votes": row[6] - row[7],
            "viewer_vote": None
        }

        # 查詢用戶投票狀態
        if viewer_user_id:
            c.execute('''
                SELECT vote_type FROM scam_report_votes
                WHERE report_id = %s AND user_id = %s
            ''', (report_id, viewer_user_id))
            vote_row = c.fetchone()
            if vote_row:
                report["viewer_vote"] = vote_row[0]

        return report

    finally:
        conn.close()


def search_wallet(wallet_address: str) -> Optional[Dict]:
    """
    搜尋指定錢包是否被舉報

    Args:
        wallet_address: 錢包地址

    Returns:
        舉報資訊或 None
    """
    # 驗證地址格式
    valid, _ = validate_pi_address(wallet_address)
    if not valid:
        return None

    conn = get_connection()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT id FROM scam_reports
            WHERE scam_wallet_address = %s
        ''', (wallet_address.upper(),))

        row = c.fetchone()
        if row:
            # 返回完整詳情
            return get_scam_report_by_id(row[0], increment_view=False)

        return None

    finally:
        conn.close()


# ============================================================================
# 投票管理
# ============================================================================

def vote_scam_report(
    report_id: int,
    user_id: str,
    vote_type: str
) -> Dict:
    """
    對舉報投票（支持 Toggle 切換）

    Args:
        report_id: 舉報 ID
        user_id: 用戶 ID
        vote_type: 投票類型 ('approve' or 'reject')

    Returns:
        {"success": bool, "action": str}
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 檢查舉報是否存在
        c.execute('SELECT reporter_user_id FROM scam_reports WHERE id = %s', (report_id,))
        report_row = c.fetchone()

        if not report_row:
            return {"success": False, "error": "report_not_found"}

        # 檢查是否為舉報者本人
        if report_row[0] == user_id:
            return {"success": False, "error": "cannot_vote_own_report"}

        # 防刷票：檢查 1 分鐘內投票次數
        c.execute('''
            SELECT COUNT(*) FROM scam_report_votes
            WHERE user_id = %s
            AND created_at > NOW() - INTERVAL '1 minute'
        ''', (user_id,))

        recent_votes = c.fetchone()[0]
        if recent_votes >= 5:
            return {"success": False, "error": "vote_too_fast"}

        # 檢查是否已投票
        c.execute('''
            SELECT vote_type FROM scam_report_votes
            WHERE report_id = %s AND user_id = %s
        ''', (report_id, user_id))

        existing = c.fetchone()

        if existing:
            old_vote = existing[0]

            # Toggle: 點擊同類型 = 取消投票
            if old_vote == vote_type:
                c.execute('''
                    DELETE FROM scam_report_votes
                    WHERE report_id = %s AND user_id = %s
                ''', (report_id, user_id))

                # 更新計數
                if vote_type == 'approve':
                    c.execute('''
                        UPDATE scam_reports
                        SET approve_count = GREATEST(0, approve_count - 1),
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (report_id,))
                else:
                    c.execute('''
                        UPDATE scam_reports
                        SET reject_count = GREATEST(0, reject_count - 1),
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (report_id,))

                action = "cancelled"

            # Switch: 切換投票類型
            else:
                c.execute('''
                    UPDATE scam_report_votes
                    SET vote_type = %s, created_at = NOW()
                    WHERE report_id = %s AND user_id = %s
                ''', (vote_type, report_id, user_id))

                # 更新計數（-1 舊的，+1 新的）
                if old_vote == 'approve':
                    c.execute('''
                        UPDATE scam_reports
                        SET approve_count = GREATEST(0, approve_count - 1),
                            reject_count = reject_count + 1,
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (report_id,))
                else:
                    c.execute('''
                        UPDATE scam_reports
                        SET approve_count = approve_count + 1,
                            reject_count = GREATEST(0, reject_count - 1),
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (report_id,))

                action = "switched"

        else:
            # 新投票
            c.execute('''
                INSERT INTO scam_report_votes (report_id, user_id, vote_type)
                VALUES (%s, %s, %s)
            ''', (report_id, user_id, vote_type))

            if vote_type == 'approve':
                c.execute('''
                    UPDATE scam_reports
                    SET approve_count = approve_count + 1,
                        updated_at = NOW()
                    WHERE id = %s
                ''', (report_id,))
            else:
                c.execute('''
                    UPDATE scam_reports
                    SET reject_count = reject_count + 1,
                        updated_at = NOW()
                    WHERE id = %s
                ''', (report_id,))

            action = "voted"

        # 更新驗證狀態
        _update_verification_status(c, report_id)

        conn.commit()
        return {"success": True, "action": action}

    except Exception as e:
        conn.rollback()
        logger.error(f"Vote failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def _update_verification_status(cursor, report_id: int):
    """
    根據投票自動更新驗證狀態

    Args:
        cursor: 數據庫游標
        report_id: 舉報 ID
    """
    cursor.execute('''
        SELECT approve_count, reject_count
        FROM scam_reports WHERE id = %s
    ''', (report_id,))

    row = cursor.fetchone()
    if not row:
        return

    approve, reject = row
    total = approve + reject

    min_votes = get_config('scam_verification_vote_threshold', 10)
    approve_rate_threshold = get_config('scam_verification_approve_rate', 0.7)

    if total >= min_votes:
        approve_rate = approve / total if total > 0 else 0

        if approve_rate >= approve_rate_threshold:
            new_status = 'verified'
        elif approve_rate < 0.3:  # 反對率 > 70%
            new_status = 'disputed'
        else:
            new_status = 'pending'
    else:
        new_status = 'pending'

    cursor.execute('''
        UPDATE scam_reports
        SET verification_status = %s,
            updated_at = NOW()
        WHERE id = %s
    ''', (new_status, report_id))


# ============================================================================
# 評論管理
# ============================================================================

def add_scam_comment(
    report_id: int,
    user_id: str,
    content: str,
    transaction_hash: Optional[str] = None
) -> Dict:
    """
    添加評論（僅 PRO 用戶）

    Args:
        report_id: 舉報 ID
        user_id: 用戶 ID
        content: 評論內容
        transaction_hash: 交易哈希（可選）

    Returns:
        {"success": bool, "comment_id": int}
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 檢查 PRO 權限
        require_pro = get_config('scam_comment_require_pro', True)
        if require_pro:
            membership = get_user_membership(user_id)
            if not membership['is_pro']:
                return {"success": False, "error": "pro_membership_required"}

        # 檢查舉報是否存在
        c.execute('SELECT id FROM scam_reports WHERE id = %s', (report_id,))
        if not c.fetchone():
            return {"success": False, "error": "report_not_found"}

        # 驗證交易哈希（如果提供）
        if transaction_hash:
            valid, error = validate_pi_tx_hash(transaction_hash)
            if not valid:
                return {"success": False, "error": "invalid_tx_hash", "detail": error}

        # 內容審核
        content_clean = sanitize_description(content)
        content_check = filter_sensitive_content(content_clean)
        if not content_check["valid"]:
            return {
                "success": False,
                "error": "content_validation_failed",
                "warnings": content_check["warnings"]
            }

        # 創建評論
        c.execute('''
            INSERT INTO scam_report_comments (
                report_id, user_id, content, transaction_hash
            ) VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (report_id, user_id, content_clean, transaction_hash))

        comment_id = c.fetchone()[0]

        # 更新評論計數
        c.execute('''
            UPDATE scam_reports
            SET comment_count = comment_count + 1,
                updated_at = NOW()
            WHERE id = %s
        ''', (report_id,))

        conn.commit()
        logger.info(f"Comment {comment_id} added to report {report_id} by {user_id}")
        return {"success": True, "comment_id": comment_id}

    except Exception as e:
        conn.rollback()
        logger.error(f"Add comment failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_scam_comments(
    report_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    獲取評論列表

    Args:
        report_id: 舉報 ID
        limit: 每頁數量
        offset: 偏移量

    Returns:
        評論列表
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT
                c.id, c.content, c.transaction_hash,
                c.created_at, u.username
            FROM scam_report_comments c
            LEFT JOIN users u ON c.user_id = u.user_id
            WHERE c.report_id = %s AND c.is_hidden = 0
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        ''', (report_id, limit, offset))

        rows = c.fetchall()
        results = []

        for r in rows:
            created_at = r[3].isoformat() if r[3] else None
            results.append({
                "id": r[0],
                "content": r[1],
                "transaction_hash": r[2],
                "created_at": created_at,
                "username": r[4]
            })

        return results

    finally:
        conn.close()
