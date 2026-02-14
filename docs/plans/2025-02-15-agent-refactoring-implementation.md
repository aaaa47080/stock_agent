# Agent 系統重構實作計劃

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 將現有的流程驅動 Agent 系統重構為 Agent 驅動的智能協作系統，具備自主決策、人機協作、經驗學習能力。

**Architecture:** 採用 Professional Agent 基類 + Orchestrator 協調架構。每個 Agent 具備工具選擇、流程參與、協作請求、討論能力、記憶學習五大自主能力。Orchestrator 負責調度但不硬性控制流程。HITL Manager 提供人機協作檢查點。Codebook Service 負責經驗存儲與檢索。

**Tech Stack:** Python 3.10+, LangChain/LangGraph, PostgreSQL + pgvector, asyncio

---

## Phase 1: Professional Agent 基類

### Task 1.1: 建立基礎資料結構

**Files:**
- Create: `core/agents_v2/__init__.py`
- Create: `core/agents_v2/base.py`
- Create: `core/agents_v2/models.py`
- Create: `tests/agents_v2/__init__.py`
- Create: `tests/agents_v2/test_base.py`

**Step 1: Write the failing test - AgentState enum**

```python
# tests/agents_v2/test_base.py
"""Tests for Professional Agent base classes"""
import pytest
from core.agents_v2.base import AgentState


class TestAgentState:
    """Test AgentState enum values"""

    def test_agent_state_values(self):
        """AgentState should have all required states"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.ANALYZING.value == "analyzing"
        assert AgentState.DISCUSSING.value == "discussing"
        assert AgentState.WAITING_FEEDBACK.value == "waiting_feedback"
        assert AgentState.COMPLETED.value == "completed"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_base.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.agents_v2'"

**Step 3: Create package structure**

```bash
mkdir -p core/agents_v2
mkdir -p tests/agents_v2
touch core/agents_v2/__init__.py
touch tests/agents_v2/__init__.py
```

**Step 4: Write AgentState enum**

```python
# core/agents_v2/base.py
"""Professional Agent base classes and interfaces"""
from enum import Enum


class AgentState(Enum):
    """Agent 運行狀態"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DISCUSSING = "discussing"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_base.py::TestAgentState -v`
Expected: PASS

**Step 6: Commit**

```bash
git add core/agents_v2/ tests/agents_v2/
git commit -m "feat(agents-v2): add AgentState enum"
```

---

### Task 1.2: 建立資料模型

**Files:**
- Modify: `core/agents_v2/models.py`
- Modify: `tests/agents_v2/test_base.py`

**Step 1: Write the failing test - Viewpoint model**

```python
# tests/agents_v2/test_base.py (add to existing file)
from core.agents_v2.models import Viewpoint, DiscussionRound


class TestViewpoint:
    """Test Viewpoint dataclass"""

    def test_viewpoint_creation(self):
        """Viewpoint should be created with required fields"""
        viewpoint = Viewpoint(
            content="BTC 短期偏多",
            confidence=0.75,
            evidence=["RSI 65", "價格高於 MA20"],
            tools_used=["rsi", "macd"]
        )
        assert viewpoint.content == "BTC 短期偏多"
        assert viewpoint.confidence == 0.75
        assert len(viewpoint.evidence) == 2
        assert viewpoint.user_agreed is None

    def test_viewpoint_user_agreed_default(self):
        """user_agreed should default to None"""
        viewpoint = Viewpoint(
            content="test",
            confidence=0.5,
            evidence=[],
            tools_used=[]
        )
        assert viewpoint.user_agreed is None


class TestDiscussionRound:
    """Test DiscussionRound dataclass"""

    def test_discussion_round_creation(self):
        """DiscussionRound should track speaker and content"""
        round_ = DiscussionRound(
            speaker="agent",
            content="我認為技術面偏多",
            type="proposal"
        )
        assert round_.speaker == "agent"
        assert round_.type == "proposal"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_base.py::TestViewpoint -v`
Expected: FAIL with "cannot import name 'Viewpoint'"

**Step 3: Write Viewpoint and DiscussionRound models**

```python
# core/agents_v2/models.py
"""Data models for Professional Agent system"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Viewpoint:
    """Agent 的分析觀點"""
    content: str                    # 觀點內容
    confidence: float               # 信心度 0-1
    evidence: List[str]             # 支撐證據
    tools_used: List[str]           # 使用的工具
    user_agreed: Optional[bool] = None  # 用戶是否認同
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "content": self.content,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "tools_used": self.tools_used,
            "user_agreed": self.user_agreed,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DiscussionRound:
    """討論回合"""
    speaker: str          # "agent" or "user"
    content: str          # 內容
    type: str             # "proposal", "concern", "revision", "agreement"
    timestamp: datetime = field(default_factory=datetime.now)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_base.py::TestViewpoint tests/agents_v2/test_base.py::TestDiscussionRound -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/models.py tests/agents_v2/test_base.py
git commit -m "feat(agents-v2): add Viewpoint and DiscussionRound models"
```

---

### Task 1.3: 建立 ProfessionalAgent 抽象基類

**Files:**
- Modify: `core/agents_v2/base.py`
- Modify: `tests/agents_v2/test_base.py`

**Step 1: Write the failing test - ProfessionalAgent abstract class**

```python
# tests/agents_v2/test_base.py (add to existing file)
from abc import ABC
from core.agents_v2.base import ProfessionalAgent


