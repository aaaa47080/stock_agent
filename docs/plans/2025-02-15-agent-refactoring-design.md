# Agent 系統重構設計文檔

> 日期：2025-02-15
> 狀態：草案
> 作者：AI + User 協作設計

---

## 1. 背景與動機

### 1.1 現有系統問題

目前的 Agent 系統採用「流程驅動」的多層委員會架構，存在以下問題：

| 問題類型 | 描述 |
|---------|------|
| **缺乏自主性** | Agents 是函數而非智能體，無法自主決策 |
| **流程硬編碼** | 永遠執行固定流程：分析師→辯論→風控 |
| **成本高昂** | 每個 Agent 獨立調用 LLM，重複處理 |
| **狀態膨脹** | LangGraph 狀態對象過大 |
| **無學習能力** | 無法從歷史經驗中學習改進 |
| **用戶參與度低** | AI 單方面輸出，用戶無法介入 |

### 1.2 重構目標

將系統從「流程驅動」轉變為「Agent 驅動」，讓每個 Agent 具備：

1. **工具選擇自主** - 自己決定調用哪些工具
2. **流程參與自主** - 自己決定是否需要參與分析
3. **協作請求自主** - 能主動請求其他 Agent 協助
4. **討論能力** - 能與用戶進行多輪討論達成共識
5. **記憶與學習** - 透過 Codebook 累積經驗

---

## 2. 系統架構

### 2.1 整體架構圖

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                       Orchestrator                            │  │
│  │                            │                                  │  │
│  │        ┌───────────────────┼───────────────────┐             │  │
│  │        ▼                   ▼                   ▼             │  │
│  │  ┌───────────┐      ┌───────────┐      ┌───────────┐        │  │
│  │  │   HITL    │      │ Codebook  │      │Conversation│        │  │
│  │  │  Manager  │◄────►│  Service  │      │  Memory   │        │  │
│  │  └─────┬─────┘      └───────────┘      └───────────┘        │  │
│  │        │                                                      │  │
│  │        ▼                                                      │  │
│  │  ┌───────────┐      ┌───────────┐                            │  │
│  │  │ Discussion│      │ Feedback  │                            │  │
│  │  │  Session  │      │ Collector │                            │  │
│  │  └───────────┘      └───────────┘                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Professional Agents                       │  │
│  │                                                              │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │  │
│  │  │Technical│  │Sentiment│  │  News   │  │Debater  │        │  │
│  │  │ Agent   │  │ Agent   │  │ Agent   │  │ Agent   │        │  │
│  │  │         │  │         │  │         │  │         │        │  │
│  │  │自主工具 │  │自主工具 │  │自主工具 │  │多空整合 │        │  │
│  │  │可討論   │  │可討論   │  │可討論   │  │可討論   │        │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │  │
│  │                                                              │  │
│  │  ┌─────────┐  ┌─────────┐                                   │  │
│  │  │  Risk   │  │ Advisor │                                   │  │
│  │  │ Manager │  │ Agent   │                                   │  │
│  │  └─────────┘  └─────────┘                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Tool Registry                            │  │
│  │   [技術指標] [新聞API] [價格數據] [鏈上數據] [社群情緒]       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      User Interface                           │  │
│  │  [聊天介面] [討論視覺化] [反饋按鈕] [評分系統]               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心組件說明

| 組件 | 職責 |
|------|------|
| **Orchestrator** | 任務解析、Agent 調度、資源分配、衝突解決 |
| **HITL Manager** | Human-in-the-Loop 檢查點管理、用戶介入控制 |
| **Codebook Service** | 經驗存儲、相似案例檢索、學習反饋 |
| **Conversation Memory** | 對話上下文追蹤、主題連續性管理 |
| **Discussion Session** | Agent-用戶討論流程、共識達成機制 |
| **Feedback Collector** | 反饋收集（讚/倒讚、評分、文字） |
| **Tool Registry** | 工具註冊、Agent 自主選擇接口 |
| **Professional Agents** | 各領域專業分析 Agent |

