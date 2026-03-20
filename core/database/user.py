"""
用戶認證相關資料庫操作
包含：用戶管理、Pi Network、會員等級
"""
import uuid
import logging
from typing import Dict, Optional
from datetime import datetime

from .connection import get_connection

logger = logging.getLogger(__name__)


def _normalize_membership_tier(tier: Optional[str]) -> str:
    return "premium" if (tier or "free").strip().lower() in {"premium", "plus", "pro"} else "free"


# ============================================================================
# 用戶 CRUD
# ============================================================================

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """根據 ID 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT user_id, username, auth_method,
                   role, is_active, membership_tier, membership_expires_at, created_at
            FROM users WHERE user_id = %s
        ''', (user_id,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "role": row[3] or "user",
                "is_active": row[4] if row[4] is not None else True,
                "membership_tier": _normalize_membership_tier(row[5]),
                "membership_expires_at": row[6].isoformat() if row[6] else None,
                "created_at": row[7].isoformat() if row[7] else None
            }
        return None
    finally:
        conn.close()


def update_last_active(user_id: str) -> bool:
    """更新用戶最後活動時間"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE users SET last_active_at = NOW()
            WHERE user_id = %s
        ''', (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        logger.warning(f"Update last active error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# Pi Network 用戶
# ============================================================================

def create_or_get_pi_user(pi_uid: str, username: Optional[str] = None, wallet_address: Optional[str] = None) -> Dict:
    """
    創建或獲取 Pi Network 用戶
    - 如果 pi_uid 已存在，返回現有用戶
    - 如果 username 被其他用戶使用，自動加隨機後綴
    - 否則創建新用戶
    """
    if not username:
        username = f"pi_{pi_uid[:8]}"
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查 pi_uid 是否已存在
        c.execute('SELECT user_id, username, auth_method, pi_username, role, membership_tier FROM users WHERE pi_uid = %s', (pi_uid,))
        row = c.fetchone()
        if row:
            # 更新 pi_username 或 wallet_address（如有新值）
            updates = []
            params = []
            if not row[3] and username:
                updates.append('pi_username = %s')
                params.append(username)
            if updates:
                params.append(pi_uid)
                c.execute(f'UPDATE users SET {", ".join(updates)} WHERE pi_uid = %s', params)
                conn.commit()
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "role": row[4] or "user",
                "membership_tier": _normalize_membership_tier(row[5]),
                "is_new": False
            }

        # 檢查 username 是否被其他用戶使用
        c.execute('SELECT user_id, auth_method FROM users WHERE username = %s', (username,))
        existing = c.fetchone()
        if existing:
            original_username = username
            suffix = str(uuid.uuid4()).replace('-', '')[:8]
            username = f"{original_username}_{suffix}"

            c.execute('SELECT 1 FROM users WHERE username = %s', (username,))
            if c.fetchone():
                username = f"{original_username}_{str(uuid.uuid4())}"

        # 創建新 Pi 用戶
        user_id = pi_uid
        c.execute('''
            INSERT INTO users (user_id, username, auth_method, pi_uid, pi_username, created_at)
            VALUES (%s, %s, 'pi_network', %s, %s, NOW())
        ''', (user_id, username, pi_uid, username))
        conn.commit()

        return {
            "user_id": user_id,
            "username": username,
            "auth_method": "pi_network",
            "role": "user",
            "membership_tier": "free",
            "is_new": True
        }
    except ValueError:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_pi_uid(pi_uid: str) -> Optional[Dict]:
    """根據 Pi UID 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, auth_method, created_at FROM users WHERE pi_uid = %s', (pi_uid,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "created_at": row[3]
            }
        return None
    finally:
        conn.close()


def get_user_wallet_status(user_id: str) -> Dict:
    """獲取用戶錢包綁定狀態"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT auth_method, pi_uid, pi_username
            FROM users WHERE user_id = %s
        ''', (user_id,))
        row = c.fetchone()
        if not row:
            return {"has_wallet": False, "auth_method": None}

        return {
            "has_wallet": row[1] is not None,  # pi_uid 存在即視為已連接
            "auth_method": row[0],
            "pi_uid": row[1],
            "pi_username": row[2],
        }
    finally:
        conn.close()


