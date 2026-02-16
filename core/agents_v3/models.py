"""
Agent V3 資料模型

定義所有 Agent 系統使用的資料結構
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class TaskType(Enum):
    """任務類型"""
    NEWS = "news"                     # 新聞查詢
    TECHNICAL = "technical"           # 技術分析
    SENTIMENT = "sentiment"           # 情緒分析
    GENERAL_CHAT = "general_chat"     # 一般對話
    DEEP_ANALYSIS = "deep_analysis"   # 深度分析（多 agent 協作）
    UNKNOWN = "unknown"               # 未知類型


class AgentState(Enum):
    """Agent 狀態"""
    IDLE = "idle"           # 閒置
    THINKING = "thinking"   # 思考中
    EXECUTING = "executing" # 執行中
    WAITING = "waiting"     # 等待使用者回應
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失敗


class HITLTriggerType(Enum):
    """HITL 觸發類型"""
    INFO_NEEDED = "info_needed"       # 需要更多資訊
    PREFERENCE = "preference"         # 詢問偏好
    CONFIRMATION = "confirmation"     # 確認決策
    SATISFACTION = "satisfaction"     # 滿意度調查
    CLARIFICATION = "clarification"   # 澄清問題


@dataclass
class Task:
    """任務定義"""
    query: str                                    # 使用者查詢
    task_type: TaskType = TaskType.UNKNOWN        # 任務類型
    symbols: List[str] = field(default_factory=list)  # 相關幣種
    context: Dict[str, Any] = field(default_factory=dict)  # 額外上下文
    priority: int = 1                             # 優先級 (1-5)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SubTask:
    """子任務（分配給 Sub-Agent 的任務）"""
    id: str
    task_type: TaskType
    description: str
    symbols: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    assigned_agent: Optional[str] = None
    status: AgentState = AgentState.IDLE


@dataclass
class AgentResult:
    """Agent 執行結果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    agent_name: str = ""
    observations: List[str] = field(default_factory=list)
    needs_more_info: bool = False
    follow_up_question: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "agent_name": self.agent_name,
            "observations": self.observations,
            "needs_more_info": self.needs_more_info,
            "follow_up_question": self.follow_up_question,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Action:
    """Manager Agent 的行動決策"""
    action_type: str  # dispatch, ask_user, finish, think
    agent_name: Optional[str] = None
    task: Optional[SubTask] = None
    question: Optional[str] = None
    question_type: Optional[HITLTriggerType] = None
    reasoning: str = ""
    final_report: Optional[str] = None


@dataclass
class ConversationContext:
    """對話上下文（用於 ReAct 循環）"""
    session_id: str
    original_query: str
    task_type: TaskType = TaskType.UNKNOWN
    symbols: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    agent_results: List[AgentResult] = field(default_factory=list)
    user_inputs: List[str] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 10

    def add_observation(self, observation: str):
        """添加觀察結果"""
        self.observations.append(observation)
        self.iteration_count += 1

    def add_agent_result(self, result: AgentResult):
        """添加 Agent 執行結果"""
        self.agent_results.append(result)
        if result.observations:
            self.observations.extend(result.observations)

    def add_user_input(self, user_input: str):
        """添加使用者輸入"""
        self.user_inputs.append(user_input)

    def is_complete(self) -> bool:
        """判斷是否完成"""
        return self.iteration_count >= self.max_iterations

    def to_prompt_string(self) -> str:
        """轉換為 prompt 格式"""
        parts = [
            f"原始查詢: {self.original_query}",
            f"任務類型: {self.task_type.value}",
            f"相關幣種: {', '.join(self.symbols) if self.symbols else '無'}",
        ]

        if self.observations:
            parts.append("\n觀察記錄:")
            for i, obs in enumerate(self.observations[-10:], 1):  # 最近 10 條
                parts.append(f"  {i}. {obs}")

        if self.agent_results:
            parts.append("\nAgent 執行結果:")
            for result in self.agent_results[-5:]:  # 最近 5 個
                status = "✅" if result.success else "❌"
                parts.append(f"  {status} {result.agent_name}: {result.message}")

        if self.user_inputs:
            parts.append("\n使用者補充資訊:")
            for inp in self.user_inputs[-3:]:  # 最近 3 條
                parts.append(f"  - {inp}")

        return "\n".join(parts)


@dataclass
class ToolInfo:
    """工具資訊"""
    name: str
    description: str
    domains: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "domains": self.domains,
            "parameters": self.parameters
        }
