"""
加密工具模組
用於安全地加密和解密用戶 API Key

安全設計：
- 使用檔案式金鑰管理（類似 JWT Key Rotation）
- 金鑰與程式碼分離
- 支援金鑰輪換
"""
import os
import json
import base64
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 金鑰檔案路徑（與 JWT keys 同一目錄）
KEYS_DIR = Path(__file__).parent.parent / "config"
KEYS_FILE = KEYS_DIR / "api_key_encryption.json"


def _ensure_keys_dir():
    """確保金鑰目錄存在"""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)


def _load_or_create_encryption_key() -> bytes:
    """
    載入或建立加密金鑰
    
    優先順序：
    1. 從金鑰檔案載入（推薦）
    2. 從環境變數載入（向後兼容）
    3. 建立新金鑰並儲存
    """
    _ensure_keys_dir()
    
    # 嘗試從檔案載入
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                data = json.load(f)
                if data.get("key"):
                    # 從 base64 解碼
                    return base64.urlsafe_b64decode(data["key"])
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to load encryption key file: {e}")
    
    # 嘗試從環境變數載入（向後兼容）
    env_secret = os.getenv("API_KEY_ENCRYPTION_SECRET")
    if env_secret:
        import logging
        logging.getLogger(__name__).warning(
            "⚠️ Using API_KEY_ENCRYPTION_SECRET from environment. "
            "Consider migrating to file-based key management."
        )
        # 從環境變數衍生金鑰
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'PiCryptoMiner_API_Key_Derivation',
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(env_secret.encode()))
    
    # 建立新的隨機金鑰
    import logging
    logging.getLogger(__name__).warning("🔑 Generating new API key encryption key")
    new_key = Fernet.generate_key()
    
    # 儲存到檔案
    _save_encryption_key(new_key)
    
    return new_key


def _save_encryption_key(key: bytes, update_rotation_time: bool = True):
    """儲存加密金鑰到檔案"""
    _ensure_keys_dir()

    # 保留舊資料中的 created_at
    existing_data = {}
    if KEYS_FILE.exists():
        try:
            with open(KEYS_FILE, 'r') as f:
                existing_data = json.load(f)
        except Exception:
            pass

    data = {
        "key": base64.urlsafe_b64encode(key).decode(),
        "created_at": existing_data.get("created_at", datetime.utcnow().isoformat()),
        "version": existing_data.get("version", 1),
    }

    if update_rotation_time:
        data["last_rotation"] = datetime.utcnow().isoformat()
    elif existing_data.get("last_rotation"):
        data["last_rotation"] = existing_data["last_rotation"]
    
    # 使用原子寫入避免損壞
    temp_file = KEYS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # 原子重命名
    temp_file.rename(KEYS_FILE)
    
    # 設定權限（僅擁有者可讀寫）
    os.chmod(KEYS_FILE, 0o600)


# 全域金鑰快取
_encryption_key_cache = None


def _get_fernet() -> Fernet:
    """取得 Fernet 實例"""
    global _encryption_key_cache
    
    if _encryption_key_cache is None:
        _encryption_key_cache = _load_or_create_encryption_key()
    
    return Fernet(_encryption_key_cache)


def encrypt_api_key(plaintext: str) -> str:
    """
    加密 API Key
    
    Args:
        plaintext: 原始 API Key
        
    Returns:
        加密後的字串（base64 編碼）
    """
    if not plaintext:
        return ""
    
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted: str) -> str:
    """
    解密 API Key
    
    Args:
        encrypted: 加密後的字串
        
    Returns:
        原始 API Key
    """
    if not encrypted:
        return ""
    
    try:
        fernet = _get_fernet()
        decoded = base64.urlsafe_b64decode(encrypted.encode())
        decrypted = fernet.decrypt(decoded)
        return decrypted.decode()
    except Exception as e:
        # 解密失敗，返回空字串
        import logging
        logging.getLogger(__name__).error(f"Failed to decrypt API key: {e}")
        return ""


