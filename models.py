from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Optional

# ============================================================================
# Agent 角色定義
# ============================================================================

class AnalystReport(BaseModel):
    """分析師報告結構"""
    analyst_type: str
    summary: str = Field(..., min_length=50)
    key_findings: List[str]
    bullish_points: List[str] = []
    bearish_points: List[str] = []
    confidence: float = Field(..., ge=0, le=100)


class ResearcherDebate(BaseModel):
    """研究員辯論結構"""
    researcher_stance: Literal['Bull', 'Bear']
    argument: str = Field(..., min_length=100)
    key_points: List[str]
    counter_arguments: List[str] = []
    confidence: float = Field(..., ge=0, le=100)


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


class RiskAssessment(BaseModel):
    """風險評估結構"""
    risk_level: Literal['低風險', '中低風險', '中風險', '中高風險', '高風險', '極高風險']
    assessment: str = Field(..., min_length=20)  # 從 50 改為 20
    warnings: List[str]
    suggested_adjustments: str
    approve: bool
    adjusted_position_size: float = Field(..., ge=0, le=1)


class FinalApproval(BaseModel):
    approved: bool
    final_decision: str
    final_position_size: float
    approved_leverage: Optional[int] = Field(default=None, ge=1, le=125)
    execution_notes: str
    rationale: str  # ✅ 正確：是 rationale，不是 reasoning