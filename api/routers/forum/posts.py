"""
文章相關 API
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from core.database import (
    get_board_by_slug,
    create_post,
    get_posts,
    get_post_by_id,
    update_post,
    delete_post,
    get_user_membership,
    check_daily_post_limit,
    get_user_by_id,
    get_prices,
    get_limits,
)
from .models import CreatePostRequest, UpdatePostRequest
import asyncio
from functools import partial
import logging
import time

# Import TEST_MODE for development/testing bypass
from core.config import TEST_MODE, TEST_USER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forum/posts", tags=["Forum - Posts"])


# 文章分類列表
VALID_CATEGORIES = ["analysis", "question", "tutorial", "news", "chat", "insight"]


@router.get("")
async def list_posts(
    board: Optional[str] = Query(None, description="看板 slug"),
    category: Optional[str] = Query(None, description="分類"),
    tag: Optional[str] = Query(None, description="標籤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    獲取文章列表

    可選篩選條件：
    - board: 看板 slug
    - category: 分類
    - tag: 標籤
    """
    try:
        loop = asyncio.get_running_loop()
        # 如果指定看板，先獲取看板 ID
        board_id = None
        if board:
            board_info = await loop.run_in_executor(None, get_board_by_slug, board)
            if not board_info:
                raise HTTPException(status_code=404, detail="看板不存在")
            board_id = board_info["id"]

        posts = await loop.run_in_executor(
            None,
            partial(get_posts, board_id=board_id, category=category, tag=tag, limit=limit, offset=offset)
        )
        return {"success": True, "posts": posts, "count": len(posts)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取文章列表失敗: {str(e)}")


from api.deps import get_current_user
from fastapi import Depends

@router.post("")
async def create_new_post(request: CreatePostRequest, user_id: str = Query(..., description="用戶 ID"), current_user: dict = Depends(get_current_user)):
    """
    發表新文章

    - 免費會員需提供 payment_tx_hash（支付費用從 /api/config/prices 獲取）
    - PRO 會員免費發文
    - 每日發文限制從 /api/config/limits 獲取，PRO 會員無限制
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to post as this user")

        loop = asyncio.get_running_loop()
        # 驗證用戶是否存在
        user = await loop.run_in_executor(None, get_user_by_id, user_id)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="用戶不存在或憑證失效，請重新登入 (User not found, please relogin)"
            )

        # 驗證分類
        if request.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"無效的分類，可選: {', '.join(VALID_CATEGORIES)}"
            )

        # 驗證看板
        board = await loop.run_in_executor(None, get_board_by_slug, request.board_slug)
        if not board:
            raise HTTPException(status_code=404, detail="看板不存在")
        if not board["is_active"]:
            raise HTTPException(status_code=400, detail="此看板目前不開放發文")

        # 檢查會員狀態
        membership = await loop.run_in_executor(None, get_user_membership, user_id)

        # 檢查每日發文限制（在付款前先檢查，避免用戶付費後才發現無法發文）
        limit_check = await loop.run_in_executor(None, check_daily_post_limit, user_id)
        if not limit_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"已達每日發文上限 ({limit_check['limit']} 篇)，升級 PRO 會員可無限發文"
            )

        # 免費會員需要付費 (測試模式下跳過)
        is_test_user = TEST_MODE and (user_id.startswith("test-user-") or user_id == TEST_USER.get("uid"))
        
        if not membership["is_pro"] and not request.payment_tx_hash:
            if is_test_user:
                # TEST_MODE: Mock payment for test users
                request.payment_tx_hash = f"test_post_{int(time.time() * 1000)}"
                logger.info(f"TEST_MODE: Bypassing payment requirement for user {user_id}")
            else:
                prices = await loop.run_in_executor(None, get_prices)
                raise HTTPException(
                    status_code=402,
                    detail=f"免費會員發文需支付 {prices.get('create_post', 1)} Pi，請提供 payment_tx_hash"
                )

        # 創建文章（跳過限制檢查，因為上面已經檢查過了）
        result = await loop.run_in_executor(
            None,
            partial(
                create_post,
                board_id=board["id"],
                user_id=user_id,
                category=request.category,
                title=request.title,
                content=request.content,
                tags=request.tags,
                payment_tx_hash=request.payment_tx_hash,
                skip_limit_check=True,
            )
        )

        if not result["success"]:
            if result.get("error") == "daily_post_limit_reached":
                raise HTTPException(
                    status_code=429,
                    detail=f"已達每日發文上限 ({result['limit']} 篇)，升級 PRO 會員可無限發文"
                )
            raise HTTPException(status_code=500, detail=result.get("error", "發表文章失敗"))

        return {
            "success": True,
            "message": "文章發表成功",
            "post_id": result["post_id"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"發表文章失敗: {str(e)}")


@router.get("/{post_id}")
async def get_post_detail(post_id: int, user_id: Optional[str] = Query(None, description="查看者的用戶 ID")):
    """
    獲取文章詳情

    會自動增加瀏覽數
    """
    try:
        loop = asyncio.get_running_loop()
        post = await loop.run_in_executor(
            None, 
            partial(get_post_by_id, post_id, increment_view=True, viewer_user_id=user_id)
        )
        if not post:
            raise HTTPException(status_code=404, detail="文章不存在")
        if post["is_hidden"]:
            raise HTTPException(status_code=404, detail="文章已被刪除")

        return {"success": True, "post": post}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取文章詳情失敗: {str(e)}")


@router.put("/{post_id}")
async def update_post_content(
    post_id: int,
    request: UpdatePostRequest,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    編輯文章（只有作者可以編輯）
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        # 驗證分類
        if request.category and request.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"無效的分類，可選: {', '.join(VALID_CATEGORIES)}"
            )

        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(
            None,
            partial(
                update_post,
                post_id=post_id,
                user_id=user_id,
                title=request.title,
                content=request.content,
                category=request.category,
            )
        )

        if not success:
            raise HTTPException(status_code=403, detail="無權編輯此文章或文章不存在")

        return {"success": True, "message": "文章更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新文章失敗: {str(e)}")


@router.delete("/{post_id}")
async def delete_post_by_id(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    刪除文章（軟刪除，只有作者可以刪除）
    """
    try:
        if current_user["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, partial(delete_post, post_id=post_id, user_id=user_id))

        if not success:
            raise HTTPException(status_code=403, detail="無權刪除此文章或文章不存在")

        return {"success": True, "message": "文章已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除文章失敗: {str(e)}")
