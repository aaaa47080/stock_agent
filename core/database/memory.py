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
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import DatabaseBase

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    雙層記憶存儲類

    管理用戶的長期記憶和對話歷史，支持記憶整合功能。
    """

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        """
        初始化記憶存儲

        Args:
            user_id: 用戶 ID
            session_id: 會話 ID（可選）
        """
        self.user_id = user_id
        self.session_id = session_id or "default"
        self._last_consolidated_index: Optional[int] = None

    # ==================== 韜期記憶操作 ====================

    def read_long_term(self) -> str:
        """
        讀取用戶的長期記憶

        Returns:
            長期記憶內容，如果不存在則返回空字符串
        """
        result = DatabaseBase.query_one(
            '''
            SELECT content FROM user_memory
            WHERE user_id = %s AND session_id = %s AND memory_type = 'long_term'
            ORDER BY updated_at DESC
            LIMIT 1
            ''',
            (self.user_id, self.session_id)
        )
        return result['content'] if result else ""

    def write_long_term(self, content: str) -> None:
        """
        寫入長期記憶

        Args:
            content: 記憶內容
        """
        if not content:
            return
        DatabaseBase.execute(
            '''
            INSERT INTO user_memory (user_id, session_id, memory_type, content, updated_at)
            VALUES (%s, %s, 'long_term', %s, NOW())
            ON CONFLICT (user_id, session_id, memory_type)
            DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
            ''',
            (self.user_id, self.session_id, content)
        )

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
            '''
            INSERT INTO user_history_log (user_id, session_id, entry, tools_used)
            VALUES (%s, %s, %s, %s)
            ''',
            (self.user_id, self.session_id, entry.rstrip(), tools_used)
        )

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        獲取歷史記錄

        Args:
            limit: 返回的記錄數量限制

        Returns:
            歷史記錄列表（按時間正序）
        """
        results = DatabaseBase.query_all(
            '''
            SELECT entry, tools_used, created_at
            FROM user_history_log
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            ''',
            (self.user_id, limit)
        )
        return list(reversed(results)) if results else []

    # ==================== 記憶上下文 ====================

    def get_memory_context(
        self,
        include_history: bool = True,
        history_limit: int = 10
    ) -> str:
        """
        獲取完整的記憶上下文（用於 LLM prompt）

        Args:
            include_history: 是否包含歷史記錄
            history_limit: 歷史記錄數量限制

        Returns:
            格式化的記憶上下文字符串
        """
        long_term = self.read_long_term()
        if not long_term:
            return ""

        context = f"## Long-term Memory\n{long_term}"

        if include_history:
            history = self.get_history(limit=history_limit)
            if history:
                history_text = "\n\n".join([
                    h.get('entry', '')
                    for h in history
                    if h.get('entry')
                ])
                if history_text:
                    context += f"\n\n## Recent History\n{history_text}"

        return context

    # ==================== 整合索引管理 ====================

    def get_last_consolidated_index(self) -> int:
        """
        獲取最後整合的索引位置

        Returns:
            最後整合的索引
        """
        if self._last_consolidated_index is not None:
            return self._last_consolidated_index

        result = DatabaseBase.query_one(
            '''
            SELECT last_consolidated_index FROM user_memory_cache
            WHERE user_id = %s
            ''',
            (self.user_id,)
        )
        self._last_consolidated_index = result['last_consolidated_index'] if result else 0
        return self._last_consolidated_index

    def set_last_consolidated_index(self, index: int) -> None:
        """
        設置最後整合的索引位置

        Args:
            index: 新的索引位置
        """
        self._last_consolidated_index = index
        DatabaseBase.execute(
            '''
            INSERT INTO user_memory_cache (user_id, session_id, last_consolidated_index, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                last_consolidated_index = EXCLUDED.last_consolidated_index,
                session_id = EXCLUDED.session_id,
                updated_at = NOW()
            ''',
            (self.user_id, self.session_id, index)
        )

    # ==================== 記憶整合 ====================

    async def consolidate(
        self,
        messages: List[Dict[str, Any]],
        llm: Any,
        memory_window: int = 50,
        archive_all: bool = False
    ) -> bool:
        """
        整合對話歷史到長期記憶

        使用 LLM 將對話歷史整合為結構化的長期記憶和歷史日誌。

        Args:
            messages: 對話消息列表
            llm: LangChain LLM 實例
            memory_window: 保留的最近消息數量
            archive_all: 是否歸檔所有消息

        Returns:
            是否成功
        """
        # 計算需要整合的消息範圍
        if archive_all:
            old_messages = messages
            keep_count = 0
            logger.info(
                f"[MemoryStore] archive_all mode: consolidating {len(messages)} messages"
            )
        else:
            keep_count = memory_window // 2
            if len(messages) <= keep_count:
                logger.info("[MemoryStore] Too few messages, skipping consolidation")
                return True

            last_consolidated = self.get_last_consolidated_index()
            if len(messages) - last_consolidated <= keep_count:
                logger.info("[MemoryStore] No new messages to consolidate")
                return True

            old_messages = messages[last_consolidated:-keep_count]
            if not old_messages:
                return True

            logger.info(
                f"[MemoryStore] Consolidating {len(old_messages)} messages, "
                f"keeping {keep_count}"
            )

        # 構建對話文本
        lines = []
        for m in old_messages:
            content = m.get("content", "")
            if not content:
                continue
            timestamp = m.get("timestamp", "?")[:16] if m.get("timestamp") else "?"
            role = m.get("role", "unknown").upper()
            tools = f" [tools: {', '.join(m.get('tools_used', []))}]" if m.get("tools_used") else ""
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
    "memory_update": "# Long-term Memory\\n\\n## User Preferences\\n- ..."
}}"""

        try:
            # 調用 LLM
            from langchain_core.messages import HumanMessage

            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 解析 JSON 響應
            # 嘗試從 markdown 代碼塊中提取 JSON
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 嘗試直接解析
                json_str = content

            # 找到 JSON 對象
            json_start = json_str.find('{')
            json_end = json_str.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = json_str[json_start:json_end + 1]

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

            # 更新整合索引
            new_index = 0 if archive_all else len(messages) - keep_count
            self.set_last_consolidated_index(new_index)

            logger.info(
                f"[MemoryStore] Consolidation done: {len(messages)} messages, "
                f"last_consolidated={new_index}"
            )
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


def get_memory_store(user_id: str, session_id: Optional[str] = None) -> MemoryStore:
    """
    獲取或創建 MemoryStore 實例

    Args:
        user_id: 用戶 ID
        session_id: 會話 ID（可選）

    Returns:
        MemoryStore 實例
    """
    cache_key = f"{user_id}:{session_id or 'default'}"
    if cache_key not in _memory_stores:
        _memory_stores[cache_key] = MemoryStore(user_id, session_id)
    return _memory_stores[cache_key]
