"""
Experience and tool memory store for Phase 3.

Provides:
- record_experience(): write task trajectory after each agent turn
- record_tool_stat(): write tool telemetry after each tool invocation
- retrieve_relevant(): 3-layer retrieval (structured + FTS + optional LLM rerank)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import DatabaseBase

logger = logging.getLogger(__name__)


def _quality_to_float(quality: Any) -> Optional[float]:
    """Map AgentResult.quality (str or float) to float for storage."""
    if quality is None:
        return None
    if isinstance(quality, float):
        return quality
    if quality == "pass":
        return 1.0
    if quality == "fail":
        return 0.0
    return None


class ExperienceStore:
    """Read/write task experiences and tool execution stats."""

    # ── writes ────────────────────────────────────────────────────────────────

    def record_experience(
        self,
        user_id: str,
        session_id: str,
        task_family: str,
        query: str,
        tools_used: List[str],
        agent_used: str,
        outcome: str,
        quality_score: Any = None,
        failure_reason: Optional[str] = None,
        response_chars: Optional[int] = None,
    ) -> None:
        """Persist one task trajectory. Called fire-and-forget from manager."""
        try:
            DatabaseBase.execute(
                """INSERT INTO task_experiences
                   (user_id, session_id, task_family, query_text,
                    tools_used, agent_used, outcome,
                    quality_score, failure_reason, response_chars)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    user_id,
                    session_id,
                    task_family,
                    query,
                    tools_used,
                    agent_used,
                    outcome,
                    _quality_to_float(quality_score),
                    failure_reason,
                    response_chars,
                ),
            )
        except Exception as exc:
            logger.warning("[ExperienceStore] record_experience failed: %s", exc)

    def record_tool_stat(
        self,
        user_id: Optional[str],
        tool_name: str,
        success: bool,
        latency_ms: Optional[int] = None,
        output_chars: Optional[int] = None,
        error_type: Optional[str] = None,
    ) -> None:
        """Persist one tool execution stat. Called fire-and-forget from manager."""
        try:
            DatabaseBase.execute(
                """INSERT INTO tool_execution_stats
                   (user_id, tool_name, success, latency_ms, output_chars, error_type)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, tool_name, success, latency_ms, output_chars, error_type),
            )
        except Exception as exc:
            logger.warning("[ExperienceStore] record_tool_stat failed: %s", exc)

    # ── retrieval ─────────────────────────────────────────────────────────────

    def retrieve_relevant(
        self,
        user_id: Optional[str],
        task_family: str,
        query: str,
        llm: Any,
        limit: int = 5,
    ) -> List[Dict]:
        """3-layer retrieval: structured filter + FTS (combined SQL) + optional LLM rerank.

        Returns empty list on any failure — never raises.
        """
        if not user_id:
            return []
        try:
            candidates = self._layer1_2_query(user_id, task_family, query, limit)
            if len(candidates) >= 2 and llm is not None:
                candidates = self._layer3_llm_rerank(candidates, query, llm)
            return candidates
        except Exception as exc:
            logger.warning("[ExperienceStore] retrieve_relevant failed: %s", exc)
            return []

    def _layer1_2_query(
        self,
        user_id: str,
        task_family: str,
        query: str,
        limit: int,
    ) -> List[Dict]:
        """Layers 1+2: structured filter + FTS ts_rank in a single SQL round-trip."""
        rows = DatabaseBase.query_all(
            """SELECT id, task_family, query_text, tools_used, agent_used,
                      outcome, quality_score, failure_reason, created_at,
                      ts_rank(query_tsv, plainto_tsquery('simple', %s)) AS rank
               FROM task_experiences
               WHERE user_id = %s
                 AND task_family = %s
               ORDER BY rank DESC, created_at DESC
               LIMIT %s""",
            (query, user_id, task_family, limit),
        )
        return rows or []

    def _layer3_llm_rerank(
        self,
        candidates: List[Dict],
        current_query: str,
        llm: Any,
    ) -> List[Dict]:
        """Layer 3: ask LLM to select the 1-2 most relevant candidates.

        Falls back to returning candidates unchanged on any failure.
        """
        try:
            from langchain_core.messages import HumanMessage

            numbered = "\n".join(
                f"{i + 1}. [{c['outcome']}] {c['query_text']} "
                f"(工具: {', '.join(c.get('tools_used') or [])})"
                for i, c in enumerate(candidates)
            )
            prompt = (
                f"Current query: {current_query}\n\n"
                f"Past experiences:\n{numbered}\n\n"
                "Which 1-2 past experiences are most relevant? "
                "Reply with only the numbers, comma-separated (e.g. '1,3')."
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            indices_str = response.content
            if isinstance(indices_str, list):
                indices_str = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in indices_str
                )
            indices_str = indices_str.strip()
            indices = [
                int(x.strip()) - 1
                for x in indices_str.split(",")
                if x.strip().isdigit()
            ]
            selected = [candidates[i] for i in indices if 0 <= i < len(candidates)]
            return selected if selected else candidates
        except Exception as exc:
            logger.debug(
                "[ExperienceStore] layer3 rerank failed, returning unranked: %s", exc
            )
            return candidates

    def format_for_prompt(self, experiences: List[Dict]) -> str:
        """Format retrieved experiences as a compact hint block for LLM injection."""
        if not experiences:
            return ""
        lines = ["## 相關過去經驗（僅供參考）"]
        for exp in experiences:
            tools = ", ".join(exp.get("tools_used") or []) or "無"
            date = str(exp.get("created_at", ""))[:10]
            outcome = exp.get("outcome", "unknown")
            reason = (
                f" 原因: {exp['failure_reason']}" if exp.get("failure_reason") else ""
            )
            lines.append(
                f"- [{exp.get('task_family', '')}, {date}] "
                f"{exp.get('query_text', '')} → 工具: {tools} → {outcome}{reason}"
            )
        return "\n".join(lines)
