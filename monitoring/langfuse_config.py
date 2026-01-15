"""
Langfuse 配置文件 - V3 版本
用於追蹤和監控 LangGraph 系統的運行狀態

Langfuse 3.x 使用環境變數自動配置，不再需要手動傳入密鑰
環境變數：
  - LANGFUSE_PUBLIC_KEY
  - LANGFUSE_SECRET_KEY
  - LANGFUSE_HOST
"""

import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# ===== Langfuse 配置 =====
LANGFUSE_CONFIG = {
    'enabled': os.getenv('LANGFUSE_ENABLED', 'true').lower() == 'true',
    'host': os.getenv('LANGFUSE_HOST', 'http://localhost:3000'),
    'public_key': os.getenv('LANGFUSE_PUBLIC_KEY'),
    'secret_key': os.getenv('LANGFUSE_SECRET_KEY'),
}

# ===== 驗證配置 =====
def validate_langfuse_config():
    """驗證 Langfuse 配置是否正確"""
    if not LANGFUSE_CONFIG['enabled']:
        print("⏭️ Langfuse 追蹤已停用")
        return False

    public_key = LANGFUSE_CONFIG['public_key']
    secret_key = LANGFUSE_CONFIG['secret_key']
    host = LANGFUSE_CONFIG['host']

    if not public_key or not secret_key:
        print("⚠️ 未設置 Langfuse 密鑰，請在 .env 設置:")
        print('   LANGFUSE_PUBLIC_KEY="pk-lf-xxx"')
        print('   LANGFUSE_SECRET_KEY="sk-lf-xxx"')
        print('   LANGFUSE_HOST="http://localhost:3000"')
        return False

    print(f"✅ Langfuse 配置已載入 (host: {host})")
    return True

# ===== 全局配置狀態 =====
langfuse_client = validate_langfuse_config()

# ===== 刷新函數 =====
def flush_langfuse():
    """強制刷新 Langfuse 緩存"""
    if not LANGFUSE_CONFIG['enabled']:
        return
    try:
        from langfuse import Langfuse
        client = Langfuse()
        client.flush()
    except Exception as e:
        print(f"⚠️ 刷新 Langfuse 緩存失敗: {e}")

# ===== 退出時自動刷新 =====
import atexit
atexit.register(flush_langfuse)