# ============================================================================
# 會員等級
# ============================================================================

def get_user_membership(user_id: str) -> Dict:
    """
    獲取用戶會員狀態（只讀）。若需要降級過期會員，請呼叫 expire_user_membership()。

    Returns:
        {"tier": str, "expires_at": str | None, "is_premium": bool, "is_expired": bool}
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT membership_tier, membership_expires_at
            FROM users WHERE user_id = %s
        ''', (user_id,))
        row = c.fetchone()

        if row:
            raw_tier = row[0] or 'free'
            tier = _normalize_membership_tier(raw_tier)
            expires_at = row[1]
            is_premium = (tier == 'premium')
            is_expired = False

            # 檢查是否過期（只檢查，不自動更新）
            if is_premium and expires_at:
                try:
                    expire_dt = expires_at

                    if expire_dt < datetime.utcnow():
                        is_expired = True
                except (ValueError, TypeError):
                    # 日期格式錯誤，視為過期
                    is_expired = True

            # 轉換 expires_at 為字符串
            if expires_at:
                expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')

            is_premium = is_premium and not is_expired
            return {
                "tier": tier,
                "expires_at": expires_at,
                "is_premium": is_premium,
                "is_expired": is_expired
            }
        return {"tier": "free", "expires_at": None, "is_premium": False, "is_expired": False}
    finally:
        conn.close()


def expire_user_membership(user_id: str) -> bool:
    """
    手動將用戶會員狀態降級為免費（用於過期處理）
    這是一個獨立的寫入方法，與讀取分離
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE users
            SET membership_tier = 'free', membership_expires_at = NULL
            WHERE user_id = %s AND membership_tier IN ('pro', 'premium')
        ''', (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        logger.error(f"Expire membership error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def upgrade_to_pro(user_id: str, months: int = 1, tx_hash: Optional[str] = None) -> bool:
    """升級用戶為 Premium 會員並記錄支付（保留舊函式名相容，支援續費順延）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 0. 如果有交易哈希，檢查是否已被使用（防止重複提交）
        if tx_hash:
            c.execute('SELECT user_id FROM membership_payments WHERE tx_hash = %s', (tx_hash,))
            existing = c.fetchone()
            if existing:
                logger.warning(f"[Upgrade] Duplicate tx_hash detected: {tx_hash} already used by user {existing[0]}")
                raise ValueError("此交易已被處理（transaction hash已存在）")

        # 1. 查詢當前狀態，決定是「新購」還是「續費」
        c.execute('SELECT membership_tier, membership_expires_at FROM users WHERE user_id = %s', (user_id,))
        row = c.fetchone()

        if not row:
            raise ValueError("用戶不存在")

        is_active_pro = False
        tier, expires_at = row
        if _normalize_membership_tier(tier) == 'premium' and expires_at:
            try:
                if expires_at > datetime.utcnow():
                    is_active_pro = True
            except (ValueError, TypeError):
                pass

        # 2. 更新會員狀態
        # SQL injection fix: Use parameterized query for INTERVAL
        if is_active_pro:
            # 續費：從原到期日往後順延
            c.execute('''
                UPDATE users
                SET membership_tier = 'premium',
                    membership_expires_at = membership_expires_at + INTERVAL %s
                WHERE user_id = %s
            ''', (f"{months} months", user_id))
        else:
            # 新購或已過期：從現在開始計算
            c.execute('''
                UPDATE users
                SET membership_tier = 'premium',
                    membership_expires_at = NOW() + INTERVAL %s
                WHERE user_id = %s
            ''', (f"{months} months", user_id))

        # 3. 如果有交易哈希，記錄支付流水帳
        if tx_hash:
            from core.database.system_config import get_prices
            prices = get_prices()
            amount = prices.get("premium", 1.0) * months
            c.execute('''
                INSERT INTO membership_payments (user_id, amount, months, tx_hash, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            ''', (user_id, amount, months, tx_hash))

        conn.commit()
        return c.rowcount > 0
    except ValueError:
        # 重複交易或用戶不存在等業務錯誤，不回滾（因為沒有執行任何寫入）
        raise
    except Exception as e:
        logger.error(f"Upgrade to premium error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