class TestProfessionalAgent:
    """Test ProfessionalAgent abstract base class"""

    def test_professional_agent_is_abstract(self):
        """ProfessionalAgent should be abstract"""
        assert issubclass(ProfessionalAgent, ABC)

    def test_cannot_instantiate_directly(self):
        """Should not be able to instantiate ProfessionalAgent directly"""
        with pytest.raises(TypeError):
            ProfessionalAgent(
                expertise="test",
                system_prompt="test prompt"
            )

    def test_concrete_implementation_required(self):
        """Concrete implementation must implement abstract methods"""

        class IncompleteAgent(ProfessionalAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent(
                expertise="test",
                system_prompt="test prompt"
            )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_base.py::TestProfessionalAgent -v`
Expected: FAIL with "cannot import name 'ProfessionalAgent'"

**Step 3: Write ProfessionalAgent abstract base class**

```python
# core/agents_v2/base.py (add to existing file)
"""Professional Agent base classes and interfaces"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Viewpoint, DiscussionRound


class AgentState(Enum):
    """Agent 運行狀態"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DISCUSSING = "discussing"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"


class ProfessionalAgent(ABC):
    """
    專業 Agent 抽象基類

    所有專業 Agent 都必須繼承此類，並實現以下自主能力：
    1. 工具選擇 - select_tools()
    2. 流程參與 - should_participate()
    """

    def __init__(
        self,
        expertise: str,
        system_prompt: str,
        personality: str = "balanced"
    ):
        """
        Initialize a Professional Agent.

        Args:
            expertise: 專業領域名稱 (e.g., "technical_analysis")
            system_prompt: 系統提示詞，定義 Agent 的行為
            personality: 分析風格 ("analytical", "aggressive", "conservative", "balanced")
        """
        self.expertise = expertise
        self.system_prompt = system_prompt
        self.personality = personality
        self.state = AgentState.IDLE
        self.available_tools: List[Any] = []
        self.current_viewpoint: Optional["Viewpoint"] = None
        self.discussion_history: List["DiscussionRound"] = []

    # === 自主能力 1: 工具選擇 ===
    @abstractmethod
    def select_tools(self, task: "Task") -> List[Any]:
        """
        自主決定需要哪些工具

        Args:
            task: 當前任務

        Returns:
            選中的工具列表
        """
        pass

    # === 自主能力 2: 流程參與 ===
    @abstractmethod
    def should_participate(self, task: "Task") -> tuple[bool, str]:
        """
        這個任務需要我參與嗎？

        Args:
            task: 當前任務

        Returns:
            (是否參與, 原因說明)
        """
        pass

    def _get_tool(self, tool_name: str) -> Optional[Any]:
        """根據名稱獲取工具"""
        for tool in self.available_tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                return tool
            if hasattr(tool, '__name__') and tool.__name__ == tool_name:
                return tool
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_base.py::TestProfessionalAgent -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/base.py tests/agents_v2/test_base.py
git commit -m "feat(agents-v2): add ProfessionalAgent abstract base class"
```

---

### Task 1.4: 實現具體 Agent 範例 - TechnicalAgent

**Files:**
- Create: `core/agents_v2/technical.py`
- Create: `tests/agents_v2/test_technical.py`
- Create: `core/agents_v2/task.py`

**Step 1: Write the failing test - Task model**

```python
# tests/agents_v2/test_technical.py
"""Tests for Technical Agent"""
import pytest
from core.agents_v2.task import Task, TaskType


class TestTask:
    """Test Task model"""

    def test_task_creation(self):
        """Task should be created with required fields"""
        task = Task(
            query="分析 BTC",
            type=TaskType.ANALYSIS,
            symbols=["BTC"],
            timeframe="4h"
        )
        assert task.query == "分析 BTC"
        assert task.type == TaskType.ANALYSIS
        assert task.symbols == ["BTC"]

    def test_task_simple_price_type(self):
        """Task should support simple_price type"""
        task = Task(
            query="BTC 現價多少",
            type=TaskType.SIMPLE_PRICE,
            symbols=["BTC"]
        )
        assert task.type == TaskType.SIMPLE_PRICE
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_technical.py::TestTask -v`
Expected: FAIL with "cannot import name 'Task'"

**Step 3: Write Task model**

```python
# core/agents_v2/task.py
"""Task models for agent system"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TaskType(Enum):
    """任務類型"""
    SIMPLE_PRICE = "simple_price"       # 簡單價格查詢
    ANALYSIS = "analysis"               # 完整分析
    DEEP_ANALYSIS = "deep_analysis"     # 深度分析（包含辯論）
    DISCUSSION = "discussion"           # 討論模式


@dataclass
class Task:
    """Agent 任務"""
    query: str                                    # 用戶查詢
    type: TaskType                                # 任務類型
    symbols: List[str] = field(default_factory=list)  # 相關幣種
    timeframe: str = "4h"                         # 時間框架
    analysis_depth: str = "normal"                # 分析深度: quick, normal, deep
    needs_backtest: bool = False                  # 是否需要回測
    context: dict = field(default_factory=dict)   # 額外上下文
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_technical.py::TestTask -v`
Expected: PASS

**Step 5: Write TechnicalAgent test**

```python
# tests/agents_v2/test_technical.py (add to existing file)
from core.agents_v2.technical import TechnicalAgent
from core.agents_v2.task import Task, TaskType


class TestTechnicalAgent:
    """Test TechnicalAgent implementation"""

    def test_technical_agent_creation(self):
        """TechnicalAgent should be created with correct expertise"""
        agent = TechnicalAgent()
        assert agent.expertise == "technical_analysis"
        assert agent.personality == "analytical"
        assert agent.state.value == "idle"

    def test_should_participate_for_analysis(self):
        """TechnicalAgent should participate in analysis tasks"""
        agent = TechnicalAgent()
        task = Task(
            query="分析 BTC 技術面",
            type=TaskType.ANALYSIS,
            symbols=["BTC"]
        )
        should_join, reason = agent.should_participate(task)
        assert should_join is True
        assert "技術分析" in reason

    def test_should_not_participate_for_simple_price(self):
        """TechnicalAgent should not participate in simple price queries"""
        agent = TechnicalAgent()
        task = Task(
            query="BTC 現價多少",
            type=TaskType.SIMPLE_PRICE,
            symbols=["BTC"]
        )
        should_join, reason = agent.should_participate(task)
        assert should_join is False
```

**Step 6: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_technical.py::TestTechnicalAgent -v`
Expected: FAIL with "cannot import name 'TechnicalAgent'"

**Step 7: Write TechnicalAgent implementation**

```python
# core/agents_v2/technical.py
"""Technical Analysis Agent"""
from typing import List
from .base import ProfessionalAgent
from .task import Task


# System prompt for technical analyst
TECHNICAL_ANALYST_PROMPT = """你是一位專業的技術分析師，擅長使用各種技術指標分析加密貨幣市場。

你的職責：
1. 分析價格走勢和技術形態
2. 識別支撐位和阻力位
3. 評估市場動量和趨勢強度
4. 提供基於技術面的交易建議

分析風格：{personality}

注意事項：
- 總是基於數據做出判斷
- 承認不確定性，不要過度自信
- 如果用戶有疑問，願意解釋你的分析邏輯
- 如果用戶提出合理的質疑，願意修正你的觀點
"""


class TechnicalAgent(ProfessionalAgent):
    """技術分析 Agent"""

    def __init__(self, llm_client=None):
        super().__init__(
            expertise="technical_analysis",
            system_prompt=TECHNICAL_ANALYST_PROMPT,
            personality="analytical"
        )
        self.llm_client = llm_client
        # 工具將在 Tool Registry 完成後添加
        self.available_tools = []

    def select_tools(self, task: Task) -> List:
        """
        根據任務自主選擇工具

        Args:
            task: 當前任務

        Returns:
            選中的工具列表
        """
        tools = []

        # 基礎技術指標
        rsi_tool = self._get_tool("rsi")
        macd_tool = self._get_tool("macd")
        if rsi_tool:
            tools.append(rsi_tool)
        if macd_tool:
            tools.append(macd_tool)

        # 根據分析深度添加更多工具
        if task.analysis_depth == "deep":
            bb_tool = self._get_tool("bollinger_bands")
            sr_tool = self._get_tool("support_resistance")
            if bb_tool:
                tools.append(bb_tool)
            if sr_tool:
                tools.append(sr_tool)

        # 如果需要回測
        if task.needs_backtest:
            backtest_tool = self._get_tool("backtest")
            if backtest_tool:
                tools.append(backtest_tool)

        return tools

    def should_participate(self, task: Task) -> tuple[bool, str]:
        """
        技術分析師幾乎總是參與，但簡單價格查詢可能跳過

        Args:
            task: 當前任務

        Returns:
            (是否參與, 原因說明)
        """
        if task.type.value == "simple_price":
            return False, "簡單價格查詢不需要技術分析"
        return True, "技術分析是投資決策的基礎"
```

**Step 8: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_technical.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add core/agents_v2/technical.py core/agents_v2/task.py tests/agents_v2/test_technical.py
git commit -m "feat(agents-v2): add Task model and TechnicalAgent implementation"
```

---

## Phase 2: Orchestrator 核心實現

### Task 2.1: 建立 Orchestrator 基礎結構

**Files:**
- Create: `core/agents_v2/orchestrator.py`
- Create: `tests/agents_v2/test_orchestrator.py`

**Step 1: Write the failing test - Orchestrator initialization**

```python
# tests/agents_v2/test_orchestrator.py
"""Tests for Orchestrator"""
import pytest
from core.agents_v2.orchestrator import Orchestrator


class TestOrchestrator:
    """Test Orchestrator class"""

    def test_orchestrator_creation(self):
        """Orchestrator should be created with empty agents"""
        orchestrator = Orchestrator()
        assert orchestrator.agents == {}
        assert orchestrator.conversation_memory is not None

    def test_register_agent(self):
        """Orchestrator should be able to register agents"""
        from core.agents_v2.technical import TechnicalAgent

        orchestrator = Orchestrator()
        agent = TechnicalAgent()
        orchestrator.register_agent(agent)

        assert "technical_analysis" in orchestrator.agents
        assert orchestrator.agents["technical_analysis"] == agent
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_orchestrator.py -v`
Expected: FAIL with "cannot import name 'Orchestrator'"

**Step 3: Write Orchestrator class**

```python
# core/agents_v2/orchestrator.py
"""Agent Orchestrator for coordinating multi-agent analysis"""
from typing import Dict, List, Optional
from .base import ProfessionalAgent


class Orchestrator:
    """
    Agent 協調中心

    職責：
    - 任務解析
    - Agent 調度
    - 資源分配
    - 衝突解決
    - 結果整合

    注意：Orchestrator 協調但不硬性控制流程
    """

    def __init__(self):
        self.agents: Dict[str, ProfessionalAgent] = {}
        self.conversation_memory = None  # 將在 Phase 3 實現
        self.hitl_manager = None         # 將在 Phase 7 實現
        self.codebook = None             # 將在 Phase 9 實現
        self.feedback_collector = None   # 將在 Phase 8 實現

    def register_agent(self, agent: ProfessionalAgent) -> None:
        """
        註冊 Agent 到協調中心

        Args:
            agent: 要註冊的 Agent 實例
        """
        self.agents[agent.expertise] = agent

    def unregister_agent(self, expertise: str) -> bool:
        """
        移除已註冊的 Agent

        Args:
            expertise: Agent 的專業領域

        Returns:
            是否成功移除
        """
        if expertise in self.agents:
            del self.agents[expertise]
            return True
        return False

    def get_agent(self, expertise: str) -> Optional[ProfessionalAgent]:
        """
        根據專業領域獲取 Agent

        Args:
            expertise: 專業領域名稱

        Returns:
            Agent 實例或 None
        """
        return self.agents.get(expertise)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_orchestrator.py::TestOrchestrator -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/orchestrator.py tests/agents_v2/test_orchestrator.py
git commit -m "feat(agents-v2): add Orchestrator base class with agent registration"
```

---

### Task 2.2: 實現任務解析

**Files:**
- Modify: `core/agents_v2/orchestrator.py`
- Modify: `core/agents_v2/task.py`
- Modify: `tests/agents_v2/test_orchestrator.py`

**Step 1: Write the failing test - Task parsing**

```python
# tests/agents_v2/test_orchestrator.py (add to existing file)
from core.agents_v2.task import Task, TaskType


class TestOrchestratorTaskParsing:
    """Test Orchestrator task parsing"""

    def test_parse_simple_price_query(self):
        """Should parse simple price query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("BTC 現價多少")
        assert task.type == TaskType.SIMPLE_PRICE
        assert "BTC" in task.symbols

    def test_parse_analysis_query(self):
        """Should parse analysis query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("分析 ETH 技術面")
        assert task.type == TaskType.ANALYSIS
        assert "ETH" in task.symbols

    def test_parse_deep_analysis_query(self):
        """Should parse deep analysis query correctly"""
        orchestrator = Orchestrator()
        task = orchestrator.parse_task("深度分析 SOL，包含多空辯論")
        assert task.type == TaskType.DEEP_ANALYSIS
        assert "SOL" in task.symbols
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_orchestrator.py::TestOrchestratorTaskParsing -v`
Expected: FAIL with "'Orchestrator' object has no attribute 'parse_task'"

**Step 3: Add parse_task method**

```python
# core/agents_v2/orchestrator.py (add to Orchestrator class)
import re
from .task import Task, TaskType


class Orchestrator:
    # ... existing code ...

    # 常見加密貨幣符號
    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

    def parse_task(self, query: str) -> Task:
        """
        解析用戶查詢為 Task 對象

        Args:
            query: 用戶查詢字符串

        Returns:
            解析後的 Task 對象
        """
        # 提取幣種
        symbols = self._extract_symbols(query)

        # 判斷任務類型
        task_type = self._determine_task_type(query)

        # 判斷分析深度
        analysis_depth = "normal"
        if "深度" in query or "詳細" in query:
            analysis_depth = "deep"
        elif "快速" in query or "簡單" in query:
            analysis_depth = "quick"

        # 是否需要回測
        needs_backtest = "回測" in query or "歷史" in query

        return Task(
            query=query,
            type=task_type,
            symbols=symbols,
            analysis_depth=analysis_depth,
            needs_backtest=needs_backtest
        )

    def _extract_symbols(self, query: str) -> List[str]:
        """從查詢中提取加密貨幣符號"""
        query_upper = query.upper()
        found = []
        for symbol in self.CRYPTO_SYMBOLS:
            if symbol in query_upper:
                found.append(symbol)
        return found if found else ["BTC"]  # 預設 BTC

    def _determine_task_type(self, query: str) -> TaskType:
        """判斷任務類型"""
        query_lower = query.lower()

        # 簡單價格查詢
        if any(kw in query_lower for kw in ["現價", "多少錢", "價格", "多少"]):
            if len(query_lower) < 15:  # 短查詢通常是價格查詢
                return TaskType.SIMPLE_PRICE

        # 深度分析
        if any(kw in query_lower for kw in ["深度", "辯論", "多空", "完整"]):
            return TaskType.DEEP_ANALYSIS

        # 標準分析
        return TaskType.ANALYSIS
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_orchestrator.py::TestOrchestratorTaskParsing -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/orchestrator.py tests/agents_v2/test_orchestrator.py
git commit -m "feat(agents-v2): add task parsing to Orchestrator"
```

---

### Task 2.3: 實現 Agent 參與決策收集

**Files:**
- Modify: `core/agents_v2/orchestrator.py`
- Modify: `tests/agents_v2/test_orchestrator.py`

**Step 1: Write the failing test - gather participants**

```python
# tests/agents_v2/test_orchestrator.py (add to existing file)
from core.agents_v2.technical import TechnicalAgent


class TestOrchestratorGatherParticipants:
    """Test Orchestrator participant gathering"""

    def test_gather_participants_for_analysis(self):
        """Should gather agents that want to participate"""
        orchestrator = Orchestrator()
        orchestrator.register_agent(TechnicalAgent())

        task = Task(
            query="分析 BTC",
            type=TaskType.ANALYSIS,
            symbols=["BTC"]
        )

        participants = orchestrator.gather_participants(task)
        assert len(participants) == 1
        assert participants[0].expertise == "technical_analysis"

    def test_gather_participants_for_simple_price(self):
        """TechnicalAgent should not participate in simple price query"""
        orchestrator = Orchestrator()
        orchestrator.register_agent(TechnicalAgent())

        task = Task(
            query="BTC 現價",
            type=TaskType.SIMPLE_PRICE,
            symbols=["BTC"]
        )

        participants = orchestrator.gather_participants(task)
        assert len(participants) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_orchestrator.py::TestOrchestratorGatherParticipants -v`
Expected: FAIL with "'Orchestrator' object has no attribute 'gather_participants'"

**Step 3: Add gather_participants method**

```python
# core/agents_v2/orchestrator.py (add to Orchestrator class)
from typing import List


class Orchestrator:
    # ... existing code ...

    def gather_participants(self, task: Task) -> List[ProfessionalAgent]:
        """
        讓 Agents 自主決定是否參與

        Args:
            task: 當前任務

        Returns:
            願意參與的 Agent 列表
        """
        participants = []
        for agent in self.agents.values():
            should_join, reason = agent.should_participate(task)
            if should_join:
                participants.append(agent)
                # 可以記錄參與原因用於日誌
        return participants
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_orchestrator.py::TestOrchestratorGatherParticipants -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/orchestrator.py tests/agents_v2/test_orchestrator.py
git commit -m "feat(agents-v2): add gather_participants method to Orchestrator"
```

---

## Phase 3: Conversation Memory

### Task 3.1: 建立 ConversationContext 模型

**Files:**
- Create: `core/agents_v2/memory.py`
- Create: `tests/agents_v2/test_memory.py`

**Step 1: Write the failing test**

```python
# tests/agents_v2/test_memory.py
"""Tests for Conversation Memory"""
import pytest
from datetime import datetime
from core.agents_v2.memory import ConversationContext


class TestConversationContext:
    """Test ConversationContext dataclass"""

    def test_context_creation(self):
        """Context should be created with session_id"""
        context = ConversationContext(session_id="test-123")
        assert context.session_id == "test-123"
        assert context.main_topic is None
        assert context.symbols_mentioned == []

    def test_context_default_values(self):
        """Context should have sensible defaults"""
        context = ConversationContext(session_id="test")
        assert context.analysis_history == []
        assert context.user_preferences == {}
        assert isinstance(context.created_at, datetime)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_memory.py -v`
Expected: FAIL with "cannot import name 'ConversationContext'"

**Step 3: Write ConversationContext model**

```python
# core/agents_v2/memory.py
"""Conversation Memory for tracking context across sessions"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ConversationContext:
    """對話上下文"""
    session_id: str
    main_topic: Optional[str] = None
    symbols_mentioned: List[str] = field(default_factory=list)
    analysis_history: List[Dict] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def touch(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def add_symbol(self, symbol: str):
        """Add a symbol if not already present"""
        if symbol not in self.symbols_mentioned:
            self.symbols_mentioned.append(symbol)
            self.touch()

    def add_analysis(self, analysis: Dict):
        """Add analysis to history"""
        self.analysis_history.append(analysis)
        self.touch()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_memory.py::TestConversationContext -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/memory.py tests/agents_v2/test_memory.py
git commit -m "feat(agents-v2): add ConversationContext model"
```

---

### Task 3.2: 建立 ConversationMemory 服務

**Files:**
- Modify: `core/agents_v2/memory.py`
- Modify: `tests/agents_v2/test_memory.py`

**Step 1: Write the failing test**

```python
# tests/agents_v2/test_memory.py (add to existing file)
from core.agents_v2.memory import ConversationMemory


class TestConversationMemory:
    """Test ConversationMemory service"""

    def test_memory_creation(self):
        """Memory should start empty"""
        memory = ConversationMemory()
        assert memory.sessions == {}

    def test_get_or_create(self):
        """Should create new context if not exists"""
        memory = ConversationMemory()
        context = memory.get_or_create("session-1")
        assert context.session_id == "session-1"
        assert "session-1" in memory.sessions

    def test_get_existing(self):
        """Should return existing context"""
        memory = ConversationMemory()
        context1 = memory.get_or_create("session-1")
        context1.main_topic = "BTC 分析"

        context2 = memory.get_or_create("session-1")
        assert context2.main_topic == "BTC 分析"

    def test_update_with_query(self):
        """Should extract symbols from query"""
        memory = ConversationMemory()
        context = memory.get_or_create("session-1")

        memory.update_with_query(context, "分析 BTC 和 ETH")
        assert "BTC" in context.symbols_mentioned
        assert "ETH" in context.symbols_mentioned
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_memory.py::TestConversationMemory -v`
Expected: FAIL with "cannot import name 'ConversationMemory'"

**Step 3: Write ConversationMemory class**

```python
# core/agents_v2/memory.py (add to existing file)
import re


class ConversationMemory:
    """對話記憶管理服務"""

    # 常見加密貨幣符號
    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

    def __init__(self):
        self.sessions: Dict[str, ConversationContext] = {}

    def get_or_create(self, session_id: str) -> ConversationContext:
        """
        獲取或創建對話上下文

        Args:
            session_id: 會話 ID

        Returns:
            對話上下文
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationContext(session_id)
        return self.sessions[session_id]

    def update_with_query(self, context: ConversationContext, query: str) -> None:
        """
        根據新查詢更新上下文

        Args:
            context: 對話上下文
            query: 用戶查詢
        """
        # 提取幣種
        symbols = self._extract_symbols(query)
        for symbol in symbols:
            context.add_symbol(symbol)

        # 判斷是否新主題
        if self._is_new_topic(query, context):
            context.main_topic = self._extract_topic(query)

        context.touch()

    def get_relevant_context(
        self,
        session_id: str,
        current_query: str = None
    ) -> Dict[str, Any]:
        """
        獲取與當前查詢相關的歷史上下文

        Args:
            session_id: 會話 ID
            current_query: 當前查詢（可選）

        Returns:
            相關上下文字典
        """
        context = self.sessions.get(session_id)
        if not context:
            return {}

        return {
            "main_topic": context.main_topic,
            "symbols": context.symbols_mentioned,
            "recent_analysis": context.analysis_history[-3:],
            "user_preferences": context.user_preferences
        }

    def _extract_symbols(self, query: str) -> List[str]:
        """從查詢中提取加密貨幣符號"""
        query_upper = query.upper()
        found = []
        for symbol in self.CRYPTO_SYMBOLS:
            if symbol in query_upper:
                found.append(symbol)
        return found

    def _is_new_topic(self, query: str, context: ConversationContext) -> bool:
        """判斷是否為新主題"""
        # 簡單實現：如果沒有主題就是新主題
        if not context.main_topic:
            return True

        # 如果查詢中包含「那」「換」等詞，可能是新主題
        new_topic_indicators = ["那", "換", "另一個", "呢"]
        return any(indicator in query for indicator in new_topic_indicators)

    def _extract_topic(self, query: str) -> str:
        """從查詢中提取主題"""
        # 簡單實現：返回查詢的前 50 個字符
        return query[:50] if len(query) > 50 else query
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/memory.py tests/agents_v2/test_memory.py
git commit -m "feat(agents-v2): add ConversationMemory service"
```

---

## Phase 4: Tool Registry

### Task 4.1: 建立 Tool Registry

**Files:**
- Create: `core/agents_v2/tool_registry.py`
- Create: `tests/agents_v2/test_tool_registry.py`

**Step 1: Write the failing test**

```python
# tests/agents_v2/test_tool_registry.py
"""Tests for Tool Registry"""
import pytest
from core.agents_v2.tool_registry import ToolRegistry, ToolInfo


class TestToolInfo:
    """Test ToolInfo dataclass"""

    def test_tool_info_creation(self):
        """ToolInfo should store tool metadata"""
        info = ToolInfo(
            name="rsi",
            description="RSI 技術指標",
            category="technical",
            tool_object=lambda: "rsi_value"
        )
        assert info.name == "rsi"
        assert info.category == "technical"


class TestToolRegistry:
    """Test ToolRegistry"""

    def test_registry_creation(self):
        """Registry should start empty"""
        registry = ToolRegistry()
        assert len(registry.list_tools()) == 0

    def test_register_tool(self):
        """Should be able to register a tool"""
        registry = ToolRegistry()
        registry.register(
            name="rsi",
            description="RSI 指標",
            category="technical",
            tool_object=lambda x: {"rsi": 65}
        )

        tools = registry.list_tools()
        assert len(tools) == 1
        assert "rsi" in tools

    def test_get_tool(self):
        """Should be able to get a registered tool"""
        registry = ToolRegistry()
        registry.register(
            name="rsi",
            description="RSI 指標",
            category="technical",
            tool_object=lambda x: {"rsi": 65}
        )

        tool = registry.get("rsi")
        assert tool is not None
        assert tool.name == "rsi"

    def test_get_by_category(self):
        """Should be able to filter by category"""
        registry = ToolRegistry()
        registry.register("rsi", "RSI", "technical", lambda: None)
        registry.register("news", "新聞", "sentiment", lambda: None)

        tech_tools = registry.get_by_category("technical")
        assert len(tech_tools) == 1
        assert tech_tools[0].name == "rsi"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_tool_registry.py -v`
Expected: FAIL with "cannot import name 'ToolRegistry'"

**Step 3: Write Tool Registry**

```python
# core/agents_v2/tool_registry.py
"""Tool Registry for managing agent tools"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolInfo:
    """工具資訊"""
    name: str
    description: str
    category: str
    tool_object: Any
    parameters: Dict = None
    required_params: List[str] = None


class ToolRegistry:
    """
    工具註冊中心

    管理所有 Agent 可用的工具，支援：
    - 工具註冊與發現
    - 按類別篩選
    - 動態載入
    """

    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}

    def register(
        self,
        name: str,
        description: str,
        category: str,
        tool_object: Any,
        parameters: Dict = None,
        required_params: List[str] = None
    ) -> None:
        """
        註冊工具

        Args:
            name: 工具名稱
            description: 工具描述
            category: 工具類別 (technical, sentiment, news, etc.)
            tool_object: 工具對象或函數
            parameters: 參數定義
            required_params: 必需參數列表
        """
        self._tools[name] = ToolInfo(
            name=name,
            description=description,
            category=category,
            tool_object=tool_object,
            parameters=parameters,
            required_params=required_params or []
        )

    def get(self, name: str) -> Optional[ToolInfo]:
        """
        獲取工具資訊

        Args:
            name: 工具名稱

        Returns:
            ToolInfo 或 None
        """
        return self._tools.get(name)

    def get_tool_object(self, name: str) -> Optional[Any]:
        """
        獲取工具對象

        Args:
            name: 工具名稱

        Returns:
            工具對象或 None
        """
        info = self._tools.get(name)
        return info.tool_object if info else None

    def list_tools(self) -> List[str]:
        """列出所有已註冊的工具名稱"""
        return list(self._tools.keys())

    def get_by_category(self, category: str) -> List[ToolInfo]:
        """
        按類別獲取工具

        Args:
            category: 工具類別

        Returns:
            該類別的工具列表
        """
        return [
            info for info in self._tools.values()
            if info.category == category
        ]

    def get_descriptions(self) -> Dict[str, str]:
        """獲取所有工具的描述"""
        return {
            name: info.description
            for name, info in self._tools.items()
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_tool_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/tool_registry.py tests/agents_v2/test_tool_registry.py
git commit -m "feat(agents-v2): add ToolRegistry for tool management"
```

---

### Task 4.2: 整合現有工具到 Tool Registry

**Files:**
- Modify: `core/agents_v2/tool_registry.py`
- Modify: `tests/agents_v2/test_tool_registry.py`

**Step 1: Write the failing test**

```python
# tests/agents_v2/test_tool_registry.py (add to existing file)


class TestToolRegistryIntegration:
    """Test integration with existing tools"""

    def test_create_from_existing_tools(self):
        """Should be able to create registry from existing tools"""
        # 模擬現有工具
        existing_tools = {
            "technical_analysis_tool": {
                "description": "技術分析",
                "category": "technical"
            },
            "news_analysis_tool": {
                "description": "新聞分析",
                "category": "news"
            }
        }

        registry = ToolRegistry.from_tool_dict(existing_tools)
        assert len(registry.list_tools()) == 2
        assert registry.get("technical_analysis_tool") is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_tool_registry.py::TestToolRegistryIntegration -v`
Expected: FAIL with "'ToolRegistry' object has no attribute 'from_tool_dict'"

**Step 3: Add from_tool_dict class method**

```python
# core/agents_v2/tool_registry.py (add to ToolRegistry class)
from typing import Dict as DictType


class ToolRegistry:
    # ... existing code ...

    @classmethod
    def from_tool_dict(
        cls,
        tools: DictType[str, DictType[str, Any]],
        tool_objects: DictType[str, Any] = None
    ) -> "ToolRegistry":
        """
        從工具字典創建 Registry

        Args:
            tools: 工具定義字典
                   {"tool_name": {"description": "...", "category": "..."}}
            tool_objects: 可選的工具對象字典

        Returns:
            ToolRegistry 實例
        """
        registry = cls()
        tool_objects = tool_objects or {}

        for name, info in tools.items():
            registry.register(
                name=name,
                description=info.get("description", ""),
                category=info.get("category", "general"),
                tool_object=tool_objects.get(name)
            )

        return registry
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_tool_registry.py::TestToolRegistryIntegration -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/tool_registry.py tests/agents_v2/test_tool_registry.py
git commit -m "feat(agents-v2): add from_tool_dict class method to ToolRegistry"
```

---

## Phase 5: Agent 間通訊

### Task 5.1: 建立協作請求模型

**Files:**
- Create: `core/agents_v2/collaboration.py`
- Create: `tests/agents_v2/test_collaboration.py`

**Step 1: Write the failing test**

```python
# tests/agents_v2/test_collaboration.py
"""Tests for Agent Collaboration"""
import pytest
from core.agents_v2.collaboration import CollaborationRequest, CollaborationResponse


class TestCollaborationRequest:
    """Test CollaborationRequest"""

    def test_request_creation(self):
        """Should create collaboration request"""
        request = CollaborationRequest(
            requester="technical_analysis",
            target="sentiment_analysis",
            reason="需要確認市場情緒",
            data_needed="social_sentiment_data"
        )
        assert request.requester == "technical_analysis"
        assert request.target == "sentiment_analysis"
        assert request.status == "pending"


class TestCollaborationResponse:
    """Test CollaborationResponse"""

    def test_response_creation(self):
        """Should create collaboration response"""
        response = CollaborationResponse(
            request_id="req-1",
            responder="sentiment_analysis",
            data={"sentiment": "positive", "score": 0.7},
            accepted=True
        )
        assert response.accepted is True
        assert response.data["sentiment"] == "positive"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents_v2/test_collaboration.py -v`
Expected: FAIL with "cannot import name 'CollaborationRequest'"

**Step 3: Write collaboration models**

```python
# core/agents_v2/collaboration.py
"""Agent Collaboration models and services"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


@dataclass
class CollaborationRequest:
    """Agent 協作請求"""
    requester: str              # 請求方 Agent
    target: str                 # 目標 Agent
    reason: str                 # 請求原因
    data_needed: str            # 需要的數據類型
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "pending"     # pending, accepted, rejected, completed
    created_at: datetime = field(default_factory=datetime.now)

    def accept(self):
        """標記請求為已接受"""
        self.status = "accepted"

    def reject(self):
        """標記請求為已拒絕"""
        self.status = "rejected"

    def complete(self):
        """標記請求為已完成"""
        self.status = "completed"


@dataclass
class CollaborationResponse:
    """Agent 協作回應"""
    request_id: str
    responder: str
    data: Dict[str, Any]
    accepted: bool = True
    message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents_v2/test_collaboraboration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agents_v2/collaboration.py tests/agents_v2/test_collaboration.py
git commit -m "feat(agents-v2): add CollaborationRequest and CollaborationResponse models"
```

---

## Phase 6-11 摘要

由於篇幅限制，以下為後續 Phases 的關鍵任務摘要：

### Phase 6: Discussion Session
- 建立 `DiscussionSession` 類別
- 實現討論狀態機 (pending → in_progress → consensus/disagree)
- 實現 `_render_discussion_ui()` 方法
- 測試多輪討論流程

### Phase 7: HITL Manager
- 建立 `HITLManager` 類別
- 實現 `HITLCheckpoint` 枚舉
- 實現檢查點創建與等待機制
- 整合 Discussion Session

### Phase 8: Feedback Collector
- 建立 `FeedbackCollector` 類別
- 實現 `FeedbackType` 枚舉
- 建立內嵌反饋組件
- 建立評分組件

### Phase 9: Codebook 系統
- 建立資料庫 Schema (`agent_codebook` 表)
- 建立 `CodebookService` 類別
- 實現相似案例檢索（向量搜索）
- 實現經驗記錄與更新

### Phase 10: 遷移現有 Agents
- 建立其他專業 Agent (NewsAgent, SentimentAgent, DebaterAgent, RiskManagerAgent)
- 重構現有 `agents.py` 中的功能
- 整合到 Orchestrator

### Phase 11: UI 整合
- 建立前端討論組件
- 建立反饋組件
- 整合 API 端點

---

## 檔案結構總覽

```
core/agents_v2/
├── __init__.py
├── base.py              # ProfessionalAgent, AgentState
├── models.py            # Viewpoint, DiscussionRound
├── task.py              # Task, TaskType
├── memory.py            # ConversationContext, ConversationMemory
├── tool_registry.py     # ToolRegistry, ToolInfo
├── collaboration.py     # CollaborationRequest, CollaborationResponse
├── discussion.py        # DiscussionSession (Phase 6)
├── hitl.py              # HITLManager, HITLCheckpoint (Phase 7)
├── feedback.py          # FeedbackCollector, Feedback (Phase 8)
├── codebook.py          # CodebookService (Phase 9)
├── orchestrator.py      # Orchestrator
├── technical.py         # TechnicalAgent
├── news.py              # NewsAgent (Phase 10)
├── sentiment.py         # SentimentAgent (Phase 10)
├── debater.py           # DebaterAgent (Phase 10)
└── risk_manager.py      # RiskManagerAgent (Phase 10)

tests/agents_v2/
├── __init__.py
├── test_base.py
├── test_models.py
├── test_task.py
├── test_memory.py
├── test_tool_registry.py
├── test_collaboration.py
├── test_discussion.py (Phase 6)
├── test_hitl.py (Phase 7)
├── test_feedback.py (Phase 8)
├── test_codebook.py (Phase 9)
├── test_technical.py
└── test_orchestrator.py
```

---

## 執行驗證命令

```bash
# 運行所有 Phase 1-5 測試
pytest tests/agents_v2/ -v

# 運行特定 Phase 測試
pytest tests/agents_v2/test_base.py -v
pytest tests/agents_v2/test_orchestrator.py -v
pytest tests/agents_v2/test_memory.py -v
pytest tests/agents_v2/test_tool_registry.py -v
pytest tests/agents_v2/test_collaboration.py -v

# 運行測試覆蓋率
pytest tests/agents_v2/ --cov=core/agents_v2 --cov-report=term-missing
```

---

*計劃版本：1.0*
*建立日期：2025-02-15*
*參考設計文檔：docs/plans/2025-02-15-agent-refactoring-design.md*
