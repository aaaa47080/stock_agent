"""
User Memory Store - Persistent agent memory system.

A two-layer memory architecture inspired by nanobot:
- Long-term Memory: Persistent facts about the user (stored in DB)
- History Log: Searchable conversation log (stored in DB)

Designed for multi-user production environment with PostgreSQL.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from .connection import get_connection

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# Tool definition for memory consolidation via LLM
_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save the memory consolidation result to persistent storage. "
                "Call this after analyzing the conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                            "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated long-term memory as markdown. Include all existing "
                            "facts plus new ones. Return unchanged if nothing new."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]

# Default long-term memory template
DEFAULT_LONG_TERM_MEMORY = """# Long-term Memory

This file stores important information that should persist across sessions.

## User Preferences

(Preferences learned from conversations)

## Investment Interests

(Cryptocurrencies, stocks, or topics the user is interested in)

## Important Context

(Key information about the user's goals or constraints)

---

*This memory is automatically updated by the AI assistant.*
"""


class MemoryStore:
    """
    Two-layer memory store backed by PostgreSQL.

    Layers:
    - Long-term Memory (user_memory table): Persistent facts
    - History Log (user_history_log table): Searchable conversation log

    Features:
    - Thread-safe via connection pool
    - Automatic history cleanup (keeps last 90 days)
    - LLM-powered memory consolidation
    """

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or "default"

    def read_long_term(self) -> str:
        """Read long-term memory from database."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT content FROM user_memory
                    WHERE user_id = %s AND session_id = %s AND memory_type = 'long_term'
                    """,
                    (self.user_id, self.session_id),
                )
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]
                return DEFAULT_LONG_TERM_MEMORY
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to read long-term memory: {e}")
            return DEFAULT_LONG_TERM_MEMORY

    def write_long_term(self, content: str) -> bool:
        """Write long-term memory to database (upsert)."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_memory (user_id, session_id, memory_type, content, updated_at)
                    VALUES (%s, %s, 'long_term', %s, NOW())
                    ON CONFLICT (user_id, session_id, memory_type)
                    DO UPDATE SET content = %s, updated_at = NOW()
                    """,
                    (self.user_id, self.session_id, content, content),
                )
                conn.commit()
                logger.info(f"[MemoryStore] Updated long-term memory for user {self.user_id}")
                return True
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to write long-term memory: {e}")
            return False

    def append_history(self, entry: str, tools_used: Optional[list[str]] = None) -> bool:
        """Append entry to history log."""
        try:
            tools_str = ",".join(tools_used) if tools_used else None
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_history_log (user_id, session_id, entry, tools_used, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (self.user_id, self.session_id, entry, tools_str),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to append history: {e}")
            return False

    def get_history(self, limit: int = 50) -> list[str]:
        """Get recent history entries."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT entry FROM user_history_log
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (self.user_id, self.session_id, limit),
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to get history: {e}")
            return []

    def get_memory_context(self, include_history: bool = True, history_limit: int = 10) -> str:
        """Get formatted memory context for LLM prompt."""
        parts = []

        # Long-term memory
        long_term = self.read_long_term()
        if long_term and long_term != DEFAULT_LONG_TERM_MEMORY:
            parts.append(f"## Long-term Memory\n{long_term}")

        # Recent history
        if include_history:
            history = self.get_history(limit=history_limit)
            if history:
                history_text = "\n\n".join(reversed(history))  # Chronological order
                parts.append(f"## Recent History\n{history_text}")

        return "\n\n".join(parts) if parts else ""

    def cleanup_old_history(self, days: int = 90) -> int:
        """Remove history entries older than specified days."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM user_history_log
                    WHERE user_id = %s AND created_at < NOW() - INTERVAL '%s days'
                    """,
                    (self.user_id, days),
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    logger.info(f"[MemoryStore] Cleaned up {deleted} old history entries")
                return deleted
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to cleanup history: {e}")
            return 0

    def get_last_consolidated_index(self) -> int:
        """Get the index of last consolidated message."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT last_consolidated_index FROM user_memory_cache
                    WHERE user_id = %s AND session_id = %s
                    """,
                    (self.user_id, self.session_id),
                )
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to get consolidated index: {e}")
            return 0

    def set_last_consolidated_index(self, index: int) -> bool:
        """Update the last consolidated message index."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_memory_cache (user_id, session_id, last_consolidated_index, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET last_consolidated_index = %s, session_id = %s, updated_at = NOW()
                    """,
                    (self.user_id, self.session_id, index, index, self.session_id),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[MemoryStore] Failed to set consolidated index: {e}")
            return False

    async def consolidate(
        self,
        messages: list[dict],
        llm: "BaseChatModel",
        *,
        memory_window: int = 50,
        archive_all: bool = False,
    ) -> bool:
        """
        Consolidate old messages into long-term memory via LLM tool call.

        This method:
        1. Takes old messages from the conversation
        2. Sends them to LLM with current memory
        3. LLM calls save_memory tool with consolidated result
        4. Updates long-term memory and history log

        Args:
            messages: List of message dicts with 'role', 'content', 'timestamp', 'tools_used'
            llm: LangChain LLM instance with tool binding support
            memory_window: Number of recent messages to keep (not consolidate)
            archive_all: If True, consolidate all messages (for session end)

        Returns:
            True on success, False on failure
        """
        if not messages:
            return True

        if archive_all:
            old_messages = messages
            keep_count = 0
            logger.info(
                f"[MemoryStore] Archive all mode: consolidating {len(messages)} messages"
            )
        else:
            keep_count = memory_window // 2
            if len(messages) <= keep_count:
                return True

            last_consolidated = self.get_last_consolidated_index()
            if len(messages) - last_consolidated <= keep_count:
                return True

            old_messages = messages[last_consolidated:-keep_count]
            if not old_messages:
                return True

            logger.info(
                f"[MemoryStore] Consolidating {len(old_messages)} messages, keeping {keep_count}"
            )

        # Format messages for LLM
        lines = []
        for m in old_messages:
            content = m.get("content", "")
            if not content:
                continue
            timestamp = m.get("timestamp", "?")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M")
            else:
                timestamp = str(timestamp)[:16]
            role = m.get("role", "unknown").upper()
            tools = m.get("tools_used", [])
            tools_str = f" [tools: {', '.join(tools)}]" if tools else ""
            lines.append(f"[{timestamp}] {role}{tools_str}: {content}")

        if not lines:
            return True

        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory}

