"""
Agent Models — Shared data structures

包含：
- 基礎類別（TaskComplexity, CollaborationRequest, AgentResult, SubTask）
- 核心類別（ExecutionMode, TaskNode, TaskGraph, ManagerState 等）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

# ============================================================================
# 基礎類別
# ============================================================================


class TaskComplexity(Enum):
    """任務複雜度"""

    SIMPLE = "simple"
    COMPLEX = "complex"
    AMBIGUOUS = "ambiguous"


@dataclass
class CollaborationRequest:
    """協作請求（基礎）"""

    requesting_agent: str
    needed_agent: str
    context: str
    priority: Literal["required", "optional"]


@dataclass
class AgentResult:
    """Agent 執行結果（基礎）"""

    success: bool
    message: str
    agent_name: str
    data: dict = field(default_factory=dict)
    quality: Literal["pass", "fail"] = "pass"
    quality_fail_reason: Optional[str] = None
    needs_collaboration: Optional[CollaborationRequest] = None


@dataclass
class SubTask:
    """子任務（基礎）"""

    step: int
    description: str
    agent: str
    tool_hint: Optional[str] = None
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[AgentResult] = None
    context: dict = field(default_factory=dict)


# ============================================================================
# 自定義 Reducer（用於 LangGraph 狀態合併）
# ============================================================================

CLEAR_SENTINEL = "__CLEAR__"  # 清除信號


def task_results_reducer(left: Dict | None, right: Dict | None) -> Dict:
    """
    自定義 task_results reducer

    行為：
    - 如果 right 包含 CLEAR_SENTINEL key → 完全替換為 right（清除舊值）
    - 否則 → 合併 left 和 right（預設行為）
    """
    if right is None:
        return left or {}
    if left is None:
        left = {}
    # 檢查清除信號
    if CLEAR_SENTINEL in right:
        # 移除信號後返回新的 dict（完全替換）
        new_dict = {k: v for k, v in right.items() if k != CLEAR_SENTINEL}
        return new_dict
    # 正常合併
    return {**left, **right}


# ============================================================================
# 執行模式
# ============================================================================


class ExecutionMode(Enum):
    """任務執行模式"""

    VENDING = "vending"  # 簡單任務：直接路由，無需複雜規劃
    RESTAURANT = "restaurant"  # 複雜任務：需要規劃、拆解、DAG 執行


class HITLType(Enum):
    """
    Human-in-the-Loop 類型

    簡化設計：
    - 只保留 CONFIRM_PLAN（計劃確認）
    - 其他互動透過自然對話處理
    """

    CONFIRM_PLAN = "confirm_plan"  # 確認計劃：展示計劃請用戶確認


# ============================================================================
# 任務節點（DAG 核心）
# ============================================================================


@dataclass
class TaskNode:
    """
    任務節點 - DAG 的基本單元

    可以是：
    - task: 單一任務（指派給某個 agent）
    - group: 任務組（包含多個 children）
    """

    id: str  # 唯一標識
    name: str  # 任務名稱
    type: Literal["task", "group"]  # 節點類型

    # task 專屬
    agent: Optional[str] = None  # 指派的 agent
    tool_hint: Optional[str] = None  # 工具提示（非強制）
    description: Optional[str] = None  # 任務描述

    # group 專屬
    children: List[TaskNode] = field(default_factory=list)

    # 執行控制
    dependencies: List[str] = field(default_factory=list)  # 依賴的任務 ID
    parallel_group: Optional[str] = None  # 並行組標識（相同標識並行執行）
    execution_strategy: Literal["sequential", "parallel", "auto"] = "auto"
    result_strategy: Literal["last_only", "combine_all", "custom"] = "last_only"

    # 執行狀態
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """驗證節點有效性"""
        if self.type == "task" and not self.agent:
            raise ValueError(f"Task node '{self.id}' must have an agent")
        if self.type == "group" and not self.children:
            raise ValueError(f"Group node '{self.id}' must have children")


@dataclass
class TaskGraph:
    """
    任務圖 - DAG 結構

    負責：
    - 管理所有任務節點
    - 拓撲排序
    - 偵測並行組
    """

    root: TaskNode
    all_nodes: Dict[str, TaskNode] = field(default_factory=dict)

    def __post_init__(self):
        """建立節點索引"""
        self._build_index(self.root)

    def _build_index(self, node: TaskNode):
        """遞迴建立節點索引"""
        self.all_nodes[node.id] = node
        for child in node.children:
            self._build_index(child)

    def get_execution_order(self) -> List[List[TaskNode]]:
        """
        取得執行順序（拓撲排序 + 並行分組）

        Returns:
            List[List[TaskNode]] - 每個內層 List 是可並行執行的任務
        """
        # 計算每個節點的入度
        in_degree = {nid: 0 for nid in self.all_nodes}
        for node in self.all_nodes.values():
            for dep_id in node.dependencies:
                if dep_id in in_degree:
                    in_degree[node.id] += 1

        # BFS 拓撲排序
        result = []
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        while queue:
            # 當前層（無依賴的節點）可並行
            current_level = [self.all_nodes[nid] for nid in queue]
            result.append(current_level)

            # 更新入度
            next_queue = []
            for nid in queue:
                node = self.all_nodes[nid]
                # 找到依賴當前節點的節點
                for other in self.all_nodes.values():
                    if nid in other.dependencies:
                        in_degree[other.id] -= 1
                        if in_degree[other.id] == 0:
                            next_queue.append(other.id)
            queue = next_queue

        return result

    def get_parallel_groups(self) -> Dict[str, List[TaskNode]]:
        """取得所有並行組"""
        groups: Dict[str, List[TaskNode]] = {}
        for node in self.all_nodes.values():
            if node.parallel_group:
                if node.parallel_group not in groups:
                    groups[node.parallel_group] = []
                groups[node.parallel_group].append(node)
        return groups


# ============================================================================
# Agent 上下文（選擇性傳輸）
# ============================================================================


@dataclass
class AgentContext:
    """
    Sub-Agent 接收的上下文

    設計原則：選擇性傳輸
    - 必帶：任務相關資訊
    - 動態帶：有依賴時帶依賴結果
    - 摘要帶：歷史壓縮
    - 不帶：完整歷史
    """

    # === 必帶 ===
    original_query: str  # 原始用戶問題
    task_description: str  # 經理指派的具體任務
    symbols: Dict[str, str]  # 萃取的實體（如 BTC → bitcoin）
    analysis_mode: str = "quick"

    # === 動態帶（有依賴時）===
    dependency_results: Dict[str, Any] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)

    # === 摘要帶（有歷史時）===
    history_summary: Optional[str] = None  # 壓縮後的對話歷史

    # === 元數據 ===
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 短期記憶
# ============================================================================


@dataclass
class MemoryFact:
    """從對話中萃取的事實"""

    key: str  # snake_case，如 preferred_coin
    value: str  # 如 BTC
    source_turn: int  # 來源對話輪次
    confidence: Literal["high", "medium", "low"] = "high"


@dataclass
class ShortTermMemory:
    """
    短期記憶 - 跨對話輪次的狀態保持

    組成：
    - conversation_history: 完整對話歷史
    - context_state: 上下文狀態（用戶偏好、萃取事實）
    - symbol_cache: 符號快取（避免重複解析）
    """

    MAX_CONVERSATION_LENGTH = 100
    MAX_FACTS = 200

    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    context_state: Dict[str, Any] = field(default_factory=dict)
    symbol_cache: Dict[str, str] = field(default_factory=dict)
    facts: List[MemoryFact] = field(default_factory=list)

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > self.MAX_CONVERSATION_LENGTH:
            self.conversation_history = self.conversation_history[
                -self.MAX_CONVERSATION_LENGTH :
            ]

    def get_compressed_history(self, max_turns: int = 10) -> str:
        """取得壓縮後的歷史摘要"""
        if not self.conversation_history:
            return ""

        # 取最近 N 輪
        recent = self.conversation_history[-(max_turns * 2) :]

        # 格式化
        lines = []
        for msg in recent:
            role = "用戶" if msg["role"] == "user" else "助手"
            lines.append(f"{role}: {msg['content'][:200]}")  # 截斷

        return "\n".join(lines)

    def update_symbol(self, user_symbol: str, resolved_symbol: str):
        """更新符號快取"""
        self.symbol_cache[user_symbol.lower()] = resolved_symbol

    def get_symbol(self, user_symbol: str) -> Optional[str]:
        """從快取取得符號"""
        return self.symbol_cache.get(user_symbol.lower())

    def add_fact(self, key: str, value: str, turn: int, confidence: str = "high"):
        """添加萃取事實"""
        # 檢查是否已存在，更新而非重複添加
        for fact in self.facts:
            if fact.key == key:
                fact.value = value
                fact.source_turn = turn
                fact.confidence = confidence
                return
        self.facts.append(MemoryFact(key, value, turn, confidence))
        if len(self.facts) > self.MAX_FACTS:
            self.facts = self.facts[-self.MAX_FACTS :]

    def get_fact(self, key: str) -> Optional[str]:
        """取得事實值"""
        for fact in self.facts:
            if fact.key == key:
                return fact.value
        return None


# ============================================================================
# 意圖理解結果（開放式）
# ============================================================================


@dataclass
class IntentUnderstanding:
    """
    意圖理解結果 - 開放式，無硬編碼類別

    LLM 自由描述：
    - 用戶想解決什麼問題
    - 需要什麼資訊

    注意：移除了 needs_clarification，因為澄清直接在回應中處理
    """

    # 用戶意圖描述
    user_intent: str  # 如 "想了解 BTC 的價格和技術分析"

    # 萃取的實體
    entities: Dict[str, str] = field(default_factory=dict)  # 如 {"symbol": "BTC"}

    # 執行模式
    execution_mode: ExecutionMode = ExecutionMode.VENDING

    # 推斷的 agent 偏好（可選）
    suggested_agent: Optional[str] = None

    # 信心度
    confidence: Literal["high", "medium", "low"] = "high"


# ============================================================================
# 執行結果
# ============================================================================


@dataclass
class TaskResult:
    """任務執行結果"""

    success: bool
    message: str
    agent_name: str
    task_id: str  # 對應的 TaskNode ID
    data: Dict[str, Any] = field(default_factory=dict)

    # 品質評估
    quality: Literal["pass", "fail"] = "pass"
    quality_fail_reason: Optional[str] = None


@dataclass
class ExecutionResult:
    """
    整體執行結果

    支援：
    - 單一結果（vending 模式）
    - 彙總結果（restaurant 模式）
    """

    success: bool
    final_response: str
    mode: ExecutionMode

    # 執行詳情
    task_results: Dict[str, TaskResult] = field(default_factory=dict)

    # 彙總策略
    aggregation_strategy: Literal["last_only", "combine_all", "custom"] = "last_only"


# ============================================================================
# Manager 狀態（LangGraph 用）
# ============================================================================


class ManagerState(TypedDict, total=False):
    """
    LangGraph 狀態包

    包含：
    - session_id, query: 必填
    - intent_understanding: 意圖理解結果
    - execution_mode: 執行模式
    - history, short_term_memory: 對話記憶
    - task_graph, current_task_id: 任務規劃
    - task_results: 執行結果
    - hitl_*: Human-in-the-Loop 相關
    - final_response: 最終輸出
    """

    # === 必填 ===
    session_id: str
    query: str

    # === 意圖理解 ===
    intent_understanding: Optional[Dict]  # IntentUnderstanding 的 dict 形式
    execution_mode: str  # "vending" or "restaurant"
    analysis_mode: str  # "quick" | "verified" | "research"

    # === 記憶 ===
    history: str  # 壓縮後的歷史
    short_term_memory: Optional[Dict]  # ShortTermMemory 的 dict 形式

    # === 規劃 ===
    task_graph: Optional[Dict]  # TaskGraph 的 dict 形式
    current_task_id: Optional[str]  # 當前執行的任務

    # === 執行 ===
    task_results: Annotated[
        Dict, task_results_reducer
    ]  # {task_id: TaskResult} - 使用自定義 reducer
    hitl_type: Optional[str]
    hitl_question: Optional[str]
    hitl_confirmed: Optional[bool]  # HITL 是否已被確認（用於 resume 後跳過 interrupt）

    # === 輸出 ===
    final_response: Optional[str]
    aggregated_response: Optional[str]

    # === 內部狀態 ===
    _processed_query: Optional[str]  # 用於追蹤已處理的查詢，檢測新查詢

    # === 控制 ===
    language: str
