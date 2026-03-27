from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.config import DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT, SUPPORTED_EXCHANGES
from core.model_config import GEMINI_DEFAULT_MODEL


# 定義請求模型
class QueryRequest(BaseModel):
    message: str
    analysis_mode: Literal["quick", "verified", "research"] = "quick"
    interval: str = DEFAULT_INTERVAL
    limit: int = DEFAULT_KLINES_LIMIT
    manual_selection: Optional[List[str]] = None
    auto_execute: bool = False
    market_type: str = "spot"
    user_provider: Optional[str] = None  # preferred provider, if any
    user_model: Optional[str] = None  # 用戶選擇的模型名稱
    session_id: str = "default"  # 會話 ID
    resume_answer: Optional[Any] = None  # HITL 回答（Accepts str or dict）
    language: str = "zh-TW"  # 用戶語言偏好（"zh-TW" | "en"）


class ScreenerRequest(BaseModel):
    exchange: str = SUPPORTED_EXCHANGES[0]
    symbols: Optional[List[str]] = None
    refresh: bool = False


class WatchlistRequest(BaseModel):
    symbol: str


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用戶名")
    password: str = Field(..., min_length=8, max_length=128, description="密碼")


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="用戶名")
    password: str = Field(..., min_length=1, max_length=128, description="密碼")


class KlineRequest(BaseModel):
    symbol: str
    exchange: str = SUPPORTED_EXCHANGES[0]
    interval: str = "1d"
    limit: int = 100


class UserSettings(BaseModel):
    """用戶動態設置"""

    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

    # 模型選擇
    primary_model_provider: str = "google_gemini"  # openai, google_gemini, openrouter
    primary_model_name: str = GEMINI_DEFAULT_MODEL  # 默認為 Google Gemini


class RefreshPulseRequest(BaseModel):
    symbols: Optional[List[str]] = None


class KeyValidationRequest(BaseModel):
    provider: str  # openai, google_gemini, openrouter
    api_key: str
    model: Optional[str] = None  # 用戶選擇的模型名稱


# ============================================================================
# 社群治理系統 Models (Community Governance System)
# ============================================================================


class ReportCreateRequest(BaseModel):
    """創建檢舉請求"""

    content_type: Literal["post", "comment"]
    content_id: int
    report_type: Literal[
        "spam", "harassment", "misinformation", "scam", "illegal", "other"
    ]
    description: Optional[str] = Field(None, max_length=1000)


class ReportResponse(BaseModel):
    """檢舉回應"""

    id: int
    content_type: str
    content_id: int
    reporter_user_id: str
    report_type: str
    description: Optional[str]
    review_status: str  # pending, approved, rejected
    created_at: str
    updated_at: Optional[str] = None


class VoteRequest(BaseModel):
    """投票請求"""

    vote_type: str  # 'approve' (認為違規) 或 'reject' (認為不違規)


class ReportDetailResponse(BaseModel):
    """檢舉詳情回應"""

    id: int
    content_type: str
    content_id: int
    reporter_user_id: str
    reporter_username: Optional[str]
    report_type: str
    description: Optional[str]
    review_status: str
    violation_level: Optional[str]
    approve_count: int
    reject_count: int
    created_at: str
    updated_at: Optional[str]
    votes: Optional[List[Dict]] = None


class ViolationPointsResponse(BaseModel):
    """違規點數回應"""

    user_id: str
    points: int
    total_violations: int
    suspension_count: int
    last_violation_at: Optional[str]
    action_threshold: Optional[str] = None  # 下一步處罰等級


class ViolationRecordResponse(BaseModel):
    """違規記錄回應"""

    id: int
    user_id: str
    violation_level: str
    violation_type: str
    points: int
    action_taken: Optional[str]
    suspended_until: Optional[str]
    created_at: str


class ActivityLogResponse(BaseModel):
    """活動日誌回應"""

    id: int
    user_id: str
    activity_type: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    metadata: Optional[Dict]
    success: bool
    error_message: Optional[str]
    created_at: str


class ReviewStatisticsResponse(BaseModel):
    """審核統計回應"""

    total_reports: int
    pending_reports: int
    approved_reports: int
    rejected_reports: int
    total_votes: int
    avg_approval_rate: float


class AuditReputationResponse(BaseModel):
    """審核聲望回應"""

    user_id: str
    username: Optional[str]
    total_reviews: int
    correct_votes: int
    accuracy_rate: float
    reputation_score: int
    vote_weight: float


class FinalizeReportRequest(BaseModel):
    """完成檢舉請求"""

    decision: str  # 'approved' 或 'rejected'
    violation_level: Optional[str] = None  # mild, medium, severe, critical


class ConsensusResponse(BaseModel):
    """共識檢查回應"""

    has_consensus: bool
    decision: Optional[str] = None  # 'approved', 'rejected', or None
    total_votes: int
    approve_count: int
    reject_count: int
    approve_rate: float
    reason: Optional[str] = None


# Price Alerts
class CreateAlertRequest(BaseModel):
    symbol: str
    market: Literal["crypto", "tw_stock", "us_stock"]
    condition: Literal["above", "below", "change_pct_up", "change_pct_down"]
    target: float
    repeat: bool = False


class APIErrorResponse(BaseModel):
    """統一 API 錯誤回應格式"""

    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"
    details: Optional[Dict] = None
