"""
用戶記憶系統

提供持久化的 Agent 記憶功能，採用 nanobot 風格的雙層記憶架構：
- 長期記憶（Long-term Memory）：存儲重要事實、偏好
- 歆史日誌（History Log）：可搜尋的對話記錄

Reference: https://github.com/HKUDS/nanobot
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import orjson
from cachetools import TTLCache

from .base import DatabaseBase

logger = logging.getLogger(__name__)

# ── Memory context cache (L1 in-process → L2 Redis → L3 PostgreSQL) ──────────
_MEM_L1: TTLCache = TTLCache(maxsize=512, ttl=30)  # 30 s in-process
_MEM_REDIS_TTL = 120  # 2 min Redis TTL
_MEM_KEY_PREFIX = "mem:"

_mem_redis_client = None
_mem_redis_init = False


def _get_redis_sync():
    global _mem_redis_client, _mem_redis_init
    if _mem_redis_init:
        return _mem_redis_client
    _mem_redis_init = True
    try:
        import redis as _r

        from core.redis_url import resolve_redis_url

        url, _ = resolve_redis_url()
        if not url:
            return None
        client = _r.from_url(
            url, decode_responses=False, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        _mem_redis_client = client
        logger.info("[MemoryCache] Redis connected")
    except Exception as exc:
        logger.warning("[MemoryCache] Redis unavailable: %s", exc)
        _mem_redis_client = None
    return _mem_redis_client


def _mem_cache_key(user_id: str) -> str:
    return _MEM_KEY_PREFIX + user_id


def _mem_l1_get(user_id: str):
    return _MEM_L1.get(_mem_cache_key(user_id))


def _mem_l1_set(user_id: str, data) -> None:
    _MEM_L1[_mem_cache_key(user_id)] = data


def _mem_l1_delete(user_id: str) -> None:
    try:
        del _MEM_L1[_mem_cache_key(user_id)]
    except KeyError:
        pass


def _mem_redis_get(user_id: str):
    r = _get_redis_sync()
    if not r:
        return None
    try:
        raw = r.get(_mem_cache_key(user_id))
        return orjson.loads(raw) if raw else None
    except Exception:
        return None


def _mem_redis_set(user_id: str, data) -> None:
    r = _get_redis_sync()
    if not r:
        return
    try:
        r.setex(_mem_cache_key(user_id), _MEM_REDIS_TTL, orjson.dumps(data))
    except Exception:
        pass


def _mem_redis_delete(user_id: str) -> None:
    r = _get_redis_sync()
    if not r:
        return
    try:
        r.delete(_mem_cache_key(user_id))
    except Exception:
        pass


def _invalidate_memory_cache(user_id: str) -> None:
    """Invalidate both L1 and L2 cache for a user."""
    _mem_l1_delete(user_id)
    _mem_redis_delete(user_id)


def _reset_for_testing() -> None:
    """Reset Redis lazy-init state. For use in tests only."""
    global _mem_redis_client, _mem_redis_init
    _mem_redis_client = None
    _mem_redis_init = False
    _MEM_L1.clear()


# ── Compact session state helpers ─────────────────────────────────────────────
_COMPACT_KEY_PREFIX = "session_compact:"
_COMPACT_REDIS_TTL = 7_200  # 2 hours


def _compact_redis_key(user_id: str, session_id: str) -> str:
    return f"{_COMPACT_KEY_PREFIX}{user_id}:{session_id}"


@dataclass
class CompactedSessionState:
    """Structured compact representation of a session's working state."""

    goal: str
    progress: str
    open_questions: str
    next_steps: str
    turn_index: int
    updated_at: str


