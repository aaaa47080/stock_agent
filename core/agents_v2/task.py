"""Task models for agent system"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List


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
