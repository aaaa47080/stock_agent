"""
Agent 管理 API 端點

提供 Agent 的 CRUD 操作：
- 列出所有 Agent
- 獲取單個 Agent 配置
- 註冊新 Agent
- 更新 Agent 配置
- 刪除 Agent
- 更新 Agent 工具列表
- 重置為預設配置
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from core.agent_registry import agent_registry, AgentConfig
from core.tools import get_available_tool_names

router = APIRouter(prefix="/agents", tags=["Agent Management"])


# ============================================================================
# Request/Response 模型
# ============================================================================

class AgentConfigRequest(BaseModel):
    """Agent 配置請求模型"""
    name: str = Field(..., description="Agent 顯示名稱")
    description: str = Field(..., description="Agent 功能描述")
    tools: List[str] = Field(default_factory=list, description="可用工具 ID 列表")
    keywords: List[str] = Field(default_factory=list, description="關鍵詞匹配列表")
    enabled: bool = Field(default=True, description="是否啟用")
    priority: int = Field(default=10, ge=1, le=100, description="優先級（1-100，數字越小越高）")
    use_debate_system: bool = Field(default=False, description="是否啟用會議討論機制")
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="可選的 LLM 配置覆蓋")


class AgentToolsUpdateRequest(BaseModel):
    """更新 Agent 工具列表請求"""
    tools: List[str] = Field(..., description="新的工具列表")


class AgentResponse(BaseModel):
    """Agent 響應模型"""
    success: bool
    message: str = ""
    agent_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ============================================================================
# API 端點
# ============================================================================

@router.get("/", summary="列出所有 Agent")
async def list_agents(enabled_only: bool = False):
    """
    列出所有 Agent 配置

    Args:
        enabled_only: 是否只返回啟用的 Agent

    Returns:
        Agent 配置字典
    """
    if enabled_only:
        agents = agent_registry.get_enabled_agents()
        return {
            agent_id: config.model_dump()
            for agent_id, config in agents.items()
        }
    return agent_registry.to_dict()


@router.get("/tools", summary="列出所有可用工具")
async def list_available_tools():
    """
    列出所有可用的工具名稱

    Returns:
        工具名稱列表
    """
    return {
        "tools": get_available_tool_names(),
        "count": len(get_available_tool_names())
    }


@router.get("/{agent_id}", summary="獲取單個 Agent 配置")
async def get_agent(agent_id: str):
    """
    獲取指定 Agent 的配置

    Args:
        agent_id: Agent 的唯一識別符

    Returns:
        Agent 配置

    Raises:
        404: Agent 不存在
    """
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )
    return {
        "agent_id": agent_id,
        "config": agent.model_dump()
    }


@router.post("/", summary="註冊新 Agent")
async def register_agent(
    agent_id: str = Body(..., embed=True, description="Agent 唯一 ID"),
    config: AgentConfigRequest = Body(..., description="Agent 配置")
):
    """
    註冊新 Agent（或更新現有 Agent）

    Args:
        agent_id: Agent 的唯一識別符
        config: Agent 配置

    Returns:
        操作結果
    """
    # 驗證工具是否存在
    available_tools = get_available_tool_names()
    invalid_tools = [t for t in config.tools if t not in available_tools]
    if invalid_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tools: {invalid_tools}. Available tools: {available_tools}"
        )

    # 創建 AgentConfig
    agent_config = AgentConfig(
        name=config.name,
        description=config.description,
        tools=config.tools,
        keywords=config.keywords,
        enabled=config.enabled,
        priority=config.priority,
        use_debate_system=config.use_debate_system,
        llm_config=config.llm_config
    )

    # 檢查是否為更新
    existing = agent_registry.get_agent(agent_id)
    is_update = existing is not None

    # 註冊
    success = agent_registry.register_agent(agent_id, agent_config)

    if success:
        return AgentResponse(
            success=True,
            message=f"Agent '{agent_id}' {'updated' if is_update else 'registered'} successfully",
            agent_id=agent_id,
            data=agent_config.model_dump()
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register agent '{agent_id}'"
        )


@router.put("/{agent_id}", summary="更新 Agent 配置")
async def update_agent(
    agent_id: str,
    config: AgentConfigRequest
):
    """
    更新指定 Agent 的配置

    Args:
        agent_id: Agent 的唯一識別符
        config: 新的 Agent 配置

    Returns:
        操作結果

    Raises:
        404: Agent 不存在
    """
    if not agent_registry.get_agent(agent_id):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )

    # 驗證工具
    available_tools = get_available_tool_names()
    invalid_tools = [t for t in config.tools if t not in available_tools]
    if invalid_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tools: {invalid_tools}"
        )

    agent_config = AgentConfig(
        name=config.name,
        description=config.description,
        tools=config.tools,
        keywords=config.keywords,
        enabled=config.enabled,
        priority=config.priority,
        use_debate_system=config.use_debate_system,
        llm_config=config.llm_config
    )

    success = agent_registry.register_agent(agent_id, agent_config)

    if success:
        return AgentResponse(
            success=True,
            message=f"Agent '{agent_id}' updated successfully",
            agent_id=agent_id,
            data=agent_config.model_dump()
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent '{agent_id}'"
        )


@router.delete("/{agent_id}", summary="刪除 Agent")
async def delete_agent(agent_id: str):
    """
    刪除指定 Agent

    Args:
        agent_id: Agent 的唯一識別符

    Returns:
        操作結果

    Raises:
        404: Agent 不存在
    """
    if not agent_registry.get_agent(agent_id):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )

    success = agent_registry.unregister_agent(agent_id)

    if success:
        return AgentResponse(
            success=True,
            message=f"Agent '{agent_id}' deleted successfully",
            agent_id=agent_id
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete agent '{agent_id}'"
        )


@router.patch("/{agent_id}/tools", summary="更新 Agent 工具列表")
async def update_agent_tools(
    agent_id: str,
    request: AgentToolsUpdateRequest
):
    """
    更新指定 Agent 的工具列表

    Args:
        agent_id: Agent 的唯一識別符
        request: 包含新工具列表的請求

    Returns:
        操作結果

    Raises:
        404: Agent 不存在
        400: 無效的工具名稱
    """
    if not agent_registry.get_agent(agent_id):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )

    # 驗證工具
    available_tools = get_available_tool_names()
    invalid_tools = [t for t in request.tools if t not in available_tools]
    if invalid_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tools: {invalid_tools}. Available tools: {available_tools}"
        )

    success = agent_registry.update_agent_tools(agent_id, request.tools)

    if success:
        updated_agent = agent_registry.get_agent(agent_id)
        return AgentResponse(
            success=True,
            message=f"Tools for agent '{agent_id}' updated successfully",
            agent_id=agent_id,
            data={"tools": updated_agent.tools}
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update tools for agent '{agent_id}'"
        )


@router.patch("/{agent_id}/enable", summary="啟用 Agent")
async def enable_agent(agent_id: str):
    """啟用指定 Agent"""
    if not agent_registry.get_agent(agent_id):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )

    success = agent_registry.enable_agent(agent_id)

    if success:
        return AgentResponse(
            success=True,
            message=f"Agent '{agent_id}' enabled",
            agent_id=agent_id
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enable agent '{agent_id}'"
        )


@router.patch("/{agent_id}/disable", summary="禁用 Agent")
async def disable_agent(agent_id: str):
    """禁用指定 Agent"""
    if not agent_registry.get_agent(agent_id):
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )

    success = agent_registry.disable_agent(agent_id)

    if success:
        return AgentResponse(
            success=True,
            message=f"Agent '{agent_id}' disabled",
            agent_id=agent_id
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable agent '{agent_id}'"
        )


@router.post("/reset", summary="重置為預設配置")
async def reset_agents():
    """
    重置所有 Agent 為預設配置

    WARNING: 這將刪除所有自定義 Agent 配置

    Returns:
        操作結果
    """
    agent_registry.reset_to_default()
    return AgentResponse(
        success=True,
        message="All agents reset to default configuration",
        data=agent_registry.to_dict()
    )


@router.get("/{agent_id}/description", summary="獲取 Agent 描述（用於 LLM）")
async def get_agent_description_for_llm(agent_id: str = None):
    """
    獲取格式化的 Agent 描述，用於 LLM 路由決策

    Args:
        agent_id: 可選，如指定則只返回該 Agent 的描述

    Returns:
        格式化的描述文本
    """
    if agent_id:
        agent = agent_registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_id}' not found"
            )
        return {
            "agent_id": agent_id,
            "description": f"**{agent_id}** ({agent.name})\n描述: {agent.description}\n可用工具: {', '.join(agent.tools) if agent.tools else '無'}"
        }

    return {
        "description": agent_registry.get_agent_description_for_llm()
    }
