"""
管理員 API 路由

提供系統配置管理功能，用於商用化後台管理。
包含價格設置、限制調整等功能。

安全注意事項：
- 此 API 應受到認證保護
- 建議在生產環境中添加 API Key 或 JWT 認證
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os

from core.database import (
    get_prices,
    get_limits,
    update_price,
    update_limit,
    set_config,
    get_config,
    list_all_configs_with_metadata,
    bulk_update_configs,
    invalidate_config_cache,
)
import asyncio
from functools import partial

router = APIRouter()

# ============================================================================
# 簡易認證（生產環境應使用更安全的方式）
# ============================================================================

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """驗證管理員 API Key"""
    if not ADMIN_API_KEY:
        # Avoid leaking internal configuration details
        # Return 403 Forbidden to mask the fact that the key is not configured
        raise HTTPException(status_code=403, detail="Forbidden: Admin access not configured")
    
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing admin API key")
    return True


# ============================================================================
# 請求模型
# ============================================================================

class UpdatePriceRequest(BaseModel):
    key: str  # create_post, tip, premium
    value: float


class UpdateLimitRequest(BaseModel):
    key: str  # daily_post_free, daily_post_premium, etc.
    value: Optional[int]  # None = unlimited


class UpdateConfigRequest(BaseModel):
    key: str
    value: Any
    value_type: Optional[str] = 'string'
    category: Optional[str] = 'general'
    description: Optional[str] = ''


class BulkUpdateRequest(BaseModel):
    configs: Dict[str, Any]

class DebugLogRequest(BaseModel):
    message: str
    level: str = "INFO"


# ============================================================================
# 配置讀取 API
# ============================================================================

@router.get("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def read_debug_log(lines: int = 50):
    """
    讀取系統日誌

    需要管理員權限
    """
    log_file_path = os.getenv("LOG_FILE_PATH", "app.log")
    if not os.path.exists(log_file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            # Get the last 'lines' number of lines
            recent_lines = all_lines[-lines:]
        return {
            "success": True,
            "log_content": "".join(recent_lines)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")


@router.get("/api/admin/config", dependencies=[Depends(verify_admin_key)])
async def get_all_admin_configs():
    """
    獲取所有系統配置（包含元數據）

    需要管理員權限
    """
    loop = asyncio.get_running_loop()
    configs = await loop.run_in_executor(None, list_all_configs_with_metadata)

    return {
        "success": True,
        "configs": configs
    }


@router.get("/api/admin/config/prices", dependencies=[Depends(verify_admin_key)])
async def get_admin_prices():
    """
    獲取所有價格配置

    需要管理員權限
    """
    loop = asyncio.get_running_loop()
    prices = await loop.run_in_executor(None, get_prices)

    return {
        "success": True,
        "prices": prices
    }


@router.get("/api/admin/config/limits", dependencies=[Depends(verify_admin_key)])
async def get_admin_limits():
    """
    獲取所有限制配置

    需要管理員權限
    """
    loop = asyncio.get_running_loop()
    limits = await loop.run_in_executor(None, get_limits)

    return {
        "success": True,
        "limits": limits
    }


# ============================================================================
# 配置更新 API
# ============================================================================

@router.put("/api/admin/config/price", dependencies=[Depends(verify_admin_key)])
async def update_price_config(
    request: UpdatePriceRequest
):
    """
    更新價格配置

    Args:
        key: 價格類型 (create_post, tip, premium)
        value: 新價格（Pi）

    需要管理員權限
    """
    valid_keys = ['create_post', 'tip', 'premium']
    if request.key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid price key. Must be one of: {valid_keys}"
        )

    if request.value < 0:
        raise HTTPException(
            status_code=400,
            detail="Price cannot be negative"
        )

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, partial(update_price, request.key, request.value))

    if success:
        new_prices = await loop.run_in_executor(None, get_prices)
        return {
            "success": True,
            "message": f"Price '{request.key}' updated to {request.value} Pi",
            "new_prices": new_prices
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update price")


@router.put("/api/admin/config/limit", dependencies=[Depends(verify_admin_key)])
async def update_limit_config(
    request: UpdateLimitRequest
):
    """
    更新限制配置

    Args:
        key: 限制類型 (daily_post_free, daily_post_premium, etc.)
        value: 新限制值（null = 無限制）

    需要管理員權限
    """
    valid_keys = ['daily_post_free', 'daily_post_premium',
                  'daily_comment_free', 'daily_comment_premium']
    if request.key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid limit key. Must be one of: {valid_keys}"
        )

    if request.value is not None and request.value < 0:
        raise HTTPException(
            status_code=400,
            detail="Limit cannot be negative"
        )

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, partial(update_limit, request.key, request.value))

    if success:
        new_limits = await loop.run_in_executor(None, get_limits)
        return {
            "success": True,
            "message": f"Limit '{request.key}' updated to {request.value if request.value is not None else 'unlimited'}",
            "new_limits": new_limits
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update limit")


@router.post("/api/debug/log", dependencies=[Depends(verify_admin_key)])
async def write_debug_log(request: DebugLogRequest):
    """
    寫入系統日誌 (僅限管理員)

    需要管理員權限
    """
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    log_level = getattr(logging, request.level.upper(), logging.INFO)
    logger.log(log_level, f"ADMIN_DEBUG: {request.message}")

    return {
        "success": True,
        "message": f"Log message '{request.message}' written with level {request.level}"
    }


@router.put("/api/admin/config", dependencies=[Depends(verify_admin_key)])
async def update_generic_config(
    request: UpdateConfigRequest
):
    """
    更新任意配置

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        partial(
            set_config,
            key=request.key,
            value=request.value,
            value_type=request.value_type,
            category=request.category,
            description=request.description
        )
    )

    if success:
        value = await loop.run_in_executor(None, get_config, request.key)
        return {
            "success": True,
            "message": f"Config '{request.key}' updated successfully",
            "value": value
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update config")


@router.post("/api/admin/config/bulk")
async def bulk_update_admin_configs(
    request: BulkUpdateRequest,
    x_admin_key: Optional[str] = Header(None)
):
    """
    批量更新配置

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, partial(bulk_update_configs, request.configs))

    if success:
        return {
            "success": True,
            "message": f"Updated {len(request.configs)} configs",
            "updated_keys": list(request.configs.keys())
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to bulk update configs")


@router.post("/api/admin/config/cache/invalidate")
async def invalidate_cache(x_admin_key: Optional[str] = Header(None)):
    """
    強制清除配置快取

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, invalidate_config_cache)

    return {
        "success": True,
        "message": "Config cache invalidated"
    }


