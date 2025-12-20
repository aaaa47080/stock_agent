from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Optional

# ============================================================================
# Agent 角色定義
# ============================================================================

class MultiTimeframeData(BaseModel):
    """多週期數據結構"""
    short_term: Optional[Dict] = None      # 短週期數據 (1m, 5m, 15m, 30m, 1h)
    medium_term: Optional[Dict] = None     # 中週期數據 (2h, 4h, 6h, 12h, 1d)
    long_term: Optional[Dict] = None       # 長週期數據 (1d, 3d, 1w, 1mo)
    overall_trend: Optional[Dict] = None   # 綜合多週期趨勢分析


class AnalystReport(BaseModel):
    """分析師報告結構"""
    analyst_type: str
    summary: str = Field(..., min_length=50)
    key_findings: List[str]
    bullish_points: List[str] = []
    bearish_points: List[str] = []
    confidence: float = Field(..., ge=0, le=100)
    # 添加多週期分析支持
    multi_timeframe_analysis: Optional[MultiTimeframeData] = None


class ResearcherDebate(BaseModel):
    """研究員辯論結構"""
    researcher_stance: Literal['Bull', 'Bear', 'Neutral'] # Added Neutral
    argument: str = Field(..., min_length=100)
    key_points: List[str]
    counter_arguments: List[str] = []
    concession_point: Optional[str] = Field(None, description="對方最有道理的觀點 (讓步點)")
    confidence: float = Field(..., ge=0, le=100)
    round_number: int = 1  # 當前是第幾輪辯論
    opponent_view: Optional[str] = None  # 對手在上一輪的觀點（用於回應）
    # 添加多週期分析支持
    multi_timeframe_analysis: Optional[MultiTimeframeData] = None

class FactCheckResult(BaseModel):
    """數據檢察官驗證結果"""
    is_accurate: bool
    corrections: List[str] = []
    confidence_score: float = Field(..., ge=0, le=100)
    comment: str


class TraderDecision(BaseModel):
    """交易員決策結構"""
    decision: Literal['Buy', 'Sell', 'Hold', 'Long', 'Short']
    reasoning: str = Field(..., min_length=100)
    position_size: float = Field(..., ge=0, le=1)
    leverage: Optional[int] = Field(None, ge=1, le=125)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = Field(..., ge=0, le=100)
    synthesis: str = Field(..., min_length=50, description="如何綜合各方意見")
    # 添加多週期分析支持
    multi_timeframe_analysis: Optional[MultiTimeframeData] = None


class RiskAssessment(BaseModel):
    """風險評估結構"""
    risk_level: Literal['低風險', '中低風險', '中風險', '中高風險', '高風險', '極高風險']
    assessment: str = Field(..., min_length=20)  # 從 50 改為 20
    warnings: List[str]
    suggested_adjustments: str
    approve: bool
    adjusted_position_size: float = Field(..., ge=0, le=1)
    # 添加多週期分析支持
    multi_timeframe_analysis: Optional[MultiTimeframeData] = None


class FinalApproval(BaseModel):
    approved: bool
    final_decision: str
    final_position_size: float
    approved_leverage: Optional[int] = Field(default=None, ge=1, le=125)
    execution_notes: str
    rationale: str  # ✅ 正確：是 rationale，不是 reasoning
    # 添加多週期分析支持
    multi_timeframe_analysis: Optional[MultiTimeframeData] = None


class DebateJudgment(BaseModel):
    """綜合交易委員會 (裁判) 的裁決結構"""
    bull_score: float = Field(..., ge=0, le=100, description="對多頭論點的公信力評分")
    bear_score: float = Field(..., ge=0, le=100, description="對空頭論點的公信力評分")
    neutral_score: float = Field(..., ge=0, le=100, description="對中立論點的公信力評分")
    judge_rationale: str = Field(..., min_length=100, description="裁決理由與各方表現評價")
    key_takeaway: str = Field(..., description="裁判總結的最核心市場事實")
    winning_stance: Literal['Bull', 'Bear', 'Neutral', 'Tie'] = Field(..., description="哪一方在辯論中更具說服力")