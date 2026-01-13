"""
Agent 註冊表 - 可配置的 Agent 路由系統
完全依賴 LLM 自主判斷選擇最佳 Agent

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
    enabled: bool = Field(default=True, description="是否啟用")
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
        "description": """處理加密貨幣的快速查詢需求，包括：
        - 即時價格查詢（如「BTC 現在多少錢？」）
        - 技術指標查詢（RSI、MACD、布林帶、均線等）
        - 最新新聞和市場動態
        - 市場脈動解釋（如「為什麼 ETH 漲了？」）
        適合需要快速獲取市場數據的用戶，不涉及深度投資建議。""",
        "tools": [
            "get_current_time_tool",
            "get_crypto_price_tool",
            "technical_analysis_tool",
            "news_analysis_tool",
            "explain_market_movement_tool"
        ],
        "enabled": True,
        "use_debate_system": False
    },

    "deep_crypto_agent": {
        "name": "深層加密貨幣 Agent",
        "description": """處理需要深度分析的投資決策，包括：
        - 完整投資分析（多空辯論、風險評估、交易建議）
        - 歷史策略回測
        - 投資建議和交易計劃
        適合詢問「XXX 可以買嗎？」「應該做多還是做空？」「給我完整分析」等需要深度洞察的問題。
        注意：此 Agent 執行時間較長（30秒-2分鐘）。""",
        "tools": [
            "full_investment_analysis_tool",
            "backtest_strategy_tool"
        ],
        "enabled": True,
        "use_debate_system": True
    },

    "admin_chat_agent": {
        "name": "行政 Agent",
        "description": """處理非加密貨幣相關的一般性問題，包括：
        - 打招呼和閒聊（如「你好」「謝謝」）
        - 系統使用說明和功能介紹
        - 當前時間和日期查詢（如「現在幾點？」「今天星期幾？」）
        - 其他非金融相關的一般性問題
        適合社交互動和系統操作指引。""",
        "tools": [
            "get_current_time_tool"
        ],
        "enabled": True,
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
    - 生成 LLM 路由描述
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

    def get_agent_description_for_llm(self) -> str:
        """
        生成用於 LLM 路由的 Agent 描述文本

        LLM 將根據這些描述自主判斷最適合的 Agent

        Returns:
            格式化的 Agent 描述字符串
        """
        lines = []
        for agent_id, config in self.get_enabled_agents().items():
            lines.append(f"### {agent_id} ({config.name})")
            lines.append(f"{config.description}")
            if config.tools:
                lines.append(f"可用工具: {', '.join(config.tools)}")
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