# ============================================================================
# 審計日誌 API
# ============================================================================

@router.get("/api/admin/config/audit/{key}")
async def get_config_audit_log(
    key: str,
    limit: int = 20,
    x_admin_key: Optional[str] = Header(None)
):
    """
    獲取配置變更歷史

    Args:
        key: 配置鍵名
        limit: 返回記錄數量（默認 20）

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    try:
        from core.database.system_config import get_config_metadata

        # 嘗試使用 V2 版本的審計日誌
        loop = asyncio.get_running_loop()
        try:
            from core.database.system_config_v2 import get_config_history
            history = await loop.run_in_executor(None, partial(get_config_history, key, limit))
        except ImportError:
            history = []

        metadata = await loop.run_in_executor(None, get_config_metadata, key)

        return {
            "success": True,
            "key": key,
            "current": metadata,
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit log: {str(e)}")


# ============================================================================
# Stage 3 Security: JWT Key Rotation Management API
# ============================================================================

@router.post("/api/admin/security/keys/rotate")
async def manual_rotate_key(x_admin_key: Optional[str] = Header(None)):
    """
    Manually trigger JWT key rotation.

    This generates a new primary key and deprecates the old one.
    Existing tokens signed with the old key remain valid until they expire.

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    # Check if key rotation is enabled
    if os.getenv("USE_KEY_ROTATION", "false").lower() != "true":
        raise HTTPException(
            status_code=400,
            detail="Key rotation is not enabled. Set USE_KEY_ROTATION=true to enable."
        )

    try:
        from core.key_rotation import get_key_manager
        from core.audit import audit_log

        key_manager = get_key_manager()
        result = key_manager.rotate_key()

        # Log audit event
        audit_log(
            action="key_rotation_manual",
            user_id="admin",
            metadata=result
        )

        return {
            "success": True,
            "message": "Key rotation completed successfully",
            "result": {
                "old_key_id": result["old_key_id"][:8] + "...",
                "new_key_id": result["new_key_id"][:8] + "...",
                "rotated_at": result["rotated_at"]
            }
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="Key rotation module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Key rotation failed: {str(e)}")


