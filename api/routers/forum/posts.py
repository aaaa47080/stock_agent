"""
Forum post API endpoints.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordBearer

from api.deps import get_current_user, resolve_request_token, verify_token
from api.middleware.rate_limit import limiter
from api.utils import run_sync
from core.config import TEST_MODE, TEST_USER
from core.database import check_daily_post_limit, get_user_membership
from core.orm.forum_repo import forum_repo

from .models import CreatePostRequest, UpdatePostRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forum/posts", tags=["Forum - Posts"])
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/user/login", auto_error=False
)

VALID_CATEGORIES = ["analysis", "question", "tutorial", "news", "chat", "insight"]


@router.get("")
async def list_posts(
    board: Optional[str] = Query(None, description="Board slug"),
    category: Optional[str] = Query(None, description="Post category"),
    tag: Optional[str] = Query(None, description="Post tag"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        board_id = None
        if board:
            board_info = await forum_repo.get_board_by_slug(board)
            if not board_info:
                raise HTTPException(status_code=404, detail="Board not found")
            board_id = board_info["id"]

        posts = await forum_repo.get_posts(
            board_id=board_id,
            category=category,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "posts": posts, "count": len(posts)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load posts")


@router.post("")
@limiter.limit("20/minute")
async def create_new_post(
    request: Request,
    body: CreatePostRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]

        if body.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Allowed: {', '.join(VALID_CATEGORIES)}",
            )

        board = await forum_repo.get_board_by_slug(body.board_slug)
        if not board:
            raise HTTPException(status_code=404, detail="Board not found")
        if not board["is_active"]:
            raise HTTPException(status_code=400, detail="Board is not active")

        membership = await run_sync(get_user_membership, user_id)

        limit_check = await run_sync(check_daily_post_limit, user_id)
        if not limit_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily post limit reached ({limit_check['limit']})",
            )

        is_test_user = TEST_MODE and (
            user_id.startswith("test-user-") or user_id == TEST_USER.get("uid")
        )

        if not membership["is_premium"]:
            if is_test_user and not body.payment_tx_hash:
                body.payment_tx_hash = f"test_post_{int(time.time() * 1000)}"
                logger.info(
                    "TEST_MODE: Bypassing payment requirement for user %s", user_id
                )
            elif not body.payment_tx_hash:
                raise HTTPException(
                    status_code=402,
                    detail="Free members must complete payment before posting",
                )
            elif body.payment_tx_hash.startswith("mock_"):
                raise HTTPException(
                    status_code=402,
                    detail="Mock payment hashes are not accepted",
                )

        result = await forum_repo.create_post(
            board_id=board["id"],
            user_id=user_id,
            category=body.category,
            title=body.title,
            content=body.content,
            tags=body.tags,
            payment_tx_hash=body.payment_tx_hash,
        )

        if not result["success"]:
            if result.get("error") == "daily_post_limit_reached":
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily post limit reached ({result['limit']})",
                )
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to create post")
            )

        return {
            "success": True,
            "message": "Post created successfully",
            "post_id": result["post_id"],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create post")


@router.get("/{post_id}")
async def get_post_detail(
    post_id: int, request: Request, token: Optional[str] = Depends(oauth2_scheme_optional)
):
    try:
        viewer_user_id = None
        resolved_token = resolve_request_token(request, token)
        if resolved_token:
            try:
                viewer_user_id = verify_token(resolved_token).get("sub")
            except HTTPException:
                viewer_user_id = None

        post = await forum_repo.get_post_by_id(
            post_id, increment_view=True, viewer_user_id=viewer_user_id
        )
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        if post["is_hidden"]:
            raise HTTPException(status_code=404, detail="Post has been hidden")

        return {"success": True, "post": post}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load post")


@router.put("/{post_id}")
@limiter.limit("10/minute")
async def update_post_content(
    post_id: int,
    request: Request,
    req: UpdatePostRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]

        if req.category and req.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Allowed: {', '.join(VALID_CATEGORIES)}",
            )

        success = await forum_repo.update_post(
            post_id=post_id,
            user_id=user_id,
            title=req.title,
            content=req.content,
            category=req.category,
        )

        if not success:
            raise HTTPException(status_code=403, detail="Cannot edit this post")

        return {"success": True, "message": "Post updated"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update post")


@router.delete("/{post_id}")
@limiter.limit("10/minute")
async def delete_post_by_id(
    request: Request, post_id: int, current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["user_id"]

        success = await forum_repo.delete_post(post_id=post_id, user_id=user_id)

        if not success:
            raise HTTPException(status_code=403, detail="Cannot delete this post")

        return {"success": True, "message": "Post deleted"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete post")
