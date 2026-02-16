"""Task models for agent system"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class TaskType(Enum):
    """任務類型"""
    SIMPLE_PRICE = "simple_price"       # 簡單價格查詢
    ANALYSIS = "analysis"               # 完整分析
    DEEP_ANALYSIS = "deep_analysis"     # 深度分析（包含辯論）
    DISCUSSION = "discussion"           # 討論模式


@dataclass
class Task:
    """Agent 任務"""
    query: str                                    # 用戶查詢
    type: TaskType                                # 任務類型
    symbols: List[str] = field(default_factory=list)  # 相關幣種
    timeframe: str = "4h"                         # 時間框架
    analysis_depth: str = "normal"                # 分析深度: quick, normal, deep
    needs_backtest: bool = False                  # 是否需要回測
    context: dict = field(default_factory=dict)   # 額外上下文


class ParsedIntent(BaseModel):
    """LLM 解析後的用戶意圖"""
    symbols: List[str] = Field(
        default_factory=list,
        description="提取的交易符號，如 BTC, ETH, SOL（大寫）"
    )
    task_type: str = Field(
        default="analysis",
        description="任務類型: simple_price（簡單價格查詢）, analysis（一般分析）, deep_analysis（深度分析含辯論）"
    )
    depth: str = Field(
        default="normal",
        description="分析深度: quick（快速）, normal（正常）, deep（深度）"
    )
    needs_backtest: bool = Field(
        default=False,
        description="是否需要歷史回測數據"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="解析信心度 0-1"
    )
    reasoning: str = Field(
        default="",
        description="LLM 的簡短推理說明"
    )
