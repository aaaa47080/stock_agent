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
from .codebook import Codebook
from .prompt_registry import PromptRegistry
from .watcher import WatcherAgent
from core.tools.universal_resolver import UniversalSymbolResolver

# 模組級共用 checkpointer：跨 bootstrap() 呼叫持久化 session state
_checkpointer = MemorySaver()


AGENT_ICONS: Dict[str, str] = {
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
    codebook_entry_id: NotRequired[Optional[str]]
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


class ManagerAgent:
    def __init__(
        self,
        llm_client,
        agent_registry: AgentRegistry,
        tool_registry: ToolRegistry,
        codebook,
        web_mode: bool = False,
    ):
        self.llm = llm_client
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        # self.hitl = hitl # Removed
        self.codebook = codebook
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
        workflow.add_node("save",           self._save_node)

        workflow.set_entry_point("classify")

        workflow.add_conditional_edges("classify", self._after_classify, {
            "clarify":      "clarify",
            "pre_research": "pre_research",   # complex → 先預研究
            "plan":         "plan",           # simple  → 直接規劃
        })
        workflow.add_edge("clarify",      "classify")    # 澄清後重新分類
        workflow.add_conditional_edges("pre_research", self._after_pre_research, {
            "plan": "plan",   # 用戶確認方向 → 進入規劃
            "save": "save",   # 用戶提問 → 回答後結束
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
            "negotiate": "negotiate_plan",         # 用戶提出修改 → 協商
            "discuss":   "discuss",               # 用戶提問 → 討論回答後結束
            "end":       END,
        })
        workflow.add_edge("negotiate_plan", "confirm_plan")  # 協商後回到確認
        workflow.add_edge("discuss",        "save")          # 討論回答後儲存結束

        # Execution Loop: execute -> check -> (execute | watcher)
        workflow.add_conditional_edges("execute", self._after_execute, {
            "continue": "execute",
            "done":     "watcher"
        })
        
        workflow.add_edge("watcher",   "synthesize")
        workflow.add_edge("synthesize", "save")
        workflow.add_edge("save",       END)

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
        result = {
            "complexity":                 complexity,
            "intent":                     intent,
            "topics":                     data.get("topics", []),
            "ambiguity_question":         data.get("ambiguity_question"),
            "replan_request":             replan_request,
            # Reset reflection state for each new query to prevent leakage
            "plan_reflection_count":      0,
            "plan_reflection_suggestion": None,
            "plan_reflection_approved":   None,
        }
        # If user explicitly re-requests planning, exit discuss mode
        if replan_request:
            result["discuss_mode"] = False
            result["discuss_plan_snapshot"] = None
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

        CONFIRM_TOKENS = {"confirm", "開始規劃", "可以", "ok", "繼續", "執行", ""}
        clarifications = list(state.get("research_clarifications") or [])

        # 5. HITL 循環：用戶可以問問題或給方向，直到確認為止
        qa_question = None
        qa_answer   = None
        first_iteration = True

        while True:
            if first_iteration:
                msg = f"我已整理 **{symbol}** 的即時資料供您參考："
                summary_tosend = research_summary
                q_prompt = "想聚焦哪個方向？（例如：只看技術面 / 重點看新聞）若有疑問也可直接問，留空確認開始分析。"
            else:
                msg = "還有其他問題嗎？"
                summary_tosend = None # Suppress summary
                q_prompt = "若無其他問題，請直接確認開始規劃。"

            payload = {
                "type":             "pre_research",
                "message":          msg,
                "research_summary": summary_tosend,
                "question":         q_prompt,
            }
            # 若有 Q&A 答案，附在 payload 讓前端顯示為主聊天訊息
            if qa_question and qa_answer:
                # Embed in message for guaranteed visibility
                # msg = f"💡 **關於「{qa_question}」的回答**：\n{qa_answer}\n\n(已更新 {symbol} 資料如上)"
                # Actually, prepend it to the message
                msg = f"💡 **回答**：{qa_question}\n\n{qa_answer}\n\n---\n{msg}"
                
                payload["qa_question"] = qa_question
                payload["qa_answer"]   = qa_answer
                payload["message"]     = msg # Update message
                qa_question = qa_answer = None  # 只傳一次

            user_response = interrupt(payload)
            first_iteration = False # Mark as not first iteration after interrupt returns
            # user_response might be a dict (from chat.js wrapper) or string
            if isinstance(user_response, dict):
                action = user_response.get("action", "")
                resp   = user_response.get("text") or user_response.get("value") or ""
            else:
                action = ""
                resp   = str(user_response or "")

            resp = resp.strip()

            # discuss_question action：使用者提問，取消 pre_research，直接以聊天回答
            if action == "discuss_question" and resp:
                qa_answer = await self._answer_research_question(resp, research_summary, symbol)
                print(f"[PreResearch] discuss_question: '{resp}' → '{qa_answer[:60]}...'")
                return {
                    "research_data":           research_data,
                    "research_summary":        research_summary,
                    "research_clarifications": clarifications,
                    "is_discussion":           True,
                    "discussion_question":     resp,
                    "final_response":          qa_answer,
                }

            # 確認詞 → 直接進入 plan
            if resp.lower() in CONFIRM_TOKENS:
                break

            # 偵測是否為問題（含問號，或以提問詞開頭）
            QUESTION_STARTERS = (
                "你覺得", "你認為", "你建議", "哪個", "哪則", "哪一", "哪些",
                "為什麼", "什麼", "怎麼", "如何", "多少", "幾個", "是否",
                "What", "Which", "How", "Why", "Who", "When", "Where",
                "Is", "Are", "Do", "Does", "Can", "Could", "Would", "Should"
            )
            resp_stripped = resp.strip()
            is_question = (
                resp_stripped.endswith("?") or resp_stripped.endswith("？") or
                any(resp_stripped.lower().startswith(w.lower()) for w in QUESTION_STARTERS)
            )

            print(f"[PreResearch] HITL Input: '{resp}' | IsQuestion: {is_question}")

            if is_question:
                qa_question = resp
                qa_answer   = await self._answer_research_question(resp, research_summary, symbol)
                print(f"[PreResearch] QA Answer: {qa_answer[:50]}...")
            else:
                # 方向提示 → 加入 clarifications，進入 plan
                clarifications.append(resp)
                break

        return {
            "research_data":           research_data,
            "research_summary":        research_summary,
            "research_clarifications": clarifications,
        }

    async def _answer_research_question(self, question: str, research_summary: str, symbol: str) -> str:
        """用 LLM 根據已收集的研究資料回答用戶的問題。若資料不足，自動用 web_search 補充。"""
        import asyncio
        loop = asyncio.get_running_loop()

        # 先嘗試從現有資料回答，若 LLM 判斷資料不足則補充 web_search
        probe_prompt = (
            f"以下是關於 {symbol} 的即時市場資料：\n\n"
            f"{research_summary}\n\n"
            f"用戶問題：{question}\n\n"
            f"若上述資料已足夠回答問題，請直接回答（繁體中文）。"
            f"若資料不足（例如問及總發行量、市值、白皮書、開發團隊等標準工具未涵蓋的資訊），"
            f"請只回覆 JSON：{{\"need_search\": true, \"search_query\": \"具體搜尋關鍵字\"}}"
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
                final_prompt = (
                    f"用戶問：{question}\n\n"
                    f"網路搜尋結果：\n{search_result}\n\n"
                    f"請根據搜尋結果用繁體中文回答，若有連結請保留 Markdown 格式 [標題](url)。"
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
            prompt = (
                f"從以下文字中提取金融資產的交易代號（ticker），包含加密貨幣（如 BTC、ETH、SOL）"
                f"或股票（如 AAPL、INTC、TSLA、2330）。"
                f"只回覆 ticker 本身（純英文大寫縮寫或數字代號），不要其他文字。"
                f"若無法識別，直接回覆原文字。\n\n文字：{candidate}"
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
            plan = [asdict(SubTask(
                step=1,
                description=query,
                agent=state.get("intent", "chat"),
                tool_hint=None,
            ))]
            return {"plan": plan, "codebook_entry_id": None}

        # Complex 任務：LLM planning + codebook 記憶
        similar = self.codebook.find_similar_entries(
            query, state.get("intent", "chat"), state.get("topics") or [], limit=3
        )
        agents_info = self.agent_registry.agents_info_for_prompt()
        tools_info  = ", ".join([t.name for t in self.tool_registry.list_all_tools()])

        past_text = "無"
        if similar:
            past_text = ""
            for i, e in enumerate(similar):
                plan_summary = "; ".join(f"{t['agent']}: {t['description']}" for t in e.plan)
                past_text += f"[{i+1}] Query: {e.query}\n    Plan: {plan_summary}\n"

        prompt = PromptRegistry.render(
            "manager", "plan",
            query=query,
            agent=state.get("intent", "chat"),
            topics=", ".join(state.get("topics") or []),
            clarifications="; ".join(state.get("user_clarifications") or []) or "無",
            past_experience=past_text,
            agents_info=agents_info,
            tools_info=tools_info,
            research_summary=state.get("research_summary") or "無",
            research_clarifications="; ".join(state.get("research_clarifications") or []) or "無",
            reflection_suggestion=state.get("plan_reflection_suggestion") or "無",
        )
        try:
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            data = self._parse_json(self._llm_content(response)) or {}
            plan_raw = data.get("plan", [])
            valid_fields = {f.name for f in fields(SubTask)}
            plan = []
            for p in plan_raw:
                task_data = {k: v for k, v in p.items() if k in valid_fields}
                plan.append(asdict(SubTask(**task_data)))
        except Exception as e:
            import traceback
            print(f"[Manager] plan error: {e}\n{traceback.format_exc()}")
            plan = [asdict(SubTask(
                step=1, description=state["query"],
                agent=state.get("intent", "chat"), tool_hint=None
            ))]

        codebook_entry_id = similar[0].id if similar else None
        return {"plan": plan, "codebook_entry_id": codebook_entry_id, "current_step_index": 0}

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
            if action == "execute_custom":
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
                # User asked a discussion question during plan confirmation — cancel plan, answer in chat
                question_text = parsed.get("text", "").strip()
                return {
                    "plan_confirmed":      False,
                    "plan_negotiating":    False,
                    "is_discussion":       True,
                    "discussion_question": question_text,
                }
            elif action == "modify_request":
                request_text = parsed.get("text", "").strip()
                return {
                    "plan_confirmed":      False,
                    "plan_negotiating":    True,
                    "negotiation_request": request_text,
                    "negotiation_response": None,
                }

        # If not a dict (action), treat as raw text input
        text_input = str(parsed).strip()

        # Explicit confirmation keywords (fast path — no LLM needed)
        CONFIRM_KEYWORDS = ["ok", "confirm", "start", "execute", "yes", "go", "开始", "執行", "確認", "好"]
        CANCEL_KEYWORDS = ["cancel", "stop", "no", "取消", "停止"]

        if text_input.lower() in CONFIRM_KEYWORDS:
            return {"plan_confirmed": True, "plan_negotiating": False}

        if text_input.lower() in CANCEL_KEYWORDS:
            return {"plan_confirmed": False, "plan_negotiating": False}

        # Use LLM to distinguish question vs. modification request
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
            return {
                "plan_confirmed":        False,
                "plan_negotiating":      False,
                "is_discussion":         True,
                "discussion_question":   text_input,
                "discuss_mode":          True,
                "discuss_plan_snapshot": list(plan),   # freeze current plan
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
        prompt = (
            f"當前分析計畫：\n{plan_text}\n\n"
            f"使用者輸入：{text}\n\n"
            f"判斷使用者意圖，只回覆以下一個詞：\n"
            f"- question：詢問資訊、意見或問題（包含計畫相關問題、市場數據、計畫優缺點等）\n"
            f"- modify：明確要求修改計畫步驟（如移除、新增、替換某步驟）\n"
            f"- confirm：確認執行計畫\n"
            f"- cancel：取消計畫\n\n"
            f"只回覆一個詞，不加任何標點或說明。"
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
        計畫討論節點：使用者在 confirm_plan HITL 中提問（非修改計畫）。
        取消計畫狀態，用 LLM 根據研究資料直接回答問題，結果作為 final_response。
        """
        import asyncio
        loop = asyncio.get_running_loop()
        question = state.get("discussion_question") or ""
        research_summary = state.get("research_summary") or ""
        plan = state.get("plan") or []
        query = state.get("query") or ""
        history = state.get("history") or ""

        # 提供計畫內容和研究資料作為上下文
        plan_text = "\n".join(
            f"步驟 {t.get('step')}: [{t.get('agent')}] {t.get('description', '')}"
            for t in plan
        ) if plan else "（無計畫）"

        context_parts = []
        if research_summary:
            context_parts.append(f"【即時市場資料】\n{research_summary}")
        if plan_text != "（無計畫）":
            context_parts.append(f"【剛才規劃的分析步驟】\n{plan_text}")
        if query:
            context_parts.append(f"【原始分析請求】\n{query}")

        context = "\n\n".join(context_parts) if context_parts else "（暫無額外背景資料）"

        prompt = (
            f"以下是剛才分析討論的背景資料：\n\n{context}\n\n"
            f"對話歷史：\n{history}\n\n"
            f"使用者提問：{question}\n\n"
            f"請用繁體中文直接回答使用者的問題。若問題涉及計畫步驟或市場資料，請根據上下文作答。"
            f"若引用新聞，必須保留原始 Markdown 連結格式 [標題](url)，不要省略連結。"
            f"保持回答清晰、具體、有幫助。計畫已取消，後續使用者可再次提出分析請求。"
        )
        try:
            response = await loop.run_in_executor(None, lambda: self.llm.invoke([HumanMessage(content=prompt)]))
            answer = self._llm_content(response).strip()
        except Exception as e:
            logger.error(f"[Discuss] LLM error: {e}")
            answer = "抱歉，暫時無法回答這個問題。請重新提問或發起新的分析。"

        logger.info(f"[Discuss] Answered question: {question[:50]}...")
        return {
            "final_response": answer,
            "plan_confirmed":  False,
            "is_discussion":   True,
        }

    async def _execute_node(self, state: ManagerState) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        plan = state.get("plan") or []
        results = state.get("agent_results") or []
        idx = state.get("current_step_index", 0)
        language = state.get("language", "zh-TW")  # 獲取用戶語言偏好

        if idx >= len(plan):
            return {}

        task_dict = plan[idx]
        task = SubTask(**{k: v for k, v in task_dict.items()
                          if k in SubTask.__dataclass_fields__})
        task.context = {
            "history": self._build_history(state),
            "language": language,  # 傳遞語言參數給 Agent
        }

        logger.info(f"[Manager] Executing step {idx+1}/{len(plan)}: {task.agent} - {task.description}")

        agent = self.router.route(task.agent)
        if not agent:
            result_data = {
                "success": False, 
                "message": f"Agent {task.agent} not found",
                "agent_name": task.agent,
                "step_index": idx
            }
        else:
            if self.progress_callback:
                self.progress_callback({
                    "type": "agent_start",
                    "agent": agent.name,
                    "step": task.step,
                    "description": task.description
                })

            try:
                # Execute agent in executor to prevent blocking
                res = await loop.run_in_executor(None, agent.execute, task)
                
                result_data = {
                    "success":    res.success,
                    "message":    res.message,
                    "agent_name": res.agent_name,
                    "data":       res.data,
                    "step_index": idx
                }
                
                if self.progress_callback:
                    self.progress_callback({
                        "type": "agent_finish",
                        "agent": res.agent_name,
                        "step": task.step,
                        "success": res.success
                    })

            except Exception as e:
                logger.error(f"[{agent.name}] Execution error: {e}")
                result_data = {
                    "success": False, 
                    "message": f"執行發生錯誤: {str(e)}", 
                    "agent_name": agent.name,
                    "step_index": idx
                }

        new_results = list(results) + [result_data]
        
        return {
            "agent_results": new_results, 
            "current_step_index": idx + 1,
            "retry_count": (state.get("retry_count") or 0)
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

    async def _save_node(self, state: ManagerState) -> dict:
        # Saving to codebook might involve IO or vector DB operations, better wrap it.
        import asyncio
        loop = asyncio.get_running_loop()
        
        complexity = state.get('complexity')
        has_resp = bool(state.get('final_response'))
        has_plan = bool(state.get('plan'))
        logger.info(f"[DEBUG] _save_node: complexity={complexity}, has_response={has_resp}, has_plan={has_plan}")
        
        if complexity == "complex" and has_resp and has_plan and not state.get("is_discussion"):
            def do_save():
                logger.info("[DEBUG] _save_node: Saving to codebook...")
                from .hierarchical_memory import MemoryEntry
                from datetime import datetime
                plan_clean = [{k: v for k, v in t.items() if k not in ("result", "icon")} for t in (state.get("plan") or [])]
                entry = MemoryEntry(
                    id=str(uuid4()),
                    query=state["query"],
                    intent=state.get("intent", "chat"),
                    topics=state.get("topics") or [],
                    plan=plan_clean,
                    complexity=complexity,
                    created_at=datetime.now().isoformat(),
                    ttl_days=14,
                )
                primary_topic = (state.get("topics") or ["DEFAULT"])[0].upper()
                try:
                    self.codebook._persist_entry(entry, primary_topic)
                    self.codebook._cache[entry.id] = entry
                    self.codebook._update_index(entry)
                    logger.info(f"[DEBUG] _save_node: Saved entry {entry.id}")
                    return {"codebook_entry_id": entry.id}
                except Exception as e:
                    logger.error(f"[DEBUG] _save_node: Failed to save to codebook: {e}")
                    return {}

            return await loop.run_in_executor(None, do_save)

        return {}

    # ── 路由函數 ─────────────────────────────────────────────────────────────

    def _after_pre_research(self, state: ManagerState) -> str:
        """pre_research 結束後：若使用者提問（discuss_question），直接結束；否則進入 plan。"""
        return "save" if state.get("is_discussion") else "plan"

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
            "codebook":        self.codebook.stats(),
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
