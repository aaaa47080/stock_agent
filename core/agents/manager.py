"""
Agent V4 — Manager Agent (LangGraph Edition)

Orchestrates the agent loop via a LangGraph StateGraph:
  classify → plan → execute → synthesize → feedback

HITL points use interrupt() so web mode can pause/resume properly.
"""
from __future__ import annotations
import json
import re
from uuid import uuid4
from dataclasses import asdict, fields
from datetime import datetime
from typing import Optional, List, Dict
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.utils import logger  # Added logger

from .models import (
    TaskComplexity, SubTask, ExecutionContext,
    AgentResult, CollaborationRequest,
)
from .agent_registry import AgentRegistry
from .tool_registry import ToolRegistry
from .router import AgentRouter
# from .hitl import HITLManager
from .prompt_registry import PromptRegistry
from .watcher import WatcherAgent
from core.tools.universal_resolver import UniversalSymbolResolver

# 模組級共用 checkpointer：跨 bootstrap() 呼叫持久化 session state
_checkpointer = MemorySaver()


AGENT_ICONS: Dict[str, str] = {
    "crypto":        "🪙",
    "tw_stock":      "📈",
    "us_stock":      "🦅",
    "full_analysis": "📊",
    "technical":     "📈",
    "sentiment":     "💬",
    "fundamental":   "🏢",
    "news":          "📰",
    "chat":          "🤖",
}


from typing import Annotated
import operator

class ManagerState(TypedDict):
    """LangGraph 節點間傳遞的狀態包。"""
    # 必填（初始化時提供）
    # Use reducer to prevent "Can receive only one value per step" error during HITL resumes
    session_id: Annotated[str, lambda x, y: y]
    query: str
    # 執行中填入
    complexity: NotRequired[Optional[str]]          # "simple" | "complex" | "ambiguous"
    intent: NotRequired[Optional[str]]
    topics: NotRequired[Optional[List[str]]]
    ambiguity_question: NotRequired[Optional[str]]
    plan: NotRequired[Optional[List[dict]]]         # List[SubTask as dict]
    agent_results: NotRequired[Optional[List[dict]]]
    user_clarifications: NotRequired[Optional[List[str]]]
    retry_count: NotRequired[Optional[int]]
    final_response: NotRequired[Optional[str]]
    plan_confirmed: NotRequired[Optional[bool]]
    history: NotRequired[Optional[str]]             # 從 DB 載入的對話歷史（純文字）
    # 計畫協商（Plan Negotiation HITL）
    plan_negotiating: NotRequired[Optional[bool]]   # 是否進入計畫協商模式
    negotiation_request: NotRequired[Optional[str]] # 用戶的修改請求文字
    negotiation_response: NotRequired[Optional[str]]# LLM 的可行性回應
    negotiate_count: NotRequired[Optional[int]]     # 協商次數（防無限循環）
    current_tool_result: NotRequired[Optional[str]] # 當前協商輪次的工具執行結果
    # Plan Reflection
    plan_reflection_count: NotRequired[Optional[int]]         # how many times reflect_plan has looped
    plan_reflection_suggestion: NotRequired[Optional[str]]    # improvement hint fed back to plan node
    plan_reflection_approved: NotRequired[Optional[bool]]     # True = plan passed quality gate
    # Pre-Research 階段
    research_data: NotRequired[Optional[dict]]           # tool 執行結果
    research_summary: NotRequired[Optional[str]]          # 人類可讀摘要（Markdown）
    research_clarifications: NotRequired[Optional[List[str]]]  # 用戶在 pre_research 補充的方向
    current_step_index: NotRequired[int] # 當前執行步驟索引 (0-based)
    # 語言偏好
    language: NotRequired[Optional[str]]                  # "zh-TW" | "en"
    # 計畫討論（使用者在 HITL 提問，取消計畫後直接回答）
    is_discussion: NotRequired[Optional[bool]]
    discussion_question: NotRequired[Optional[str]]
    # Discuss Mode: free-form Q&A after plan is shown, without re-entering planning
    discuss_mode: NotRequired[Optional[bool]]             # True = discussion mode active
    discuss_plan_snapshot: NotRequired[Optional[List[dict]]]  # frozen plan being discussed
    replan_request: NotRequired[Optional[bool]]           # True = user wants a new plan
    reroute_classify: NotRequired[Optional[bool]]         # True = confirm_plan redirects to classify


