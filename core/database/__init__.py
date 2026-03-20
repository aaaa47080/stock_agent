"""
資料庫模組

統一導出所有資料庫操作函數，保持向後兼容。
使用 lazy import 避免 package import 時載入整個資料庫子系統，
這對 pytest collect 與工具腳本都更穩定。
"""

from importlib import import_module
from typing import Dict, Tuple

from . import connection as _connection

get_connection = _connection.get_connection
init_db = _connection.init_db
close_all_connections = _connection.close_all_connections

_EXPORTS: Dict[str, Tuple[str, str]] = {
    # user
    "get_user_by_id": (".user", "get_user_by_id"),
    "update_last_active": (".user", "update_last_active"),
    "create_or_get_pi_user": (".user", "create_or_get_pi_user"),
    "get_user_by_pi_uid": (".user", "get_user_by_pi_uid"),
    "get_user_wallet_status": (".user", "get_user_wallet_status"),
    "get_user_membership": (".user", "get_user_membership"),
    "upgrade_to_pro": (".user", "upgrade_to_pro"),
    # chat
    "create_session": (".chat", "create_session"),
    "update_session_title": (".chat", "update_session_title"),
    "toggle_session_pin": (".chat", "toggle_session_pin"),
    "get_sessions": (".chat", "get_sessions"),
    "delete_session": (".chat", "delete_session"),
    "save_chat_message": (".chat", "save_chat_message"),
    "get_chat_history": (".chat", "get_chat_history"),
    "clear_chat_history": (".chat", "clear_chat_history"),
    # forum
    "get_boards": (".forum", "get_boards"),
    "get_board_by_slug": (".forum", "get_board_by_slug"),
    "check_daily_post_limit": (".forum", "check_daily_post_limit"),
    "create_post": (".forum", "create_post"),
    "get_posts": (".forum", "get_posts"),
    "get_post_by_id": (".forum", "get_post_by_id"),
    "update_post": (".forum", "update_post"),
    "delete_post": (".forum", "delete_post"),
    "get_user_posts": (".forum", "get_user_posts"),
    "get_daily_post_count": (".forum", "get_daily_post_count"),
    "add_comment": (".forum", "add_comment"),
    "get_comments": (".forum", "get_comments"),
    "get_daily_comment_count": (".forum", "get_daily_comment_count"),
    "create_tip": (".forum", "create_tip"),
    "get_tips_sent": (".forum", "get_tips_sent"),
    "get_tips_received": (".forum", "get_tips_received"),
    "get_tips_total_received": (".forum", "get_tips_total_received"),
    "get_trending_tags": (".forum", "get_trending_tags"),
    "get_posts_by_tag": (".forum", "get_posts_by_tag"),
    "search_tags": (".forum", "search_tags"),
    "get_user_forum_stats": (".forum", "get_user_forum_stats"),
    "get_user_payment_history": (".forum", "get_user_payment_history"),
    # trading
    "add_to_watchlist": (".trading", "add_to_watchlist"),
    "remove_from_watchlist": (".trading", "remove_from_watchlist"),
    "get_watchlist": (".trading", "get_watchlist"),
    # friends
    "search_users": (".friends", "search_users"),
    "get_public_user_profile": (".friends", "get_public_user_profile"),
    "send_friend_request": (".friends", "send_friend_request"),
    "accept_friend_request": (".friends", "accept_friend_request"),
    "reject_friend_request": (".friends", "reject_friend_request"),
    "cancel_friend_request": (".friends", "cancel_friend_request"),
    "remove_friend": (".friends", "remove_friend"),
    "block_user": (".friends", "block_user"),
    "unblock_user": (".friends", "unblock_user"),
    "get_blocked_users": (".friends", "get_blocked_users"),
    "get_friends_list": (".friends", "get_friends_list"),
    "get_pending_requests_received": (".friends", "get_pending_requests_received"),
    "get_pending_requests_sent": (".friends", "get_pending_requests_sent"),
    "get_friendship_status": (".friends", "get_friendship_status"),
    "get_bulk_friendship_status": (".friends", "get_bulk_friendship_status"),
    "get_friends_count": (".friends", "get_friends_count"),
    "get_pending_count": (".friends", "get_pending_count"),
    "is_blocked": (".friends", "is_blocked"),
    "is_friend": (".friends", "is_friend"),
    # messages
    "get_or_create_conversation": (".messages", "get_or_create_conversation"),
    "get_conversations": (".messages", "get_conversations"),
    "get_conversation_by_id": (".messages", "get_conversation_by_id"),
    "get_conversation_with_user": (".messages", "get_conversation_with_user"),
    "get_conversation_with_messages": (".messages", "get_conversation_with_messages"),
    "send_dm_message": (".messages", "send_message"),
    "get_dm_messages": (".messages", "get_messages"),
    "mark_as_read": (".messages", "mark_as_read"),
    "get_unread_count": (".messages", "get_unread_count"),
    "check_message_limit": (".messages", "check_message_limit"),
    "check_and_increment_message": (".messages", "check_and_increment_message"),
    "increment_message_count": (".messages", "increment_message_count"),
    "check_greeting_limit": (".messages", "check_greeting_limit"),
    "check_and_increment_greeting": (".messages", "check_and_increment_greeting"),
    "increment_greeting_count": (".messages", "increment_greeting_count"),
    "send_greeting": (".messages", "send_greeting"),
    "search_messages": (".messages", "search_messages"),
    "delete_dm_message": (".messages", "delete_dm_message"),
    "hide_dm_message_for_user": (".messages", "hide_dm_message_for_user"),
    "hide_conversation_for_user": (".messages", "hide_conversation_for_user"),
    # cache
    "set_cache": (".cache", "set_cache"),
    "get_cache": (".cache", "get_cache"),
    "delete_cache": (".cache", "delete_cache"),
    "clear_all_cache": (".cache", "clear_all_cache"),
    # system config
    "get_config": (".system_config", "get_config"),
    "get_all_configs": (".system_config", "get_all_configs"),
    "get_prices": (".system_config", "get_prices"),
    "get_limits": (".system_config", "get_limits"),
    "set_config": (".system_config", "set_config"),
    "update_price": (".system_config", "update_price"),
    "update_limit": (".system_config", "update_limit"),
    "bulk_update_configs": (".system_config", "bulk_update_configs"),
    "get_config_metadata": (".system_config", "get_config_metadata"),
    "list_all_configs_with_metadata": (".system_config", "list_all_configs_with_metadata"),
    "invalidate_config_cache": (".system_config", "invalidate_cache"),
    "get_config_history": (".system_config", "get_config_history"),
    "init_audit_table": (".system_config", "init_audit_table"),
    # analysis
    "save_analysis_report": (".analysis", "save_analysis_report"),
    "get_analysis_reports": (".analysis", "get_analysis_reports"),
    "get_analysis_report_by_id": (".analysis", "get_analysis_report_by_id"),
    # notifications
    "create_notifications_table": (".notifications", "create_notifications_table"),
    "create_notification": (".notifications", "create_notification"),
    "get_notifications": (".notifications", "get_notifications"),
    "mark_notification_as_read": (".notifications", "mark_notification_as_read"),
    "mark_all_as_read": (".notifications", "mark_all_as_read"),
    "delete_notification": (".notifications", "delete_notification"),
    "notify_friend_request": (".notifications", "notify_friend_request"),
    "notify_friend_accepted": (".notifications", "notify_friend_accepted"),
    "notify_new_message": (".notifications", "notify_new_message"),
    "notify_post_interaction": (".notifications", "notify_post_interaction"),
    "notify_system_update": (".notifications", "notify_system_update"),
    "notify_announcement": (".notifications", "notify_announcement"),
    # price alerts
    "create_price_alerts_table": (".price_alerts", "create_price_alerts_table"),
    "create_alert": (".price_alerts", "create_alert"),
    "get_user_alerts": (".price_alerts", "get_user_alerts"),
    "delete_alert": (".price_alerts", "delete_alert"),
    "get_active_alerts": (".price_alerts", "get_active_alerts"),
    "mark_alert_triggered": (".price_alerts", "mark_alert_triggered"),
    "count_user_alerts": (".price_alerts", "count_user_alerts"),
    # tools
    "seed_tools_catalog": (".tools", "seed_tools_catalog"),
    "get_allowed_tools": (".tools", "get_allowed_tools"),
    "check_tool_quota": (".tools", "check_tool_quota"),
    "increment_tool_usage": (".tools", "increment_tool_usage"),
    "get_tools_for_frontend": (".tools", "get_tools_for_frontend"),
    "update_user_tool_preference": (".tools", "update_user_tool_preference"),
    # memory
    "MemoryStore": (".memory", "MemoryStore"),
    "get_memory_store": (".memory", "get_memory_store"),
}

__all__ = [
    "DATABASE_URL",
    "get_connection",
    "init_db",
    "close_all_connections",
    *_EXPORTS.keys(),
]


def __getattr__(name: str):
    if name == "DATABASE_URL":
        return _connection.get_database_url()
    if name in {"get_connection", "init_db", "close_all_connections"}:
        return globals()[name]
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(__all__)
