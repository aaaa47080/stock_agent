"""
可疑錢包追蹤系統 API 路由
"""
from fastapi import APIRouter
from .reports import router as reports_router
from .votes import router as votes_router
from .comments import router as comments_router

router = APIRouter(prefix="/api/scam-tracker", tags=["Scam Tracker"])

router.include_router(reports_router)
router.include_router(votes_router)
router.include_router(comments_router)
