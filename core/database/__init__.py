"""
資料庫模組

統一導出所有資料庫操作函數，保持向後兼容。
使用方式：
    from core.database import get_connection, create_user, get_posts
"""

# 連接管理
from .connection import (
    DATABASE_URL,
    get_connection,
    init_db,
    close_all_connections,  # 新增：連接池清理
)

# 用戶相關
from .user import (
    # 密碼處理
    hash_password,
    verify_password,
    # 用戶 CRUD
    create_user,
    get_user_by_username,
    get_user_by_id,
    update_password,
    is_username_available,
    update_last_active,
    # Pi Network
    create_or_get_pi_user,
    get_user_by_pi_uid,
    link_pi_wallet,
    get_user_wallet_status,
    # 會員等級
    get_user_membership,
    upgrade_to_pro,
    # 密碼重置
    # create_reset_token,
    # get_reset_token,
    # delete_reset_token,
    # cleanup_expired_tokens,
    # 登入嘗試
    MAX_LOGIN_ATTEMPTS,
    LOCKOUT_HOURS,
    record_login_attempt,
    get_failed_attempts,
    is_account_locked,
    clear_login_attempts,
)

# 對話歷史
from .chat import (
    # 會話管理
    create_session,
    update_session_title,
    toggle_session_pin,
    get_sessions,
    delete_session,
    # 訊息
    save_chat_message,
    get_chat_history,
    clear_chat_history,
)

# 論壇功能
from .forum import (
    # 看板
    get_boards,
    get_board_by_slug,
    # 文章
    check_daily_post_limit,
    create_post,
    get_posts,
    get_post_by_id,
    update_post,
    delete_post,
    get_user_posts,
    get_daily_post_count,
    # 回覆
    add_comment,
    get_comments,
    get_daily_comment_count,
    # 打賞
    create_tip,
    get_tips_sent,
    get_tips_received,
    get_tips_total_received,
    # 標籤
    get_trending_tags,
    get_posts_by_tag,
    search_tags,
    # 用戶統計
    get_user_forum_stats,
    get_user_payment_history,
)

# 交易相關
from .trading import (
    # 自選清單
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
)

# 好友功能
from .friends import (
    # 用戶搜尋
    search_users,
    get_public_user_profile,
    # 好友請求
    send_friend_request,
    accept_friend_request,
    reject_friend_request,
    cancel_friend_request,
    remove_friend,
    # 封鎖功能
    block_user,
    unblock_user,
    get_blocked_users,
    # 好友列表
    get_friends_list,
    get_pending_requests_received,
    get_pending_requests_sent,
    get_friendship_status,
    get_friends_count,
    get_pending_count,
    is_blocked,
    is_friend,
)

# 私訊功能
from .messages import (
    # 對話管理
    get_or_create_conversation,
    get_conversations,
    get_conversation_by_id,
    get_conversation_with_user,
    get_conversation_with_messages,  # 優化版：一次取得對話和訊息
    # 訊息操作
    validate_message_send,  # 優化：合併驗證查詢
    send_message as send_dm_message,
    get_messages as get_dm_messages,
    mark_as_read,
    get_unread_count,
    # 訊息限制
    check_message_limit,
    increment_message_count,
    check_greeting_limit,
    increment_greeting_count,
    # 打招呼（Pro）
    send_greeting,
    # 搜尋（Pro）
    search_messages,
    delete_dm_message,
    hide_dm_message_for_user,  # 只對自己隱藏訊息
    hide_conversation_for_user,  # 隱藏整段對話
)

# 系統快取
from .cache import (
    set_cache,
    get_cache,
    delete_cache,
    clear_all_cache,
)

# 系統配置（商用化 V2 - Redis + 審計日誌）
from .system_config import (
    # 配置讀取
    get_config,
    get_all_configs,
    get_prices,
    get_limits,
    # 配置更新
    set_config,
    update_price,
    update_limit,
    bulk_update_configs,
    # 配置管理
    get_config_metadata,
    list_all_configs_with_metadata,
    invalidate_cache as invalidate_config_cache,
    # 審計日誌
    get_config_history,
    init_audit_table,
)

# 分析報告（Agent 輸出）
from .analysis import (
    save_analysis_report,
    get_analysis_reports,
    get_analysis_report_by_id,
)

# 通知功能
from .notifications import (
    create_notifications_table,
    create_notification,
    get_notifications,
    get_unread_count,
    mark_notification_as_read,
    mark_all_as_read,
    delete_notification,
    notify_friend_request,
    notify_friend_accepted,
    notify_new_message,
    notify_post_interaction,
    notify_system_update,
    notify_announcement,
)


# Price Alerts
from .price_alerts import (
    create_price_alerts_table,
    create_alert,
    get_user_alerts,
    delete_alert,
    get_active_alerts,
    mark_alert_triggered,
    count_user_alerts,
)


# 定義公開 API
__all__ = [
    # 連接
    'DATABASE_URL',
    'get_connection',
    'init_db',
    'close_all_connections',  # 新增
    # 用戶
    'hash_password',
    'verify_password',
    'create_user',
    'get_user_by_username',
    'get_user_by_id',
    'get_user_by_email',
    'update_password',
    'is_username_available',
    'update_last_active',
    'create_or_get_pi_user',
    'get_user_by_pi_uid',
    'link_pi_wallet',
    'get_user_wallet_status',
    'get_user_membership',
    'upgrade_to_pro',
    'create_reset_token',
    'get_reset_token',
    'delete_reset_token',
    'cleanup_expired_tokens',
    'MAX_LOGIN_ATTEMPTS',
    'LOCKOUT_HOURS',
    'record_login_attempt',
    'get_failed_attempts',
    'is_account_locked',
    'clear_login_attempts',
    # 對話
    'create_session',
    'update_session_title',
    'toggle_session_pin',
    'get_sessions',
    'delete_session',
    'save_chat_message',
    'get_chat_history',
    'clear_chat_history',
    # 論壇
    'get_boards',
    'get_board_by_slug',
    'check_daily_post_limit',
    'create_post',
    'get_posts',
    'get_post_by_id',
    'update_post',
    'delete_post',
    'get_user_posts',
    'get_daily_post_count',
    'add_comment',
    'get_comments',
    'get_daily_comment_count',
    'create_tip',
    'get_tips_sent',
    'get_tips_received',
    'get_tips_total_received',
    'get_trending_tags',
    'get_posts_by_tag',
    'search_tags',
    'get_user_forum_stats',
    'get_user_payment_history',
    # 交易
    'add_to_watchlist',
    'remove_from_watchlist',
    'get_watchlist',
    # 好友功能
    'search_users',
    'get_public_user_profile',
    'send_friend_request',
    'accept_friend_request',
    'reject_friend_request',
    'cancel_friend_request',
    'remove_friend',
    'block_user',
    'unblock_user',
    'get_blocked_users',
    'get_friends_list',
    'get_pending_requests_received',
    'get_pending_requests_sent',
    'get_friendship_status',
    'get_friends_count',
    'get_pending_count',
    'is_blocked',
    'is_friend',
    # 私訊功能
    'get_or_create_conversation',
    'get_conversations',
    'get_conversation_by_id',
    'get_conversation_with_user',
    'send_dm_message',
    'get_dm_messages',
    'mark_as_read',
    'get_unread_count',
    'check_message_limit',
    'increment_message_count',
    'check_greeting_limit',
    'increment_greeting_count',
    'send_greeting',
    'search_messages',
    'delete_dm_message',
    'hide_dm_message_for_user',
    'hide_conversation_for_user',
    'get_conversation_with_messages',
    # 快取
    'set_cache',
    'get_cache',
    'delete_cache',
    'clear_all_cache',
    # 系統配置
    'get_config',
    'get_all_configs',
    'get_prices',
    'get_limits',
    'set_config',
    'update_price',
    'update_limit',
    'bulk_update_configs',
    'get_config_metadata',
    'list_all_configs_with_metadata',
    'invalidate_config_cache',
    # 審計日誌
    'get_config_history',
    'init_audit_table',
    # 分析報告
    'save_analysis_report',
    'get_analysis_reports',
    'get_analysis_report_by_id',
    # 通知功能
    'create_notifications_table',
    'create_notification',
    'get_notifications',
    'get_unread_count',
    'mark_notification_as_read',
    'mark_all_as_read',
    'delete_notification',
    'notify_friend_request',
    'notify_friend_accepted',
    'notify_new_message',
    'notify_post_interaction',
    'notify_system_update',
    'notify_announcement',
    # Price Alerts
    'create_price_alerts_table',
    'create_alert',
    'get_user_alerts',
    'delete_alert',
    'get_active_alerts',
    'mark_alert_triggered',
    'count_user_alerts',
]
