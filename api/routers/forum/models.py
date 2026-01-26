"""
論壇 API 請求/回應模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# 文章相關
# ============================================================================

class CreatePostRequest(BaseModel):
    """發表文章請求"""
    board_slug: str = Field(..., description="看板 slug")
    category: str = Field(..., description="分類: analysis/question/tutorial/news/chat/insight")
    title: str = Field(..., max_length=50, description="標題，限 50 字")
    content: str = Field(..., description="內容")
    tags: Optional[List[str]] = Field(None, max_length=5, description="標籤，最多 5 個")
    payment_tx_hash: Optional[str] = Field(None, description="Pi 支付交易哈希（免費會員需提供）")


class UpdatePostRequest(BaseModel):
    """編輯文章請求"""
    title: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = None
    category: Optional[str] = None


class PostListQuery(BaseModel):
    """文章列表查詢參數"""
    board_slug: Optional[str] = None
    category: Optional[str] = None
    tag: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


# ============================================================================
# 回覆相關
# ============================================================================

class AddCommentRequest(BaseModel):
    """新增回覆請求"""
    type: str = Field(..., description="類型: push/boo/comment")
    content: Optional[str] = Field(None, max_length=100, description="回覆內容，限 100 字")
    parent_id: Optional[int] = Field(None, description="父回覆 ID（用於巢狀回覆）")


# ============================================================================
# 打賞相關
# ============================================================================

class CreateTipRequest(BaseModel):
    """打賞請求"""
    tx_hash: str = Field(..., description="Pi 支付交易哈希")
    amount: float = Field(..., description="打賞金額（從 /api/config/prices 獲取 tip 價格）")


# ============================================================================
# Pi 支付回調
# ============================================================================

class PiPaymentCallback(BaseModel):
    """Pi 支付回調"""
    payment_id: str
    txid: str
    amount: float
    memo: Optional[str] = None
    from_address: str
    to_address: str
    status: str


# ============================================================================
# 通用回應
# ============================================================================

class SuccessResponse(BaseModel):
    """成功回應"""
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """錯誤回應"""
    success: bool = False
    error: str
    detail: Optional[str] = None
