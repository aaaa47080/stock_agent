"""
可疑錢包追蹤系統 - Pydantic 模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class ScamReportCreate(BaseModel):
    """創建舉報請求"""
    scam_wallet_address: str = Field(..., min_length=56, max_length=56)
    reporter_wallet_address: str = Field(..., min_length=56, max_length=56)
    scam_type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=20, max_length=2000)
    transaction_hash: Optional[str] = Field(None, min_length=64, max_length=64)

    @field_validator('scam_wallet_address', 'reporter_wallet_address')
    @classmethod
    def validate_wallet_format(cls, v):
        if not v.startswith('G'):
            raise ValueError("Pi Network 地址必須以 'G' 開頭")
        return v.upper()

    @field_validator('transaction_hash')
    @classmethod
    def validate_tx_hash(cls, v):
        if v:
            return v.lower()
        return v


class ScamReportResponse(BaseModel):
    """舉報響應"""
    id: int
    scam_wallet_address: str
    scam_type: str
    description: str
    verification_status: str
    approve_count: int
    reject_count: int
    comment_count: int
    view_count: int
    reporter_wallet_masked: str
    reporter_username: Optional[str]
    created_at: str
    net_votes: int


class ScamReportDetailResponse(ScamReportResponse):
    """舉報詳情響應"""
    transaction_hash: Optional[str]
    updated_at: str
    viewer_vote: Optional[str]


class VoteRequest(BaseModel):
    """投票請求"""
    vote_type: str = Field(..., pattern="^(approve|reject)$")


class CommentCreate(BaseModel):
    """創建評論請求"""
    content: str = Field(..., min_length=10, max_length=1000)
    transaction_hash: Optional[str] = Field(None, min_length=64, max_length=64)

    @field_validator('transaction_hash')
    @classmethod
    def validate_tx_hash(cls, v):
        if v:
            return v.lower()
        return v
