"""
工具輸入模型定義 (Pydantic Schema)
所有 LangChain 工具的輸入參數結構
"""

from typing import Optional
from pydantic import BaseModel, Field


class TechnicalAnalysisInput(BaseModel):
    """技術分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣交易對符號，如 'BTC', 'ETH', 'SOL', 'PI'。不需要加 'USDT' 後綴。"
    )
    interval: str = Field(
        default="1d",
        description="K線時間週期。選項: '1m', '5m', '15m', '1h', '4h', '1d', '1w'。預設為日線 '1d'。"
    )
    exchange: Optional[str] = Field(
        default=None,
        description="交易所名稱。選項: 'okx' (預設), 'binance'。"
    )


class NewsAnalysisInput(BaseModel):
    """新聞分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH', 'PI'。"
    )
    include_sentiment: bool = Field(
        default=True,
        description="是否包含情緒分析。預設為 True。"
    )


class PriceInput(BaseModel):
    """價格查詢工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH', 'SOL', 'PI'。"
    )
    exchange: Optional[str] = Field(
        default=None,
        description="交易所名稱。選項: 'okx' (預設), 'binance'。"
    )


class CurrentTimeInput(BaseModel):
    """當前時間查詢工具的輸入參數"""
    timezone: str = Field(
        default="Asia/Taipei",
        description="時區名稱，如 'Asia/Taipei', 'UTC', 'America/New_York'。預設為台北時間。"
    )


class MarketPulseInput(BaseModel):
    """市場脈動分析工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH', 'SOL'。"
    )


class BacktestStrategyInput(BaseModel):
    """回測策略工具的輸入參數"""
    symbol: str = Field(
        description="加密貨幣符號，如 'BTC', 'ETH'。"
    )
    interval: str = Field(
        default="1d",
        description="時間週期，如 '1d', '4h', '1h'。"
    )
    period: int = Field(
        default=90,
        description="回測天數，預設 90 天。"
    )


class ExtractCryptoSymbolsInput(BaseModel):
    """從用戶查詢中提取加密貨幣符號的工具輸入參數"""
    user_query: str = Field(
        description="用戶的查詢文本，可能包含一種或多種加密貨幣符號，如 'BTC今天值得買嗎？' 或 '分析ETH和SOL的走勢'"
    )
