"""
私訊功能資料庫操作（向後兼容模組）
實際實現在 core/database/messages/ 子目錄中
"""

# Re-export everything from the submodule for backward compatibility
from .messages import (
    check_greeting_limit,
    # 訊息限制
    check_message_limit,
    delete_dm_message,
    get_conversation_by_id,
    get_conversation_with_messages,
    get_conversation_with_user,
    get_conversations,
    get_messages,
    # 對話管理
    get_or_create_conversation,
    get_unread_count,
    hide_conversation_for_user,
    hide_dm_message_for_user,
    increment_greeting_count,
    increment_message_count,
    mark_as_read,
    # 搜尋
    search_messages,
    # 輔助功能
    send_greeting,
    send_message,
    # 訊息操作
    validate_message_send,
)

__all__ = [
    # 對話管理
    "get_or_create_conversation",
    "get_conversations",
    "get_conversation_by_id",
    "get_conversation_with_user",
    # 訊息操作
    "validate_message_send",
    "send_message",
    "get_messages",
    "mark_as_read",
    "get_unread_count",
    # 訊息限制
    "check_message_limit",
    "increment_message_count",
    "check_greeting_limit",
    "increment_greeting_count",
    # 搜尋
    "search_messages",
    # 輔助功能
    "send_greeting",
    "delete_dm_message",
    "hide_dm_message_for_user",
    "get_conversation_with_messages",
    "hide_conversation_for_user",
]