@router.get("/api/admin/security/keys/status")
async def get_keys_status(x_admin_key: Optional[str] = Header(None)):
    """
    Get the status of all JWT keys.

    Returns information about the current primary key,
    deprecated keys, and their expiration dates.

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    # Check if key rotation is enabled
    if os.getenv("USE_KEY_ROTATION", "false").lower() != "true":
        raise HTTPException(
            status_code=400,
            detail="Key rotation is not enabled. Set USE_KEY_ROTATION=true to enable."
        )

    try:
        from core.key_rotation import get_key_manager

        key_manager = get_key_manager()
        status = key_manager.get_keys_status()

        return {
            "success": True,
            "key_rotation_enabled": True,
            "status": status
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="Key rotation module not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get key status: {str(e)}")


# ============================================================================
# Stage 4 Security: Security Monitoring API
# ============================================================================

@router.get("/api/admin/security/events")
async def get_security_events(
    hours: int = 24,
    x_admin_key: Optional[str] = Header(None)
):
    """
    Get recent security events.

    Args:
        hours: Number of hours to look back (default: 24, max: 168)

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    # Validate hours parameter
    hours = min(max(1, hours), 168)

    try:
        from core.security_monitor import get_security_monitor

        monitor = get_security_monitor()
        events = monitor.get_recent_events(hours=hours)

        return {
            "success": True,
            "events": events,
            "total": len(events),
            "period_hours": hours
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="Security monitor not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get security events: {str(e)}")


@router.get("/api/admin/security/statistics")
async def get_security_statistics(
    days: int = 7,
    x_admin_key: Optional[str] = Header(None)
):
    """
    Get security statistics for the last N days.

    Args:
        days: Number of days to analyze (default: 7, max: 30)

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    # Validate days parameter
    days = min(max(1, days), 30)

    try:
        from core.security_monitor import get_security_monitor

        monitor = get_security_monitor()
        stats = monitor.get_statistics(days=days)

        return {
            "success": True,
            "statistics": stats
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="Security monitor not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get security statistics: {str(e)}")


@router.post("/api/admin/security/test-alert")
async def test_security_alert(
    channel: str = "telegram",
    x_admin_key: Optional[str] = Header(None)
):
    """
    Send a test security alert to verify alert configuration.

    Args:
        channel: Alert channel to test (telegram or email)

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    if channel not in ["telegram", "email"]:
        raise HTTPException(status_code=400, detail="Invalid channel. Use 'telegram' or 'email'")

    try:
        from core.alert_dispatcher import get_alert_dispatcher

        dispatcher = get_alert_dispatcher()
        success = dispatcher.send(
            channel=channel,
            severity="low",
            title="🧪 Security Alert Test",
            message="This is a test security alert from the Pi Crypto Insight system.\n\n"
                   "If you received this, your alert configuration is working correctly!"
        )

        if success:
            return {
                "success": True,
                "message": f"Test alert sent successfully via {channel}"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send test alert via {channel}. Check your configuration."
            }

    except ImportError:
        raise HTTPException(status_code=500, detail="Alert dispatcher not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test alert: {str(e)}")
