"""
用戶認證相關資料庫操作
包含：用戶管理、密碼處理、Pi Network、密碼重置、登入嘗試
"""
import os
import hashlib
import uuid
import psycopg2
from typing import Dict, Optional
from datetime import datetime, timedelta

from .connection import get_connection


# ============================================================================
# 密碼處理
# ============================================================================

def hash_password(password: str) -> str:
    """使用 SHA-256 和隨機鹽值雜湊密碼"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()


def verify_password(stored_password: str, provided_password: str) -> bool:
    """驗證密碼"""
    try:
        salt_hex, key_hex = stored_password.split(':')
        salt = bytes.fromhex(salt_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return new_key.hex() == key_hex
    except Exception:
        return False


# ============================================================================
# 用戶 CRUD
# ============================================================================

def create_user(username: str, password: str, email: str = None) -> Dict:
    """創建新用戶"""
    conn = get_connection()
    c = conn.cursor()
    try:
        if email:
            c.execute('SELECT user_id FROM users WHERE email = %s', (email,))
            if c.fetchone():
                raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)

        c.execute('''
            INSERT INTO users (user_id, username, password_hash, email, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        ''', (user_id, username, password_hash, email))
        conn.commit()
        return {"user_id": user_id, "username": username}
    except psycopg2.IntegrityError as e:
        conn.rollback()
        if "email" in str(e).lower():
            raise ValueError("Email already registered")
        raise ValueError("Username already exists")
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict]:
    """根據用戶名獲取用戶信息（包含密碼雜湊）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE username = %s', (username,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "email": row[3]
            }
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """根據 ID 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, email, auth_method FROM users WHERE user_id = %s', (user_id,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "email": row[2],
                "auth_method": row[3]
            }
        return None
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict]:
    """根據 Email 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE email = %s', (email,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "email": row[3]
            }
        return None
    finally:
        conn.close()


def update_password(user_id: str, new_password: str) -> bool:
    """更新用戶密碼"""
    conn = get_connection()
    c = conn.cursor()
    try:
        password_hash = hash_password(new_password)
        c.execute('UPDATE users SET password_hash = %s WHERE user_id = %s', (password_hash, user_id))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Update password error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def is_username_available(username: str) -> bool:
    """檢查用戶名是否可用"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT 1 FROM users WHERE username = %s', (username,))
        return c.fetchone() is None
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
        print(f"Update last active error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# Pi Network 用戶
# ============================================================================

def create_or_get_pi_user(pi_uid: str, username: str) -> Dict:
    """
    創建或獲取 Pi Network 用戶
    - 如果 pi_uid 已存在，返回現有用戶
    - 如果 username 被其他用戶使用，拋出錯誤
    - 否則創建新用戶
    """
    print(f"[DEBUG] create_or_get_pi_user called: pi_uid={pi_uid}, username={username}")
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查 pi_uid 是否已存在
        c.execute('SELECT user_id, username, auth_method, pi_username FROM users WHERE pi_uid = %s', (pi_uid,))
        row = c.fetchone()
        if row:
            print(f"[DEBUG] Found existing Pi user: {row}")
            # 如果 pi_username 為空，更新它
            if not row[3]:
                c.execute('UPDATE users SET pi_username = %s WHERE pi_uid = %s', (username, pi_uid))
                conn.commit()
                print(f"[DEBUG] Updated pi_username for existing user: {username}")
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "is_new": False
            }

        # 檢查 username 是否被其他用戶使用
        c.execute('SELECT user_id, auth_method FROM users WHERE username = %s', (username,))
        existing = c.fetchone()
        if existing:
            # 如果用戶名衝突，自動加上隨機後綴（使用8位避免極端衝突）
            original_username = username
            # 使用 UUID 的前8位作為後綴，降低衝突機率
            suffix = str(uuid.uuid4()).replace('-', '')[:8]
            username = f"{original_username}_{suffix}"
            print(f"[DEBUG] Username conflict: {original_username} taken. Assigned new username: {username}")

            # 理論上8位 UUID 衝突機率極低，但仍然檢查
            c.execute('SELECT 1 FROM users WHERE username = %s', (username,))
            if c.fetchone():
                # 極端情況：使用完整 UUID 確保唯一
                username = f"{original_username}_{str(uuid.uuid4())}"
                print(f"[DEBUG] Secondary collision detected, using full UUID: {username}")

        # 創建新 Pi 用戶
        print(f"[DEBUG] Creating new Pi user: pi_uid={pi_uid}, username={username}")
        user_id = pi_uid
        c.execute('''
            INSERT INTO users (user_id, username, password_hash, auth_method, pi_uid, pi_username, created_at)
            VALUES (%s, %s, NULL, 'pi_network', %s, %s, NOW())
        ''', (user_id, username, pi_uid, username))
        conn.commit()
        print(f"[DEBUG] Pi user created successfully: user_id={user_id}")

        return {
            "user_id": user_id,
            "username": username,
            "auth_method": "pi_network",
            "is_new": True
        }
    except ValueError:
        raise
    except Exception as e:
        print(f"[ERROR] create_or_get_pi_user failed: {type(e).__name__}: {e}")
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


def link_pi_wallet(user_id: str, pi_uid: str, pi_username: str) -> Dict:
    """
    將 Pi 錢包綁定到現有帳密用戶
    - 檢查該 pi_uid 是否已被其他用戶使用
    - 檢查該用戶是否已綁定其他錢包
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 檢查 pi_uid 是否已被使用
        c.execute('SELECT user_id, username FROM users WHERE pi_uid = %s', (pi_uid,))
        existing = c.fetchone()
        if existing:
            if existing[0] == user_id:
                return {"success": True, "message": "錢包已綁定此帳號", "already_linked": True}
            raise ValueError(f"此 Pi 錢包已綁定到其他帳號 ({existing[1]})")

        # 檢查該用戶是否已有綁定錢包
        c.execute('SELECT pi_uid FROM users WHERE user_id = %s', (user_id,))
        row = c.fetchone()
        if row and row[0]:
            raise ValueError("此帳號已綁定其他 Pi 錢包")

        # 綁定錢包
        c.execute('''
            UPDATE users
            SET pi_uid = %s, pi_username = %s
            WHERE user_id = %s
        ''', (pi_uid, pi_username, user_id))
        conn.commit()

        if c.rowcount == 0:
            raise ValueError("用戶不存在")

        return {"success": True, "message": "Pi 錢包綁定成功", "already_linked": False}
    except ValueError:
        raise
    except Exception as e:
        print(f"[ERROR] link_pi_wallet failed: {e}")
        conn.rollback()
        raise
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
            "has_wallet": row[1] is not None,
            "auth_method": row[0],
            "pi_uid": row[1],
            "pi_username": row[2]
        }
    finally:
        conn.close()


