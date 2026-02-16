"""
Agent V3 Sub-Agent 基類

所有專業 Agent 繼承此類，實現自主決策和 ReAct 循環
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from .models import Task, SubTask, AgentResult, AgentState, TaskType
from .tools import BaseTool, ToolResult
from .tool_registry import ToolRegistry
from .hitl import EnhancedHITLManager


@dataclass
class AgentThought:
    """Agent 思考結果"""
    thought: str           # 思考內容
    action: str            # 行動類型 (use_tool, ask_user, finish)
    tool_name: str = ""    # 工具名稱（如果 action 是 use_tool）
    tool_args: Dict = field(default_factory=dict)  # 工具參數
    question: str = ""     # 問題（如果 action 是 ask_user）
    result: str = ""       # 最終結果（如果 action 是 finish）


class SubAgent(ABC):
    """
    Sub-Agent 基類

    所有專業 Agent 繼承此類，實現：
    - should_participate: 判斷是否應該參與當前任務
    - execute: 執行任務（使用 ReAct 模式）
    - get_tools: 返回可用的工具
    """

    REACT_PROMPT = """你是一個專業的 {role}。

你的職責：
{responsibilities}

可用工具：
{tools}

當前任務：{task}
上下文：{context}

請按照 ReAct 格式思考：
1. Thought: 分析當前情況，思考下一步
2. Action: 決定要執行的行動

行動選項：
- use_tool: 使用工具（需指定工具名稱和參數）
- ask_user: 向使用者詢問（需指定問題）
- finish: 完成任務（需提供最終結果）

請以 JSON 格式回覆：
{{
    "thought": "你的思考過程",
    "action": "use_tool|ask_user|finish",
    "tool_name": "工具名稱（如果 action 是 use_tool）",
    "tool_args": {{ "參數名": "參數值" }},
    "question": "問題（如果 action 是 ask_user）",
    "result": "最終結果（如果 action 是 finish）"
}}
"""

    def __init__(
        self,
        llm_client,
        tool_registry: ToolRegistry,
        hitl: EnhancedHITLManager
    ):
        """
        初始化 Sub-Agent

        Args:
            llm_client: LangChain LLM 客戶端
            tool_registry: 工具註冊表
            hitl: HITL Manager
        """
        self.llm = llm_client
        self.tool_registry = tool_registry
        self.hitl = hitl
        self.state = AgentState.IDLE
        self._observations: List[str] = []
        self._max_iterations = 5

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名稱"""
        pass

    @property
    @abstractmethod
    def expertise(self) -> str:
        """專業領域（用於工具分配）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Agent 描述（供 Manager 參考）"""
        pass

    @property
    @abstractmethod
    def responsibilities(self) -> str:
        """職責描述"""
        pass

    @abstractmethod
    def should_participate(self, task: Task) -> Tuple[bool, str]:
        """
        判斷是否應該參與此任務

        Args:
            task: 當前任務

        Returns:
            (should_join: bool, reason: str)
        """
        pass

    def get_tools(self) -> Dict[str, BaseTool]:
        """獲取此 Agent 可用的工具"""
        return self.tool_registry.get_tools_for_domain(self.expertise)

    def execute(self, task: Task) -> AgentResult:
        """
        執行任務

        使用 ReAct 模式：
        1. 思考需要什麼資訊
        2. 調用工具或詢問使用者
        3. 觀察結果
        4. 重複直到完成或達到最大迭代次數

        Args:
            task: 要執行的任務

        Returns:
            執行結果
        """
        self.state = AgentState.THINKING
        self._observations = []
        iteration = 0

        try:
            while iteration < self._max_iterations:
                iteration += 1

                # 思考下一步
                thought = self._think(task)

                # 執行行動
                if thought.action == "use_tool":
                    self.state = AgentState.EXECUTING
                    result = self._use_tool(thought.tool_name, thought.tool_args)

                    if result.success:
                        self._add_observation(f"工具 {thought.tool_name} 執行成功: {result.data}")
                    else:
                        self._add_observation(f"工具 {thought.tool_name} 執行失敗: {result.error}")

                elif thought.action == "ask_user":
                    self.state = AgentState.WAITING
                    if self.hitl and thought.question:
                        response = self.hitl.ask(thought.question)
                        self._add_observation(f"使用者回應: {response}")
                    else:
                        self._add_observation("無法詢問使用者（HITL 未啟用）")

                elif thought.action == "finish":
                    self.state = AgentState.COMPLETED
                    return AgentResult(
                        success=True,
                        message=thought.result,
                        agent_name=self.name,
                        observations=self._observations
                    )

                else:
                    # 未知行動，終止
                    break

            # 達到最大迭代次數
            self.state = AgentState.COMPLETED
            return AgentResult(
                success=True,
                message=self._generate_summary(),
                agent_name=self.name,
                observations=self._observations
            )

        except Exception as e:
            self.state = AgentState.FAILED
            return AgentResult(
                success=False,
                message=f"執行錯誤: {str(e)}",
                agent_name=self.name,
                observations=self._observations
            )

    def _think(self, task: Task) -> AgentThought:
        """
        思考下一步行動

        Args:
            task: 當前任務

        Returns:
            思考結果
        """
        # 構建工具描述
        tools = self.get_tools()
        tools_desc = "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in tools.items()
        ])

        # 構建上下文
        context = "\n".join(self._observations[-5:]) if self._observations else "無"

        prompt = self.REACT_PROMPT.format(
            role=self.description,
            responsibilities=self.responsibilities,
            tools=tools_desc,
            task=task.query,
            context=context
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return self._parse_thought(response.content)
        except Exception as e:
            print(f"[{self.name}] 思考錯誤: {e}")
            return AgentThought(
                thought="思考過程出錯",
                action="finish",
                result="無法完成任務"
            )

    def _use_tool(self, tool_name: str, args: Dict) -> ToolResult:
        """
        使用工具

        Args:
            tool_name: 工具名稱
            args: 工具參數

        Returns:
            工具執行結果
        """
        return self.tool_registry.execute(
            tool_name=tool_name,
            agent_name=self.name,
            **args
        )

    def _add_observation(self, observation: str) -> None:
        """添加觀察結果"""
        self._observations.append(f"[{datetime.now().strftime('%H:%M:%S')}] {observation}")

    def _generate_summary(self) -> str:
        """生成任務摘要"""
        if not self._observations:
            return "任務完成，但沒有觀察記錄"

        return f"任務完成。觀察記錄：{'; '.join(self._observations[-3:])}"

    def _parse_thought(self, content: str) -> AgentThought:
        """解析 LLM 回應為思考結果"""
        import json
        import re

        # 嘗試提取 JSON
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return AgentThought(
                    thought=data.get("thought", ""),
                    action=data.get("action", "finish"),
                    tool_name=data.get("tool_name", ""),
                    tool_args=data.get("tool_args", {}),
                    question=data.get("question", ""),
                    result=data.get("result", "")
                )
            except:
                pass

        # 解析失敗，返回默認值
        return AgentThought(
            thought=content,
            action="finish",
            result="無法解析思考結果"
        )

    def ask_user(self, question: str) -> str:
        """
        通過 HITL 詢問使用者

        Args:
            question: 問題內容

        Returns:
            使用者回應（如果 HITL 未啟用則返回空字串）
        """
        if self.hitl:
            return self.hitl.ask(question)
        return ""

    def get_status(self) -> dict:
        """獲取 Agent 狀態"""
        return {
            "name": self.name,
            "expertise": self.expertise,
            "state": self.state.value,
            "observations_count": len(self._observations)
        }