class ManagerAgent:
    def __init__(
        self,
        llm_client,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        web_mode: bool = False,
    ):
        self.llm = llm_client
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        # self.hitl = hitl # Removed
        self.router = AgentRouter(agent_registry)
        self.web_mode = web_mode
        self.progress_callback = None
        self.watcher = WatcherAgent(llm_client)
        self.universal_resolver = UniversalSymbolResolver()

        # 編譯 LangGraph
        self.graph = self._build_graph()

    # ── Graph 建構 ──────────────────────────────────────────────────────────

    def _build_graph(self):
        workflow = StateGraph(ManagerState)

        workflow.add_node("classify",       self._classify_node)
        workflow.add_node("clarify",        self._clarify_node)
        workflow.add_node("pre_research",   self._pre_research_node)   # 複雜任務預研究
        workflow.add_node("plan",           self._plan_node)
        workflow.add_node("reflect_plan",   self._reflect_plan_node)  # Plan quality gate
        workflow.add_node("confirm_plan",   self._confirm_plan_node)
        workflow.add_node("negotiate_plan", self._negotiate_plan_node)  # 計畫協商
        workflow.add_node("discuss",        self._discuss_node)         # 計畫討論問題回答
        workflow.add_node("execute",        self._execute_node)
        workflow.add_node("watcher",        self._watcher_node)
        workflow.add_node("synthesize",     self._synthesize_node)

        workflow.set_entry_point("classify")

        workflow.add_conditional_edges("classify", self._after_classify, {
            "clarify":      "clarify",
            "pre_research": "pre_research",   # complex → 先預研究
            "plan":         "plan",           # simple  → 直接規劃
        })
        workflow.add_edge("clarify",      "classify")    # 澄清後重新分類
        workflow.add_conditional_edges("pre_research", self._after_pre_research, {
            "plan": "plan",   # 用戶確認方向 → 進入規劃
            "end": END,       # 用戶提問 → 回答後結束
            "classify": "classify", # 用戶給予全新主題 → 重新分類
        })

        workflow.add_conditional_edges("plan", self._after_plan, {
            "reflect_plan": "reflect_plan",   # complex → quality gate
            "execute":      "execute",        # simple  → direct execute
        })
        workflow.add_conditional_edges("reflect_plan", self._after_reflect_plan, {
            "confirm":  "confirm_plan",   # approved → show to user
            "re_plan":  "plan",           # rejected → re-plan with suggestion
        })
        workflow.add_conditional_edges("confirm_plan", self._after_confirm, {
            "execute":   "execute",
            "negotiate": "negotiate_plan",    # 用戶提出修改 → 協商
            "classify":  "classify",          # 用戶提問 → 取消計畫，走正常 agent 流程
            "discuss":   "discuss",           # 舊版相容（保留）
            "end":       END,
        })
        workflow.add_edge("negotiate_plan", "confirm_plan")  # 協商後回到確認
        workflow.add_edge("discuss",        END)             # 討論回答後儲存結束

        # Execution Loop: execute -> check -> (execute | watcher)
        workflow.add_conditional_edges("execute", self._after_execute, {
            "continue": "execute",
            "done":     "watcher"
        })
        
        workflow.add_edge("watcher",   "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile(checkpointer=_checkpointer)

    # ── 節點實作 ─────────────────────────────────────────────────────────────

    async def _classify_node(self, state: ManagerState) -> dict:
        query = state.get("query", "")

        # ── LLM Classification（含 symbol 萃取）──
        # LLM 一次完成：agent 選擇 + 各市場 symbol 萃取（含代詞解析）
        agents_info = self.agent_registry.agents_info_for_prompt()
        tools_info  = ", ".join([t.name for t in self.tool_registry.list_all_tools()])
        history     = state.get("history") or "（無對話歷史）"
        prompt = PromptRegistry.render(
            "manager", "classify",
            query=query,
            agents_info=agents_info,
            tools_info=tools_info,
            history=history,
        )
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            data = self._parse_json(self._llm_content(response)) or {}
        except Exception as e:
            print(f"[Manager] classify error: {e}")
            data = {"complexity": "simple", "intent": "chat", "topics": []}

        # 相容舊版 prompt 回傳 "agent" 欄位
        intent     = data.get("intent") or data.get("agent", "chat")
        complexity = data.get("complexity", "simple")
        symbols    = data.get("symbols") or {}

        # ── Symbol-based routing（從 LLM 萃取的 symbols 驅動）──
        market_to_agent = {"crypto": "crypto", "tw": "tw_stock", "us": "us_stock"}
        matched = [(m, symbols[m]) for m in ("crypto", "tw", "us") if symbols.get(m)]

        if len(matched) > 1:
            # 多市場：建立確定性 plan，跳過 HITL planning
            steps = [
                {
                    "step": i,
                    "description": f"分析 {sym}",
                    "agent": market_to_agent[mkt],
                    "tool_hint": None,
                }
                for i, (mkt, sym) in enumerate(matched, 1)
            ]
            return {
                "complexity":     "complex",
                "intent":         steps[0]["agent"],
                "topics":         [sym for _, sym in matched],
                "plan":           steps,
                "plan_confirmed": True,
                # Reset reflection state to prevent leakage
                "plan_reflection_count":      0,
                "plan_reflection_suggestion": None,
                "plan_reflection_approved":   None,
            }
        elif len(matched) == 1:
            # 單一市場：覆蓋 intent（LLM 萃取比 agent 選擇更可靠）
            mkt, sym = matched[0]
            intent = market_to_agent[mkt]
            if not data.get("topics"):
                data["topics"] = [sym]

        # 若 LLM 回傳不認識的 agent name，fallback 到 chat
        known_agents = {m.name for m in self.agent_registry.list_all()}
        if intent not in known_agents:
            logger.warning(f"[Classify] Unknown agent '{intent}', falling back to chat")
            intent = "chat"

        replan_request = bool(data.get("replan_request", False))

        # ── Fallback: Force complex for investment queries just in case LLM classify fails ──
        invest_keywords = ["投資", "買進", "進場", "分析", "值得買", "買"]
        if complexity == "simple" and any(k in query for k in invest_keywords) and data.get("topics"):
            logger.info(f"[Classify] Forcing complexity to 'complex' due to investment keywords in query: {query}")
            complexity = "complex"
            if intent == "chat" and symbols:
                if symbols.get("crypto"): intent = "crypto"
                elif symbols.get("tw"): intent = "tw_stock"
                elif symbols.get("us"): intent = "us_stock"

        result = {
            "complexity":                 complexity,
            "intent":                     intent,
            "topics":                     data.get("topics", []),
            "ambiguity_question":         data.get("ambiguity_question"),
            "replan_request":             replan_request,
            "reroute_classify":           False,  # clear flag to prevent loop
            # Reset reflection state for each new query to prevent leakage
            "plan_reflection_count":      0,
            "plan_reflection_suggestion": None,
            "plan_reflection_approved":   None,
        }
        return result

    async def _clarify_node(self, state: ManagerState) -> dict:
        """HITL Point 1：歧義澄清。"""
        question = state.get("ambiguity_question") or "請問您具體想了解什麼？"
        answer = interrupt({
            "type":     "clarification",
            "question": question,
        })
        new_query = f"{state.get('query', '')}\n使用者補充：{answer}"
        clarifications = list(state.get("user_clarifications") or []) + [answer]
        # Reset topics so _classify_node re-derives them from the updated query,
        # preventing stale topics from carrying incorrect symbols into pre_research.
        return {"query": new_query, "user_clarifications": clarifications, "topics": []}

    async def _pre_research_node(self, state: ManagerState) -> dict:
        """Pre-Research 節點：自動收集資料，一次 HITL 讓用戶補充或確認分析方向。"""
        import asyncio
        query  = state.get("query", "")
        topics = state.get("topics") or []
        loop = asyncio.get_running_loop()

        # 1. 從 topics/query 提取主要幣種
        symbol = await self._extract_research_symbol(topics, query)

        # 2. 發送 progress 事件（讓前端顯示「正在收集資料」）
        if self.progress_callback:
            self.progress_callback({"type": "research_start", "symbol": symbol})

        # 3. 自動執行工具（不 interrupt）
        research_data: dict = {}

        news_meta  = self.tool_registry.get("google_news",      caller_agent="manager")
        price_meta = self.tool_registry.get("get_crypto_price", caller_agent="manager")

        if news_meta:
            try:
                # Wrap tool execution
                result = await loop.run_in_executor(None, lambda: news_meta.handler.invoke({"symbol": symbol, "limit": 5}))
                if result:
                    research_data["news"] = result
            except Exception as e:
                print(f"[PreResearch] google_news failed: {e}")

        if price_meta:
            try:
                result = await loop.run_in_executor(None, lambda: price_meta.handler.invoke({"symbol": symbol}))
                if result:
                    research_data["price"] = result
            except Exception as e:
                print(f"[PreResearch] get_crypto_price failed: {e}")

        # 4. 格式化 Markdown 摘要
        research_summary = self._format_research_summary(research_data, symbol)

        # pre_research 靜默完成，不中斷使用者，直接帶著資料進入 plan
        return {
            "research_data":           research_data,
            "research_summary":        research_summary,
            "research_clarifications": list(state.get("research_clarifications") or []),
        }

    async def _answer_research_question(self, question: str, research_summary: str, symbol: str) -> str:
        """用 LLM 根據已收集的研究資料回答用戶的問題。若資料不足，自動用 web_search 補充。"""
        import asyncio
        loop = asyncio.get_running_loop()

        # 先嘗試從現有資料回答，若 LLM 判斷資料不足則補充 web_search
        probe_prompt = PromptRegistry.render(
            "manager", "research_question_probe",
            symbol=symbol,
            research_summary=research_summary,
            question=question
        )
        try:
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=probe_prompt)]))
            raw = self._llm_content(response).strip()

            # 檢查是否需要 web_search
            parsed = self._parse_json(raw)
            if parsed and parsed.get("need_search"):
                search_query = parsed.get("search_query", f"{symbol} {question}")
                ws_tool = self.tool_registry.get("web_search", caller_agent="manager")
                search_result = ""
                if ws_tool:
                    try:
                        sr = await loop.run_in_executor(
                            None, lambda: ws_tool.handler.invoke({"query": search_query, "purpose": "research"})
                        )
                        search_result = str(sr)[:1500]
                    except Exception as e:
                        print(f"[PreResearch] web_search failed: {e}")

                # 有了搜尋結果，重新請 LLM 回答
                final_prompt = PromptRegistry.render(
                    "manager", "research_question_final",
                    question=question,
                    search_result=search_result
                )
                response2 = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=final_prompt)]))
                return self._llm_content(response2).strip()

            return raw
        except Exception as e:
            print(f"[PreResearch] answer_question failed: {e}")
            return "抱歉，暫時無法回答這個問題，請直接開始分析。"

    async def _extract_research_symbol(self, topics: list, query: str) -> str:
        """從 topics 或 query 提取主要交易代號（加密貨幣或股票）。"""
        import asyncio
        loop = asyncio.get_running_loop()
        if topics:
            candidate = topics[0]
        else:
            candidate = query

        try:
            prompt = PromptRegistry.render(
                "manager", "extract_symbol",
                candidate=candidate
            )
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            return self._llm_content(response).strip().upper().split()[0]
        except Exception:
            return candidate.strip().upper().split()[0] if candidate.strip() else "BTC"

    def _format_research_summary(self, research_data: dict, symbol: str) -> str:
        # Pure sync helper, no change needed
        parts = []
        price = research_data.get("price")
        if price:
            price_info = price.get("price_info", "") if isinstance(price, dict) else str(price)
            if price_info:
                parts.append(price_info)

        news = research_data.get("news")
        if news and isinstance(news, list):
            lines = [f"📰 **{symbol} 最新新聞**\n"]
            for i, item in enumerate(news[:5], 1):
                if isinstance(item, dict):
                    title    = item.get("title", "")
                    link     = item.get("url") or item.get("link", "")
                    date_raw = item.get("published_at") or item.get("published", "")
                else:
                    title, link, date_raw = str(item), "", ""
                date_str = f"（{str(date_raw)[:10]}）" if date_raw else ""
                if link:
                    lines.append(f"{i}. [{title}]({link}){date_str}")
                else:
                    lines.append(f"{i}. {title}{date_str}")
            parts.append("\n".join(lines))

        if not parts:
            return f"*（{symbol} 資料暫時無法取得，將直接進行規劃）*"

        return "\n\n".join(parts)

    async def _plan_node(self, state: ManagerState) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        query = state.get("query", "")

        # Multi-market pre-confirmed plan: skip LLM planning
        if state.get("plan_confirmed") and state.get("plan"):
            return {}

        if state.get("complexity") == "simple":
            # Prepend extracted ticker(s) so sub-agents can identify the symbol
            topics = state.get("topics") or []
            ticker_prefix = f"[{' '.join(topics)}] " if topics else ""
            plan = [asdict(SubTask(
                step=1,
                description=f"{ticker_prefix}{query}",
                agent=state.get("intent", "chat"),
                tool_hint=None,
            ))]
            return {"plan": plan, "current_step_index": 0}

        # Complex 任務：強制交由 LLM 動態規劃，不再依賴 Codebook 樣本複製
        agents_info = self.agent_registry.agents_info_for_prompt()
        tools_info  = ", ".join([t.name for t in self.tool_registry.list_all_tools()])

        prompt = PromptRegistry.render(
            "manager", "plan",
            query=query,
            agent=state.get("intent", "chat"),
            topics=", ".join(state.get("topics") or []),
            clarifications="; ".join(state.get("user_clarifications") or []) or "無",
            past_experience="無",
            agents_info=agents_info,
            tools_info=tools_info,
            research_summary=state.get("research_summary") or "無",
            research_clarifications="; ".join(state.get("research_clarifications") or []) or "無",
            reflection_suggestion=state.get("plan_reflection_suggestion") or "無",
            discussion_summary=state.get("discussion_summary") or "無",
        )
        try:
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            data = self._parse_json(self._llm_content(response)) or {}
            plan_raw = data.get("plan", [])
            valid_fields = {f.name for f in fields(SubTask)}
            plan = []
            # 注入 [TOPIC] 前綴，讓 sub-agent 能直接取得 symbol，避免 fallback 到 BTC
            topics = state.get("topics") or []
            ticker_prefix = f"[{' '.join(topics)}] " if topics else ""
            for p in plan_raw:
                task_data = {k: v for k, v in p.items() if k in valid_fields}
                subtask = SubTask(**task_data)
                if ticker_prefix and not subtask.description.startswith("["):
                    subtask.description = ticker_prefix + subtask.description
                plan.append(asdict(subtask))
        except Exception as e:
            import traceback
            print(f"[Manager] plan error: {e}\n{traceback.format_exc()}")
            plan = []

        # 若計畫為空（LLM 回傳空陣列或解析失敗），建立預設單步計畫
        if not plan:
            plan = [asdict(SubTask(
                step=1, description=state["query"],
                agent=state.get("intent", "chat"), tool_hint=None
            ))]

        return {"plan": plan, "current_step_index": 0}

    async def _reflect_plan_node(self, state: ManagerState) -> dict:
        """Reflection quality gate: checks whether the plan actually answers the user's query.
        Only runs for complex queries. Simple queries are approved immediately.
        """
        import asyncio
        from core.config import PLAN_REFLECTION_MAX_RETRIES

        # Simple queries — skip reflection, approve immediately
        if state.get("complexity") != "complex":
            return {"plan_reflection_approved": True}

        # Pre-confirmed plans (multi-market) — skip reflection
        if state.get("plan_confirmed"):
            return {"plan_reflection_approved": True}

        loop = asyncio.get_running_loop()
        query               = state.get("query", "")
        plan                = state.get("plan") or []
        history             = state.get("history") or "（無）"
        topics              = ", ".join(state.get("topics") or []) or "未知"
        clarifications      = "; ".join(state.get("user_clarifications") or []) or "無"
        previous_suggestion = state.get("plan_reflection_suggestion") or "無"
        agents_info         = self.agent_registry.agents_info_for_prompt()

        plan_text = "\n".join(
            f"{p.get('step', i + 1)}. [{p.get('agent', '')}] {p.get('description', '')}"
            for i, p in enumerate(plan)
        )

        prompt = PromptRegistry.render(
            "manager", "reflect_plan",
            query=query,
            history=history,
            topics=topics,
            clarifications=clarifications,
            plan_text=plan_text,
            agents_info=agents_info,
            previous_suggestion=previous_suggestion,
        )

        approved = True
        suggestion = None
        try:
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke([HumanMessage(content=prompt)])
            )
            data       = self._parse_json(self._llm_content(response)) or {}
            if not data:
                logger.warning("[Reflect] LLM returned unparseable JSON, auto-approving")
            approved   = bool(data.get("approved", True))
            suggestion = data.get("suggestion") or None
            reason     = data.get("reason", "")
            logger.info(f"[Reflect] approved={approved} reason={reason}")
        except Exception as e:
            logger.warning(f"[Reflect] reflection error, auto-approving: {e}")

        count = state.get("plan_reflection_count", 0) or 0
        if not approved:
            count += 1

        return {
            "plan_reflection_approved":   approved,
            "plan_reflection_count":      count,
            "plan_reflection_suggestion": suggestion if not approved else None,
        }

    async def _confirm_plan_node(self, state: ManagerState) -> dict:
        """HITL Point 2：複雜任務計畫確認（支援協商模式）。"""
        plan = state.get("plan") or []
        negotiation_response = state.get("negotiation_response")

        plan_with_icons = [
            {**t, "icon": AGENT_ICONS.get(t.get("agent", ""), "🔧")}
            for t in plan
        ]

        interrupt_payload = {
            "type":    "confirm_plan",
            "message": "針對您的問題，我規劃了以下分析步驟：",
            "plan":    plan_with_icons,
        }
        if negotiation_response:
            interrupt_payload["negotiation_response"] = negotiation_response

        interrupt_payload["negotiation_limit_reached"] = (state.get("negotiate_count", 0) > 3)

        answer = interrupt(interrupt_payload)

        parsed = answer
        if isinstance(answer, str):
            stripped = answer.strip()
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = stripped

        if isinstance(parsed, dict):
            action = parsed.get("action", "")
            if action == "execute":
                # User clicked "Execute All" — confirm immediately, no LLM needed
                return {"plan_confirmed": True, "plan_negotiating": False, "current_step_index": 0}
            elif action == "execute_custom":
                selected = parsed.get("selected_steps", [])
                filtered = [t for t in plan if t.get("step") in selected]
                return {
                    "plan_confirmed": True,
                    "plan_negotiating": False,
                    "plan": filtered or plan,
                    "current_step_index": 0,
                }
            elif action == "cancel":
                return {"plan_confirmed": False, "plan_negotiating": False}
            elif action == "discuss_question":
                # User asked a question — cancel plan, re-route to classify for normal agent handling
                question_text = parsed.get("text", "").strip()
                return {
                    "plan_confirmed":        False,
                    "plan_negotiating":      False,
                    "plan":                  [],
                    "query":                 question_text,
                    "reroute_classify":      True,
                    "discuss_mode":          False,
                    "discuss_plan_snapshot": None,
                }
            elif action == "modify_request":
                # Don't blindly treat as modification — fall through to intent detection below
                text_input = parsed.get("text", "").strip()
            else:
                text_input = str(parsed).strip()
        else:
            text_input = str(parsed).strip()

        if not text_input:
            text_input = str(parsed).strip() if not isinstance(parsed, dict) else ""

        # If not a dict (action) OR modify_request — unified intent detection path

        # Use LLM to classify all user intent — no hardcoded keywords
        plan_text_for_detection = "\n".join(
            f"步驟 {t.get('step')}: [{t.get('agent')}] {t.get('description', '')}"
            for t in plan
        )
        intent = await self._detect_confirm_intent(text_input, plan_text_for_detection)

        if intent == "confirm":
            return {"plan_confirmed": True, "plan_negotiating": False}
        if intent == "cancel":
            return {"plan_confirmed": False, "plan_negotiating": False}
        if intent == "question":
            # Cancel plan, re-route to classify — specialized agents will handle the question
            return {
                "plan_confirmed":        False,
                "plan_negotiating":      False,
                "plan":                  [],
                "query":                 text_input,
                "reroute_classify":      True,
                "discuss_mode":          False,
                "discuss_plan_snapshot": None,
            }
        # intent == "modify"
        return {
            "plan_confirmed":      False,
            "plan_negotiating":    True,
            "negotiation_request": text_input,
            "negotiation_response": None,
        }

    async def _detect_confirm_intent(self, text: str, plan_text: str) -> str:
        """
        Use LLM to classify user's intent during plan confirmation.
        Returns: 'question' | 'modify' | 'confirm' | 'cancel'
        """
        import asyncio
        loop = asyncio.get_running_loop()
        prompt = PromptRegistry.render(
            "manager", "confirm_intent",
            plan_text=plan_text,
            text=text
        )
        try:
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke([HumanMessage(content=prompt)])
            )
            intent = self._llm_content(response).strip().lower().split()[0]
            if intent in ("question", "modify", "confirm", "cancel"):
                return intent
            return "question"  # safe default
        except Exception as e:
            logger.warning(f"[ConfirmPlan] intent detection failed: {e}, defaulting to question")
            return "question"

    async def _negotiate_plan_node(self, state: ManagerState) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        plan    = state.get("plan") or []
        request = state.get("negotiation_request") or ""
        count   = (state.get("negotiate_count") or 0) + 1

        if count > 3:
            return {
                "negotiate_count":       count,
                "plan_negotiating":      False,
                "negotiation_response":  "已達協商上限（3次），請直接確認或取消目前計畫。",
            }

        plan_text   = "\n".join(
            f"步驟 {t.get('step')}: [{t.get('agent')}] {t.get('description', '')}"
            for t in plan
        )
        agents_info = self.agent_registry.agents_info_for_prompt()
        tools_info  = ", ".join([t.name for t in self.tool_registry.list_all_tools()])

        prompt = PromptRegistry.render(
            "manager", "negotiate_plan",
            query=state.get("query", ""),
            plan_text=plan_text,
            negotiation_request=request,
            tool_results=state.get("current_tool_result", "無"),
            agents_info=agents_info,
            tools_info=tools_info,
        )
        try:
            response     = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            data         = self._parse_json(self._llm_content(response)) or {}

            tool_call = data.get("tool_call")
            if tool_call:
                tool_depth = state.get("tool_depth", 0)
                if tool_depth < 3:
                    t_name = tool_call.get("name")
                    t_args = tool_call.get("args") or {}
                    print(f"[Manager] Negotiate Tool Call: {t_name}({t_args})")
                    
                    tool = self.tool_registry.get(t_name, caller_agent="manager")
                    if tool:
                        try:
                            if hasattr(tool.handler, "invoke"):
                                t_result = await loop.run_in_executor(None, lambda: tool.handler.invoke(t_args))
                            else:
                                t_result = await loop.run_in_executor(None, lambda: tool.handler(**t_args))
                            t_output = (
                                f"--- Auto-Tool Execution ---\n"
                                f"Tool: {t_name}\n"
                                f"Result: {str(t_result)[:2000]}"
                            )
                            state["current_tool_result"] = t_output
                            state["tool_depth"] = tool_depth + 1
                            # Recursive call - in async we return the node result, so we call it again?
                            # LangGraph nodes usually shouldn't recurse directly if they are async... 
                            # actually they can.
                            return await self._negotiate_plan_node(state)
                        except Exception as te:
                            print(f"[Manager] Tool execution failed: {te}")
                    else:
                        print(f"[Manager] Tool {t_name} not found")

            new_plan_raw = data.get("modified_plan", [])
            valid_fields = {f.name for f in fields(SubTask)}
            new_plan = []
            if new_plan_raw:
                for p in new_plan_raw:
                    # Ensure required fields exist
                    if "step" not in p:
                        continue # Skip invalid steps
                    
                    task_data = {k: v for k, v in p.items() if k in valid_fields}
                    
                    # Provide defaults for required fields if missing or empty
                    if not task_data.get("description"):
                        task_data["description"] = "執行步驟"
                    if not task_data.get("agent"):
                        task_data["agent"] = "chat"
                        
                    new_plan.append(asdict(SubTask(**task_data)))
            else:
                new_plan = plan
            negotiation_response = data.get("explanation", "已根據您的建議調整計畫，請確認。")
        
        except Exception as e:
            import traceback
            print(f"[Manager] negotiate_plan error: {e}\n{traceback.format_exc()}")
            new_plan             = plan
            negotiation_response = "無法處理修改請求，請重新嘗試或直接執行原計畫。"

        if "tool_depth" in state:
            del state["tool_depth"]
        if "current_tool_result" in state:
            del state["current_tool_result"]

        return {
            "plan":                  new_plan,
            "negotiate_count":       count,
            "plan_negotiating":      False,
            "negotiation_response":  negotiation_response,
        }

    async def _discuss_node(self, state: ManagerState) -> dict:
        """
        討論模式節點：回答使用者在計畫確認前提出的任何問題。
        支援工具呼叫（遞迴模式，同 negotiate_plan）。
        保持 discuss_mode=True，不取消計畫。
        """
        import asyncio
        loop = asyncio.get_running_loop()

        # Use discuss_plan_snapshot if available (frozen from confirm_plan),
        # otherwise fall back to current plan
        plan = state.get("discuss_plan_snapshot") or state.get("plan") or []
        # For multi-turn discuss: question is either from confirm_plan (first turn)
        # or from the new user message (subsequent turns)
        question = state.get("discussion_question") or state.get("query") or ""
        query    = state.get("query") or ""
        history  = state.get("history") or ""

        plan_text = "\n".join(
            f"步驟 {t.get('step')}: [{t.get('agent')}] {t.get('description', '')}"
            for t in plan
        ) if plan else "（無待執行計畫）"

        tools_info   = ", ".join([t.name for t in self.tool_registry.list_all_tools()])
        tool_results = state.get("current_tool_result", "無")

        prompt = PromptRegistry.render(
            "manager", "discuss",
            query=query,
            plan_text=plan_text,
            history=history,
            tools_info=tools_info,
            tool_results=tool_results,
            question=question,
        )

        try:
            response = await loop.run_in_executor(
                None, lambda: self.llm.invoke([HumanMessage(content=prompt)])
            )
            data = self._parse_json(self._llm_content(response)) or {}
        except Exception as e:
            logger.error(f"[Discuss] LLM error: {e}")
            data = {"answer": "抱歉，暫時無法回答這個問題，請重新提問。", "tool_call": None}

        # Handle tool call (recursive pattern — same as negotiate_plan)
        tool_call = data.get("tool_call")
        if tool_call:
            tool_depth = state.get("tool_depth", 0)
            if tool_depth < 3:
                t_name = tool_call.get("name")
                t_args = tool_call.get("args") or {}
                logger.info(f"[Discuss] Tool call: {t_name}({t_args})")
                tool = self.tool_registry.get(t_name, caller_agent="manager")
                if tool:
                    try:
                        t_result = await loop.run_in_executor(
                            None, lambda: tool.handler.invoke(t_args)
                        )
                        state["current_tool_result"] = (
                            f"--- Tool: {t_name} ---\n{str(t_result)[:2000]}"
                        )
                        state["tool_depth"] = tool_depth + 1
                        return await self._discuss_node(state)
                    except Exception as te:
                        logger.warning(f"[Discuss] Tool {t_name} failed: {te}")
                else:
                    logger.warning(f"[Discuss] Tool {t_name} not found")

        # Clean up tool state
        state.pop("tool_depth", None)
        state.pop("current_tool_result", None)

        answer = data.get("answer") or "抱歉，無法回答這個問題。"
        logger.info(f"[Discuss] Answered: {question[:50]}...")

        return {
            "final_response":        answer,
            "is_discussion":         True,
            "discuss_mode":          True,          # keep mode active for follow-up questions
            "discuss_plan_snapshot": plan,           # preserve snapshot for subsequent turns
            "discussion_question":   None,           # clear for next turn (use query instead)
        }

    async def _execute_node(self, state: ManagerState) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        plan = state.get("plan") or []
        existing_results = state.get("agent_results") or []
        idx = state.get("current_step_index", 0)
        language = state.get("language", "zh-TW")

        if idx >= len(plan):
            return {}

        history = self._build_history(state)

        async def _run_one(task_dict, step_idx: int) -> dict:
            task = SubTask(**{k: v for k, v in task_dict.items()
                              if k in SubTask.__dataclass_fields__})
            task.context = {
                "history":  history,
                "language": language,
            }
            logger.info(f"[Manager] Executing step {step_idx+1}/{len(plan)}: {task.agent} - {task.description}")

            agent = self.router.route(task.agent)
            if not agent:
                return {
                    "success": False,
                    "message": f"Agent {task.agent} not found",
                    "agent_name": task.agent,
                    "step_index": step_idx,
                }

            if self.progress_callback:
                self.progress_callback({
                    "type": "agent_start",
                    "agent": agent.name,
                    "step": task.step,
                    "description": task.description,
                })
            try:
                res = await loop.run_in_executor(None, agent.execute, task)
                result_data = {
                    "success":    res.success,
                    "message":    res.message,
                    "agent_name": res.agent_name,
                    "data":       res.data,
                    "step_index": step_idx,
                }
                if self.progress_callback:
                    self.progress_callback({
                        "type": "agent_finish",
                        "agent": res.agent_name,
                        "step": task.step,
                        "success": res.success,
                    })
            except Exception as e:
                logger.error(f"[{agent.name}] Execution error: {e}")
                result_data = {
                    "success":    False,
                    "message":    f"執行發生錯誤: {str(e)}",
                    "agent_name": agent.name,
                    "step_index": step_idx,
                }
            return result_data

        # Run all remaining steps in parallel
        remaining = plan[idx:]
        tasks = [_run_one(task_dict, idx + i) for i, task_dict in enumerate(remaining)]
        new_results = await asyncio.gather(*tasks)

        # Sort by step_index to preserve plan order
        new_results = sorted(new_results, key=lambda r: r.get("step_index", 0))

        return {
            "agent_results": list(existing_results) + list(new_results),
            "current_step_index": len(plan),   # mark all steps done
            "retry_count": (state.get("retry_count") or 0),
        }

    async def _watcher_node(self, state: ManagerState) -> dict:
        """Watcher Node: Critique execution results."""
        import asyncio
        loop = asyncio.get_running_loop()
        results = state.get("agent_results") or []
        query = state.get("query", "")
        
        if state.get("complexity") != "complex":
            return {}

        logger.info("[Watcher] Reviewing results...")
        
        for res in results:
            if not res.get("success"): 
                continue
                
            # Wrap watcher critique in executor
            # Assuming self.watcher.critique is sync
            critique = await loop.run_in_executor(
                None, 
                lambda: self.watcher.critique(
                    query=query,
                    step_description=f"Agent: {res.get('agent_name')}", 
                    result=res.get("message", "")
                )
            )
            
            if critique.get("status") == "FAIL":
                logger.warning(f"[Watcher] Flagged result from {res.get('agent_name')}: {critique.get('feedback')}")
                res["watcher_feedback"] = critique.get("feedback")
                
        return {"agent_results": results}

    async def _synthesize_node(self, state: ManagerState) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        results = state.get("agent_results") or []

        if state.get("complexity") == "simple":
            for r in results:
                if r.get("success") and r.get("message"):
                    return {"final_response": r["message"]}
            
            failure_context = "\n".join(
                f"- [{r.get('agent_name', '?')}] {r.get('message', '未知錯誤')}"
                for r in results if r
            )
            chat_agent = self.router.route("chat")
            if chat_agent:
                try:
                    fallback_task = SubTask(step=1, description=state.get("query", ""), agent="chat")
                    fallback_task.context = {
                        "history":        self._build_history(state),
                        "agent_failures": failure_context,
                    }
                    fallback_result = await loop.run_in_executor(None, chat_agent.execute, fallback_task)
                    if fallback_result.success and fallback_result.message:
                        return {"final_response": fallback_result.message}
                except Exception as e:
                    logger.error(f"[Synthesize] chat fallback failed: {e}")
            return {"final_response": f"⚠️ 無法取得分析數據：\n{failure_context}"}

        successful = [r for r in results if r.get("success")]
        if not successful:
            failed_info = "; ".join(
                f"{r.get('agent_name', '?')}: {r.get('message', '')[:100]}"
                for r in results
            )
            return {"final_response": f"⚠️ 所有分析步驟均失敗，無法生成報告。\n\n原因：{failed_info}"}

        AGENT_LABELS = {
            "crypto":   "🔐 加密貨幣",
            "tw_stock": "🇹🇼 台股",
            "us_stock": "📈 美股",
            "chat":     "💬 對話",
        }
        results_text = "\n\n---\n\n".join(
            f"## {AGENT_LABELS.get(r['agent_name'], r['agent_name'])}\n\n{r['message']}"
            for r in successful
        )
        
        plan = state.get("plan") or []
        plan_summary = "\n".join(
            f"{i+1}. [{t.get('agent')}] {t.get('description')}" 
            for i, t in enumerate(plan)
        ) or "（無計畫）"

        prompt = PromptRegistry.render(
            "manager", "synthesize",
            query=state["query"],
            plan_summary=plan_summary,
            clarifications="; ".join(state.get("user_clarifications") or []) or "無",
            results=results_text,
        )
        try:
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            final = self._llm_content(response)
        except Exception:
            final = results_text or "（無法生成回應）"

        return {"final_response": final}

    # ── 路由函數 ─────────────────────────────────────────────────────────────

    def _after_pre_research(self, state: ManagerState) -> str:
        """pre_research 結束後：若使用者提問（discuss_question），直接結束；若提出全新主題則重新分類；否則進入 plan。"""
        if state.get("reroute_classify"):
            return "classify"
        return "end" if state.get("is_discussion") else "plan"

    def _after_classify(self, state: ManagerState) -> str:
        if state.get("plan_confirmed"):
            return "plan"   # Multi-market: skip pre_research, plan node will no-op
        if state.get("complexity") == "ambiguous":
            return "clarify"
        elif state.get("complexity") == "complex" and state.get("intent") == "crypto":
            return "pre_research"   # complex 加密貨幣任務先做預研究
        else:
            return "plan"

    def _after_plan(self, state: ManagerState) -> str:
        if state.get("plan_confirmed"):
            return "execute"
        if state.get("complexity") == "complex":
            return "reflect_plan"   # complex → quality gate before user confirmation
        return "execute"

    def _after_reflect_plan(self, state: ManagerState) -> str:
        """Route after reflection: confirm if approved or max retries hit, else re-plan."""
        from core.config import PLAN_REFLECTION_MAX_RETRIES
        approved = state.get("plan_reflection_approved", True)
        count    = state.get("plan_reflection_count", 0)

        if approved or count > PLAN_REFLECTION_MAX_RETRIES:
            return "confirm"   # proceed to user confirmation
        return "re_plan"       # loop back to plan node for a better plan

    def _after_confirm(self, state: ManagerState) -> str:
        if state.get("reroute_classify"):
            return "classify"
        if state.get("plan_negotiating"):
            return "negotiate"
        if state.get("is_discussion"):
            return "discuss"
        return "execute" if state.get("plan_confirmed") else "end"

    def _after_execute(self, state: ManagerState) -> str:
        idx = state.get("current_step_index", 0)
        plan = state.get("plan") or []
        if idx < len(plan):
            return "continue"
        return "done"

    # ── CLI 入口 ─────────────────────────────────────────────────────────────

    def process(self, query: str, session_id: str = None) -> str:
        """CLI 模式：自動處理 interrupt，使用 HITLManager 提問。"""
        if session_id is None:
            session_id = str(uuid4())

        config = {"configurable": {"thread_id": session_id}}
        initial = {
            "session_id":                session_id,
            "query":                     query,
            "agent_results":             [],
            "user_clarifications":       [],
            "retry_count":               0,
            "plan_reflection_count":     0,
            "plan_reflection_suggestion": None,
            "discuss_mode":              False,
            "discuss_plan_snapshot":     None,
            "replan_request":            False,
        }

        result = self.graph.invoke(initial, config)

        # CLI loop：自動處理所有 interrupt
        while result.get("__interrupt__"):
            iv     = result["__interrupt__"][0].value
            itype  = iv.get("type", "")

            if itype == "confirm_plan":
                # CLI 模式：顯示計畫步驟並詢問是否執行
                plan = iv.get("plan", [])
                plan_text = "\n".join(
                    f"  {t.get('icon','🔧')} {t.get('description','')}" for t in plan
                )
                question = f"{iv.get('message','執行計畫？')}\n{plan_text}"
                options  = ["執行", "取消"]
            else:
                question = iv.get("question", "請回答：")
                options  = iv.get("options")

            answer = input(f"\n[HITL] {question} (Options: {options}): ")
            result = self.graph.invoke(Command(resume=answer), config)

        return result.get("final_response") or "（無回應）"

    def get_status(self) -> dict:
        return {
            "agents":          [m.name for m in self.agent_registry.list_all()],
            "tools":           [t.name for t in self.tool_registry.list_all_tools()],
            "active_sessions": 0,  # checkpointer manages this now
        }

    # ── 工具方法 ─────────────────────────────────────────────────────────────

    def _build_history(self, state: ManagerState) -> str:
        """組合 DB 載入的歷史 + 本輪 clarifications，提供給 agent 作上下文。"""
        parts = []

        # DB 歷史（由 analysis.py 在請求進入時載入）
        db_history = (state.get("history") or "").strip()
        if db_history:
            parts.append(db_history)

        # 本輪 HITL 補充說明
        clarifications = state.get("user_clarifications") or []
        if clarifications:
            parts.append("\n".join(f"補充 {i+1}: {c}" for i, c in enumerate(clarifications)))

        return "\n".join(parts) if parts else "這是新對話的開始"

    @staticmethod
    def _llm_content(response) -> str:
        """安全地從 LLM 回應提取文字。content 可能是 str、list 或 dict（部分 LangChain adapter）。"""
        content = response.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Google / Anthropic multi-part format: [{type: "text", text: "..."}]
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                else:
                    parts.append(str(block))
            return "".join(parts)
        if isinstance(content, dict):
            return content.get("text", str(content))
        return str(content)

    def _parse_json(self, text) -> Optional[dict]:
        if not isinstance(text, str):
            text = str(text)
        clean = text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            try:
                match = re.search(r'\{.*\}', text.replace('\n', ''), re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except Exception:
                pass
            return None