# ============================================================================
# 會員等級
# ============================================================================

def get_user_membership(user_id: str, auto_update_expired: bool = False) -> Dict:
    """
    獲取用戶會員狀態

    Args:
        user_id: 用戶 ID
        auto_update_expired: 是否自動更新過期會員狀態（默認 False，避免讀取中執行寫入）

    Returns:
        {
            "tier": str,
            "expires_at": str | None,
            "is_pro": bool,
            "is_expired": bool  # 新增：標記是否已過期（但未更新）
        }
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
            tier = row[0] or 'free'
            expires_at = row[1]
            is_pro = (tier == 'pro')
            is_expired = False

            # 檢查是否過期（只檢查，不自動更新）
            if is_pro and expires_at:
                try:
                    # PostgreSQL 返回 datetime 對象
                    if isinstance(expires_at, str):
                        expire_dt = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                    else:
                        expire_dt = expires_at

                    if expire_dt < datetime.utcnow():
                        is_expired = True

                        # 只有明確要求才自動更新
                        if auto_update_expired:
                            c.execute('''
                                UPDATE users
                                SET membership_tier = 'free', membership_expires_at = NULL
                                WHERE user_id = %s
                            ''', (user_id,))
                            conn.commit()

                            # 更新返回值
                            tier = 'free'
                            expires_at = None
                            is_pro = False
                            is_expired = False  # 已經更新了，不再是「過期未更新」狀態
                            print(f"[Membership] User {user_id} expired, downgraded to free.")
                except (ValueError, TypeError):
                    # 日期格式錯誤，視為過期
                    is_expired = True

            # 轉換 expires_at 為字符串
            if expires_at and not isinstance(expires_at, str):
                expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')

            return {
                "tier": tier,
                "expires_at": expires_at,
                "is_pro": is_pro and not is_expired,  # 已過期的不算 pro
                "is_expired": is_expired
            }
        return {"tier": "free", "expires_at": None, "is_pro": False, "is_expired": False}
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
            WHERE user_id = %s AND membership_tier = 'pro'
        ''', (user_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Expire membership error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def upgrade_to_pro(user_id: str, months: int = 1, tx_hash: str = None) -> bool:
    """升級用戶為 PRO 會員並記錄支付（支援續費順延）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 0. 如果有交易哈希，檢查是否已被使用（防止重複提交）
        if tx_hash:
            c.execute('SELECT user_id FROM membership_payments WHERE tx_hash = %s', (tx_hash,))
            existing = c.fetchone()
            if existing:
                print(f"[Upgrade] Duplicate tx_hash detected: {tx_hash} already used by user {existing[0]}")
                raise ValueError(f"此交易已被處理（transaction hash已存在）")

        # 1. 查詢當前狀態，決定是「新購」還是「續費」
        c.execute('SELECT membership_tier, membership_expires_at FROM users WHERE user_id = %s', (user_id,))
        row = c.fetchone()

        if not row:
            raise ValueError("用戶不存在")

        is_active_pro = False
        tier, expires_at = row
        if tier == 'pro' and expires_at:
            try:
                if isinstance(expires_at, str):
                    current_expires = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                else:
                    current_expires = expires_at
                if current_expires > datetime.utcnow():
                    is_active_pro = True
            except (ValueError, TypeError):
                pass

        # 2. 更新會員狀態
        if is_active_pro:
            # 續費：從原到期日往後順延
            c.execute('''
                UPDATE users
                SET membership_tier = 'pro',
                    membership_expires_at = membership_expires_at + INTERVAL '%s months'
                WHERE user_id = %s
            ''' % (months, '%s'), (user_id,))
        else:
            # 新購或已過期：從現在開始計算
            c.execute('''
                UPDATE users
                SET membership_tier = 'pro',
                    membership_expires_at = NOW() + INTERVAL '%s months'
                WHERE user_id = %s
            ''' % (months, '%s'), (user_id,))

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
        print(f"Upgrade to pro error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ============================================================================
# 密碼重置 Token
# ============================================================================

def create_reset_token(user_id: str, expires_minutes: int = 30) -> str:
    """創建密碼重置 Token（30 分鐘有效）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE user_id = %s', (user_id,))

        token = str(uuid.uuid4())
        c.execute('''
            INSERT INTO password_reset_tokens (token, user_id, created_at, expires_at)
            VALUES (%s, %s, NOW(), NOW() + INTERVAL '%s minutes')
        ''' % ('%s', '%s', expires_minutes), (token, user_id))
        conn.commit()
        return token
    except Exception as e:
        print(f"Create reset token error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_reset_token(token: str) -> Optional[Dict]:
    """驗證重置 Token 並返回用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT user_id, expires_at
            FROM password_reset_tokens
            WHERE token = %s AND expires_at > NOW()
        ''', (token,))
        row = c.fetchone()
        if row:
            expires_at = row[1]
            if expires_at and not isinstance(expires_at, str):
                expires_at = expires_at.strftime('%Y-%m-%d %H:%M:%S')
            return {
                "user_id": row[0],
                "expires_at": expires_at
            }
        return None
    finally:
        conn.close()


def delete_reset_token(token: str) -> bool:
    """刪除已使用的重置 Token"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE token = %s', (token,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Delete reset token error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def cleanup_expired_tokens():
    """清理過期的 Token"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE expires_at < NOW()')
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# 登入嘗試（防暴力破解）
# ============================================================================

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_HOURS = 24


def record_login_attempt(username: str, success: bool, ip_address: str = None):
    """記錄登入嘗試"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO login_attempts (username, ip_address, attempt_time, success)
            VALUES (%s, %s, NOW(), %s)
        ''', (username, ip_address, 1 if success else 0))
        conn.commit()

        if success:
            c.execute('''
                DELETE FROM login_attempts
                WHERE username = %s AND success = 0
            ''', (username,))
            conn.commit()
    finally:
        conn.close()


