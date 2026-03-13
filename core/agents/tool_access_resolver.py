"""
Tool access resolver.

Resolves the final allowed tool set before an agent executes, so membership
tiers and user preferences remain outside agent reasoning.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.database.tools import get_allowed_tools, normalize_membership_tier


class ToolAccessResolver:
    """Resolve and cache allowed tools per agent for the current user scope."""

    def __init__(self, user_tier: str = "free", user_id: Optional[str] = None):
        self.user_tier = normalize_membership_tier(user_tier)
        self.user_id = user_id
        self._cache: Dict[str, List[str]] = {}

    def update_scope(self, user_tier: str, user_id: Optional[str]) -> None:
        normalized_tier = normalize_membership_tier(user_tier)
        if normalized_tier == self.user_tier and user_id == self.user_id:
            return
        self.user_tier = normalized_tier
        self.user_id = user_id
        self._cache.clear()

    def resolve_for_agent(self, agent_name: str) -> List[str]:
        if agent_name in self._cache:
            return list(self._cache[agent_name])

        allowed_tools = get_allowed_tools(
            agent_name,
            user_tier=self.user_tier,
            user_id=self.user_id,
        )
        self._cache[agent_name] = list(allowed_tools)
        return list(allowed_tools)
