"""
Admin Panel Router Module
Combines notifications, users, forum, config, and stats endpoints
"""
from fastapi import APIRouter

from .notifications import router as notifications_router
from .users import router as users_router
from .forum import router as forum_router
from .config import router as config_router
from .stats import router as stats_router
from .schemas import (
    BroadcastRequest,
    SetRoleRequest,
    SetMembershipRequest,
    SetStatusRequest,
    PostVisibilityRequest,
    PostPinRequest,
    ResolveReportRequest,
    UpdateConfigRequest,
)

router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])
router.include_router(notifications_router)
router.include_router(users_router)
router.include_router(forum_router)
router.include_router(config_router)
router.include_router(stats_router)


# Re-export all for backward compatibility
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
