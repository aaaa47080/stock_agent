"""
Tools API Router

Endpoints for listing tools and managing user tool preferences.
"""
import asyncio
from functools import partial
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.deps import get_current_user
from core.database import get_tools_for_frontend, update_user_tool_preference
from core.database.tools import normalize_membership_tier
from api.utils import logger

router = APIRouter()


async def _list_tools_impl(current_user: dict) -> dict:
    """Return all tools with per-user enabled/locked status."""
    from core.database.tools import seed_tools_catalog
    user_tier = normalize_membership_tier(current_user.get("membership_tier", "free"))
    user_id = current_user.get("user_id")

    loop = asyncio.get_running_loop()
    tools = await loop.run_in_executor(
        None,
        partial(get_tools_for_frontend, user_tier, user_id),
    )
    # Auto-seed if catalog is empty (first request after fresh DB)
    if not tools:
        try:
            await loop.run_in_executor(None, seed_tools_catalog)
            tools = await loop.run_in_executor(
                None,
                partial(get_tools_for_frontend, user_tier, user_id),
            )
        except Exception as e:
            logger.warning(f"[tools] auto-seed failed: {e}")
    return {"tools": tools, "user_tier": user_tier}


@router.get("/api/tools")
async def list_tools(current_user: dict = Depends(get_current_user)):
    return await _list_tools_impl(current_user)


@router.get("/api/user/tools")
async def list_user_tools(current_user: dict = Depends(get_current_user)):
    return await _list_tools_impl(current_user)


class ToolPreferenceRequest(BaseModel):
    is_enabled: bool


async def _set_tool_preference_impl(
    tool_id: str,
    request: ToolPreferenceRequest,
    current_user: dict,
) -> dict:
    """Toggle a tool on/off (premium tier only)."""
    user_tier = normalize_membership_tier(current_user.get("membership_tier", "free"))

    if user_tier != "premium":
        raise HTTPException(status_code=403, detail="Premium 會員才能自訂工具偏好")

    user_id = current_user.get("user_id")
    loop = asyncio.get_running_loop()
    tools = await loop.run_in_executor(
        None,
        partial(get_tools_for_frontend, user_tier, user_id),
    )
    target_tool = next((tool for tool in tools if tool.get("tool_id") == tool_id), None)
    if target_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if target_tool.get("locked"):
        raise HTTPException(status_code=403, detail="目前會員等級無法設定此工具")

    await loop.run_in_executor(
        None,
        partial(update_user_tool_preference, user_id, tool_id, request.is_enabled),
    )

    try:
        from core.agents.bootstrap import invalidate_manager_cache
        invalidate_manager_cache(user_id)
    except Exception as e:
        logger.warning(f"[tools] Failed to invalidate manager cache: {e}")

    return {"success": True, "tool_id": tool_id, "is_enabled": request.is_enabled}


@router.put("/api/tools/{tool_id}/preference")
async def set_tool_preference(
    tool_id: str,
    request: ToolPreferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _set_tool_preference_impl(tool_id, request, current_user)


@router.put("/api/user/tools/{tool_id}/preference")
async def set_user_tool_preference(
    tool_id: str,
    request: ToolPreferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _set_tool_preference_impl(tool_id, request, current_user)
