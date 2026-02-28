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
from api.utils import logger

router = APIRouter()


@router.get("/api/tools")
async def list_tools(current_user: dict = Depends(get_current_user)):
    """Return all tools with per-user enabled/locked status."""
    user_tier = current_user.get("membership_tier", "free")
    user_id   = current_user.get("user_id")
    loop = asyncio.get_running_loop()
    tools = await loop.run_in_executor(
        None,
        partial(get_tools_for_frontend, user_tier, user_id),
    )
    return {"tools": tools, "user_tier": user_tier}


class ToolPreferenceRequest(BaseModel):
    is_enabled: bool


@router.put("/api/tools/{tool_id}/preference")
async def set_tool_preference(
    tool_id: str,
    request: ToolPreferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    """Toggle a tool on/off (Premium only)."""
    user_tier = current_user.get("membership_tier", "free")
    if user_tier != "premium":
        raise HTTPException(status_code=403, detail="Premium 會員才能自訂工具偏好")

    user_id = current_user.get("user_id")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        partial(update_user_tool_preference, user_id, tool_id, request.is_enabled),
    )
    return {"success": True, "tool_id": tool_id, "is_enabled": request.is_enabled}
