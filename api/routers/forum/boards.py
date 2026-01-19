"""
看板相關 API
"""
from fastapi import APIRouter, HTTPException

from core.database import get_boards, get_board_by_slug

router = APIRouter(prefix="/api/forum/boards", tags=["Forum - Boards"])


@router.get("")
async def list_boards():
    """
    獲取所有啟用的看板列表

    Returns:
        - boards: 看板列表
    """
    try:
        boards = get_boards(active_only=True)
        return {"success": True, "boards": boards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取看板列表失敗: {str(e)}")


@router.get("/{slug}")
async def get_board(slug: str):
    """
    獲取指定看板詳情

    Args:
        slug: 看板 slug (如 "crypto")

    Returns:
        - board: 看板詳情
    """
    try:
        board = get_board_by_slug(slug)
        if not board:
            raise HTTPException(status_code=404, detail="看板不存在")
        return {"success": True, "board": board}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取看板詳情失敗: {str(e)}")
