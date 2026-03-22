"""
Agent Tracing — 結構化追蹤 LangGraph 節點執行

提供：
- AgentTrace: 單一節點的執行記錄
- TraceCollector: 收集一次完整 graph 執行的所有 traces
- get_trace_summary(): 結構化 JSON 摘要
- format_trace_log(): 人類可讀的 log 格式

設計原則：
- Trace 失敗不影響主流程（defensive）
- 零外部依賴（只用標準庫）
- 不修改 graph 節點的行為或返回值
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentTrace:
    """單一 graph 節點的執行記錄。

    Attributes:
        node_name: LangGraph 節點名稱（如 "understand_intent"）
        start_time: 節點開始執行的 UNIX timestamp
        end_time: 節點結束執行的 UNIX timestamp（None 表示尚未結束）
        input_summary: 節點輸入的摘要（截斷避免過大）
        output_summary: 節點輸出的摘要（截斷避免過大）
        token_usage: 本次 LLM 調用消耗的 token 數（若有）
        model_name: 本次使用的模型名稱（若有）
        error: 執行過程中的錯誤訊息（None 表示成功）
        duration_ms: 執行耗時（毫秒），end_time 存在時計算
    """

    node_name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    model_name: Optional[str] = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> Optional[float]:
        """執行耗時（毫秒），end_time 不存在時回傳 None。"""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(
        self,
        output_summary: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        model_name: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """標記節點執行完成，記錄結束時間和結果。"""
        self.end_time = time.time()
        self.output_summary = output_summary
        self.token_usage = token_usage
        self.model_name = model_name
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """序列化為 dict，適合 JSON 輸出。"""
        result: Dict[str, Any] = {
            "node": self.node_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
        }
        if self.input_summary is not None:
            result["input_summary"] = self.input_summary
        if self.output_summary is not None:
            result["output_summary"] = self.output_summary
        if self.token_usage is not None:
            result["token_usage"] = self.token_usage
        if self.model_name is not None:
            result["model_name"] = self.model_name
        if self.error is not None:
            result["error"] = self.error
        return result


# 摘要截斷長度，避免 trace 資料過大
_SUMMARY_MAX_LEN = 500


def _truncate(value: Any, max_len: int = _SUMMARY_MAX_LEN) -> Optional[str]:
    """將任意值截斷為字串摘要。"""
    if value is None:
        return None
    try:
        text = (
            json.dumps(value, ensure_ascii=False)
            if not isinstance(value, str)
            else value
        )
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
    except (TypeError, ValueError):
        text = str(value)
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text


class TraceCollector:
    """收集一次完整 LangGraph graph 執行的所有節點 traces。

    使用方式：
        collector = TraceCollector(session_id="abc", query="BTC 價格")
        with collector.trace("understand_intent", state):
            ...  # node 執行邏輯
        # 自動記錄 start/end
        summary = collector.get_trace_summary()
        log_text = collector.format_trace_log()
    """

    def __init__(
        self,
        session_id: str = "",
        query: str = "",
    ):
        self.session_id = session_id
        self.query = query
        self._traces: List[AgentTrace] = []
        self._start_time: float = time.time()

    @property
    def traces(self) -> List[AgentTrace]:
        """回傳所有已收集的 traces（唯讀副本）。"""
        return list(self._traces)

    @property
    def total_duration_ms(self) -> float:
        """從 collector 建立到現在的總耗時（毫秒）。"""
        return (time.time() - self._start_time) * 1000

    def start_trace(
        self,
        node_name: str,
        input_summary: Any = None,
    ) -> AgentTrace:
        """開始記錄一個節點執行，回傳 AgentTrace 供後續 finish() 使用。"""
        trace = AgentTrace(
            node_name=node_name,
            input_summary=_truncate(input_summary),
        )
        self._traces.append(trace)
        try:
            logger.info(
                "[Trace] ▶ node=%s started (session=%s)",
                node_name,
                self.session_id,
            )
        except Exception:
            pass
        return trace

    def finish_trace(
        self,
        trace: AgentTrace,
        output_summary: Any = None,
        token_usage: Optional[Dict[str, int]] = None,
        model_name: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """結束一個節點的 trace 記錄。"""
        try:
            trace.finish(
                output_summary=_truncate(output_summary),
                token_usage=token_usage,
                model_name=model_name,
                error=error,
            )
            status = "✓" if trace.error is None else "✗"
            duration = f"{trace.duration_ms:.0f}ms" if trace.duration_ms else "?"
            logger.info(
                "[Trace] ◀ node=%s %s (%s) (session=%s)",
                trace.node_name,
                status,
                duration,
                self.session_id,
            )
        except Exception:
            pass

    def get_trace_summary(self) -> Dict[str, Any]:
        """回傳結構化的執行摘要（JSON-serializable dict）。

        包含：
        - session_id, query: 請求上下文
        - total_duration_ms: 總耗時
        - node_count: 經過的節點數
        - nodes: 每個節點的詳細 trace
        - total_tokens: 彙總 token 使用量
        - errors: 有錯誤的節點列表
        """
        total_tokens: Dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
        errors: List[Dict[str, Any]] = []
        nodes: List[Dict[str, Any]] = []

        for trace in self._traces:
            nodes.append(trace.to_dict())
            if trace.token_usage:
                total_tokens["prompt"] += trace.token_usage.get("prompt_tokens", 0)
                total_tokens["completion"] += trace.token_usage.get(
                    "completion_tokens", 0
                )
                total_tokens["total"] += trace.token_usage.get("total_tokens", 0)
            if trace.error:
                errors.append(
                    {
                        "node": trace.node_name,
                        "error": trace.error,
                        "duration_ms": trace.duration_ms,
                    }
                )

        return {
            "session_id": self.session_id,
            "query": self.query[:200],
            "total_duration_ms": round(self.total_duration_ms, 2),
            "node_count": len(self._traces),
            "nodes": nodes,
            "total_tokens": total_tokens,
            "errors": errors,
            "success": len(errors) == 0,
        }

    def format_trace_log(self) -> str:
        """回傳人類可讀的 log 格式字串。

        範例：
            ══════════════════════════════════════
            TRACE  session=abc  query="BTC 價格"
            ══════════════════════════════════════
            [1] understand_intent     320ms  ✓
            [2] execute_task          1,200ms  ✓
            [3] aggregate_results       5ms  ✓
            [4] reflect_on_results    800ms  ✓
            [5] synthesize_response   950ms  ✓
            ────────────────────────────────────
            Total: 3,275ms | Nodes: 5 | Tokens: 2,340
            ══════════════════════════════════════
        """
        sep = "=" * 39
        lines = [
            sep,
            f'TRACE  session={self.session_id}  query="{self.query[:80]}"',
            sep,
        ]

        total_tokens = 0
        for idx, trace in enumerate(self._traces, 1):
            duration = f"{trace.duration_ms:,.0f}ms" if trace.duration_ms else "?ms"
            status = "✓" if trace.error is None else f"✗ {trace.error}"
            node_line = f"[{idx}] {trace.node_name:<25s} {duration:>10s}  {status}"
            lines.append(node_line)
            if trace.token_usage:
                total_tokens += trace.token_usage.get("total_tokens", 0)

        divider = "-" * 39
        lines.append(divider)
        lines.append(
            f"Total: {self.total_duration_ms:,.0f}ms | "
            f"Nodes: {len(self._traces)} | "
            f"Tokens: {total_tokens:,}"
        )
        lines.append(sep)
        return "\n".join(lines)

    def reset(self) -> None:
        """清除所有 traces，重置計時器。"""
        self._traces.clear()
        self._start_time = time.time()
