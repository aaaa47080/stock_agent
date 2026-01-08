"""
Agent 註冊表 - 可配置的 Agent 路由系統
支持配置文件預設 + API 運行時動態修改

使用方式:
    from core.agent_registry import agent_registry

    # 獲取 Agent 配置
    config = agent_registry.get_agent("shallow_crypto_agent")

    # 註冊新 Agent
    agent_registry.register_agent("my_agent", AgentConfig(...))

    # 更新工具列表
    agent_registry.update_agent_tools("my_agent", ["tool1", "tool2"])
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import copy


class AgentConfig(BaseModel):
    """Agent 配置模型"""
    name: str = Field(..., description="Agent 顯示名稱")
    description: str = Field(..., description="Agent 功能描述，用於 LLM 路由判斷")
    tools: List[str] = Field(default_factory=list, description="可用工具 ID 列表")
    keywords: List[str] = Field(default_factory=list, description="關鍵詞匹配（用於快速路由）")
    enabled: bool = Field(default=True, description="是否啟用")
    priority: int = Field(default=10, description="優先級（數字越小越高）")
    use_debate_system: bool = Field(default=False, description="是否啟用完整會議討論機制")
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="可選的 LLM 模型配置覆蓋")

    class Config:
        # 允許額外的字段（向前兼容）
        extra = "allow"


# ============================================================================
# 預設 Agent 配置
# ============================================================================

DEFAULT_AGENT_REGISTRY: Dict[str, dict] = {
    "shallow_crypto_agent": {
        "name": "淺層加密貨幣 Agent",
        "description": "處理加密貨幣簡單相關問題，包括：即時價格查詢、技術指標（RSI、MACD、布林帶、均線等）、最新新聞。適合快速獲取市場數據，不涉及深度投資分析。",
        "tools": [
            "get_crypto_price_tool",
            "technical_analysis_tool",
            "news_analysis_tool"
        ],
        "keywords": [],
        "enabled": True,
        "priority": 1,
        "use_debate_system": False
    },

    "deep_crypto_agent": {
        "name": "深層加密貨幣 Agent",
        "description": "詳細加密貨幣交易對分析，制定相關投資策略，並進行歷史回測。適合需要深入市場洞察和策略建議的用戶。",
        "tools": [
            "full_investment_analysis_tool",
            "backtest_strategy_tool"
        ],
        "keywords": [],
        "enabled": True,
        "priority": 2,
        "use_debate_system": True
    },

    "admin_chat_agent": {
        "name": "行政 Agent",
        "description": "處理一般性閒聊、系統操作問題、使用說明。適合打招呼、詢問系統功能、非金融相關問題。",
        "tools": [],
        "keywords": [
            "你好", "哈囉", "嗨", "早安", "午安", "晚安",
            "謝謝", "感謝", "掰掰", "再見",
            "幫助", "怎麼用", "如何使用", "功能", "介紹",
            "你是誰", "你是什麼", "系統"
        ],
        "enabled": True,
        "priority": 3,
        "use_debate_system": False
    }
}


class AgentRegistry:
    """
    Agent 註冊表管理器

    支持：
    - 預設配置初始化
    - 運行時動態新增/刪除/修改 Agent
    - 工具列表更新
    - 導出為字典格式（用於 API）
    """

    def __init__(self):
        """初始化註冊表，載入預設配置"""
        self._registry: Dict[str, AgentConfig] = {}
        self._load_defaults()

    def _load_defaults(self):
        """載入預設 Agent 配置"""
        for agent_id, config_dict in DEFAULT_AGENT_REGISTRY.items():
            self._registry[agent_id] = AgentConfig(**config_dict)

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """
        獲取 Agent 配置

        Args:
            agent_id: Agent 的唯一識別符

        Returns:
            AgentConfig 或 None（如果不存在）
        """
        return self._registry.get(agent_id)

    def get_enabled_agents(self) -> Dict[str, AgentConfig]:
        """
        獲取所有啟用的 Agent

        Returns:
            啟用的 Agent 字典 {agent_id: AgentConfig}
        """
        return {
            agent_id: config
            for agent_id, config in self._registry.items()
            if config.enabled
        }

    def get_all_agents(self) -> Dict[str, AgentConfig]:
        """
        獲取所有 Agent（包括禁用的）

        Returns:
            所有 Agent 字典 {agent_id: AgentConfig}
        """
        return copy.deepcopy(self._registry)

    def register_agent(self, agent_id: str, config: AgentConfig) -> bool:
        """
        註冊新 Agent（或更新現有 Agent）

        Args:
            agent_id: Agent 的唯一識別符
            config: Agent 配置

        Returns:
            是否成功
        """
        try:
            self._registry[agent_id] = config
            return True
        except Exception as e:
            print(f"Failed to register agent {agent_id}: {e}")
            return False

    def register_agent_from_dict(self, agent_id: str, config_dict: dict) -> bool:
        """
        從字典註冊 Agent（用於 API 請求）

        Args:
            agent_id: Agent 的唯一識別符
            config_dict: Agent 配置字典

        Returns:
            是否成功
        """
        try:
            config = AgentConfig(**config_dict)
            return self.register_agent(agent_id, config)
        except Exception as e:
            print(f"Failed to register agent {agent_id} from dict: {e}")
            return False

    def unregister_agent(self, agent_id: str) -> bool:
        """
        移除 Agent

        Args:
            agent_id: Agent 的唯一識別符

        Returns:
            是否成功（False 表示 Agent 不存在）
        """
        if agent_id in self._registry:
            del self._registry[agent_id]
            return True
        return False

    def update_agent_tools(self, agent_id: str, tools: List[str]) -> bool:
        """
        更新 Agent 的工具列表

        Args:
            agent_id: Agent 的唯一識別符
            tools: 新的工具列表

        Returns:
            是否成功
        """
        if agent_id not in self._registry:
            return False

        # 創建新的配置對象（Pydantic 模型是 immutable 的）
        old_config = self._registry[agent_id]
        new_config_dict = old_config.model_dump()
        new_config_dict["tools"] = tools
        self._registry[agent_id] = AgentConfig(**new_config_dict)
        return True

    def enable_agent(self, agent_id: str) -> bool:
        """啟用 Agent"""
        if agent_id not in self._registry:
            return False

        old_config = self._registry[agent_id]
        new_config_dict = old_config.model_dump()
        new_config_dict["enabled"] = True
        self._registry[agent_id] = AgentConfig(**new_config_dict)
        return True

    def disable_agent(self, agent_id: str) -> bool:
        """禁用 Agent"""
        if agent_id not in self._registry:
            return False

        old_config = self._registry[agent_id]
        new_config_dict = old_config.model_dump()
        new_config_dict["enabled"] = False
        self._registry[agent_id] = AgentConfig(**new_config_dict)
        return True

    def update_agent_priority(self, agent_id: str, priority: int) -> bool:
        """更新 Agent 優先級"""
        if agent_id not in self._registry:
            return False

        old_config = self._registry[agent_id]
        new_config_dict = old_config.model_dump()
        new_config_dict["priority"] = priority
        self._registry[agent_id] = AgentConfig(**new_config_dict)
        return True

    def to_dict(self) -> Dict[str, dict]:
        """
        導出為字典格式（用於 API 響應）

        Returns:
            {agent_id: config_dict} 格式的字典
        """
        return {
            agent_id: config.model_dump()
            for agent_id, config in self._registry.items()
        }

    def reset_to_default(self):
        """重置為預設配置"""
        self._registry.clear()
        self._load_defaults()

    def get_agents_by_priority(self) -> List[tuple]:
        """
        按優先級排序獲取啟用的 Agent

        Returns:
            [(agent_id, AgentConfig), ...] 按優先級排序
        """
        enabled = self.get_enabled_agents()
        return sorted(enabled.items(), key=lambda x: x[1].priority)

    def find_agent_by_keyword(self, message: str) -> Optional[str]:
        """
        通過關鍵詞快速匹配 Agent（用於 fallback）

        Args:
            message: 用戶消息

        Returns:
            匹配的 agent_id 或 None
        """
        message_lower = message.lower()

        # 按優先級順序檢查
        for agent_id, config in self.get_agents_by_priority():
            for keyword in config.keywords:
                if keyword.lower() in message_lower:
                    return agent_id

        return None

    def get_agent_description_for_llm(self) -> str:
        """
        生成用於 LLM 路由的 Agent 描述文本

        Returns:
            格式化的 Agent 描述字符串
        """
        lines = []
        for agent_id, config in self.get_agents_by_priority():
            lines.append(f"- **{agent_id}** ({config.name})")
            lines.append(f"  描述: {config.description}")
            if config.tools:
                lines.append(f"  可用工具: {', '.join(config.tools)}")
            lines.append("")
        return "\n".join(lines)


# ============================================================================
# 全局單例
# ============================================================================

agent_registry = AgentRegistry()


# ============================================================================
# 便捷函數
# ============================================================================

def get_agent_config(agent_id: str) -> Optional[AgentConfig]:
    """獲取 Agent 配置的便捷函數"""
    return agent_registry.get_agent(agent_id)


def get_enabled_agent_ids() -> List[str]:
    """獲取所有啟用的 Agent ID 列表"""
    return list(agent_registry.get_enabled_agents().keys())


def is_debate_agent(agent_id: str) -> bool:
    """檢查 Agent 是否啟用會議討論機制"""
    config = agent_registry.get_agent(agent_id)
    return config.use_debate_system if config else False
