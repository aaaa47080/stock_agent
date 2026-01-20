"""
用戶認證相關資料庫操作
包含：用戶管理、密碼處理、Pi Network、密碼重置、登入嘗試
"""
import os
import hashlib
import uuid
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
    import sqlite3
    conn = get_connection()
    c = conn.cursor()
    try:
        if email:
            c.execute('SELECT user_id FROM users WHERE email = ?', (email,))
            if c.fetchone():
                raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)

        c.execute('''
            INSERT INTO users (user_id, username, password_hash, email, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (user_id, username, password_hash, email))
        conn.commit()
        return {"user_id": user_id, "username": username}
    except sqlite3.IntegrityError as e:
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
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE username = ?', (username,))
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


def get_user_by_email(email: str) -> Optional[Dict]:
    """根據 Email 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, password_hash, email FROM users WHERE email = ?', (email,))
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
        c.execute('UPDATE users SET password_hash = ? WHERE user_id = ?', (password_hash, user_id))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Update password error: {e}")
        return False
    finally:
        conn.close()


def is_username_available(username: str) -> bool:
    """檢查用戶名是否可用"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT 1 FROM users WHERE username = ?', (username,))
        return c.fetchone() is None
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
        c.execute('SELECT user_id, username, auth_method, pi_username FROM users WHERE pi_uid = ?', (pi_uid,))
        row = c.fetchone()
        if row:
            print(f"[DEBUG] Found existing Pi user: {row}")
            # 如果 pi_username 為空，更新它
            if not row[3]:
                c.execute('UPDATE users SET pi_username = ? WHERE pi_uid = ?', (username, pi_uid))
                conn.commit()
                print(f"[DEBUG] Updated pi_username for existing user: {username}")
            return {
                "user_id": row[0],
                "username": row[1],
                "auth_method": row[2],
                "is_new": False
            }

        # 檢查 username 是否被其他用戶使用
        c.execute('SELECT user_id, auth_method FROM users WHERE username = ?', (username,))
        existing = c.fetchone()
        if existing:
            # 💡 修復：如果用戶名衝突，不報錯，而是自動加上隨機後綴
            import random
            original_username = username
            suffix = str(random.randint(1000, 9999))
            username = f"{original_username}_{suffix}"
            print(f"[DEBUG] Username conflict: {original_username} taken. Assigned new username: {username}")
            
            # 再次檢查新用戶名是否也衝突（極低機率）
            c.execute('SELECT 1 FROM users WHERE username = ?', (username,))
            if c.fetchone():
                username = f"{original_username}_{str(uuid.uuid4())[:4]}"

        # 創建新 Pi 用戶
        print(f"[DEBUG] Creating new Pi user: pi_uid={pi_uid}, username={username}")
        user_id = pi_uid
        c.execute('''
            INSERT INTO users (user_id, username, password_hash, auth_method, pi_uid, pi_username, created_at)
            VALUES (?, ?, NULL, 'pi_network', ?, ?, datetime('now'))
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
        raise
    finally:
        conn.close()


def get_user_by_pi_uid(pi_uid: str) -> Optional[Dict]:
    """根據 Pi UID 獲取用戶信息"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, username, auth_method, created_at FROM users WHERE pi_uid = ?', (pi_uid,))
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
        c.execute('SELECT user_id, username FROM users WHERE pi_uid = ?', (pi_uid,))
        existing = c.fetchone()
        if existing:
            if existing[0] == user_id:
                return {"success": True, "message": "錢包已綁定此帳號", "already_linked": True}
            raise ValueError(f"此 Pi 錢包已綁定到其他帳號 ({existing[1]})")

        # 檢查該用戶是否已有綁定錢包
        c.execute('SELECT pi_uid FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row and row[0]:
            raise ValueError("此帳號已綁定其他 Pi 錢包")

        # 綁定錢包
        c.execute('''
            UPDATE users
            SET pi_uid = ?, pi_username = ?
            WHERE user_id = ?
        ''', (pi_uid, pi_username, user_id))
        conn.commit()

        if c.rowcount == 0:
            raise ValueError("用戶不存在")

        return {"success": True, "message": "Pi 錢包綁定成功", "already_linked": False}
    except ValueError:
        raise
    except Exception as e:
        print(f"[ERROR] link_pi_wallet failed: {e}")
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
            FROM users WHERE user_id = ?
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

def get_user_membership(user_id: str) -> Dict:
    """獲取用戶會員狀態"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT membership_tier, membership_expires_at
            FROM users WHERE user_id = ?
        ''', (user_id,))
        row = c.fetchone()
        if row:
            tier = row[0] or 'free'
            expires_at = row[1]

            # 檢查 PRO 會員是否過期
            if tier == 'pro' and expires_at:
                if datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S') < datetime.utcnow():
                    tier = 'free'

            return {
                "tier": tier,
                "expires_at": expires_at,
                "is_pro": tier == 'pro'
            }
        return {"tier": "free", "expires_at": None, "is_pro": False}
    finally:
        conn.close()


def upgrade_to_pro(user_id: str, months: int = 1, tx_hash: str = None) -> bool:
    """升級用戶為 PRO 會員"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE users
            SET membership_tier = 'pro',
                membership_expires_at = datetime('now', '+' || ? || ' months')
            WHERE user_id = ?
        ''', (months, user_id))
        conn.commit()
        return c.rowcount > 0
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
        c.execute('DELETE FROM password_reset_tokens WHERE user_id = ?', (user_id,))

        token = str(uuid.uuid4())
        c.execute('''
            INSERT INTO password_reset_tokens (token, user_id, created_at, expires_at)
            VALUES (?, ?, datetime('now'), datetime('now', '+' || ? || ' minutes'))
        ''', (token, user_id, expires_minutes))
        conn.commit()
        return token
    except Exception as e:
        print(f"Create reset token error: {e}")
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
            WHERE token = ? AND expires_at > datetime('now')
        ''', (token,))
        row = c.fetchone()
        if row:
            return {
                "user_id": row[0],
                "expires_at": row[1]
            }
        return None
    finally:
        conn.close()


def delete_reset_token(token: str) -> bool:
    """刪除已使用的重置 Token"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE token = ?', (token,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Delete reset token error: {e}")
        return False
    finally:
        conn.close()


def cleanup_expired_tokens():
    """清理過期的 Token"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM password_reset_tokens WHERE expires_at < datetime("now")')
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
            VALUES (?, ?, datetime('now'), ?)
        ''', (username, ip_address, 1 if success else 0))
        conn.commit()

        if success:
            c.execute('''
                DELETE FROM login_attempts
                WHERE username = ? AND success = 0
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
            WHERE username = ?
              AND success = 0
              AND attempt_time > datetime('now', '-' || ? || ' hours')
        ''', (username, hours))
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
                WHERE username = ? AND success = 0
                ORDER BY attempt_time DESC
                LIMIT 1
            ''', (username,))
            row = c.fetchone()
            if row:
                latest_attempt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
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
        c.execute('DELETE FROM login_attempts WHERE username = ?', (username,))
        conn.commit()
    finally:
        conn.close()
