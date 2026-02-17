"""
Agent V4 — Manager Agent (LangGraph Edition)

Uses LangGraph StateGraph to orchestrate:
  classify → plan → execute → synthesize → feedback

Same public API: manager.process(query) → str
"""
from __future__ import annotations
import json
import re
from typing import List, Optional, Dict, Any, TypedDict
from uuid import uuid4
from dataclasses import asdict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
from langchain_core.messages import HumanMessage

from .models import (
    TaskComplexity, SubTask, ExecutionContext,
    AgentResult, CollaborationRequest,
)
from .agent_registry import AgentRegistry
from .router import AgentRouter
from .hitl import HITLManager
from .codebook import Codebook
from .prompt_registry import PromptRegistry


# ══════════════════════════════════════════
# 1. State Definition (like V1's AgentState)
# ══════════════════════════════════════════

class V4State(TypedDict, total=False):
    """State that flows through the LangGraph nodes."""
    # Input
    query: str
    session_id: str

    # Conversation memory (short-term)
    messages: List[dict]     # [{"role": "user"|"assistant", "content": str}, ...]
    memory: List[dict]       # structured extracted facts (MemoryFact dicts)

    # Classification results
    agent_name: str
    complexity: str          # "simple" | "complex" | "ambiguous"
    symbols: List[str]
    entities: List[str]      # generic named entities (superset of symbols)
    ambiguity_question: Optional[str]

    # Planning
    plan: List[dict]         # serialized SubTask dicts
    codebook_entry_id: Optional[str]

    # Execution
    results: List[dict]      # serialized AgentResult dicts
    context: Optional[dict]  # serialized ExecutionContext

    # Output
    final_response: str

    # Flow control
    clarification: Optional[str]  # user answer for ambiguous
    needs_synthesis: bool
    plan_user_modification: Optional[str]  # user's requested modification to plan
    plan_cancelled: bool

    # Satisfaction loop
    satisfaction_retry: bool       # True = user wants retry
    satisfaction_feedback: Optional[str]  # user's retry feedback
    satisfaction_skip: bool        # True = simple task, skip satisfaction


