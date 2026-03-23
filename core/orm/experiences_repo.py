"""
Async ORM repository for Task Experience operations.

Provides async equivalents of the functions in core.database.experiences,
using SQLAlchemy 2.0 select with the TaskExperience model.

Usage::

    from core.orm.experiences_repo import experiences_repo

    await experiences_repo.record_experience("user-1", "session-1", "crypto", ...)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TaskExperience
from .session import using_session

logger = logging.getLogger(__name__)


def _quality_to_float(quality: Any) -> Optional[float]:
    """Map AgentResult.quality (str or float) to float for storage."""
    if quality is None:
        return None
    if isinstance(quality, float):
        return quality
    if isinstance(quality, str):
        if quality == "pass":
            return 1.0
        if quality == "fail":
            return 0.0
    return None


def _to_dict(exp: TaskExperience) -> Dict[str, Any]:
    """Convert a TaskExperience ORM object to dict format expected by routes."""
    return {
        "id": exp.id,
        "user_id": exp.user_id,
        "session_id": exp.session_id,
        "task_family": exp.task_family,
        "query_text": exp.query_text,
        "tools_used": exp.tools_used,
        "agent_used": exp.agent_used,
        "outcome": exp.outcome,
        "quality_score": exp.quality_score,
        "failure_reason": exp.failure_reason,
        "response_chars": exp.response_chars,
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
    }


class ExperiencesRepository:
    """Async ORM repository for task experiences and tool execution stats."""

    async def record_experience(
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
        session: AsyncSession | None = None,
    ) -> None:
        """Persist one task trajectory. Called fire-and-forget from manager."""
        try:
            exp = TaskExperience(
                user_id=user_id,
                session_id=session_id,
                task_family=task_family,
                query_text=query,
                tools_used=tools_used,
                agent_used=agent_used,
                outcome=outcome,
                quality_score=_quality_to_float(quality_score),
                failure_reason=failure_reason,
                response_chars=response_chars,
            )

            async with using_session(session) as s:
                s.add(exp)
        except Exception as exc:
            logger.warning("[ExperiencesRepo] record_experience failed: %s", exc)

    async def retrieve_relevant(
        self,
        user_id: Optional[str],
        task_family: str,
        query: str,
        limit: int = 5,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant past experiences via structured filter + FTS.

        Returns empty list on any failure — never raises.
        """
        if not user_id:
            return []
        try:
            return await self._layer1_2_query(
                user_id, task_family, query, limit, session
            )
        except Exception as exc:
            logger.warning(
                "[ExperiencesRepo] retrieve_relevant failed: %s", exc
            )
            return []

    async def _layer1_2_query(
        self,
        user_id: str,
        task_family: str,
        query: str,
        limit: int,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Structured filter + FTS ts_rank in a single SQL round-trip."""
        rank_expr = func.ts_rank(
            TaskExperience.query_tsv,
            func.plainto_tsquery("simple", query),
        ).label("rank")

        stmt = (
            select(
                TaskExperience.id,
                TaskExperience.task_family,
                TaskExperience.query_text,
                TaskExperience.tools_used,
                TaskExperience.agent_used,
                TaskExperience.outcome,
                TaskExperience.quality_score,
                TaskExperience.failure_reason,
                TaskExperience.created_at,
                rank_expr,
            )
            .where(
                TaskExperience.user_id == user_id,
                TaskExperience.task_family == task_family,
            )
            .order_by(rank_expr.desc(), TaskExperience.created_at.desc())
            .limit(limit)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            return [
                {
                    "id": r[0],
                    "task_family": r[1],
                    "query_text": r[2],
                    "tools_used": r[3],
                    "agent_used": r[4],
                    "outcome": r[5],
                    "quality_score": r[6],
                    "failure_reason": r[7],
                    "created_at": r[8],
                    "rank": r[9],
                }
                for r in rows
            ]

    def format_for_prompt(self, experiences: List[Dict]) -> str:
        """Format retrieved experiences as a compact hint block for LLM injection."""
        if not experiences:
            return ""
        lines = ["## 相關過去經驗（僅供參考）"]
        for exp in experiences:
            tools = ", ".join(exp.get("tools_used") or []) or "無"
            date_str = str(exp.get("created_at", ""))[:10]
            outcome = exp.get("outcome", "unknown")
            reason = (
                f" 原因: {exp['failure_reason']}" if exp.get("failure_reason") else ""
            )
            lines.append(
                f"- [{exp.get('task_family', '')}, {date_str}] "
                f"{exp.get('query_text', '')} → 工具: {tools} → {outcome}{reason}"
            )
        return "\n".join(lines)


experiences_repo = ExperiencesRepository()
