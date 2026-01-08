from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Optional

# ============================================================================
# Admin Agent 任務分析模型
# ============================================================================

class TaskAnalysis(BaseModel):
    """任務分析結果 - Admin Agent 使用"""
    is_complex: bool = Field(..., description="是否為複雜任務")
    complexity_reason: str = Field(default="", description="複雜度判斷原因")
    assigned_agent: str = Field(..., description="指派的 Agent ID")
    symbols: List[str] = Field(default_factory=list, description="提取的加密貨幣符號")
    confidence: float = Field(default=0.8, ge=0, le=1, description="分析置信度")
    original_question: str = Field(default="", description="用戶原始問題")


class SubTask(BaseModel):
    """子任務定義 - Planning Manager 使用"""
    id: str = Field(..., description="子任務唯一 ID")
    description: str = Field(..., description="任務描述")
    assigned_agent: str = Field(..., description="指派的 Agent ID")
    tools_hint: List[str] = Field(default_factory=list, description="建議使用的工具")
    dependencies: List[str] = Field(default_factory=list, description="依賴的其他子任務 ID")
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending", description="任務狀態"
    )
    result: Optional[str] = Field(default=None, description="任務執行結果")
    symbol: Optional[str] = Field(default=None, description="相關的加密貨幣符號")
    priority: int = Field(default=5, description="執行優先級（數字越小越優先）")


class TaskPlan(BaseModel):
    """任務規劃結果 - Planning Manager 使用"""
    original_question: str = Field(..., description="原始用戶問題")
    is_complex: bool = Field(default=False, description="是否為複雜任務")
    complexity_reason: str = Field(default="", description="複雜度判斷原因")
    subtasks: List[SubTask] = Field(default_factory=list, description="子任務列表")
    execution_strategy: Literal["parallel", "sequential", "mixed", "direct"] = Field(
        default="parallel", description="執行策略"
    )
    estimated_steps: int = Field(default=1, description="預估步驟數")


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
    """交易員決策結構 - 基於裁判裁決而非主觀信心"""
    decision: Literal['Buy', 'Sell', 'Hold', 'Long', 'Short']
    reasoning: str = Field(..., min_length=20, description="為什麼做出此決策（必須引用裁判的裁決）")
    position_size: float = Field(..., ge=0, le=1, description="倉位大小，基於裁判建議行動強度")
    leverage: Optional[int] = Field(None, ge=1, le=125)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    # 移除 confidence，改為遵循裁判的 suggested_action
    follows_judge: bool = Field(..., description="是否遵循裁判建議")
    deviation_reason: Optional[str] = Field(None, description="如果不遵循裁判，說明原因")
    key_risk: str = Field(..., description="此交易的主要風險點")
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
    """綜合交易委員會 (裁判) 的裁決結構 - 基於論點品質而非數字評分"""

    # 各方論點評估（文字描述，非數字）
    bull_evaluation: str = Field(..., min_length=10, description="多頭論點的優缺點評估")
    bear_evaluation: str = Field(..., min_length=10, description="空頭論點的優缺點評估")
    neutral_evaluation: str = Field(..., min_length=10, description="中立論點的優缺點評估")

    # 關鍵論點對決
    strongest_bull_point: str = Field(..., description="多頭最有力的論點")
    strongest_bear_point: str = Field(..., description="空頭最有力的論點")
    fatal_flaw: Optional[str] = Field(None, description="某方論點的致命缺陷（如有）")

    # 裁決結果
    winning_stance: Literal['Bull', 'Bear', 'Neutral', 'Tie'] = Field(..., description="勝出方")
    winning_reason: str = Field(..., min_length=10, description="為什麼這一方獲勝（具體引用其論點）")

    # 交易建議
    suggested_action: Literal['強烈做多', '適度做多', '觀望', '適度做空', '強烈做空'] = Field(..., description="基於辯論結果的建議行動")
    action_rationale: str = Field(..., description="建議行動的依據")
    key_takeaway: str = Field(..., description="裁判總結的最核心市場事實")