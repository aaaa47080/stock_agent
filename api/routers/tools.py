"""
Tools API Router

Endpoints for listing tools and managing user tool preferences.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from api.utils import logger, run_sync
from core.database.tools import seed_tools_catalog
from core.orm.tools_repo import _normalize_tier as normalize_membership_tier
from core.orm.tools_repo import tools_repo

router = APIRouter()


async def _list_tools_impl(current_user: dict) -> dict:
    """Return all tools with per-user enabled/locked status."""
    user_tier = normalize_membership_tier(current_user.get("membership_tier", "free"))
    user_id = current_user.get("user_id")

    tools = await tools_repo.get_tools_for_frontend(user_tier, user_id)
    if not tools:
        try:
            await run_sync(seed_tools_catalog)
            tools = await tools_repo.get_tools_for_frontend(user_tier, user_id)
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
    tools = await tools_repo.get_tools_for_frontend(user_tier, user_id)
    target_tool = next((tool for tool in tools if tool.get("tool_id") == tool_id), None)
    if target_tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    if target_tool.get("locked"):
        raise HTTPException(status_code=403, detail="目前會員等級無法設定此工具")

    await tools_repo.update_user_tool_preference(user_id, tool_id, request.is_enabled)

    try:
        from core.agents.bootstrap import invalidate_manager_cache

        invalidate_manager_cache(user_id)
    except Exception as e:
        logger.warning(f"[tools] Failed to invalidate manager cache: {e}")

    return {"success": True, "tool_id": tool_id, "is_enabled": request.is_enabled}


@router.put("/api/tools/{tool_id}/preference")
@limiter.limit("20/minute")
async def set_tool_preference(
    request: Request,
    tool_id: str,
    req: ToolPreferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _set_tool_preference_impl(tool_id, req, current_user)


@router.put("/api/user/tools/{tool_id}/preference")
@limiter.limit("20/minute")
async def set_user_tool_preference(
    request: Request,
    tool_id: str,
    req: ToolPreferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    return await _set_tool_preference_impl(tool_id, req, current_user)