class ManagerAgent:
    def __init__(
        self,
        llm_client,
        agent_registry: AgentRegistry,
        all_tools: list,
        hitl: HITLManager,
        codebook: Codebook,
        web_mode: bool = False,
    ):
        self.llm = llm_client
        self.agent_registry = agent_registry
        self.all_tools = all_tools  # list of @tool functions
        self.hitl = hitl
        self.codebook = codebook
        self.router = AgentRouter(agent_registry)
        self.web_mode = web_mode

        # Initialize Checkpointer (Postgres or Memory)
        self.checkpointer = self._init_checkpointer()
        
        # Build and compile the LangGraph
        self.graph = self._build_graph()

    def _init_checkpointer(self):
        """Initialize appropriate checkpointer based on config."""
        import os
        db_url = os.environ.get("DATABASE_URL")
        
        if db_url and HAS_POSTGRES:
            try:
                # Use synchronous connection for simplicity in this version
                # Note: creating a new pool for the manager instance
                # from_conn_string returns a context manager, need to enter it
                # STORE CM in self to prevent GC from closing the pool!
                self._checkpointer_cm = PostgresSaver.from_conn_string(db_url)
                checkpointer = self._checkpointer_cm.__enter__()
                
                # DEBUG: Trace persistence object
                print(f"[DEBUG] Checkpointer Type: {type(checkpointer)}")
                # print(f"[DEBUG] Checkpointer Dir: {dir(checkpointer)}")
                
                checkpointer.setup()  # Ensure tables exist
                print(f"[Manager] Using PostgresSaver for memory ✅")
                return checkpointer
            except Exception as e:
                print(f"[Manager] Failed to init PostgresSaver: {e}. Falling back to InMemorySaver.")
        
        print(f"[Manager] Using InMemorySaver for memory ⚠️ (state lost on restart)")
        return InMemorySaver()

    # ══════════════════════════════════════════
    # 2. Graph Construction (like V1's workflow)
    # ══════════════════════════════════════════

    def _build_graph(self):
        """Build the LangGraph StateGraph — similar to V1's graph.py pattern."""
        workflow = StateGraph(V4State)

        # Add nodes
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("ask_user", self._ask_user_node)
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("confirm_plan", self._confirm_plan_node)
        workflow.add_node("execute", self._execute_node)
        workflow.add_node("synthesize", self._synthesize_node)
        workflow.add_node("feedback", self._feedback_node)
        workflow.add_node("save_messages", self._save_messages_node)
        workflow.add_node("extract_memory", self._extract_memory_node)
        workflow.add_node("ask_satisfaction", self._ask_satisfaction_node)
        workflow.add_node("save_codebook", self._save_codebook_node)

        # Set entry point
        workflow.set_entry_point("classify")

        # Edges — conditional routing after classification
        workflow.add_conditional_edges(
            "classify",
            self._after_classify_router,
            {
                "simple": "execute",
                "complex": "plan",
                "ambiguous": "ask_user",
            }
        )

        # ask_user loops back to classify
        workflow.add_edge("ask_user", "classify")

        # plan → confirm_plan (HITL: user confirms/modifies/cancels)
        workflow.add_edge("plan", "confirm_plan")

        # Conditional after confirm_plan
        workflow.add_conditional_edges(
            "confirm_plan",
            self._after_confirm_router,
            {
                "execute": "execute",
                "modify": "plan",     # loop back to re-plan
                "cancel": "feedback", # skip to end
            }
        )

        # Conditional after execute: single result → feedback, multi → synthesize
        workflow.add_conditional_edges(
            "execute",
            self._after_execute_router,
            {
                "single": "feedback",
                "multi": "synthesize",
            }
        )

        # synthesize → feedback
        workflow.add_edge("synthesize", "feedback")

        # feedback → save_messages → extract_memory → ask_satisfaction → END/save_codebook/retry
        workflow.add_edge("feedback", "save_messages")
        workflow.add_edge("save_messages", "extract_memory")
        workflow.add_edge("extract_memory", "ask_satisfaction")
        workflow.add_conditional_edges(
            "ask_satisfaction",
            self._after_satisfaction_router,
            {
                "skip": END,           # simple task — no confirmation needed
                "save": "save_codebook",  # satisfied — persist to codebook
                "retry": "execute",    # not satisfied — re-execute with feedback
            }
        )
        workflow.add_edge("save_codebook", END)

        # Compile with checkpointer for short-term memory
        # self.checkpointer is initialized in __init__
        graph = workflow.compile(checkpointer=self.checkpointer)
        print("[Manager] LangGraph workflow compiled ✅ (with memory)")
        return graph

    # ══════════════════════════════════════════
    # 3. Router Functions (like V1's routers)
    # ══════════════════════════════════════════

    def _after_classify_router(self, state: V4State) -> str:
        """Route after classification — same pattern as V1's after_analyst_team_router."""
        complexity = state.get("complexity", "simple")
        if complexity == "ambiguous":
            return "ambiguous"
        elif complexity == "complex":
            return "complex"
        else:
            return "simple"

    def _after_execute_router(self, state: V4State) -> str:
        """Route after execution — single result or needs synthesis."""
        if state.get("needs_synthesis", False):
            return "multi"
        return "single"

    def _after_confirm_router(self, state: V4State) -> str:
        """Route after plan confirmation — execute, modify, or cancel."""
        if state.get("plan_cancelled", False):
            return "cancel"
        if state.get("plan_user_modification"):
            return "modify"
        return "execute"

    def _after_satisfaction_router(self, state: V4State) -> str:
        """Route after satisfaction check."""
        if state.get("satisfaction_skip"):
            return "skip"
        if state.get("satisfaction_retry"):
            return "retry"
        return "save"

    def _make_hitl_fn(self):
        """Build HITL callback for sub-agents — wraps interrupt() or hitl.ask()."""
        if self.web_mode:
            def ask(question, options=None):
                return interrupt({
                    "type": "sub_agent_hitl",
                    "question": question,
                    "options": options or [],
                })
            return ask
        return lambda q, opts=None: self.hitl.ask(q, opts)

    # ══════════════════════════════════════════
    # 4. Node Functions (like V1's node functions)
    # ══════════════════════════════════════════

    def _classify_node(self, state: V4State) -> dict:
        """Node 1: Classify the user query — pick agent from dynamic registry."""
        query = state["query"]

        # If we have a clarification from ask_user, append it
        clarification = state.get("clarification")
        if clarification:
            query = f"{query}\n使用者補充：{clarification}"

        # Build conversation context from messages (short-term memory)
        messages = state.get("messages", [])
        if len(messages) > 1:  # has previous turns
            recent = messages[-6:]  # last 3 turns
            context_lines = []
            for m in recent[:-1]:  # exclude current query (already in query)
                role = "用戶" if m["role"] == "user" else "助手"
                context_lines.append(f"{role}: {m['content'][:100]}")
            if context_lines:
                query = "對話歷史：\n" + "\n".join(context_lines) + f"\n\n當前問題：{query}"

        # Inject structured memory facts into classify context
        memory = state.get("memory", [])
        if memory:
            facts_str = "; ".join(f"{f['key']}={f['value']}" for f in memory[:5])
            query = f"[已知事實: {facts_str}]\n\n{query}"

        classification = self._classify(query)
        complexity = classification.get("complexity", "simple")
        agent_name = classification.get("agent", "chat")
        symbols = classification.get("symbols", [])
        entities = classification.get("entities", symbols)

        # Validate agent exists
        if not self.agent_registry.get(agent_name):
            agent_name = "chat"

        print(f"[Node: classify] agent={agent_name}, complexity={complexity}, symbols={symbols}, entities={entities}")

        return {
            "agent_name": agent_name,
            "complexity": complexity,
            "symbols": symbols,
            "entities": entities,
            "ambiguity_question": classification.get("ambiguity_question"),
        }

    def _ask_user_node(self, state: V4State) -> dict:
        """Node: Ask user for clarification when query is ambiguous.

        Web mode: uses LangGraph interrupt() — pauses graph, saves state via
        checkpointer, resumes when client sends Command(resume=answer).
        CLI mode: uses HITLManager.ask() which reads from stdin.
        """
        question = state.get("ambiguity_question", "請問您想分析什麼？")

        if self.web_mode:
            answer = interrupt({"type": "clarification", "question": question})
        else:
            answer = self.hitl.ask(question)

        print(f"[Node: ask_user] question='{question}', answer='{answer}'")
        return {"clarification": answer}

    def _confirm_plan_node(self, state: V4State) -> dict:
        """Node: Show plan to user and ask confirm/modify/cancel.

        Web mode: uses LangGraph interrupt() with a single round-trip.
          - "確認執行" / "1" / "" → proceed
          - "取消" / "2" → cancel
          - anything else → treat as free-text modification request
        CLI mode: multi-step stdin interaction (original behaviour).
        """
        plan = state.get("plan", [])
        plan_text = "\n".join(
            f"  {i+1}. [{p.get('agent', '?')}] {p.get('description', '')}"
            for i, p in enumerate(plan)
        )

        prompt = f"以下是為您的查詢制定的執行計畫：\n\n查詢：{state['query']}\n\n計畫步驟：\n{plan_text}\n\n請問是否按此計畫執行？"

        if self.web_mode:
            answer = interrupt({
                "type": "plan_confirm",
                "question": prompt,
                "options": ["確認執行", "取消", "修改計畫"],
            })
            # In web mode, simplify: non-confirm responses become free-text modification
            if answer in ["取消", "2"]:
                print("[Node: confirm_plan] User cancelled (web)")
                return {"plan_cancelled": True, "final_response": "已取消任務。"}
            if answer not in ["確認執行", "1", ""]:
                print(f"[Node: confirm_plan] User modification (web): {answer}")
                return {"plan_user_modification": answer, "plan_cancelled": False}
            print("[Node: confirm_plan] User confirmed (web)")
            return {"plan_confirmed": True, "plan_cancelled": False}
        else:
            answer = self.hitl.ask(prompt, options=["確認執行", "取消", "修改計畫"])

        if answer in ["取消", "2"]:
            print("[Node: confirm_plan] User cancelled")
            return {"plan_cancelled": True, "final_response": "已取消任務。"}

        if answer in ["修改計畫", "3"] or (answer not in ["確認執行", "1", ""] and len(answer) > 2):
            # Step 1: Ask which step to modify
            if answer in ["修改計畫", "3"]:
                step_options = [f"{i+1}" for i in range(len(plan))] + ["全部"]
                step_answer = self.hitl.ask(
                    f"請選擇要修改的步驟編號（1-{len(plan)}），或輸入「全部」重新規劃整個計畫："
                )
            else:
                # User typed modification directly
                modification = answer
                print(f"[Node: confirm_plan] User modification: {modification}")
                return {"plan_user_modification": modification, "plan_cancelled": False}

            # Step 2: Get modification details for the selected step
            if step_answer.strip() in ["全部", "all", "0"]:
                modification = self.hitl.ask("請描述您想要的整體修改：")
            else:
                try:
                    step_idx = int(step_answer.strip()) - 1
                    if 0 <= step_idx < len(plan):
                        step_info = plan[step_idx]
                        modification_detail = self.hitl.ask(
                            f"第 {step_idx+1} 步目前為：[{step_info.get('agent', '?')}] {step_info.get('description', '')}\n"
                            f"請描述您想如何修改這一步："
                        )
                        modification = f"修改第 {step_idx+1} 步 [{step_info.get('agent', '?')}]: {step_info.get('description', '')} → 用戶想改成: {modification_detail}"
                    else:
                        modification = self.hitl.ask(f"步驟編號超出範圍（1-{len(plan)}），請直接描述您想要的修改：")
                except ValueError:
                    modification = step_answer  # treat as free text modification

            print(f"[Node: confirm_plan] User modification: {modification}")
            return {"plan_user_modification": modification, "plan_cancelled": False}

        print("[Node: confirm_plan] User confirmed")
        return {"plan_user_modification": None, "plan_cancelled": False}

    def _build_history_for_agent(self, agent_name: str, messages: list, memory: list) -> dict:
        """Build agent-appropriate context — different agents need different history depth."""
        if agent_name == "chat":
            # Conversational agent: 5 full turns + memory facts for personalization
            recent = messages[-10:]
            context_lines = [
                f"{'用戶' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
                for m in recent[:-1]
            ]
            history_str = "\n".join(context_lines) or "這是新對話的開始"
            memory_facts = "\n".join(
                f"- {f['key']}: {f['value']}"
                for f in memory
                if f.get("confidence") in ("high", "medium")
            ) or "無"
            return {"history": history_str, "memory_facts": memory_facts}

        elif agent_name in ("technical", "news", "full_analysis"):
            # Analytical agents: only last 2 turns for disambiguation
            recent = messages[-4:]
            context_lines = [
                f"{'用戶' if m['role'] == 'user' else '助手'}: {m['content'][:100]}"
                for m in recent[:-1]
            ]
            history_str = "\n".join(context_lines) or "這是新對話的開始"
            return {"history": history_str}

        else:
            # Default: last 3 turns
            recent = messages[-6:]
            context_lines = [
                f"{'用戶' if m['role'] == 'user' else '助手'}: {m['content'][:100]}"
                for m in recent[:-1]
            ]
            return {"history": "\n".join(context_lines) or "這是新對話的開始"}

    def _plan_node(self, state: V4State) -> dict:
        """Node: Create execution plan (codebook lookup or LLM planning)."""
        query = state["query"]
        agent_name = state["agent_name"]
        symbols = state.get("symbols", [])

        # If user requested modification, append to query for re-planning
        user_mod = state.get("plan_user_modification")
        if user_mod:
            query = f"{query}\n使用者要求修改計畫：{user_mod}"
            print(f"[Node: plan] Re-planning with user modification: {user_mod}")
        else:
            # Codebook lookup only on first plan (not re-plan)
            match = self.codebook.find_match(query, agent_name, symbols)
            if match:
                print(f"[Node: plan] Codebook hit: {match.id[:8]}...")
                plan = match.plan  # already dicts
                return {"plan": plan, "codebook_entry_id": match.id}

        # LLM planning
        subtasks = self._plan(query, agent_name, symbols)
        plan = [asdict(t) for t in subtasks]
        # Clear result field to avoid serialization issues
        for p in plan:
            p["result"] = None

        print(f"[Node: plan] LLM plan with {len(plan)} steps")
        return {"plan": plan, "codebook_entry_id": None, "plan_user_modification": None}

    def _execute_node(self, state: V4State) -> dict:
        """Node: Execute the plan — dispatch to registered agents."""
        query = state["query"]

        # Retry with user feedback from satisfaction check
        retry_feedback = state.get("satisfaction_feedback")
        if retry_feedback:
            query = f"{query}\n\n使用者補充：{retry_feedback}"

        agent_name = state["agent_name"]
        complexity = state.get("complexity", "simple")
        symbols = state.get("symbols", [])
        session_id = state.get("session_id", str(uuid4()))

        # Build plan from state
        plan_dicts = state.get("plan")
        if plan_dicts:
            plan = [SubTask(**p) for p in plan_dicts]
        else:
            # Simple path: single-step plan
            plan = [SubTask(step=1, description=query, agent=agent_name, tool_hint=None)]

        # Build ExecutionContext
        context = ExecutionContext(
            session_id=session_id,
            original_query=query,
            complexity=TaskComplexity(complexity),
            intent=agent_name,
            symbols=symbols,
            plan=plan,
            codebook_entry_id=state.get("codebook_entry_id"),
        )

        # Execute all tasks
        results = []
        messages = state.get("messages", [])
        memory = state.get("memory", [])
        hitl_fn = self._make_hitl_fn()

        for task in plan:
            task.status = "in_progress"
            task.context = self._build_history_for_agent(task.agent, messages, memory)

            agent = self.router.route(task.agent)
            if agent is None:
                task.status = "failed"
                task.result = AgentResult(
                    success=False, message=f"Agent '{task.agent}' not found",
                    agent_name=task.agent,
                )
                results.append(asdict(task.result))
                continue

            agent.hitl_fn = hitl_fn
            result = agent.execute(task)
            agent.hitl_fn = None  # cleanup
            task.status = "completed" if result.success else "failed"
            task.result = result
            context.agent_results.append(result)
            results.append({
                "success": result.success,
                "message": result.message,
                "agent_name": result.agent_name,
                "data": result.data,
            })

            # Handle collaboration
            if result.needs_collaboration:
                collab_result = self._handle_collaboration(result.needs_collaboration, context)
                if collab_result:
                    context.agent_results.append(collab_result)
                    results.append({
                        "success": collab_result.success,
                        "message": collab_result.message,
                        "agent_name": collab_result.agent_name,
                    })

        print(f"[Node: execute] {len(results)} results")

        # Serialize context for downstream nodes
        needs_synthesis = len(results) > 1 and complexity == "complex"

        # For simple case, store the response directly
        final_response = ""
        if not needs_synthesis and results:
            r = results[0]
            final_response = r["message"] if r["success"] else f"執行失敗：{r['message']}"

        return {
            "results": results,
            "needs_synthesis": needs_synthesis,
            "final_response": final_response,
            "context": {
                "session_id": session_id,
                "original_query": query,
                "complexity": complexity,
                "intent": agent_name,
                "symbols": symbols,
                "plan": [asdict(t) for t in plan],
                "codebook_entry_id": state.get("codebook_entry_id"),
                "agent_results": results,
            },
        }

    def _synthesize_node(self, state: V4State) -> dict:
        """Node: Synthesize multiple agent results into final report."""
        results = state.get("results", [])

        results_text = "\n\n".join(
            f"### [{r.get('agent_name', '?')}]\n{r.get('message', '')}"
            for r in results
            if r.get("success")
        )
        if not results_text:
            results_text = "（所有 Agent 均未產生結果）"

        prompt = PromptRegistry.render(
            "manager", "synthesize",
            query=state["query"],
            clarifications=state.get("clarification") or "無",
            results=results_text,
        )
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            final_response = response.content
        except Exception:
            final_response = results_text

        print(f"[Node: synthesize] Generated report ({len(final_response)} chars)")
        return {"final_response": final_response}

    def _feedback_node(self, state: V4State) -> dict:
        """Node: Prepare context for downstream nodes (codebook save moved to save_codebook)."""
        return {}

    def _save_codebook_node(self, state: V4State) -> dict:
        """Node: Save successful, user-satisfied execution to codebook."""
        ctx_data = state.get("context")
        if not ctx_data:
            return {}
        try:
            plan = []
            for p in ctx_data.get("plan", []):
                p_copy = p.copy()
                p_copy["result"] = None
                plan.append(SubTask(**p_copy))

            context = ExecutionContext(
                session_id=ctx_data.get("session_id", ""),
                original_query=ctx_data.get("original_query", ""),
                complexity=TaskComplexity(ctx_data.get("complexity", "simple")),
                intent=ctx_data.get("intent", "chat"),
                symbols=ctx_data.get("symbols", []),
                plan=plan,
                codebook_entry_id=ctx_data.get("codebook_entry_id"),
            )
            has_success = any(r.get("success") for r in state.get("results", []))
            if has_success:
                self.codebook.save(context)
                print("[Node: save_codebook] Saved to codebook ✅")
        except Exception as e:
            print(f"[Node: save_codebook] error: {e}")
        return {}

    def _save_messages_node(self, state: V4State) -> dict:
        """Append assistant response to messages for next-turn memory."""
        response = state.get("final_response", "")
        messages = state.get("messages", [])
        if response:
            messages = messages + [{"role": "assistant", "content": response}]
        return {"messages": messages}

    def _ask_satisfaction_node(self, state: V4State) -> dict:
        """Node: Ask user for satisfaction on complex tasks only."""
        complexity = state.get("complexity", "simple")
        if complexity != "complex":
            return {"satisfaction_skip": True, "satisfaction_retry": False}

        final_response = state.get("final_response", "")

        if self.web_mode:
            answer = interrupt({
                "type": "satisfaction",
                "question": "這個結果符合您的需求嗎？",
                "options": ["滿意", "不滿意，需要補充"],
                "preview": final_response[:300],
            })
            if answer in ("滿意", "1", ""):
                return {"satisfaction_retry": False, "satisfaction_skip": False}
            return {
                "satisfaction_retry": True,
                "satisfaction_feedback": answer,
                "satisfaction_skip": False,
            }
        else:
            satisfied, feedback = self.hitl.ask_satisfaction(final_response)
            if satisfied:
                return {"satisfaction_retry": False, "satisfaction_skip": False}
            return {
                "satisfaction_retry": True,
                "satisfaction_feedback": feedback,
                "satisfaction_skip": False,
            }

    def _extract_memory_node(self, state: V4State) -> dict:
        """Extract structured facts from the latest turn — avoids summarization pitfalls."""
        messages = state.get("messages", [])
        if len(messages) < 3:  # need at least one complete turn
            return {}

        # Find last user + assistant messages
        last_user = last_assistant = None
        for m in reversed(messages):
            if m["role"] == "assistant" and last_assistant is None:
                last_assistant = m["content"]
            elif m["role"] == "user" and last_user is None:
                last_user = m["content"]
            if last_user and last_assistant:
                break

        if not last_user or not last_assistant:
            return {}

        existing_facts = state.get("memory", [])
        turn_index = len(messages) // 2

        prompt = PromptRegistry.render(
            "manager", "extract_memory",
            user_message=last_user[:300],
            assistant_message=last_assistant[:300],
            existing_facts=json.dumps(existing_facts, ensure_ascii=False),
            turn_index=turn_index,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            new_facts = self._parse_json(response.content).get("facts", [])

            # Merge: same key overwrites existing
            fact_map = {f["key"]: f for f in existing_facts if f.get("key")}
            for f in new_facts:
                if f.get("key") and f.get("value"):
                    fact_map[f["key"]] = f

            updated = list(fact_map.values())[-20:]  # cap at 20 facts
            print(f"[Node: extract_memory] {len(updated)} facts total")
            return {"memory": updated}
        except Exception as e:
            print(f"[Node: extract_memory] error: {e}")
            return {}

    # ══════════════════════════════════════════
    # 5. Public API (unchanged — same as before)
    # ══════════════════════════════════════════

    def process(self, query: str, session_id: str = None) -> str:
        """Main entry point — invoke the LangGraph with memory."""
        if session_id is None:
            session_id = str(uuid4())

        # Build config with thread_id for checkpointer (short-term memory)
        config = {"configurable": {"thread_id": session_id}}

        # Get existing messages and memory from previous turns (if any)
        existing_messages = []
        existing_memory = []
        try:
            checkpoint = self.checkpointer.get(config)
            if checkpoint and checkpoint.get("channel_values"):
                existing_messages = checkpoint["channel_values"].get("messages", [])
                existing_memory = checkpoint["channel_values"].get("memory", [])
        except Exception:
            pass

        # Append current user message
        messages = existing_messages + [{"role": "user", "content": query}]

        # Keep last 10 messages (5 turns) — structured memory carries long-term context
        if len(messages) > 10:
            messages = messages[-10:]

        # Invoke the compiled graph
        initial_state: V4State = {
            "query": query,
            "session_id": session_id,
            "messages": messages,
            "memory": existing_memory,
        }

        result = self.graph.invoke(initial_state, config)

        # Append assistant response to messages for next turn
        response = result.get("final_response", "無回應")
        return response

    def get_status(self) -> dict:
        """Return system status for diagnostics."""
        agents = [m.name for m in self.agent_registry.list_all()]
        tools = [t.name for t in self.all_tools]
        return {
            "agents": agents,
            "tools": tools,
            "codebook": self.codebook.stats(),
        }

    # ══════════════════════════════════════════
    # Internal Helpers (same as before)
    # ══════════════════════════════════════════

    def _classify(self, query: str) -> dict:
        agents_info = self.agent_registry.agents_info_for_prompt()
        tools_info = self._build_tools_info()
        prompt = PromptRegistry.render(
            "manager", "classify",
            query=query,
            agents_info=agents_info,
            tools_info=tools_info,
        )
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_json(response.content)
            if result:
                return result
        except Exception as e:
            print(f"[Manager] classify error: {e}")

        return {
            "complexity": "simple",
            "agent": "chat",
            "symbols": [],
            "ambiguity_question": None,
        }

    def _build_tools_info(self) -> str:
        """Dynamic tool descriptions for prompts — from @tool functions."""
        return "\n".join(
            f"- {t.name}: {t.description}"
            for t in self.all_tools
        )

    def _plan(self, query: str, agent_name: str, symbols: List[str]) -> List[SubTask]:
        tools_info = self._build_tools_info()
        agents_info = self.agent_registry.agents_info_for_prompt()
        prompt = PromptRegistry.render(
            "manager", "plan",
            query=query,
            agent=agent_name,
            symbols=", ".join(symbols) if symbols else "未指定",
            clarifications="無",
            agents_info=agents_info,
            tools_info=tools_info,
        )
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_json(response.content)
            plan_data = result.get("plan", [])
            return [
                SubTask(
                    step=item.get("step", i + 1),
                    description=item.get("description", query),
                    agent=item.get("agent", agent_name),
                    tool_hint=item.get("tool_hint"),
                )
                for i, item in enumerate(plan_data)
            ]
        except Exception as e:
            print(f"[Manager] plan error: {e}")

        return [SubTask(step=1, description=query, agent=agent_name, tool_hint=None)]

    def _handle_collaboration(self, request: CollaborationRequest, context: ExecutionContext) -> Optional[AgentResult]:
        """Handle a collaboration request from one agent to another."""
        agent = self.router.route_collaboration(request)
        if agent is None:
            print(f"[Manager] collaboration failed: no agent for '{request.needed_agent}'")
            return None

        collab_task = SubTask(
            step=len(context.plan) + 1,
            description=request.context,
            agent=request.needed_agent,
            tool_hint=None,
        )
        return agent.execute(collab_task)

    def _parse_json(self, content: str) -> dict:
        """Parse JSON from LLM response (handles markdown blocks, etc)."""
        try:
            return json.loads(content)
        except Exception:
            pass
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', content)
            return json.loads(cleaned)
        except Exception:
            pass
        try:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                return json.loads(content[start:end + 1])
        except Exception:
            pass
        return {}