## Conversation to Process
{chr(10).join(lines)}

Analyze the conversation and:
1. Update the long-term memory with any new important facts about the user
2. Create a concise history entry summarizing the key topics discussed
"""

        try:
            # Bind tool and invoke LLM
            llm_with_tools = llm.bind_tools(_SAVE_MEMORY_TOOL)
            response = llm_with_tools.invoke(
                [
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool."},
                    {"role": "user", "content": prompt},
                ]
            )

            # Extract tool call
            if not response.tool_calls:
                logger.warning("[MemoryStore] LLM did not call save_memory tool")
                return False

            tool_call = response.tool_calls[0]
            args = tool_call.get("args", {})

            # Handle args that might be string or list (edge cases from different providers)
            if isinstance(args, str):
                args = json.loads(args)
            if isinstance(args, list) and args and isinstance(args[0], dict):
                args = args[0]

            if not isinstance(args, dict):
                logger.warning(f"[MemoryStore] Unexpected args type: {type(args)}")
                return False

            # Save history entry
            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)

            # Update long-term memory
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)

            # Update consolidation index
            new_index = 0 if archive_all else len(messages) - keep_count
            self.set_last_consolidated_index(new_index)

            logger.info(
                f"[MemoryStore] Consolidation complete. "
                f"Total messages: {len(messages)}, new index: {new_index}"
            )
            return True

        except Exception as e:
            logger.error(f"[MemoryStore] Consolidation failed: {e}")
            return False


def get_memory_store(user_id: str, session_id: Optional[str] = None) -> MemoryStore:
    """Factory function to create a MemoryStore instance."""
    return MemoryStore(user_id, session_id)