class MemoryStore:
    """
    雙層記憶存儲類

    管理用戶的長期記憶和對話歷史，支持記憶整合功能。
    """

    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        """
        初始化記憶存儲

        Args:
            user_id: 用戶 ID
            session_id: 會話 ID（可選）
            workspace_id: 工作區 ID（可選，用於多租戶隔離）
        """
        self.user_id = user_id
        self.session_id = session_id or "default"
        self.workspace_id = workspace_id
        self._last_consolidated_index: Optional[int] = None

    @property
    def scope(self) -> str:
        """Cache key namespace — user_id, optionally qualified by workspace_id."""
        if self.workspace_id:
            return f"{self.user_id}|workspace:{self.workspace_id}"
        return self.user_id

    # ==================== 韜期記憶操作 ====================

    def read_long_term(self) -> str:
        """
        讀取用戶的長期記憶
        ✅ 跨 session：讀取最新的長期記憶（不限 session，避免開新對話後記憶消失）

        Returns:
            長期記憶內容，如果不存在則返回空字符串
        """
        result = DatabaseBase.query_one(
            """
            SELECT content FROM user_memory
            WHERE user_id = %s AND memory_type = 'long_term'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (self.user_id,),
        )
        return result["content"] if result else ""

    def write_long_term(self, content: str) -> None:
        """
        寫入長期記憶
        ✅ 固定用 session_id='global'，確保每個用戶只有一筆長期記憶
        避免多 session 各存一筆、造成 read_long_term 只讀到其中一筆的問題
        """
        if not content:
            return
        DatabaseBase.execute(
            """
            INSERT INTO user_memory (user_id, session_id, memory_type, content, updated_at)
            VALUES (%s, 'global', 'long_term', %s, NOW())
            ON CONFLICT (user_id, session_id, memory_type)
            DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
            """,
            (self.user_id, content),
        )
        _invalidate_memory_cache(self.scope)

    # ==================== 歷史日誌操作 ====================

    def append_history(self, entry: str, tools_used: Optional[str] = None) -> None:
        """
        添加歷史記錄條目

        Args:
            entry: 歷史記錄條目（應以 [YYYY-MM-DD HH:MM] 開頭）
            tools_used: 使用的工具（可選）
        """
        if not entry or not entry.strip():
            return
        DatabaseBase.execute(
            """
            INSERT INTO user_history_log (user_id, session_id, entry, tools_used)
            VALUES (%s, %s, %s, %s)
            """,
            (self.user_id, self.session_id, entry.rstrip(), tools_used),
        )
        _invalidate_memory_cache(self.scope)

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        獲取歷史記錄
        ✅ 跨 session：返回該用戶所有 session 的最近歷史（不限 session）

        Args:
            limit: 返回的記錄數量限制

        Returns:
            歷史記錄列表（按時間正序）
        """
        results = DatabaseBase.query_all(
            """
            SELECT entry, tools_used, created_at
            FROM user_history_log
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (self.user_id, limit),
        )
        return list(reversed(results)) if results else []

    # ==================== 記憶上下文 ====================

    def _read_from_db(
        self,
        include_history: bool = True,
        history_limit: int = 10,
    ) -> str:
        """Actual PostgreSQL read — called only on cache miss."""
        parts = []

        # 1. 結構化事實（nanoclaw facts）
        facts_text = self.facts_to_text()
        if facts_text and facts_text != "（尚無已知事實）":
            parts.append(f"## 已知用戶事實\n{facts_text}")

        # 2. 長期記憶摘要（consolidation 產生）
        long_term = self.read_long_term()
        if long_term:
            parts.append(f"## Long-term Memory\n{long_term}")

        if not parts:
            return ""

        context = "\n\n".join(parts)

        # 3. 歷史日誌
        if include_history:
            history = self.get_history(limit=history_limit)
            if history:
                history_text = "\n\n".join(
                    [h.get("entry", "") for h in history if h.get("entry")]
                )
                if history_text:
                    context += f"\n\n## Recent History\n{history_text}"

        return context

    def get_memory_context(
        self,
        include_history: bool = True,
        history_limit: int = 10,
    ) -> str:
        """
        獲取完整的記憶上下文（用於 LLM prompt），採用 L1 → L2 → L3 快取策略。

        Args:
            include_history: 是否包含歷史記錄
            history_limit: 歷史記錄數量限制

        Returns:
            格式化的記憶上下文字符串
        """
        scope = self.scope
        # L1: in-process TTLCache
        cached = _mem_l1_get(scope)
        if cached is not None:
            return cached
        # L2: Redis
        redis_hit = _mem_redis_get(scope)
        if redis_hit is not None:
            _mem_l1_set(scope, redis_hit)
            return redis_hit
        # L3: PostgreSQL
        result = self._read_from_db(include_history, history_limit)
        _mem_l1_set(scope, result)
        _mem_redis_set(scope, result)
        return result

    # ==================== Compact session state ====================

    def read_compact_state(self) -> Optional["CompactedSessionState"]:
        """Read compact session state: Redis → PostgreSQL → None."""
        redis_client = _get_redis_sync()
        key = _compact_redis_key(self.user_id, self.session_id)
        if redis_client:
            try:
                raw = redis_client.get(key)
                if raw:
                    data = orjson.loads(raw)
                    return CompactedSessionState(**data)
            except Exception:
                pass
        # Fall back to PostgreSQL
        row = DatabaseBase.query_one(
            """SELECT content FROM user_memory
               WHERE user_id = %s AND session_id = %s AND memory_type = 'session_compact'
               ORDER BY updated_at DESC LIMIT 1""",
            (self.user_id, self.session_id),
        )
        if row:
            try:
                data = json.loads(row["content"])
                state = CompactedSessionState(**data)
                # backfill Redis
                if redis_client:
                    try:
                        redis_client.setex(key, _COMPACT_REDIS_TTL, orjson.dumps(data))
                    except Exception:
                        pass
                return state
            except Exception:
                pass
        return None

    def write_compact_state(self, state: "CompactedSessionState") -> None:
        """Persist compact session state to Redis + PostgreSQL."""
        data = {
            "goal": state.goal,
            "progress": state.progress,
            "open_questions": state.open_questions,
            "next_steps": state.next_steps,
            "turn_index": state.turn_index,
            "updated_at": state.updated_at,
        }
        # Write Redis first (fast path)
        redis_client = _get_redis_sync()
        if redis_client:
            try:
                redis_client.setex(
                    _compact_redis_key(self.user_id, self.session_id),
                    _COMPACT_REDIS_TTL,
                    orjson.dumps(data),
                )
            except Exception as exc:
                logger.debug("[MemoryStore] compact state Redis write failed: %s", exc)
        # Write PostgreSQL (durable)
        DatabaseBase.execute(
            """INSERT INTO user_memory (user_id, session_id, memory_type, content, updated_at)
               VALUES (%s, %s, 'session_compact', %s, NOW())
               ON CONFLICT (user_id, session_id, memory_type)
               DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()""",
            (self.user_id, self.session_id, json.dumps(data)),
        )

    # ==================== 結構化事實（nanoclaw extract_memory） ====================

    def read_facts(self) -> dict:
        """
        讀取用戶的結構化事實 (key-value pairs)

        Returns:
            {key: {value, confidence, source_turn}} dict
        """
        results = DatabaseBase.query_all(
            """
            SELECT key, value, confidence, source_turn
            FROM user_facts
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (self.user_id,),
        )
        return {
            r["key"]: {
                "value": r["value"],
                "confidence": r["confidence"],
                "source_turn": r["source_turn"],
            }
            for r in (results or [])
        }

    def write_facts(self, facts: list) -> None:
        """
        寫入結構化事實（upsert，新事實新增、已有的更新）

        Args:
            facts: [{'key': str, 'value': str, 'confidence': str, 'source_turn': int}]
        """
        if not facts:
            return
        for fact in facts:
            key = fact.get("key", "").strip()
            value = str(fact.get("value", "")).strip()
            if not key or not value:
                continue
            DatabaseBase.execute(
                """
                INSERT INTO user_facts (user_id, key, value, confidence, source_turn, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    confidence = EXCLUDED.confidence,
                    source_turn = EXCLUDED.source_turn,
                    updated_at = NOW()
                """,
                (
                    self.user_id,
                    key,
                    value,
                    fact.get("confidence", "high"),
                    fact.get("source_turn"),
                ),
            )
        _invalidate_memory_cache(self.scope)

    def facts_to_text(self) -> str:
        """將結構化事實格式化為 LLM 可讀的文字"""
        facts = self.read_facts()
        if not facts:
            return "（尚無已知事實）"
        lines = []
        for key, meta in facts.items():
            conf_icon = {"high": "✅", "medium": "🔶", "low": "❓"}.get(
                meta["confidence"], ""
            )
            lines.append(f"- {key}: {meta['value']} {conf_icon}")
        return "\n".join(lines)

    async def extract_facts_from_turn(
        self,
        user_message: str,
        assistant_message: str,
        turn_index: int,
        llm: any,
        tools_used: Optional[List[str]] = None,
    ) -> bool:
        """
        nanoclaw extract_memory 核心實作：
        從單輪對話中萃取結構化事實，立即寫入 PSQL
        （輕量、逐輪執行，不像 consolidate 需要等累積）

        Args:
            user_message: 用戶訊息
            assistant_message: 助手回覆
            turn_index: 當前輪次編號
            llm: LangChain LLM 實例
            tools_used: 本輪使用的工具列表
        """
        from langchain_core.messages import HumanMessage

        existing_facts = self.facts_to_text()

        tools_section = ""
        if tools_used:
            tools_section = f"\n本輪使用工具：{', '.join(tools_used)}"

        prompt = f"""從以下最新對話輪次中提取重要事實。只提取「明確說出的」事實，不推斷。

使用者說：{user_message}
助手回覆：{assistant_message}{tools_section}

已存在事實（避免重複）：
{existing_facts}
當前輪次編號：{turn_index}

請以 JSON 回覆，只包含本輪新增或更新的事實：
{{"facts": [
  {{"key": "user_name", "value": "Danny", "source_turn": {turn_index}, "confidence": "high"}}
]}}

規則：
- 只保留「未來對話有用」的事實（使用者名稱、偏好、關注主題、投資風格等）
- 不提取一次性數字（如具體價格、今日新聞）
- key 用 snake_case 英文
- confidence: high=使用者明確說出, medium=可推斷, low=不確定
- 無新事實則回覆 {{"facts": []}}
- 最多 3 個事實"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content
            if isinstance(raw, list):
                raw = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in raw
                )
            raw = raw.strip()
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
            json_str = json_match.group(1).strip() if json_match else raw
            j_start = json_str.find("{")
            j_end = json_str.rfind("}")
            if j_start >= 0 and j_end > j_start:
                json_str = json_str[j_start : j_end + 1]

            result = json.loads(json_str)
            facts = result.get("facts", [])

            if facts:
                self.write_facts(facts)
                logger.info(
                    f"[MemoryStore] Extracted {len(facts)} facts at turn {turn_index}"
                )

            return True

        except json.JSONDecodeError as e:
            logger.warning(f"[MemoryStore] extract_facts JSON parse failed: {e}")
            return False
        except Exception as e:
            logger.error(f"[MemoryStore] extract_facts failed: {e}")
            return False

    # ==================== 整合索引管理 ====================

    def get_last_consolidated_index(self) -> int:
        """
        獲取最後整合的索引位置

        Returns:
            最後整合的索引

        Bug #8 fix: 每次都從 DB 讀取，確保一致性
        """
        result = DatabaseBase.query_one(
            """
            SELECT last_consolidated_index FROM user_memory_cache
            WHERE user_id = %s
            """,
            (self.user_id,),
        )
        self._last_consolidated_index = (
            result["last_consolidated_index"] if result else 0
        )
        return self._last_consolidated_index

    def set_last_consolidated_index(self, index: int) -> None:
        """
        設置最後整合的索引位置

        Args:
            index: 新的索引位置

        Raises:
            Exception: 如果 DB 寫入失敗

        Bug #4 fix: 先寫 DB，成功後才更新本地
        """
        DatabaseBase.execute(
            """
            INSERT INTO user_memory_cache (user_id, session_id, last_consolidated_index, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                last_consolidated_index = EXCLUDED.last_consolidated_index,
                session_id = EXCLUDED.session_id,
                updated_at = NOW()
            """,
            (self.user_id, self.session_id, index),
        )
        # DB 寫入成功後才更新本地
        self._last_consolidated_index = index

    # ==================== 記憶整合 ====================

    async def consolidate(
        self,
        messages_to_consolidate: List[Dict[str, Any]],
        llm: Any,
    ) -> bool:
        """
        整合對話歷史到長期記憶

        職責分離：調用方負責計算要整合哪些消息，此方法只負責執行整合。

        Args:
            messages_to_consolidate: 需要整合的消息列表（由調用方計算切片）
            llm: LangChain LLM 實例

        Returns:
            是否成功
        """
        if not messages_to_consolidate:
            logger.info("[MemoryStore] No messages to consolidate")
            return True

        logger.info(
            f"[MemoryStore] Consolidating {len(messages_to_consolidate)} messages"
        )

        # 構建對話文本
        lines = []
        for m in messages_to_consolidate:
            content = m.get("content", "")
            if not content:
                continue
            timestamp = m.get("timestamp", "?")[:16] if m.get("timestamp") else "?"
            role = m.get("role", "unknown").upper()
            tools = (
                f" [tools: {', '.join(m.get('tools_used', []))}]"
                if m.get("tools_used")
                else ""
            )
            lines.append(f"[{timestamp}] {role}{tools}: {content}")

        current_memory = self.read_long_term()

        # 構建整合 prompt
        prompt = f"""Process this conversation and provide a structured memory update.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}

---

Please analyze the conversation and provide:
1. A history entry (2-5 sentences summarizing key events/decisions/topics, starting with [YYYY-MM-DD HH:MM])
2. An updated long-term memory (include all existing facts plus new ones as markdown)

Respond in this exact JSON format:
{{
    "history_entry": "[2026-01-01 10:00] Summary of what happened...",
    "memory_update": "# Long-term Memory\\n\\n## User Preferences\\n- ...",
    "compact_state": {{
        "goal": "What the user is trying to achieve this session",
        "progress": "What has been resolved or answered",
        "open_questions": "Unresolved questions or threads (empty string if none)",
        "next_steps": "Suggested next actions (empty string if none)"
    }}
}}"""

        try:
            # 調用 LLM
            from langchain_core.messages import HumanMessage

            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            content = content.strip()

            # 解析 JSON 響應
            # 嘗試從 markdown 代碼塊中提取 JSON
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 嘗試直接解析
                json_str = content

            # 找到 JSON 對象
            json_start = json_str.find("{")
            json_end = json_str.rfind("}")
            if json_start >= 0 and json_end > json_start:
                json_str = json_str[json_start : json_end + 1]

            result = json.loads(json_str)

            # 保存 history_entry
            entry = result.get("history_entry")
            if entry:
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)

            # 保存 memory_update
            update = result.get("memory_update")
            if update:
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)

            # 保存 compact session state
            compact_data = result.get("compact_state")
            if compact_data and isinstance(compact_data, dict):
                try:
                    state = CompactedSessionState(
                        goal=str(compact_data.get("goal", "")),
                        progress=str(compact_data.get("progress", "")),
                        open_questions=str(compact_data.get("open_questions", "")),
                        next_steps=str(compact_data.get("next_steps", "")),
                        turn_index=len(messages_to_consolidate),
                        updated_at=datetime.now(timezone.utc).isoformat(),
                    )
                    self.write_compact_state(state)
                except Exception as exc:
                    logger.warning("[MemoryStore] compact_state write failed: %s", exc)
            else:
                logger.debug(
                    "[MemoryStore] compact_state absent from LLM consolidation response"
                )

            logger.info(f"[MemoryStore] Consolidation done: {len(messages_to_consolidate)} messages")
            return True

        except json.JSONDecodeError as e:
            logger.warning(f"[MemoryStore] Failed to parse LLM response as JSON: {e}")
            return False
        except Exception as e:
            logger.exception(f"[MemoryStore] Consolidation failed: {e}")
            return False


# ==================== 工廠函數 ====================

# 單例緩存
_memory_stores: Dict[str, MemoryStore] = {}


def get_memory_store(
    user_id: str,
    session_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> MemoryStore:
    """
    獲取或創建 MemoryStore 實例

    Args:
        user_id: 用戶 ID
        session_id: 會話 ID（可選）
        workspace_id: 工作區 ID（可選）

    Returns:
        MemoryStore 實例
    """
    cache_key = f"{user_id}:{session_id or 'default'}:{workspace_id or ''}"
    if cache_key not in _memory_stores:
        _memory_stores[cache_key] = MemoryStore(user_id, session_id, workspace_id)
    return _memory_stores[cache_key]
