"""
Analysis policy resolver.

Centralizes analysis-mode and query-type decisions so runtime behavior is
policy-driven instead of being scattered across agent branches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


@dataclass(frozen=True)
class PolicyDecision:
    required_tool_role: Optional[str] = None
    fail_reason: Optional[str] = None


@dataclass(frozen=True)
class ModeAccessPolicy:
    allowed_modes: tuple[str, ...]
    default_mode: str


class AnalysisPolicyResolver:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).resolve().parents[2] / "config" / "analysis_policy.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, object]:
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def get_mode_access_policy(self, user_tier: Optional[str]) -> ModeAccessPolicy:
        normalized_tier = "premium" if str(user_tier or "free").strip().lower() in {"premium", "plus", "pro"} else "free"
        tier_modes = self.config.get("tier_modes", {})
        if not isinstance(tier_modes, dict):
            return ModeAccessPolicy(allowed_modes=("quick",), default_mode="quick")

        raw_policy = tier_modes.get(normalized_tier) or tier_modes.get("free") or {}
        if not isinstance(raw_policy, dict):
            return ModeAccessPolicy(allowed_modes=("quick",), default_mode="quick")

        raw_allowed_modes = raw_policy.get("allowed_modes", ["quick"])
        if not isinstance(raw_allowed_modes, list):
            raw_allowed_modes = ["quick"]

        allowed_modes = tuple(
            mode for mode in raw_allowed_modes
            if isinstance(mode, str) and mode in {"quick", "verified", "research"}
        ) or ("quick",)

        default_mode = raw_policy.get("default_mode")
        if not isinstance(default_mode, str) or default_mode not in allowed_modes:
            default_mode = allowed_modes[0]

        return ModeAccessPolicy(
            allowed_modes=allowed_modes,
            default_mode=default_mode,
        )

    def ensure_allowed_mode(self, user_tier: Optional[str], requested_mode: Optional[str]) -> str:
        policy = self.get_mode_access_policy(user_tier)
        if requested_mode in policy.allowed_modes:
            return str(requested_mode)
        return policy.default_mode

    def build_query_profile(self, query: str, candidates: list[str]) -> Dict[str, object]:
        query_type = "general"
        query_type_rules = self.config.get("query_types", {})
        if isinstance(query_type_rules, dict):
            for name, rule in query_type_rules.items():
                if not isinstance(rule, dict):
                    continue
                patterns = rule.get("patterns", [])
                requires_candidates = bool(rule.get("requires_symbol_candidates"))
                if not isinstance(patterns, list):
                    continue
                if requires_candidates and not candidates:
                    continue
                if _matches_any(query or "", patterns):
                    query_type = name
                    break

        return {
            "query_type": query_type,
            "has_symbol_candidates": bool(candidates),
        }

    def resolve(self, context: Dict[str, object]) -> PolicyDecision:
        analysis_mode = context.get("analysis_mode", "quick")
        if analysis_mode not in {"verified", "research"}:
            return PolicyDecision()

        metadata = context.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        market_resolution = metadata.get("market_resolution", {})
        if not isinstance(market_resolution, dict):
            market_resolution = {}

        query_profile = metadata.get("query_profile", {})
        if not isinstance(query_profile, dict):
            query_profile = {}

        query_type = query_profile.get("query_type", "general")
        modes = self.config.get("modes", {})
        if not isinstance(modes, dict):
            return PolicyDecision()
        mode_rules = modes.get(str(analysis_mode), {})
        if not isinstance(mode_rules, dict):
            return PolicyDecision()
        query_rules = mode_rules.get(str(query_type), {})
        if not isinstance(query_rules, dict):
            return PolicyDecision()

        if market_resolution.get("requires_discovery_lookup"):
            return PolicyDecision(
                required_tool_role=query_rules.get("discovery_role"),
                fail_reason=query_rules.get("discovery_fail_reason"),
            )

        if context.get("tool_required"):
            return PolicyDecision(
                required_tool_role=query_rules.get("resolved_role"),
                fail_reason=query_rules.get("resolved_fail_reason"),
            )

        return PolicyDecision()
