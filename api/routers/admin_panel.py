"""
管理後台 API（獨立模組）
- 模組已拆分為 api/routers/admin/ 子模組
- 通知管理
- 用戶管理
- 論壇管理 (P1)
- 系統設定 (P1)
- 統計儀表板 (P2)

此文件為向後兼容的重新導出模組
實際實現在 api/routers/admin/ 子目錄中
"""

# Re-export everything from the admin submodule for backward compatibility
from api.routers.admin import (
    router,
    notifications_router,
    users_router,
    forum_router,
    config_router,
    stats_router,
    BroadcastRequest,
    SetRoleRequest,
    SetMembershipRequest,
    SetStatusRequest,
    PostVisibilityRequest,
    PostPinRequest,
    ResolveReportRequest,
    UpdateConfigRequest,
)

__all__ = [
    "router",
    "notifications_router",
    "users_router",
    "forum_router",
    "config_router",
    "stats_router",
    "BroadcastRequest",
    "SetRoleRequest",
    "SetMembershipRequest",
    "SetStatusRequest",
    "PostVisibilityRequest",
    "PostPinRequest",
    "ResolveReportRequest",
    "UpdateConfigRequest",
]
