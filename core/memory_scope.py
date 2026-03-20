"""
Shared scope helpers for tenant-aware memory and compacted tool results.

Current contract:
- `user_id` is the canonical owner boundary.
- `session_id` is a conversation/thread boundary.
- `workspace_id` is an optional higher-level collaboration boundary.

For current memory context caching we keep cross-session semantics, so cache keys
default to user/workspace scope and exclude session unless explicitly requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MemoryScope:
    user_id: str
    session_id: str = "default"
    workspace_id: Optional[str] = None


def build_scope(
    user_id: Optional[str],
    session_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> MemoryScope:
    return MemoryScope(
        user_id=(user_id or "anonymous"),
        session_id=(session_id or "default"),
        workspace_id=workspace_id or None,
    )


def scope_namespace(scope: MemoryScope, *, include_session: bool = False) -> str:
    parts = [f"user:{scope.user_id}"]
    if scope.workspace_id:
        parts.append(f"workspace:{scope.workspace_id}")
    elif include_session:
        parts.append(f"session:{scope.session_id}")
    return "|".join(parts)
