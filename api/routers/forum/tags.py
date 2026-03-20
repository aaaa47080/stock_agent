"""
標籤相關 API
"""

from fastapi import APIRouter, HTTPException, Query

from api.utils import run_sync
from core.database import (
    get_posts_by_tag,
    get_trending_tags,
    search_tags,
)

router = APIRouter(prefix="/api/forum/tags", tags=["Forum - Tags"])


@router.get("")
async def list_tags(
    q: str = Query(None, description="搜尋關鍵字"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    獲取標籤列表

    - 若提供 q 參數，則進行搜尋
    - 否則返回熱門標籤
    """
    try:
        if q:
            tags = await run_sync(lambda: search_tags(q, limit=limit))
        else:
            tags = await run_sync(lambda: get_trending_tags(limit=limit))

        return {
            "success": True,
            "tags": tags,
            "count": len(tags),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取標籤列表失敗，請稍後再試")


@router.get("/trending")
async def get_hot_tags(limit: int = Query(10, ge=1, le=20)):
    """
    獲取熱門標籤（近 7 天內使用頻率最高）
    """
    try:
        tags = await run_sync(lambda: get_trending_tags(limit=limit))
        return {
            "success": True,
            "tags": tags,
            "count": len(tags),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取熱門標籤失敗，請稍後再試")


@router.get("/{tag_name}/posts")
async def get_posts_with_tag(
    tag_name: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    獲取指定標籤的文章列表
    """
    try:
        posts = await run_sync(
            lambda: get_posts_by_tag(tag_name, limit=limit, offset=offset)
        )
        return {
            "success": True,
            "tag": tag_name.upper(),
            "posts": posts,
            "count": len(posts),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="獲取標籤文章失敗，請稍後再試")