def mask_api_key(api_key: str) -> str:
    """
    遮蔽 API Key 用於顯示
    
    Args:
        api_key: 原始 API Key
        
    Returns:
        遮蔽後的字串，如 "sk-****...****abc123"
    """
    if not api_key or len(api_key) < 8:
        return "****"
    
    # 保留前綴和後綴
    prefix_len = min(4, len(api_key) // 4)
    suffix_len = min(4, len(api_key) // 4)
    
    prefix = api_key[:prefix_len]
    suffix = api_key[-suffix_len:]
    
    return f"{prefix}****...****{suffix}"


def rotate_encryption_key() -> dict:
    """
    輪換加密金鑰（管理員功能）

    這會：
    1. 生成新金鑰
    2. 重新加密所有現有 API Keys
    3. 更新金鑰檔案

    Returns:
        {"success": bool, "re_encrypted_count": int}
    """
    from core.database.connection import get_connection

    # 載入舊金鑰
    old_fernet = _get_fernet()

    # 生成新金鑰
    new_key = Fernet.generate_key()
    new_fernet = Fernet(new_key)

    # 重新加密所有 API Keys
    conn = get_connection()
    c = conn.cursor()
    re_encrypted_count = 0

    try:
        c.execute('SELECT id, encrypted_key FROM user_api_keys')
        rows = c.fetchall()

        for row in rows:
            key_id = row[0]
            old_encrypted = row[1]

            try:
                # 用舊金鑰解密
                decoded = base64.urlsafe_b64decode(old_encrypted.encode())
                plaintext = old_fernet.decrypt(decoded).decode()

                # 用新金鑰加密
                new_encrypted = new_fernet.encrypt(plaintext.encode())
                new_encoded = base64.urlsafe_b64encode(new_encrypted).decode()

                # 更新資料庫
                c.execute(
                    'UPDATE user_api_keys SET encrypted_key = %s WHERE id = %s',
                    (new_encoded, key_id)
                )
                re_encrypted_count += 1

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Failed to re-encrypt key {key_id}: {e}"
                )

        conn.commit()

        # 儲存新金鑰（更新 last_rotation 時間戳）
        global _encryption_key_cache
        _encryption_key_cache = new_key
        _save_encryption_key(new_key, update_rotation_time=True)

        import logging
        logging.getLogger(__name__).info(
            f"🔑 API key encryption rotated, re-encrypted {re_encrypted_count} keys"
        )

        return {"success": True, "re_encrypted_count": re_encrypted_count}

    except Exception as e:
        conn.rollback()
        import logging
        logging.getLogger(__name__).error(f"Key rotation failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_key_rotation_status() -> dict:
    """
    取得金鑰輪換狀態

    Returns:
        Dictionary with rotation status information
    """
    _ensure_keys_dir()

    if not KEYS_FILE.exists():
        return {
            "exists": False,
            "last_rotation": None,
            "should_rotate": True
        }

    try:
        with open(KEYS_FILE, 'r') as f:
            data = json.load(f)

        return {
            "exists": True,
            "created_at": data.get("created_at"),
            "last_rotation": data.get("last_rotation"),
            "version": data.get("version", 1)
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to read key status: {e}")
        return {
            "exists": True,
            "error": str(e),
            "should_rotate": True
        }


def should_rotate_api_key_encryption(interval_days: int = 90) -> bool:
    """
    檢查是否需要輪換 API Key 加密金鑰

    Args:
        interval_days: 輪換間隔（預設 90 天）

    Returns:
        True 如果需要輪換
    """
    from datetime import timedelta

    status = get_key_rotation_status()

    if not status.get("exists"):
        return False  # 沒有金鑰檔案，不需要輪換

    last_rotation = status.get("last_rotation")
    if not last_rotation:
        # 沒有 last_rotation 記錄，可能是舊版本
        # 檢查 created_at
        created_at = status.get("created_at")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                if datetime.utcnow() > created + timedelta(days=interval_days):
                    return True
            except (ValueError, TypeError):
                pass
        return False

    try:
        last_rot = datetime.fromisoformat(last_rotation)
        next_rotation = last_rot + timedelta(days=interval_days)
        return datetime.utcnow() >= next_rotation
    except (ValueError, TypeError):
        return True
