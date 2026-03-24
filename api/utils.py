import asyncio
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger("API")

_ssl_verify = os.getenv("SSL_VERIFY", "true").lower() in ("true", "1", "yes")

_db_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="db_sync")


async def run_sync(fn: Callable[..., Any], *args: Any) -> Any:
    return await asyncio.get_running_loop().run_in_executor(_db_executor, fn, *args)


# Default to WARNING in production to reduce noisy logs and ephemeral-storage pressure.
# Override with APP_LOG_LEVEL=INFO/DEBUG when detailed tracing is needed.
logger.setLevel(
    getattr(logging, os.getenv("APP_LOG_LEVEL", "WARNING").upper(), logging.WARNING)
)

# ============================================
# Shared HTTP Client with Connection Pool
# ============================================

# 全局共享的 HTTP 客戶端（連接池）
# 使用 lazy initialization 確保在需要時才創建
_shared_http_client: Optional[httpx.AsyncClient] = None


def get_shared_http_client() -> httpx.AsyncClient:
    """
    獲取共享的 HTTP 客戶端（帶連接池）。

    使用連接池的好處：
    - 減少 TCP 連接建立的開銷
    - 復用連接，提高效能
    - 統一管理超時和重試策略

    Returns:
        httpx.AsyncClient: 共享的異步 HTTP 客戶端
    """
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        _shared_http_client = httpx.AsyncClient(
            verify=_ssl_verify,
            limits=httpx.Limits(
                max_connections=100,  # 最大連接數
                max_keepalive_connections=20,  # 保持活躍的連接數
            ),
            timeout=httpx.Timeout(
                connect=10.0,  # 連接超時 10 秒
                read=30.0,  # 讀取超時 30 秒
                write=10.0,  # 寫入超時 10 秒
                pool=5.0,  # 從池中獲取連接超時 5 秒
            ),
            follow_redirects=True,
            max_redirects=5,
        )
    return _shared_http_client


async def close_shared_http_client():
    """
    關閉共享的 HTTP 客戶端。
    在應用關閉時調用，確保資源正確釋放。
    """
    global _shared_http_client
    if _shared_http_client is not None and not _shared_http_client.is_closed:
        await _shared_http_client.aclose()
        _shared_http_client = None
        logger.info("Shared HTTP client closed")


def update_env_file(keys: Dict[str, str], project_root: str):
    """Helper function to update or append keys to the .env file"""
    env_path = os.path.join(project_root, ".env")

    for k, v in keys.items():
        sanitized = v.replace("\n", "").replace("\r", "").replace("\x00", "")
        keys[k] = sanitized
    env_path = os.path.join(project_root, ".env")

    # Read existing lines
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []

    # Prepare new content
    new_lines = []
    updated_keys = set()

    for line in lines:
        key_match = False
        for k, v in keys.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated_keys.add(k)
                key_match = True
                break
        if not key_match:
            new_lines.append(line)

    # Append new keys that weren't in the file
    if len(new_lines) > 0 and not new_lines[-1].endswith("\n"):
        new_lines.append("\n")

    for k, v in keys.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    # Write back atomically
    fd, tmp_path = tempfile.mkstemp(dir=project_root, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        os.replace(tmp_path, env_path)
    except BaseException:
        os.unlink(tmp_path)
        raise
