"""
Manager Agent - Response Construction

Contains response building and formatting:
- _collect_response_evidence: Collect evidence from task results
- _format_response_evidence: Format evidence for prompt
- _build_mode_response_contract: Build response contract by mode
- _build_response_format_guidance: Build format guidance by mode
- _finalize_mode_response: Post-process response by analysis mode
- _build_market_resolution_metadata: Build market resolution metadata
- _build_query_policy_metadata: Build query policy metadata
- _build_response_trace_metadata: Build response trace metadata
- _quick_anomaly_check: Quick anomaly detection without LLM
- _ANOMALY_PATTERNS: Patterns for anomaly detection
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from core.agents.prompt_registry import PromptRegistry

from .mixin_base import ManagerAgentMixin


class ResponseMixin(ManagerAgentMixin):
    """Response construction for ManagerAgent."""

    _ANOMALY_PATTERNS = [
        "XXX",
        "N/A",
        "null",
        "undefined",
        "獲取失敗",
        "timeout",
        "error",
        "Error",
        "ERR",
    ]

    def _quick_anomaly_check(self, results: dict) -> bool:
        """快速檢查是否有明顯異常（無需 LLM）"""
        for task_id, result in results.items():
            msg = str(result.get("message", ""))
            if any(p in msg for p in self._ANOMALY_PATTERNS):
                return True
        return False

    def _collect_response_evidence(
        self, task_results: Dict[str, Dict[str, object]]
    ) -> Dict[str, object]:
        used_tools: List[str] = []
        data_points: List[str] = []
        verification_statuses: List[str] = []
        markets: List[str] = []
        query_types: List[str] = []
        policy_paths: List[str] = []

        for result in task_results.values():
            if not isinstance(result, dict):
                continue
            data = result.get("data", {})
            if not isinstance(data, dict):
                continue
            used_tools.extend(
                tool
                for tool in data.get("used_tools", [])
                if isinstance(tool, str) and tool
            )
            if isinstance(data.get("data_as_of"), str) and data["data_as_of"]:
                data_points.append(data["data_as_of"])
            if (
                isinstance(data.get("verification_status"), str)
                and data["verification_status"]
            ):
                verification_statuses.append(data["verification_status"])
            if isinstance(data.get("resolved_market"), str) and data["resolved_market"]:
                markets.append(data["resolved_market"])
            if isinstance(data.get("query_type"), str) and data["query_type"]:
                query_types.append(data["query_type"])
            if isinstance(data.get("policy_path"), str) and data["policy_path"]:
                policy_paths.append(data["policy_path"])

        return {
            "used_tools": sorted(set(used_tools)),
            "data_as_of": data_points[0] if data_points else None,
            "verification_status": (
                verification_statuses[0] if verification_statuses else None
            ),
            "resolved_markets": sorted(set(markets)),
            "query_types": sorted(set(query_types)),
            "policy_paths": sorted(set(policy_paths)),
        }

    def _format_response_evidence(self, evidence: Dict[str, object]) -> str:
        parts = []
        tools = evidence.get("used_tools", [])
        if tools:
            parts.append(f"- 工具：{', '.join(tools)}")
        if evidence.get("data_as_of"):
            parts.append(f"- 資料時間：{evidence['data_as_of']}")
        if evidence.get("verification_status"):
            parts.append(f"- 驗證狀態：{evidence['verification_status']}")
        markets = evidence.get("resolved_markets", [])
        if markets:
            parts.append(f"- 解析市場：{', '.join(markets)}")
        query_types = evidence.get("query_types", [])
        if query_types:
            parts.append(f"- 查詢類型：{', '.join(query_types)}")
        policy_paths = evidence.get("policy_paths", [])
        if policy_paths:
            parts.append(f"- 路徑：{', '.join(policy_paths)}")
        return "\n".join(parts) if parts else "- 無結構化依據"

    def _build_mode_response_contract(
        self,
        analysis_mode: str,
        query: str,
        evidence: Dict[str, object],
    ) -> str:
        lowered_query = (query or "").lower()
        is_compare = any(
            token in lowered_query for token in ("比較", "compare", "vs", "差異")
        )

        if analysis_mode == "verified":
            return PromptRegistry.render(
                "manager",
                "response_contract_verified",
                include_time=False,
            )
        if analysis_mode == "research":
            return PromptRegistry.render(
                "manager",
                "response_contract_research_compare"
                if is_compare
                else "response_contract_research",
                include_time=False,
            )
        return PromptRegistry.render(
            "manager",
            "response_contract_quick",
            include_time=False,
        )

    def _build_response_format_guidance(
        self,
        analysis_mode: str,
        query: str,
    ) -> str:
        lowered_query = (query or "").lower()
        is_compare = any(
            token in lowered_query for token in ("比較", "compare", "vs", "差異")
        )

        if is_compare:
            return PromptRegistry.render(
                "manager",
                "response_format_compare",
                include_time=False,
            )

        if analysis_mode == "research":
            return PromptRegistry.render(
                "manager",
                "response_format_research",
                include_time=False,
            )

        if analysis_mode == "verified":
            return PromptRegistry.render(
                "manager",
                "response_format_verified",
                include_time=False,
            )

        return PromptRegistry.render(
            "manager",
            "response_format_quick",
            include_time=False,
        )

    def _finalize_mode_response(
        self,
        response: str,
        analysis_mode: str,
        evidence: Dict[str, object],
        query: str = "",
    ) -> str:
        cleaned = re.sub(
            r"^#\s*Sub-Agent 執行結果\s*", "", response, flags=re.MULTILINE
        ).strip()
        cleaned = re.sub(
            r"^###\s*任務\s+\d+\s+\[[^\]]+\]\s*", "", cleaned, flags=re.MULTILINE
        ).strip()
        cleaned = re.sub(
            r"^\s*-\s*(資料時間|驗證來源|驗證狀態)[:：].*$",
            "",
            cleaned,
            flags=re.MULTILINE,
        ).strip()
        cleaned = re.sub(r"\n*驗證資訊[:：].*", "", cleaned).strip()
        cleaned = re.sub(r"\n*研究依據[:：].*", "", cleaned).strip()
        cleaned = re.sub(
            r"\n+#{3,6}\s*驗證資訊\s*[\s\S]*$",
            "",
            cleaned,
            flags=re.MULTILINE,
        ).strip()
        cleaned = re.sub(
            r"\n+#{3,6}\s*研究依據\s*[\s\S]*$",
            "",
            cleaned,
            flags=re.MULTILINE,
        ).strip()

        lowered_query = (query or "").lower()
        is_compare = any(
            token in lowered_query for token in ("比較", "compare", "vs", "差異")
        )
        if not is_compare:
            cleaned = re.sub(
                r"\n*###\s*標的比較[\s\S]*?(?=\n###\s|\Z)",
                "",
                cleaned,
                flags=re.MULTILINE,
            ).strip()

        if analysis_mode == "verified":
            lacks_verified_evidence = evidence.get("verification_status") != "verified"
            is_causal_question = any(
                token in lowered_query
                for token in ("為什麼", "原因", "why", "怎麼跌", "怎麼漲")
            )
            if lacks_verified_evidence and is_causal_question:
                cleaned = "目前缺少可驗證的事件資料來源，無法確認漲跌原因。若你要，我可以先查新聞與公告後再回答。"
            evidence_lines = []
            if evidence.get("data_as_of"):
                evidence_lines.append(f"- 資料時間：{evidence['data_as_of']}")
            tools = evidence.get("used_tools", [])
            if tools:
                evidence_lines.append(f"- 驗證來源：{', '.join(tools)}")
            if evidence.get("verification_status"):
                evidence_lines.append(f"- 驗證狀態：{evidence['verification_status']}")
            if not evidence_lines:
                evidence_lines.append(
                    "- 驗證資訊目前有限，請結合畫面上的 metadata 與工具來源判讀。"
                )
            cleaned = f"{cleaned}\n\n### 驗證資訊\n" + "\n".join(evidence_lines)
        elif analysis_mode == "research":
            evidence_lines = []
            tools = evidence.get("used_tools", [])
            if tools:
                evidence_lines.append(f"- 研究工具：{', '.join(tools)}")
            if evidence.get("data_as_of"):
                evidence_lines.append(f"- 資料時間：{evidence['data_as_of']}")
            if not evidence_lines:
                evidence_lines.append(
                    "- 本回答已依 research 模式整理，但目前沒有額外可展示的工具時間戳。"
                )
            cleaned = f"{cleaned}\n\n### 研究依據\n" + "\n".join(evidence_lines)

        return cleaned.strip()

    def _build_market_resolution_metadata(
        self,
        query: str,
        entities: Optional[Dict[str, Optional[str]]] = None,
    ) -> Dict[str, object]:
        """建立市場解析狀態，供後續 policy 與 tool selection 使用。"""
        normalized = self._normalize_query_text(query)
        entities = entities or {"crypto": None, "tw": None, "us": None}
        candidates = self._extract_symbol_candidates(normalized)
        unresolved_candidates: List[str] = []
        ambiguous_candidates: List[str] = []
        candidate_scores: Dict[str, Dict[str, object]] = {}

        for candidate in candidates:
            resolution = self._symbol_resolver.resolve_with_context(
                candidate, context_text=query
            )
            flat_resolution = resolution.get("resolution", {})
            candidate_scores[candidate] = resolution.get("candidates", {})
            matched_markets = self._symbol_resolver.matched_markets(flat_resolution)
            if not matched_markets:
                unresolved_candidates.append(candidate)
            elif resolution.get("ambiguous") or len(matched_markets) > 1:
                ambiguous_candidates.append(candidate)

        matched_entities = {
            market: value for market, value in entities.items() if value
        }
        requires_discovery_lookup = bool(candidates) and (
            not matched_entities or bool(ambiguous_candidates)
        )

        return {
            "candidates": candidates,
            "matched_entities": matched_entities,
            "unresolved_candidates": unresolved_candidates,
            "ambiguous_candidates": ambiguous_candidates,
            "candidate_scores": candidate_scores,
            "requires_discovery_lookup": requires_discovery_lookup,
        }

    def _build_query_policy_metadata(
        self, query: str, market_resolution: Dict[str, object]
    ) -> Dict[str, object]:
        candidates = (
            market_resolution.get("candidates", [])
            if isinstance(market_resolution, dict)
            else []
        )
        if not isinstance(candidates, list):
            candidates = []
        return self.analysis_policy_resolver.build_query_profile(query, candidates)

    def _build_response_trace_metadata(
        self,
        market_resolution: Dict[str, object],
        query_profile: Dict[str, object],
    ) -> Dict[str, object]:
        matched_entities = (
            market_resolution.get("matched_entities", {})
            if isinstance(market_resolution, dict)
            else {}
        )
        if not isinstance(matched_entities, dict):
            matched_entities = {}

        resolved_markets = [
            market for market, value in matched_entities.items() if value
        ]
        resolved_market = None
        if len(resolved_markets) == 1:
            resolved_market = resolved_markets[0]
        elif len(resolved_markets) > 1:
            resolved_market = "ambiguous"

        query_type = (
            query_profile.get("query_type", "general")
            if isinstance(query_profile, dict)
            else "general"
        )
        return {
            "query_type": query_type,
            "resolved_market": resolved_market,
        }