---

## 3. 核心設計

### 3.1 Professional Agent 基類

每個專業 Agent 都繼承此基類，具備完整的自主能力：

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

class AgentState(Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    DISCUSSING = "discussing"
    WAITING_FEEDBACK = "waiting_feedback"
    COMPLETED = "completed"

@dataclass
class Viewpoint:
    """Agent 的分析觀點"""
    content: str                    # 觀點內容
    confidence: float               # 信心度 0-1
    evidence: List[str]             # 支撐證據
    tools_used: List[str]           # 使用的工具
    user_agreed: Optional[bool] = None  # 用戶是否認同

@dataclass
class DiscussionRound:
    """討論回合"""
    speaker: str          # "agent" or "user"
    content: str          # 內容
    type: str             # "proposal", "concern", "revision", "agreement"

class ProfessionalAgent(ABC):
    """專業 Agent 基類"""

    def __init__(
        self,
        expertise: str,
        system_prompt: str,
        personality: str = "balanced"
    ):
        self.expertise = expertise
        self.system_prompt = system_prompt
        self.personality = personality
        self.state = AgentState.IDLE
        self.available_tools: List[Tool] = []
        self.current_viewpoint: Optional[Viewpoint] = None
        self.discussion_history: List[DiscussionRound] = []

    # === 自主能力 1: 工具選擇 ===
    @abstractmethod
    def select_tools(self, task: "Task") -> List["Tool"]:
        """
        自主決定需要哪些工具

        Returns:
            選中的工具列表
        """
        pass

    # === 自主能力 2: 流程參與 ===
    @abstractmethod
    def should_participate(self, task: "Task") -> tuple[bool, str]:
        """
        這個任務需要我參與嗎？

        Returns:
            (是否參與, 原因說明)
        """
        pass

    # === 自主能力 3: 協作請求 ===
    def request_collaboration(
        self,
        other_agent: str,
        reason: str,
        data_needed: str
    ) -> "CollaborationRequest":
        """
        主動請求其他 Agent 協助
        """
        return CollaborationRequest(
            requester=self.expertise,
            target=other_agent,
            reason=reason,
            data_needed=data_needed
        )

    def respond_to_request(
        self,
        request: "CollaborationRequest"
    ) -> "CollaborationResponse":
        """
        回應其他 Agent 的請求
        """
        pass

    # === 自主能力 4: 討論能力 ===
    def propose_viewpoint(self, context: Dict[str, Any]) -> Viewpoint:
        """
        提出分析觀點
        """
        self.state = AgentState.ANALYZING
        # ... 分析邏輯
        return self.current_viewpoint

    def receive_user_feedback(
        self,
        feedback: str,
        agree: bool
    ) -> Optional[Viewpoint]:
        """
        接收用戶反饋，決定是否修正觀點

        Returns:
            如果需要修正，返回新觀點；否則返回 None
        """
        self.state = AgentState.DISCUSSING
        self.discussion_history.append(DiscussionRound(
            speaker="user",
            content=feedback,
            type="concern" if not agree else "agreement"
        ))

        if not agree:
            # 需要修正
            return self._revise_viewpoint(feedback)

        self.current_viewpoint.user_agreed = True
        return None

    def _revise_viewpoint(self, user_concern: str) -> Viewpoint:
        """
        根據用戶反饋修正觀點
        """
        # 可能需要調用更多工具
        additional_tools = self.select_tools_for_concern(user_concern)
        # ... 重新分析
        pass

    # === 自主能力 5: 記憶與學習 ===
    def consult_codebook(
        self,
        situation: "MarketSituation"
    ) -> List["CodebookEntry"]:
        """
        查詢類似情況的歷史經驗
        """
        pass

    def record_experience(
        self,
        situation: "MarketSituation",
        viewpoint: Viewpoint,
        outcome: Optional[str] = None
    ):
        """
        記錄本次經驗到 Codebook
        """
        pass
```

### 3.2 Orchestrator 設計

Orchestrator 負責協調但不硬性控制流程：

```python
class Orchestrator:
    """Agent 協調中心"""

    def __init__(self):
        self.agents: Dict[str, ProfessionalAgent] = {}
        self.hitl_manager = HITLManager()
        self.codebook = CodebookService()
        self.conversation_memory = ConversationMemory()
        self.feedback_collector = FeedbackCollector()

    async def process_query(self, query: str, session_id: str) -> "AnalysisResult":
        """
        處理用戶查詢的主流程
        """
        # 1. 獲取/更新對話上下文
        context = self.conversation_memory.get_or_create(session_id)
        context.update_with_query(query)

        # 2. 解析任務
        task = self._parse_task(query, context)

        # 3. 詢問各 Agent 是否參與
        participants = await self._gather_participants(task)

        # 4. 讓參與者自主執行分析
        viewpoints = await self._run_analysis(participants, task)

        # 5. HITL 檢查點：分析結果確認
        confirmed_viewpoints = await self.hitl_manager.checkpoint(
            session_id,
            HITLCheckpoint.ANALYSIS_REVIEW,
            viewpoints
        )

        # 6. 如有衝突，觸發辯論
        if self._has_conflict(confirmed_viewpoints):
            debate_result = await self._run_debate(confirmed_viewpoints)
            confirmed_viewpoints = await self.hitl_manager.checkpoint(
                session_id,
                HITLCheckpoint.CONFLICT_RESOLUTION,
                debate_result
            )

        # 7. 風險評估與最終建議
        final_recommendation = await self._generate_recommendation(
            confirmed_viewpoints
        )

        # 8. HITL 檢查點：最終決策確認
        result = await self.hitl_manager.checkpoint(
            session_id,
            HITLCheckpoint.FINAL_DECISION,
            final_recommendation
        )

        # 9. 收集反饋
        await self.feedback_collector.request_feedback(session_id, result)

        return result

    async def _gather_participants(self, task: "Task") -> List[ProfessionalAgent]:
        """
        讓 Agents 自主決定是否參與
        """
        participants = []
        for agent in self.agents.values():
            should_join, reason = agent.should_participate(task)
            if should_join:
                participants.append(agent)
        return participants
```

### 3.3 Human-in-the-Loop 設計

```python
class HITLCheckpoint(Enum):
    ANALYSIS_REVIEW = "analysis_review"       # 分析完成後確認
    CONFLICT_RESOLUTION = "conflict"          # 多空衝突時裁決
    FINAL_DECISION = "final_decision"         # 最終決策確認
    CODEBOOK_LEARNING = "codebook_learn"      # 學習反饋

class HITLManager:
    """Human-in-the-Loop 管理器"""

    def __init__(self, config: "HITLConfig" = None):
        self.config = config or HITLConfig()
        self.pending_checkpoints: Dict[str, "Checkpoint"] = {}

    async def checkpoint(
        self,
        session_id: str,
        checkpoint_type: HITLCheckpoint,
        data: Any
    ) -> Any:
        """
        創建檢查點，等待用戶確認
        """
        checkpoint = Checkpoint(
            session_id=session_id,
            type=checkpoint_type,
            data=data,
            options=self._generate_options(checkpoint_type, data)
        )

        self.pending_checkpoints[session_id] = checkpoint

        # 等待用戶回應
        response = await self._wait_for_user_response(
            checkpoint,
            timeout=self.config.timeout_seconds
        )

        return self._process_response(checkpoint, response)

    def _generate_options(
        self,
        checkpoint_type: HITLCheckpoint,
        data: Any
    ) -> List["CheckpointOption"]:
        """
        根據檢查點類型生成用戶選項
        """
        if checkpoint_type == HITLCheckpoint.ANALYSIS_REVIEW:
            return [
                CheckpointOption("全部認同", "accept_all"),
                CheckpointOption("部分認同", "partial"),
                CheckpointOption("想討論某個", "discuss"),
                CheckpointOption("重新分析", "reanalyze"),
            ]
        elif checkpoint_type == HITLCheckpoint.CONFLICT_RESOLUTION:
            return [
                CheckpointOption("同意多方", "bull"),
                CheckpointOption("同意空方", "bear"),
                CheckpointOption("保持中性", "neutral"),
                CheckpointOption("我有不同意見", "custom"),
            ]
        # ... 其他類型

@dataclass
class HITLConfig:
    """HITL 配置"""
    intervention_level: str = "moderate"  # minimal, moderate, active
    timeout_seconds: int = 300
    timeout_action: str = "proceed"       # proceed, abort, ask_again
    discussion_enabled: bool = True
    max_discussion_rounds: int = 5
```

### 3.4 Discussion Session 設計

```python
class DiscussionState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CONSENSUS = "consensus"
    DISAGREE = "disagree"
    TIMEOUT = "timeout"

class DiscussionSession:
    """Agent-用戶 討論會話"""

    def __init__(
        self,
        agent: ProfessionalAgent,
        topic: str,
        max_rounds: int = 5
    ):
        self.agent = agent
        self.topic = topic
        self.max_rounds = max_rounds
        self.state = DiscussionState.PENDING
        self.rounds: List[DiscussionRound] = []
        self.final_viewpoint: Optional[Viewpoint] = None

    def start(self, initial_viewpoint: Viewpoint):
        """
        開始討論，Agent 提出初始觀點
        """
        self.state = DiscussionState.IN_PROGRESS
        self.rounds.append(DiscussionRound(
            speaker="agent",
            content=initial_viewpoint.content,
            type="proposal"
        ))
        return self._render_discussion_ui()

    def user_responds(
        self,
        response: str,
        agree: bool = False
    ) -> "DiscussionResponse":
        """
        用戶回應
        """
        self.rounds.append(DiscussionRound(
            speaker="user",
            content=response,
            type="agreement" if agree else "concern"
        ))

        if agree:
            self.state = DiscussionState.CONSENSUS
            self._record_to_codebook()
            return DiscussionResponse(
                state=self.state,
                message="達成共識！",
                final_viewpoint=self.agent.current_viewpoint
            )

        if len(self.rounds) >= self.max_rounds * 2:
            self.state = DiscussionState.DISAGREE
            return DiscussionResponse(
                state=self.state,
                message="無法達成共識，保留不同意見",
                final_viewpoint=self.agent.current_viewpoint
            )

        # Agent 需要回應
        revised = self.agent.receive_user_feedback(response, agree=False)
        if revised:
            self.rounds.append(DiscussionRound(
                speaker="agent",
                content=f"修正觀點：{revised.content}",
                type="revision"
            ))

        return DiscussionResponse(
            state=self.state,
            discussion_ui=self._render_discussion_ui()
        )

    def _render_discussion_ui(self) -> str:
        """
        生成視覺化討論介面
        """
        lines = [
            f"## 討論主題: {self.topic}",
            f"**狀態**: {self.state.value}",
            f"**參與者**: [{self.agent.expertise}] [用戶]",
            "",
            "### 討論記錄:",
        ]

        for i, round in enumerate(self.rounds, 1):
            speaker = "🤖 Agent" if round.speaker == "agent" else "👤 用戶"
            type_emoji = {
                "proposal": "💡",
                "concern": "❓",
                "revision": "🔄",
                "agreement": "✅"
            }.get(round.type, "")
            lines.append(f"{i}. {speaker} {type_emoji}: {round.content}")

        return "\n".join(lines)
```

### 3.5 Conversation Memory 設計

```python
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

class ConversationMemory:
    """對話記憶管理"""

    def __init__(self):
        self.sessions: Dict[str, ConversationContext] = {}

    def get_or_create(self, session_id: str) -> ConversationContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationContext(session_id)
        return self.sessions[session_id]

    def update_with_query(self, context: ConversationContext, query: str):
        """
        根據新查詢更新上下文
        """
        # 提取幣種
        symbols = self._extract_symbols(query)
        context.symbols_mentioned.extend(symbols)

        # 判斷是否新主題
        if self._is_new_topic(query, context):
            context.main_topic = self._extract_topic(query)

        context.last_activity = datetime.now()

    def get_relevant_context(
        self,
        session_id: str,
        current_query: str
    ) -> Dict[str, Any]:
        """
        獲取與當前查詢相關的歷史上下文
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
```

### 3.6 Feedback Collector 設計

```python
class FeedbackType(Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    DISCUSSION = "discussion"
    RATING = "rating"
    TEXT = "text"
    OUTCOME = "outcome"

@dataclass
class Feedback:
    session_id: str
    agent_type: str
    viewpoint_id: str
    feedback_type: FeedbackType
    value: Any  # bool for thumbs, int for rating, str for text
    timestamp: datetime = field(default_factory=datetime.now)

class FeedbackCollector:
    """反饋收集器"""

    def __init__(self, codebook: "CodebookService"):
        self.codebook = codebook
        self.pending_feedback: Dict[str, List[Feedback]] = {}

    def create_inline_widget(
        self,
        agent_type: str,
        viewpoint_id: str
    ) -> Dict:
        """
        創建內嵌反饋組件（用於 Agent 觀點後）
        """
        return {
            "type": "inline_feedback",
            "agent": agent_type,
            "viewpoint_id": viewpoint_id,
            "options": [
                {"emoji": "👍", "value": "thumbs_up", "label": "認同"},
                {"emoji": "👎", "value": "thumbs_down", "label": "不認同"},
                {"emoji": "💬", "value": "discussion", "label": "想討論"},
            ]
        }

    def create_rating_widget(self, session_id: str) -> Dict:
        """
        創建評分組件（用於最終報告後）
        """
        return {
            "type": "rating",
            "session_id": session_id,
            "max_stars": 5,
            "allow_text": True,
            "prompt": "這份分析對你有幫助嗎？"
        }

    def collect(self, feedback: Feedback):
        """
        收集反饋並存儲
        """
        if feedback.session_id not in self.pending_feedback:
            self.pending_feedback[feedback.session_id] = []
        self.pending_feedback[feedback.session_id].append(feedback)

        # 同步到 Codebook
        self.codebook.record_feedback(feedback)

    async def request_feedback(
        self,
        session_id: str,
        result: "AnalysisResult"
    ):
        """
        請求用戶對分析結果的反饋
        """
        # 返回評分組件給前端
        return self.create_rating_widget(session_id)
```

### 3.7 Codebook 設計

#### 3.7.1 資料庫 Schema

```sql
-- Agent 經驗 Codebook
CREATE TABLE agent_codebook (
    id SERIAL PRIMARY KEY,
    agent_type VARCHAR(50) NOT NULL,

    -- 情境模式
    situation_pattern JSONB NOT NULL,
    -- 例：{
    --   "symbol": "BTC",
    --   "market_condition": {"rsi": [60,70], "trend": "uptrend"},
    --   "timeframe": "4h"
    -- }

    -- 行動與觀點
    action_taken JSONB NOT NULL,
    -- 例：{
    --   "viewpoint": "偏多，建議買入",
    --   "confidence": 0.75,
    --   "tools_used": ["rsi", "macd", "support_resistance"]
    -- }

    -- 結果評估
    outcome_score FLOAT DEFAULT 0.5,
    outcome_count INT DEFAULT 1,

    -- 用戶反饋
    user_feedback JSONB,
    -- 例：{
    --   "agreed": true,
    --   "rating": 4,
    --   "discussion_rounds": 2,
    --   "final_confidence": 0.85
    -- }

    -- 元數據
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 向量嵌入（用於相似度搜索）
    embedding VECTOR(1536)
);

-- 建立向量索引
CREATE INDEX idx_codebook_embedding ON agent_codebook
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 建立情境模式索引
CREATE INDEX idx_codebook_agent_type ON agent_codebook(agent_type);
CREATE INDEX idx_codebook_situation ON agent_codebook USING GIN (situation_pattern);
```

#### 3.7.2 Codebook Service

```python
class CodebookService:
    """Codebook 服務"""

    def __init__(self, db_connection):
        self.db = db_connection

    async def find_similar_cases(
        self,
        agent_type: str,
        situation: "MarketSituation",
        limit: int = 5
    ) -> List["CodebookEntry"]:
        """
        查詢類似情況的歷史經驗
        """
        situation_embedding = self._embed_situation(situation)

        query = """
            SELECT *,
                   1 - (embedding <=> %s) as similarity
            FROM agent_codebook
            WHERE agent_type = %s
            ORDER BY embedding <=> %s
            LIMIT %s
        """

        results = await self.db.fetch(
            query,
            situation_embedding,
            agent_type,
            situation_embedding,
            limit
        )

        return [CodebookEntry.from_row(r) for r in results]

    async def record_experience(
        self,
        agent_type: str,
        situation: "MarketSituation",
        viewpoint: Viewpoint,
        user_feedback: Optional[Dict] = None
    ):
        """
        記錄新經驗
        """
        situation_embedding = self._embed_situation(situation)

        # 檢查是否已有類似記錄
        existing = await self._find_exact_match(agent_type, situation)

        if existing:
            # 更新現有記錄
            await self._update_outcome(existing.id, user_feedback)
        else:
            # 創建新記錄
            await self.db.execute("""
                INSERT INTO agent_codebook
                (agent_type, situation_pattern, action_taken,
                 user_feedback, embedding)
                VALUES (%s, %s, %s, %s, %s)
            """,
                agent_type,
                situation.to_dict(),
                viewpoint.to_dict(),
                user_feedback,
                situation_embedding
            )

    async def _update_outcome(self, entry_id: int, feedback: Dict):
        """
        更新經驗的結果評分
        """
        await self.db.execute("""
            UPDATE agent_codebook
            SET outcome_count = outcome_count + 1,
                outcome_score = (outcome_score * outcome_count + %s)
                               / (outcome_count + 1),
                user_feedback = %s,
                last_used_at = NOW()
            WHERE id = %s
        """,
            1.0 if feedback.get("agreed") else 0.0,
            feedback,
            entry_id
        )

    def _embed_situation(self, situation: "MarketSituation") -> List[float]:
        """
        將情境轉換為向量嵌入
        """
        text = situation.to_search_text()
        return get_embedding(text)  # 使用 OpenAI 或其他 embedding 服務
```

---

## 4. 具體 Agent 設計

### 4.1 Technical Agent

```python
class TechnicalAgent(ProfessionalAgent):
    """技術分析 Agent"""

    def __init__(self):
        super().__init__(
            expertise="technical_analysis",
            system_prompt=TECHNICAL_ANALYST_PROMPT,
            personality="analytical"
        )
        self.available_tools = [
            RSITool(),
            MACDTool(),
            BollingerBandsTool(),
            SupportResistanceTool(),
            BacktestTool(),
        ]

    def select_tools(self, task: Task) -> List[Tool]:
        """
        根據任務自主選擇工具
        """
        tools = []

        # 基礎技術指標總是需要
        tools.extend([
            self._get_tool("rsi"),
            self._get_tool("macd"),
        ])

        # 根據任務類型添加
        if task.analysis_depth == "deep":
            tools.extend([
                self._get_tool("bollinger_bands"),
                self._get_tool("support_resistance"),
            ])

        # 如果涉及策略驗證
        if task.needs_backtest:
            tools.append(self._get_tool("backtest"))

        return tools

    def should_participate(self, task: Task) -> tuple[bool, str]:
        """
        技術分析師幾乎總是參與，但簡單價格查詢可能跳過
        """
        if task.type == "simple_price":
            return False, "簡單價格查詢不需要技術分析"
        return True, "技術分析是投資決策的基礎"
```

### 4.2 News Agent

```python
class NewsAgent(ProfessionalAgent):
    """新聞分析 Agent"""

    def __init__(self):
        super().__init__(
            expertise="news_analysis",
            system_prompt=NEWS_ANALYST_PROMPT,
            personality="cautious"
        )
        self.available_tools = [
            CryptoNewsTool(),
            SocialSentimentTool(),
            EventsCalendarTool(),
        ]

    def select_tools(self, task: Task) -> List[Tool]:
        tools = [self._get_tool("crypto_news")]

        if task.timeframe in ["1d", "1w"]:
            tools.append(self._get_tool("events_calendar"))

        return tools

    def should_participate(self, task: Task) -> tuple[bool, str]:
        # 新聞分析對所有投資決策都很重要
        if task.type == "simple_price":
            return False, "簡單價格查詢不需要新聞分析"
        return True, "新聞事件可能影響市場走勢"
```

### 4.3 Debater Agent

```python
class DebaterAgent(ProfessionalAgent):
    """辯論整合 Agent"""

    def __init__(self):
        super().__init__(
            expertise="debate_synthesis",
            system_prompt=DEBATER_PROMPT,
            personality="balanced"
        )

    def should_participate(self, task: Task) -> tuple[bool, str]:
        # 只有在觀點衝突時才參與
        return False, "等待 Orchestrator 召喚"

    def conduct_debate(
        self,
        viewpoints: Dict[str, Viewpoint]
    ) -> "DebateResult":
        """
        整合多方觀點，進行辯論
        """
        # 識別多空陣營
        bull_views = [v for v in viewpoints.values() if v.bias > 0.3]
        bear_views = [v for v in viewpoints.values() if v.bias < -0.3]

        # 生成辯論
        debate = self._generate_debate(bull_views, bear_views)

        # 總結與建議
        return DebateResult(
            bull_arguments=debate.bull_points,
            bear_arguments=debate.bear_points,
            winner=debate.winner,
            confidence=debate.confidence,
            recommendation=debate.recommendation
        )
```

---

## 5. 用戶介面整合

### 5.1 討論視覺化組件

```javascript
// React 組件範例
function DiscussionPanel({ session }) {
  return (
    <div className="discussion-panel">
      <header>
        <h3>討論主題: {session.topic}</h3>
        <StatusBadge state={session.state} />
      </header>

      <div className="discussion-timeline">
        {session.rounds.map((round, i) => (
          <DiscussionBubble
            key={i}
            speaker={round.speaker}
            type={round.type}
            content={round.content}
          />
        ))}
      </div>

      <div className="discussion-actions">
        <button onClick={() => agree()}>✅ 認同</button>
        <button onClick={() => disagree()}>❌ 不認同</button>
        <button onClick={() => openChat()}>💬 繼續討論</button>
      </div>
    </div>
  );
}
```

### 5.2 反饋組件

```javascript
function InlineFeedback({ agentType, viewpointId, onFeedback }) {
  return (
    <div className="inline-feedback">
      <button onClick={() => onFeedback('thumbs_up')}>👍</button>
      <button onClick={() => onFeedback('thumbs_down')}>👎</button>
      <button onClick={() => onFeedback('discussion')}>💬</button>
    </div>
  );
}

function RatingWidget({ sessionId, onSubmit }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');

  return (
    <div className="rating-widget">
      <p>這份分析對你有幫助嗎？</p>
      <StarRating value={rating} onChange={setRating} />
      <textarea
        placeholder="有什麼建議嗎？（選填）"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <button onClick={() => onSubmit({ rating, comment })}>
        送出反饋
      </button>
    </div>
  );
}
```

---

## 6. 實作計劃

### 6.1 階段劃分

| 階段 | 內容 | 預計產出 |
|------|------|---------|
| **Phase 1** | Agent 基類重構 | ProfessionalAgent 基類、自主決策介面 |
| **Phase 2** | Orchestrator 實現 | 任務解析、Agent 調度核心 |
| **Phase 3** | Conversation Memory | 對話上下文管理 |
| **Phase 4** | Tool Registry | 工具註冊與自主選擇 |
| **Phase 5** | Agent 間通訊 | 協作請求機制 |
| **Phase 6** | Discussion Session | 具象化討論流程 |
| **Phase 7** | HITL Manager | 檢查點與討論整合 |
| **Phase 8** | Feedback Collector | 反饋收集系統 |
| **Phase 9** | Codebook 系統 | 資料庫 Schema、經驗存取 |
| **Phase 10** | 遷移現有 Agents | 逐步替換舊 Agents |
| **Phase 11** | UI 整合 | 討論視覺化、反饋介面 |

### 6.2 技術債務處理

在重構過程中需要處理的現有問題：

1. **agents.py (1600+ 行)** - 拆分為獨立模組
2. **硬編碼 Prompts** - 外部化為配置文件
3. **LangGraph 狀態膨脹** - 使用輕量會話狀態
4. **重複 LLM 調用** - 共享推理結果

---

## 7. 風險與緩解

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| 遷移期間功能中斷 | 高 | 新舊系統並行，逐步切換 |
| 討論流程過長影響體驗 | 中 | 設置最大討論輪數，超時自動繼續 |
| Codebook 向量搜索效能 | 中 | 使用 pgvector 索引優化 |
| 用戶不願參與討論 | 低 | 提供「跳過」選項，預設自動繼續 |

---

## 8. 成功指標

| 指標 | 目標 |
|------|------|
| Agent 自主決策準確率 | > 80% |
| 用戶討論參與率 | > 30% |
| Codebook 案例覆蓋率 | > 70% 常見情境 |
| 用戶滿意度評分 | > 4.0/5.0 |
| 分析結果準確度（事後追蹤） | > 65% |

---

## 9. 附錄

### A. Prompts 配置範例

```yaml
# prompts/technical_analyst.yaml
system_prompt: |
  你是一位專業的技術分析師，擅長使用各種技術指標分析加密貨幣市場。

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

personality_options:
  analytical: "注重數據和邏輯，避免情緒化判斷"
  aggressive: "更願意承擔風險，尋找激進的交易機會"
  conservative: "謹慎行事，優先考慮風險控制"
```

### B. API 接口設計

```python
# 新的 Agent API 設計

@router.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    session_id: str = Depends(get_session_id)
) -> AnalyzeResponse:
    """
    啟動分析流程
    """
    result = await orchestrator.process_query(
        query=request.query,
        session_id=session_id
    )
    return AnalyzeResponse(
        session_id=session_id,
        status="in_progress",
        checkpoints=result.checkpoints
    )

@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest
) -> FeedbackResponse:
    """
    提交用戶反饋
    """
    await feedback_collector.collect(Feedback(**feedback.dict()))
    return FeedbackResponse(status="recorded")

@router.post("/discussion/respond")
async def discussion_respond(
    session_id: str,
    agent_type: str,
    response: DiscussionResponse
) -> DiscussionUpdate:
    """
    用戶在討論中回應
    """
    session = discussion_manager.get_session(session_id, agent_type)
    result = session.user_responds(
        response=response.content,
        agree=response.agree
    )
    return DiscussionUpdate(
        state=result.state,
        discussion_ui=result.discussion_ui
    )
```

---

*文檔版本：1.0*
*最後更新：2025-02-15*