def get_failed_attempts(username: str, hours: int = LOCKOUT_HOURS) -> int:
    """獲取指定時間內的失敗登入次數"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT COUNT(*) FROM login_attempts
            WHERE username = %s
              AND success = 0
              AND attempt_time > NOW() - INTERVAL '%s hours'
        ''' % ('%s', hours), (username,))
        return c.fetchone()[0]
    finally:
        conn.close()


def is_account_locked(username: str) -> tuple:
    """
    檢查帳號是否被鎖定
    返回: (is_locked: bool, remaining_minutes: int)
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        failed_count = get_failed_attempts(username, LOCKOUT_HOURS)

        if failed_count >= MAX_LOGIN_ATTEMPTS:
            c.execute('''
                SELECT attempt_time FROM login_attempts
                WHERE username = %s AND success = 0
                ORDER BY attempt_time DESC
                LIMIT 1
            ''', (username,))
            row = c.fetchone()
            if row:
                latest_attempt = row[0]
                if isinstance(latest_attempt, str):
                    latest_attempt = datetime.strptime(latest_attempt, '%Y-%m-%d %H:%M:%S')
                unlock_time = latest_attempt + timedelta(hours=LOCKOUT_HOURS)
                now = datetime.utcnow()
                if now < unlock_time:
                    remaining = (unlock_time - now).total_seconds() / 60
                    return (True, int(remaining))

        return (False, 0)
    finally:
        conn.close()


def clear_login_attempts(username: str):
    """清除用戶的登入嘗試記錄"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM login_attempts WHERE username = %s', (username,))
        conn.commit()
    finally:
        conn.close()
