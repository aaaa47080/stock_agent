"""
Planning Manager - 複雜任務規劃和拆分

Planning Manager 負責：
1. 將複雜任務拆分為可並行執行的子任務（使用 LLM 智能拆分）
2. 規劃子任務的執行順序和依賴關係
3. 追蹤子任務執行狀態

注意：任務複雜度的判斷已由 AdminAgent.analyze_task() 使用 LLM 完成，
本模組不再包含硬編碼的複雜度判斷邏輯。
"""
import json
import re
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

# LangChain Imports
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from core.agent_registry import agent_registry
from utils.llm_client import extract_json_from_response

# ============================================================================
# 數據模型
# ============================================================================

class SubTask(BaseModel):
    """子任務定義"""
    id: str = Field(..., description="子任務唯一 ID")
    description: str = Field(..., description="任務描述")
    assigned_agent: str = Field(..., description="指派的 Agent ID")
    tools_hint: List[str] = Field(default_factory=list, description="建議使用的工具")
    dependencies: List[str] = Field(default_factory=list, description="依賴的其他子任務 ID")
    status: str = Field(default="pending", description="任務狀態: pending, in_progress, completed, failed")
    result: Optional[str] = Field(default=None, description="任務執行結果")
    symbol: Optional[str] = Field(default=None, description="相關的加密貨幣符號")
    priority: int = Field(default=5, description="執行優先級（數字越小越優先）")


class TaskPlan(BaseModel):
    """任務規劃結果"""
    original_question: str = Field(..., description="原始用戶問題")
    is_complex: bool = Field(default=False, description="是否為複雜任務")
    complexity_reason: str = Field(default="", description="複雜度判斷原因")
    subtasks: List[SubTask] = Field(default_factory=list, description="子任務列表")
    execution_strategy: str = Field(default="parallel", description="執行策略: parallel, sequential, mixed")
    estimated_steps: int = Field(default=1, description="預估步驟數")


# ============================================================================
# Planning Manager 主類
# ============================================================================

