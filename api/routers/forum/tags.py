"""
標籤相關 API
"""
from fastapi import APIRouter, HTTPException, Query

from core.database import (
    get_trending_tags,
    get_posts_by_tag,
    search_tags,
)
import asyncio
from functools import partial

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
        loop = asyncio.get_running_loop()
        if q:
            tags = await loop.run_in_executor(None, partial(search_tags, q, limit=limit))
        else:
            tags = await loop.run_in_executor(None, partial(get_trending_tags, limit=limit))

        return {
            "success": True,
            "tags": tags,
            "count": len(tags),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取標籤列表失敗: {str(e)}")


@router.get("/trending")
async def get_hot_tags(limit: int = Query(10, ge=1, le=20)):
    """
    獲取熱門標籤（近 7 天內使用頻率最高）
    """
    try:
        loop = asyncio.get_running_loop()
        tags = await loop.run_in_executor(None, partial(get_trending_tags, limit=limit))
        return {
            "success": True,
            "tags": tags,
            "count": len(tags),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取熱門標籤失敗: {str(e)}")


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
        loop = asyncio.get_running_loop()
        posts = await loop.run_in_executor(None, partial(get_posts_by_tag, tag_name, limit=limit, offset=offset))
        return {
            "success": True,
            "tag": tag_name.upper(),
            "posts": posts,
            "count": len(posts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取標籤文章失敗: {str(e)}")
