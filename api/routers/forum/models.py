"""
Forum API request models.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """Create post payload."""

    board_slug: str = Field(..., description="Board slug")
    category: str = Field(
        ..., description="Post category: analysis/question/tutorial/news/chat/insight"
    )
    title: str = Field(..., max_length=200, description="Post title")
    content: str = Field(..., description="Post content")
    tags: Optional[List[str]] = Field(None, max_length=5, description="Post tags")
    payment_id: Optional[str] = Field(
        None, description="Pi payment ID for server-side verification"
    )
    payment_tx_hash: Optional[str] = Field(
        None, description="Pi blockchain transaction hash"
    )


class UpdatePostRequest(BaseModel):
    """Update post payload."""

    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    category: Optional[str] = None


class AddCommentRequest(BaseModel):
    """Add comment payload."""

    type: str = Field(..., description="Comment type: push/boo/comment")
    content: Optional[str] = Field(
        None, max_length=100, description="Comment content"
    )
    parent_id: Optional[int] = Field(None, description="Parent comment ID")


class CreateTipRequest(BaseModel):
    tx_hash: Optional[str] = Field(None, description="Pi blockchain tx hash")
    payment_id: Optional[str] = Field(
        None, description="Pi payment ID for server-side verification"
    )
    amount: float = Field(..., description="Tip amount (from /api/config/prices)")


class PiPaymentCallback(BaseModel):
    """Pi payment callback payload."""

    payment_id: str
    txid: str
    amount: float
    memo: Optional[str] = None
    from_address: str
    to_address: str
    status: str
