"""
管理員 API 路由

提供系統配置管理功能，用於商用化後台管理。
包含價格設置、限制調整等功能。

安全注意事項：
- 此 API 應受到認證保護
- 建議在生產環境中添加 API Key 或 JWT 認證
"""

from fastapi import APIRouter, HTTPException, Header
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

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev_admin_key_change_in_production")


def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """驗證管理員 API Key"""
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


# ============================================================================
# 配置讀取 API
# ============================================================================

@router.get("/api/admin/config")
async def get_all_admin_configs(x_admin_key: Optional[str] = Header(None)):
    """
    獲取所有系統配置（包含元數據）

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    configs = await loop.run_in_executor(None, list_all_configs_with_metadata)

    return {
        "success": True,
        "configs": configs
    }


@router.get("/api/admin/config/prices")
async def get_admin_prices(x_admin_key: Optional[str] = Header(None)):
    """
    獲取所有價格配置

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    prices = await loop.run_in_executor(None, get_prices)

    return {
        "success": True,
        "prices": prices
    }


@router.get("/api/admin/config/limits")
async def get_admin_limits(x_admin_key: Optional[str] = Header(None)):
    """
    獲取所有限制配置

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

    loop = asyncio.get_running_loop()
    limits = await loop.run_in_executor(None, get_limits)

    return {
        "success": True,
        "limits": limits
    }


# ============================================================================
# 配置更新 API
# ============================================================================

@router.put("/api/admin/config/price")
async def update_price_config(
    request: UpdatePriceRequest,
    x_admin_key: Optional[str] = Header(None)
):
    """
    更新價格配置

    Args:
        key: 價格類型 (create_post, tip, premium)
        value: 新價格（Pi）

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

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


@router.put("/api/admin/config/limit")
async def update_limit_config(
    request: UpdateLimitRequest,
    x_admin_key: Optional[str] = Header(None)
):
    """
    更新限制配置

    Args:
        key: 限制類型 (daily_post_free, daily_post_premium, etc.)
        value: 新限制值（null = 無限制）

    需要管理員權限
    """
    verify_admin_key(x_admin_key)

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


@router.put("/api/admin/config")
async def update_generic_config(
    request: UpdateConfigRequest,
    x_admin_key: Optional[str] = Header(None)
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
