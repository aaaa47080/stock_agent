"""
用戶 API Key 資料庫操作
安全地儲存和管理用戶的第三方 API Key
"""
from typing import Dict, Optional

from .connection import get_connection
from utils.encryption import encrypt_api_key, decrypt_api_key, mask_api_key


# 支援的 Provider 列表
SUPPORTED_PROVIDERS = [
    "openai",
    "google_gemini", 
    "anthropic",
    "groq",
    "openrouter",
]


# ✅ 效能優化：只建表一次，避免每個 DB 函式都重複 CREATE TABLE IF NOT EXISTS
_table_initialized = False

def _ensure_table_exists():
    """確保 user_api_keys 表存在（只執行一次）"""
    global _table_initialized
    if _table_initialized:
        return
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_api_keys (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                model_selection TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                UNIQUE(user_id, provider),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        # 確保 index 存在
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_id ON user_api_keys(user_id)')
        conn.commit()
        _table_initialized = True
    finally:
        conn.close()


def save_user_api_key(user_id: str, provider: str, api_key: str, model: str = None) -> Dict:
    """
    儲存用戶的 API Key（加密後儲存）
    
    Args:
        user_id: 用戶 ID
        provider: 服務提供商（openai, google_gemini, etc.）
        api_key: 原始 API Key
        model: 可選的模型選擇
        
    Returns:
        {"success": bool, "error": str (如果失敗)}
    """
    if provider not in SUPPORTED_PROVIDERS:
        return {"success": False, "error": f"Unsupported provider: {provider}"}
    
    if not api_key or not api_key.strip():
        return {"success": False, "error": "API key cannot be empty"}
    
    _ensure_table_exists()
    
    encrypted_key = encrypt_api_key(api_key.strip())
    
    conn = get_connection()
    c = conn.cursor()
    try:
        # 使用 UPSERT
        c.execute('''
            INSERT INTO user_api_keys (user_id, provider, encrypted_key, model_selection, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, provider) 
            DO UPDATE SET 
                encrypted_key = EXCLUDED.encrypted_key,
                model_selection = EXCLUDED.model_selection,
                updated_at = NOW()
        ''', (user_id, provider, encrypted_key, model))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_user_api_key(user_id: str, provider: str) -> Optional[str]:
    """
    取得用戶的 API Key（解密後返回）
    
    Args:
        user_id: 用戶 ID
        provider: 服務提供商
        
    Returns:
        解密後的 API Key，如果不存在則返回 None
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT encrypted_key FROM user_api_keys
            WHERE user_id = %s AND provider = %s
        ''', (user_id, provider))
        
        row = c.fetchone()
        if not row:
            return None
        
        # ✅ 效能優化：移除讀操作的 UPDATE last_used_at，讀取不應觸發寫入
        # last_used_at 僅在 save_user_api_key 時更新即可
        return decrypt_api_key(row[0])
    finally:
        conn.close()


def get_user_api_key_masked(user_id: str, provider: str) -> Optional[Dict]:
    """
    取得用戶 API Key 的遮蔽版本（用於前端顯示）
    
    Returns:
        {"has_key": bool, "masked_key": str, "model": str, "updated_at": str}
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT encrypted_key, model_selection, updated_at
            FROM user_api_keys
            WHERE user_id = %s AND provider = %s
        ''', (user_id, provider))
        
        row = c.fetchone()
        if not row:
            return {"has_key": False, "masked_key": None, "model": None, "updated_at": None}
        
        decrypted = decrypt_api_key(row[0])
        masked = mask_api_key(decrypted) if decrypted else None
        
        return {
            "has_key": True,
            "masked_key": masked,
            "model": row[1],
            "updated_at": row[2].isoformat() if row[2] else None
        }
    finally:
        conn.close()


def get_all_user_api_keys(user_id: str) -> Dict[str, Dict]:
    """
    取得用戶所有 API Key 的遮蔽版本
    
    Returns:
        {provider: {"has_key": bool, "masked_key": str, "model": str}}
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT provider, encrypted_key, model_selection, updated_at
            FROM user_api_keys
            WHERE user_id = %s
        ''', (user_id,))
        
        rows = c.fetchall()
        result = {}
        
        for row in rows:
            provider = row[0]
            decrypted = decrypt_api_key(row[1])
            masked = mask_api_key(decrypted) if decrypted else None
            
            result[provider] = {
                "has_key": True,
                "masked_key": masked,
                "model": row[2],
                "updated_at": row[3].isoformat() if row[3] else None
            }
        
        # 確保所有支援的 provider 都有記錄
        for provider in SUPPORTED_PROVIDERS:
            if provider not in result:
                result[provider] = {"has_key": False, "masked_key": None, "model": None, "updated_at": None}
        
        return result
    finally:
        conn.close()


def delete_user_api_key(user_id: str, provider: str) -> Dict:
    """
    刪除用戶的 API Key
    
    Returns:
        {"success": bool, "error": str (如果失敗)}
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            DELETE FROM user_api_keys
            WHERE user_id = %s AND provider = %s
        ''', (user_id, provider))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def delete_all_user_api_keys(user_id: str) -> Dict:
    """
    刪除用戶所有 API Key（用於帳號刪除時）
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM user_api_keys WHERE user_id = %s', (user_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def save_user_model_selection(user_id: str, provider: str, model: str) -> Dict:
    """
    儲存用戶的模型選擇（不更改 API Key）
    """
    _ensure_table_exists()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE user_api_keys SET model_selection = %s, updated_at = NOW()
            WHERE user_id = %s AND provider = %s
        ''', (model, user_id, provider))
        
        conn.commit()
        
        if c.rowcount == 0:
            return {"success": False, "error": "No API key found for this provider"}
        
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
