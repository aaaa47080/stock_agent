"""
Manager Agent - Memory System

Contains short-term and long-term memory management:
- _get_memory: Get or create short-term memory
- get_long_term_memory_context: Get long-term memory context for LLM prompt
- _track_conversation: Track conversation and trigger consolidation
- _extract_facts_background: Background fact extraction (nanoclaw style)
- _record_experience_background: Background experience recording
- check_idle_consolidation: Check if idle consolidation is needed
- switch_session: Switch to a new session with consolidation
- _background_memory_consolidation: Background memory consolidation
- _do_consolidation: Actual consolidation logic
- consolidate_session_memory: Manual/session-end consolidation
- _get_memory_store: Lazy-init MemoryStore
- _get_agents_description: Get all agents description
"""

from __future__ import annotations

import time
from typing import List, Optional

from api.utils import logger

from ..models import ShortTermMemory
from .mixin_base import ManagerAgentMixin


class MemoryMixin(ManagerAgentMixin):
    """Memory system for ManagerAgent."""

    def _get_memory(self, session_id: str) -> ShortTermMemory:
        """獲取或創建短期記憶"""
        if session_id not in self._memory_cache:
            self._memory_cache[session_id] = ShortTermMemory()
        return self._memory_cache[session_id]

    def get_long_term_memory_context(self) -> str:
        """獲取長期記憶上下文（用於 LLM prompt）"""
        try:
            memory_store = self._get_memory_store()
            if not memory_store:
                return ""
            return memory_store.get_memory_context(
                include_history=True, history_limit=10
            )
        except Exception as e:
            logger.warning(f"[Manager] Failed to get long-term memory: {e}")
            return ""

    def _get_memory_store(self):
        """
        延遲初始化 MemoryStore
        
        ✅ 跨 session 設計：記憶以 user_id 為主鍵，開新對話仍能讀到歷史記憶
        ✅ 啟動時同步 last_consolidated_index：避免 server 重啟後狀態丟失
        """
        from core.config import TEST_MODE

        if TEST_MODE:
            return False

        if self._memory_store is None:
            try:
                from core.database.memory import MemoryStore

                self._memory_store = MemoryStore(self.user_id, self.session_id)
                
                # 啟動時同步 index（避免 server 重啟後重複整合）
                if self._last_consolidated_index == 0:
                    db_index = self._memory_store.get_last_consolidated_index()
                    if db_index > 0:
                        self._last_consolidated_index = db_index
                        logger.info(f"[Manager] Synced consolidation index from DB: {db_index}")
                        
            except ImportError as e:
                import logging

                logging.getLogger(__name__).warning(f"Memory module not available: {e}")
                self._memory_store = False
        return self._memory_store

    async def _track_conversation(
        self,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None,
    ) -> None:
        """
        追蹤對話歷史並在達到閾值時自動觸發記憶整合（nanoclaw 風格雙層）

        Args:
            user_message: 用戶訊息
            assistant_response: 助手回應
            tools_used: 使用的工具列表
        """
        import sys

        from ._main import MEMORY_CONSOLIDATION_THRESHOLD

        facade = sys.modules.get("core.agents.manager")
        _rb = facade._run_background if facade else None
        _es = facade._experience_store if facade else None

        # 更新活動時間
        self._last_activity_time = time.time()

        # 添加到短期記憶
        memory = self._get_memory(self.session_id)
        memory.add_message("user", user_message)
        memory.add_message("assistant", assistant_response)

        self._message_count += 2
        turn_index = self._message_count // 2  # 輪次編號（1 輪 = 1 user + 1 assistant）

        # ✅ nanoclaw extract_memory：每輪對話立即萃取結構化事實（背景執行）
        # 輕量操作，不需等到 consolidation threshold
        _rb(
            self._extract_facts_background(user_message, assistant_response, turn_index)
        )
        _rb(
            self._record_experience_background(
                user_message, assistant_response, tools_used
            )
        )

        # 計算未整合的消息數量
        unconsolidated = self._message_count - self._last_consolidated_index

        # 達到閾值才觸發重量級 consolidation（摘要 + 長期記憶更新）
        if unconsolidated >= MEMORY_CONSOLIDATION_THRESHOLD and not self._consolidating:
            logger.info(
                f"[Manager] Triggering memory consolidation: "
                f"{unconsolidated} unconsolidated messages"
            )
            # 創建背景任務進行整合
            self._consolidation_task = _rb(self._background_memory_consolidation())

    async def _extract_facts_background(
        self, user_message: str, assistant_response: str, turn_index: int
    ) -> None:
        """背景執行 nanoclaw 事實萃取，不阻塞對話回應"""
        try:
            memory_store = self._get_memory_store()
            if not memory_store:
                return
            await memory_store.extract_facts_from_turn(
                user_message=user_message,
                assistant_message=assistant_response,
                turn_index=turn_index,
                llm=self.llm,
            )
        except Exception as e:
            logger.warning(f"[Manager] extract_facts_background failed: {e}")

    async def _record_experience_background(
        self,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]],
        task_results: Optional[dict] = None,
    ) -> None:
        """Fire-and-forget: record task trajectory after each turn."""
        from ._main import _experience_store

        try:
            # Determine task_family from agent names used
            task_family = "chat"
            if task_results:
                agents_used = [
                    v.get("agent_name", "")
                    for v in task_results.values()
                    if isinstance(v, dict)
                ]
                for agent in agents_used:
                    if agent in (
                        "crypto",
                        "tw_stock",
                        "us_stock",
                        "forex",
                        "commodity",
                        "economic",
                    ):
                        task_family = agent
                        break

            # Determine outcome from task_results quality
            outcome = "success"
            quality = None
            if task_results:
                qualities = [
                    v.get("quality")
                    for v in task_results.values()
                    if isinstance(v, dict)
                ]
                if "fail" in qualities:
                    outcome = "failure"
                    quality = "fail"
                else:
                    quality = "pass"

            _experience_store.record_experience(
                user_id=self.user_id or "anonymous",
                session_id=self.session_id,
                task_family=task_family,
                query=user_message,
                tools_used=tools_used or [],
                agent_used=",".join(
                    set(
                        v.get("agent_name", "")
                        for v in (task_results or {}).values()
                        if isinstance(v, dict) and v.get("agent_name")
                    )
                ),
                outcome=outcome,
                quality_score=quality,
                failure_reason=None,
                response_chars=len(assistant_response),
            )
        except Exception as exc:
            logger.debug("[Manager] _record_experience_background failed: %s", exc)

    def check_idle_consolidation(self) -> bool:
        """
        檢查是否需要因閒置而整合記憶

        Returns:
            True 如果需要整合
        """
        from ._main import MEMORY_IDLE_TIMEOUT

        if self._consolidating:
            return False

        idle_time = time.time() - self._last_activity_time
        unconsolidated = self._message_count - self._last_consolidated_index

        # 閒置超過 5 分鐘且有未整合消息
        if idle_time >= MEMORY_IDLE_TIMEOUT and unconsolidated > 0:
            logger.info(
                f"[Manager] Idle consolidation triggered: "
                f"idle={idle_time:.0f}s, unconsolidated={unconsolidated}"
            )
            return True
        return False

    async def switch_session(self, new_session_id: str) -> None:
        """
        切換會話並整合舊會話記憶

        Args:
            new_session_id: 新會話 ID
        """
        # 整合舊會話的所有記憶
        if self._message_count > self._last_consolidated_index:
            logger.info(
                f"[Manager] Session switch: consolidating {self._message_count - self._last_consolidated_index} messages"
            )
            await self.consolidate_session_memory()

        # 切換到新會話
        old_session_id = self.session_id
        self.session_id = new_session_id

        # 重置新會話的計數器
        self._message_count = 0
        self._last_consolidated_index = 0
        self._memory_store = None  # 重置記憶存儲以使用新 session_id

        logger.info(f"[Manager] Switched session: {old_session_id} -> {new_session_id}")

    async def _background_memory_consolidation(self) -> bool:
        """
        背景記憶整合（nanobot 風格）

        - 異步執行，不阻塞對話
        - 使用鎖防止重複整合
        - 追蹤已整合的索引

        Returns:
            True 如果整合成功
        """
        if self._consolidating:
            return False

        async with self._consolidation_lock:
            self._consolidating = True
            try:
                return await self._do_consolidation(archive_all=False)
            finally:
                self._consolidating = False

    async def _do_consolidation(self, archive_all: bool = False) -> bool:
        """
        執行實際的記憶整合

        職責分離：
        - ManagerAgent 負責計算要整合哪些消息
        - MemoryStore 負責執行 LLM 整合並寫入 DB

        Args:
            archive_all: 是否整合所有消息

        Returns:
            True 如果成功
        """
        from ._main import MEMORY_CONSOLIDATION_THRESHOLD

        try:
            memory = self._get_memory(self.session_id)
            memory_store = self._get_memory_store()
            if not memory_store:
                return False

            if not memory.conversation_history:
                return True

            # === ManagerAgent 負責計算切片 ===
            if archive_all:
                messages_to_consolidate = memory.conversation_history
            else:
                keep_count = MEMORY_CONSOLIDATION_THRESHOLD // 2
                start_idx = memory_store.get_last_consolidated_index()
                end_idx = len(memory.conversation_history) - keep_count

                if end_idx <= start_idx:
                    logger.info("[Manager] No new messages to consolidate")
                    return True

                messages_to_consolidate = memory.conversation_history[start_idx:end_idx]

                if not messages_to_consolidate:
                    return True

                logger.info(
                    f"[Manager] Consolidating {len(messages_to_consolidate)} messages "
                    f"(offset={start_idx}, keep={keep_count})"
                )

            # 準備訊息格式
            formatted_messages = []
            for msg in messages_to_consolidate:
                from datetime import datetime, timezone

                formatted_messages.append(
                    {
                        "role": msg.get("role", "unknown"),
                        "content": msg.get("content", ""),
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                        "tools_used": msg.get("tools_used", []),
                    }
                )

            # === MemoryStore 負責執行整合 ===
            success = await memory_store.consolidate(
                messages_to_consolidate=formatted_messages,
                llm=self.llm,
            )

            if success:
                # 更新本地 index（同步到 DB 由 MemoryStore 完成）
                self._last_consolidated_index = len(memory.conversation_history)
                memory_store.set_last_consolidated_index(self._last_consolidated_index)
                logger.info(f"[Manager] Consolidation done, index={self._last_consolidated_index}")

            return success

        except Exception as e:
            logger.error(f"[Manager] Memory consolidation failed: {e}")
            return False

    async def consolidate_session_memory(self) -> bool:
        """
        會話結束時整合所有記憶（手動調用或 /new 命令）

        Returns:
            True 如果整合成功
        """
        async with self._consolidation_lock:
            return await self._do_consolidation(archive_all=True)

    def _get_agents_description(self) -> str:
        """獲取所有 agents 的描述"""
        return self.agent_registry.agents_info_for_prompt()
