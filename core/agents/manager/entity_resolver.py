"""
Manager Agent - Market Entity Resolution

Contains market entity extraction and resolution:
- _extract_market_entities: Extract single-market entities from query
- _reconcile_market_entities: Reconcile LLM and resolver entities
- _apply_pronoun_entity_carryover: Pronoun-based entity carryover
- _extract_symbol_candidates: Extract possible market symbol candidates
- _normalize_query_text: Unicode normalization for query text
- _contains_symbol_pronoun: Check if text contains symbol pronouns
- _resolve_boundary_agent_name: Resolve boundary agent name from registry
- _extract_latest_user_utterance: Extract latest user utterance from history
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional

from .mixin_base import ManagerAgentMixin


class EntityResolverMixin(ManagerAgentMixin):
    """Market entity resolution for ManagerAgent."""

    def _extract_market_entities(
        self, query: str, history: str = ""
    ) -> Dict[str, Optional[str]]:
        """從 query 擷取單市場實體，避免把 routing 綁死在 prompt。"""
        normalized = self._normalize_query_text(query)
        result = {"crypto": None, "tw": None, "us": None}
        candidates = self._extract_symbol_candidates(normalized)
        if not candidates and self._contains_symbol_pronoun(normalized):
            latest_user_utterance = self._extract_latest_user_utterance(history)
            if latest_user_utterance:
                candidates = self._extract_symbol_candidates(
                    self._normalize_query_text(latest_user_utterance)
                )
        for candidate in candidates:
            resolution = self._symbol_resolver.resolve_with_context(
                candidate, context_text=normalized
            )
            flat_resolution = resolution.get("resolution", {})
            if not isinstance(flat_resolution, dict):
                flat_resolution = {}
            primary_market = resolution.get("primary_market")
            if primary_market in result:
                primary_symbol = flat_resolution.get(primary_market)
                if primary_symbol and result.get(primary_market) is None:
                    result[primary_market] = primary_symbol
                continue

            for market, value in flat_resolution.items():
                if value and result.get(market) is None:
                    result[market] = value

        return result

    @staticmethod
    def _extract_latest_user_utterance(history: str) -> str:
        if not history:
            return ""
        lines = [line.strip() for line in history.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("使用者:"):
                return line.split(":", 1)[1].strip()
            if line.lower().startswith("user:"):
                return line.split(":", 1)[1].strip()
        return ""

    def _reconcile_market_entities(
        self,
        query: str,
        history: str,
        llm_entities: Optional[Dict[str, Optional[str]]] = None,
    ) -> Dict[str, Optional[str]]:
        normalized_llm_entities = {
            "crypto": None,
            "tw": None,
            "us": None,
        }
        if isinstance(llm_entities, dict):
            for market in normalized_llm_entities:
                value = llm_entities.get(market)
                if value:
                    normalized_llm_entities[market] = value

        resolver_entities = self._extract_market_entities(query, history=history)
        llm_markets = [
            market for market, value in normalized_llm_entities.items() if value
        ]
        resolver_markets = [
            market for market, value in resolver_entities.items() if value
        ]

        if len(resolver_markets) == 1:
            resolver_market = resolver_markets[0]
            if len(llm_markets) != 1 or llm_markets[0] != resolver_market:
                return resolver_entities
            if normalized_llm_entities.get(resolver_market) != resolver_entities.get(
                resolver_market
            ):
                return resolver_entities

        if len(llm_markets) == 1:
            return normalized_llm_entities

        return resolver_entities if resolver_markets else normalized_llm_entities

    def _apply_pronoun_entity_carryover(
        self,
        query: str,
        current_entities: Dict[str, Optional[str]],
        prior_entities: Dict[str, Optional[str]],
    ) -> Dict[str, Optional[str]]:
        """If a query only uses pronouns and no explicit symbol, keep last resolved entity."""
        normalized = self._normalize_query_text(query)
        if self._extract_symbol_candidates(normalized):
            return current_entities
        if not self._contains_symbol_pronoun(normalized):
            return current_entities

        prior = {"crypto": None, "tw": None, "us": None}
        if isinstance(prior_entities, dict):
            for market in prior:
                value = prior_entities.get(market)
                if value:
                    prior[market] = value

        prior_markets = [market for market, value in prior.items() if value]
        if len(prior_markets) != 1:
            return current_entities
        return prior

    @staticmethod
    def _contains_symbol_pronoun(text: str) -> bool:
        return bool(
            re.search(
                r"(它|他|她|這個幣|這支股票|那個|這檔|那檔|that one|it)",
                text,
                flags=re.IGNORECASE,
            )
        )

    def _extract_symbol_candidates(self, query: str) -> List[str]:
        """抽取可能的市場符號候選，保持順序與去重。"""
        raw_candidates = re.findall(r"[A-Za-z]{1,10}|\d{2,6}", query)
        seen = set()
        candidates: List[str] = []
        for candidate in raw_candidates:
            normalized = candidate.strip()
            if not normalized:
                continue
            key = normalized.upper()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(normalized)
        return candidates

    def _normalize_query_text(self, query: str) -> str:
        """先做 Unicode 正規化，降低全形/半形混用造成的 routing 偏差。"""
        return unicodedata.normalize("NFKC", query or "").strip()

    def _resolve_boundary_agent_name(self, market: str) -> Optional[str]:
        """根據 registry metadata 反查對應 agent，避免在 manager 維護名稱映射表。"""
        matched_metadata = []
        for metadata in self.agent_registry.list_all():
            tokens = metadata.name.lower().split("_")
            if market in tokens:
                matched_metadata.append(metadata)

        if not matched_metadata:
            return None

        matched_metadata.sort(key=lambda metadata: (-metadata.priority, metadata.name))
        for metadata in matched_metadata:
            if self.agent_registry.get(metadata.name) is not None:
                return metadata.name
        return None
