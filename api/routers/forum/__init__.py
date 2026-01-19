"""
論壇 API 模組

將所有論壇相關的路由整合為一個 router
"""
from fastapi import APIRouter

from .boards import router as boards_router
from .posts import router as posts_router
from .comments import router as comments_router
from .tips import router as tips_router
from .tags import router as tags_router
from .me import router as me_router

# 創建主路由
router = APIRouter()

# 註冊子路由
router.include_router(boards_router)
router.include_router(posts_router)
router.include_router(comments_router)
router.include_router(tips_router)
router.include_router(tags_router)
router.include_router(me_router)


# 導出
__all__ = ["router"]