class PlanningManager:
    """
    複雜任務規劃器

    使用方式:
        planner = PlanningManager(user_llm_client, user_provider)

        # 創建任務計劃（複雜度已由 AdminAgent 判斷）
        plan = planner.create_task_plan(message, symbols, is_complex=True)

        # 或者直接創建子任務
        subtasks = planner.create_subtasks(message, symbols)
    """

    def __init__(
        self,
        user_llm_client: BaseChatModel = None,
        user_provider: str = "openai",
        user_model: str = None,
        verbose: bool = False
    ):
        """
        初始化 Planning Manager

        Args:
            user_llm_client: 用戶提供的 LLM Client (LangChain BaseChatModel)
            user_provider: LLM Provider
            user_model: 用戶選擇的模型名稱
            verbose: 是否顯示詳細日誌
        """
        self.user_llm_client = user_llm_client
        self.user_provider = user_provider
        self.user_model = user_model
        self.verbose = verbose

    # analyze_complexity 已被移除
    # 複雜度判斷現在由 AdminAgent.analyze_task() 使用 LLM 完成
    # 不再使用硬編碼的關鍵詞匹配

    def create_subtasks(
        self,
        message: str,
        symbols: List[str],
        assigned_agent: str = None
    ) -> List[SubTask]:
        """
        將複雜任務拆分為子任務

        Args:
            message: 用戶消息
            symbols: 提取的幣種列表
            assigned_agent: 建議的主要 Agent（可選）

        Returns:
            子任務列表
        """
        # 如果有 LLM client，使用智能拆分
        if self.user_llm_client:
            return self._llm_create_subtasks(message, symbols, assigned_agent)

        # 否則使用規則化拆分
        return self._rule_based_subtasks(message, symbols, assigned_agent)

    def _llm_create_subtasks(
        self,
        message: str,
        symbols: List[str],
        assigned_agent: str = None
    ) -> List[SubTask]:
        """使用 LLM 智能拆分任務"""
        enabled_agents = list(agent_registry.get_enabled_agents().keys())

        system_prompt = f"""你是一個任務規劃專家。你的任務是將用戶的複雜問題拆分為可執行的子任務。

## 可用的 Agent：
{', '.join(enabled_agents)}

## Agent 說明：
- shallow_crypto_agent: 適合快速獲取價格、技術指標、新聞等數據
- deep_crypto_agent: 適合需要深度分析、投資決策、會議討論的任務
- admin_chat_agent: 適合一般閒聊、系統操作

## 拆分原則：
1. 數據獲取類任務可以並行（無依賴）
2. 分析類任務通常依賴數據獲取
3. 比較/綜合類任務依賴各項分析完成
4. 盡量讓獨立任務並行執行以提高效率

## 輸出格式（JSON）：
{{
    "subtasks": [
        {{
            "id": "task_1",
            "description": "獲取 BTC 技術指標",
            "assigned_agent": "shallow_crypto_agent",
            "dependencies": [],
            "symbol": "BTC",
            "priority": 1
        }},
        {{
            "id": "task_2",
            "description": "分析 BTC 投資價值",
            "assigned_agent": "deep_crypto_agent",
            "dependencies": ["task_1"],
            "symbol": "BTC",
            "priority": 2
        }}
    ],
    "execution_strategy": "mixed"
}}

用戶問題涉及的幣種: {', '.join(symbols) if symbols else '無特定幣種'}
"""

        try:
            # LangChain Invoke
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message)
            ]
            
            response = self.user_llm_client.invoke(messages)
            result_text = response.content

            # 解析 JSON
            try:
                result = extract_json_from_response(result_text)
                subtasks = []

                for st in result.get("subtasks", []):
                    # 驗證 agent 是有效的
                    agent = st.get("assigned_agent", "shallow_crypto_agent")
                    if agent not in enabled_agents:
                        agent = "shallow_crypto_agent"

                    subtasks.append(SubTask(
                        id=st.get("id", f"task_{len(subtasks)}"),
                        description=st.get("description", ""),
                        assigned_agent=agent,
                        dependencies=st.get("dependencies", []),
                        symbol=st.get("symbol"),
                        priority=st.get("priority", 5)
                    ))

                return subtasks if subtasks else self._rule_based_subtasks(message, symbols, assigned_agent)

            except Exception:
                if self.verbose:
                    print(f"[PlanningManager] JSON parse error: {result_text[:200]}")
                return self._rule_based_subtasks(message, symbols, assigned_agent)

        except Exception as e:
            if self.verbose:
                print(f"[PlanningManager] LLM error: {e}")
            return self._rule_based_subtasks(message, symbols, assigned_agent)

    def _rule_based_subtasks(
        self,
        message: str,
        symbols: List[str],
        assigned_agent: str = None
    ) -> List[SubTask]:
        """規則化任務拆分（Fallback）"""
        subtasks = []
        message_lower = message.lower()

        # 判斷是否需要深度分析
        needs_deep = any(k in message_lower for k in [
            "投資", "買", "賣", "建議", "策略", "值得", "應該"
        ])

        # 判斷是否需要比較
        needs_comparison = len(symbols) > 1

        # 為每個幣種創建子任務
        for i, symbol in enumerate(symbols):
            # 1. 數據獲取任務（可並行）
            subtasks.append(SubTask(
                id=f"data_{symbol}_{i}",
                description=f"獲取 {symbol} 的價格和技術指標",
                assigned_agent="shallow_crypto_agent",
                dependencies=[],
                symbol=symbol,
                priority=1
            ))

            # 2. 深度分析任務（如果需要）
            if needs_deep:
                subtasks.append(SubTask(
                    id=f"analysis_{symbol}_{i}",
                    description=f"深度分析 {symbol} 的投資價值",
                    assigned_agent="deep_crypto_agent",
                    dependencies=[f"data_{symbol}_{i}"],
                    symbol=symbol,
                    priority=2
                ))

        # 3. 比較任務（如果有多個幣種）
        if needs_comparison and len(symbols) > 1:
            dep_ids = [f"analysis_{s}_{i}" if needs_deep else f"data_{s}_{i}"
                      for i, s in enumerate(symbols)]
            subtasks.append(SubTask(
                id="comparison",
                description=f"比較 {', '.join(symbols)} 的投資價值",
                assigned_agent="shallow_crypto_agent",
                dependencies=dep_ids,
                priority=3
            ))

        return subtasks

    def create_task_plan(
        self,
        message: str,
        symbols: List[str],
        assigned_agent: str = None,
        is_complex: bool = True
    ) -> TaskPlan:
        """
        創建完整的任務計劃

        注意：此方法通常在 AdminAgent 已經使用 LLM 判斷為複雜任務後才被調用，
        因此 is_complex 參數默認為 True。

        Args:
            message: 用戶消息
            symbols: 幣種列表
            assigned_agent: 建議的主要 Agent
            is_complex: 是否為複雜任務（由 AdminAgent.analyze_task() 判斷）

        Returns:
            TaskPlan 對象
        """
        if not is_complex:
            # 簡單任務，不需要拆分
            return TaskPlan(
                original_question=message,
                is_complex=False,
                complexity_reason="簡單查詢，無需拆分",
                subtasks=[],
                execution_strategy="direct",
                estimated_steps=1
            )

        # 複雜任務，創建子任務
        subtasks = self.create_subtasks(message, symbols, assigned_agent)

        # 判斷執行策略
        has_dependencies = any(st.dependencies for st in subtasks)
        if not has_dependencies:
            strategy = "parallel"
        elif all(st.dependencies for st in subtasks[1:]):
            strategy = "sequential"
        else:
            strategy = "mixed"

        # 計算複雜度原因
        reasons = []
        if len(symbols) > 1:
            reasons.append(f"涉及多個幣種（{', '.join(symbols)}）")
        if any(st.assigned_agent == "deep_crypto_agent" for st in subtasks):
            reasons.append("需要深度投資分析")
        if len(subtasks) > 2:
            reasons.append(f"需要多步驟處理（{len(subtasks)} 個子任務）")

        return TaskPlan(
            original_question=message,
            is_complex=True,
            complexity_reason="; ".join(reasons) if reasons else "複雜任務",
            subtasks=subtasks,
            execution_strategy=strategy,
            estimated_steps=len(subtasks)
        )

    def get_executable_subtasks(self, subtasks: List[SubTask]) -> List[SubTask]:
        """
        獲取當前可執行的子任務（依賴已完成）

        Args:
            subtasks: 所有子任務列表

        Returns:
            可執行的子任務列表
        """
        completed_ids = {st.id for st in subtasks if st.status == "completed"}

        executable = []
        for st in subtasks:
            if st.status == "pending":
                # 檢查所有依賴是否已完成
                deps_met = all(dep in completed_ids for dep in st.dependencies)
                if deps_met:
                    executable.append(st)

        # 按優先級排序
        executable.sort(key=lambda x: x.priority)
        return executable

    def update_subtask_status(
        self,
        subtasks: List[SubTask],
        task_id: str,
        status: str,
        result: str = None
    ) -> List[SubTask]:
        """
        更新子任務狀態

        Args:
            subtasks: 子任務列表
            task_id: 要更新的任務 ID
            status: 新狀態
            result: 執行結果（可選）

        Returns:
            更新後的子任務列表
        """
        for st in subtasks:
            if st.id == task_id:
                st.status = status
                if result:
                    st.result = result
                break
        return subtasks

    def is_plan_complete(self, subtasks: List[SubTask]) -> bool:
        """檢查計劃是否已全部完成"""
        return all(st.status in ["completed", "failed"] for st in subtasks)

    def get_plan_summary(self, subtasks: List[SubTask]) -> Dict:
        """獲取計劃執行摘要"""
        total = len(subtasks)
        completed = sum(1 for st in subtasks if st.status == "completed")
        failed = sum(1 for st in subtasks if st.status == "failed")
        pending = sum(1 for st in subtasks if st.status == "pending")
        in_progress = sum(1 for st in subtasks if st.status == "in_progress")

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "in_progress": in_progress,
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }