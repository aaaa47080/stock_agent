"""
資料庫模組

統一導出所有資料庫操作函數，保持向後兼容。
使用方式：
    from core.database import get_connection, create_user, get_posts
"""

# 連接管理
from .connection import (
    DB_PATH,
    get_connection,
    init_db,
)

# 用戶相關
from .user import (
    # 密碼處理
    hash_password,
    verify_password,
    # 用戶 CRUD
    create_user,
    get_user_by_username,
    get_user_by_email,
    update_password,
    is_username_available,
    # Pi Network
    create_or_get_pi_user,
    get_user_by_pi_uid,
    link_pi_wallet,
    get_user_wallet_status,
    # 會員等級
    get_user_membership,
    upgrade_to_pro,
    # 密碼重置
    create_reset_token,
    get_reset_token,
    delete_reset_token,
    cleanup_expired_tokens,
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
    # 預測
    submit_prediction,
    get_leaderboard,
    get_user_predictions,
)

# 系統快取
from .cache import (
    set_cache,
    get_cache,
    delete_cache,
    clear_all_cache,
)


# 定義公開 API
__all__ = [
    # 連接
    'DB_PATH',
    'get_connection',
    'init_db',
    # 用戶
    'hash_password',
    'verify_password',
    'create_user',
    'get_user_by_username',
    'get_user_by_email',
    'update_password',
    'is_username_available',
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
    'submit_prediction',
    'get_leaderboard',
    'get_user_predictions',
    # 快取
    'set_cache',
    'get_cache',
    'delete_cache',
    'clear_all_cache',
]
