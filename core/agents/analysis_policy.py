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


class AnalysisPolicyResolver:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).resolve().parents[2] / "config" / "analysis_policy.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, object]:
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

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
        if analysis_mode != "verified":
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
