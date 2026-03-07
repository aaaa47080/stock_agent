"""
私訊功能資料庫操作模組
包含：對話管理、訊息發送、已讀狀態、訊息限制
"""
# 對話管理
from .conversations import (
    get_or_create_conversation,
    get_conversations,
    get_conversation_by_id,
    get_conversation_with_user,
)

# 訊息操作
from .messaging import (
    validate_message_send,
    send_message,
    get_messages,
    mark_as_read,
    get_unread_count,
)

# 訊息限制
from .limits import (
    check_message_limit,
    increment_message_count,
    check_greeting_limit,
    increment_greeting_count,
)

# 搜尋
from .search import search_messages

# 輔助功能
from .helpers import (
    send_greeting,
    delete_dm_message,
    hide_dm_message_for_user,
    get_conversation_with_messages,
    hide_conversation_for_user,
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
