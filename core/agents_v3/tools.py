"""
Agent V3 工具定義

定義所有可供 Agent 使用的工具
"""
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class ToolResult:
    """工具執行結果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    工具基類

    所有工具必須繼承此類並實現 execute 方法
    """

    def __init__(self, name: str, description: str, domains: List[str]):
        self.name = name
        self.description = description
        self.domains = domains

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """執行工具"""
        pass

    def get_schema(self) -> dict:
        """返回工具的 schema（供 LLM 調用參考）"""
        return {
            "name": self.name,
            "description": self.description,
            "domains": self.domains
        }


class FunctionTool(BaseTool):
    """
    函數工具 - 將普通函數包裝為工具
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str,
        domains: List[str]
    ):
        super().__init__(name, description, domains)
        self.func = func

    def execute(self, **kwargs) -> ToolResult:
        """執行函數"""
        try:
            result = self.func(**kwargs)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ============================================
# 新聞工具
# ============================================

class GoogleNewsTool(BaseTool):
    """Google News RSS 工具"""

    def __init__(self):
        super().__init__(
            name="google_news",
            description="從 Google News RSS 獲取加密貨幣相關新聞，無需 API Key",
            domains=["news", "general"]
        )

    def execute(self, symbol: str = "BTC", limit: int = 5, **kwargs) -> ToolResult:
        """獲取新聞"""
        try:
            from utils.utils import get_crypto_news_google
            news = get_crypto_news_google(symbol=symbol, limit=limit)
            return ToolResult(
                success=True,
                data=news,
                metadata={"symbol": symbol, "count": len(news)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CryptoPanicTool(BaseTool):
    """CryptoPanic 新聞工具"""

    def __init__(self):
        super().__init__(
            name="cryptopanic",
            description="從 CryptoPanic 獲取專業加密貨幣新聞",
            domains=["news"]
        )

    def execute(self, symbols: List[str] = None, limit: int = 5, **kwargs) -> ToolResult:
        """獲取新聞"""
        try:
            from utils.utils import get_crypto_news_cryptopanic
            symbol = symbols[0] if symbols else "BTC"
            news = get_crypto_news_cryptopanic(symbol=symbol, limit=limit)
            return ToolResult(
                success=True,
                data=news,
                metadata={"symbol": symbol, "count": len(news)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MultiSourceNewsTool(BaseTool):
    """多來源新聞聚合工具"""

    def __init__(self):
        super().__init__(
            name="aggregate_news",
            description="從多個來源聚合加密貨幣新聞（Google, CryptoPanic, CryptoCompare）",
            domains=["news"]
        )

    def execute(self, symbol: str = "BTC", limit: int = 5, **kwargs) -> ToolResult:
        """聚合新聞"""
        try:
            from utils.utils import get_crypto_news
            news = get_crypto_news(symbol=symbol, limit=limit, enabled_sources=['google', 'cryptocompare'])
            return ToolResult(
                success=True,
                data=news,
                metadata={"symbol": symbol, "count": len(news)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ============================================
# 技術分析工具
# ============================================

class TechnicalAnalysisTool(BaseTool):
    """技術指標分析工具"""

    def __init__(self):
        super().__init__(
            name="technical_analysis",
            description="獲取加密貨幣的技術指標（RSI, MACD, 均線等）",
            domains=["technical"]
        )

    def execute(self, symbol: str = "BTC", interval: str = "1d", **kwargs) -> ToolResult:
        """獲取技術指標"""
        try:
            from core.tools.crypto_tools import technical_analysis_tool
            result = technical_analysis_tool.invoke({
                "symbol": symbol,
                "interval": interval
            })
            return ToolResult(
                success=True,
                data=result,
                metadata={"symbol": symbol, "interval": interval}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class PriceDataTool(BaseTool):
    """價格數據工具"""

    def __init__(self):
        super().__init__(
            name="price_data",
            description="獲取加密貨幣的即時價格和歷史數據",
            domains=["technical", "general"]
        )

    def execute(self, symbol: str = "BTC", **kwargs) -> ToolResult:
        """獲取價格"""
        try:
            # 使用現有的價格獲取邏輯
            from utils.utils import get_binance_klines
            klines = get_binance_klines(symbol=f"{symbol}USDT", interval="1d", limit=30)
            return ToolResult(
                success=True,
                data=klines,
                metadata={"symbol": symbol}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ============================================
# V1 工具包裝器（復用現有工具）
# ============================================

class CryptoPriceTool(BaseTool):
    """加密貨幣價格工具（包裝 V1）"""

    def __init__(self):
        super().__init__(
            name="get_crypto_price",
            description="獲取加密貨幣的即時價格（精確價格查詢）",
            domains=["technical", "general"]
        )

    def execute(self, symbol: str = "BTC", **kwargs) -> ToolResult:
        """獲取即時價格"""
        try:
            from core.tools.crypto_tools import get_crypto_price_tool
            result = get_crypto_price_tool.invoke({"symbol": symbol})
            return ToolResult(
                success=True,
                data={"price_info": result},
                metadata={"symbol": symbol}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MarketMovementTool(BaseTool):
    """市場動態解釋工具"""

    def __init__(self):
        super().__init__(
            name="explain_market_movement",
            description="解釋加密貨幣市場動態和價格變化原因",
            domains=["technical", "general"]
        )

    def execute(self, symbol: str = "BTC", **kwargs) -> ToolResult:
        """解釋市場動態"""
        try:
            from core.tools.crypto_tools import explain_market_movement_tool
            result = explain_market_movement_tool(symbol)
            return ToolResult(
                success=True,
                data={"explanation": result},
                metadata={"symbol": symbol}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BacktestTool(BaseTool):
    """回測策略工具"""

    def __init__(self):
        super().__init__(
            name="backtest_strategy",
            description="回測交易策略的歷史表現",
            domains=["technical"]
        )

    def execute(self, symbol: str = "BTC", strategy: str = "ma_cross", **kwargs) -> ToolResult:
        """執行回測"""
        try:
            from core.tools.crypto_tools import backtest_strategy_tool
            result = backtest_strategy_tool.invoke({
                "symbol": symbol,
                "strategy": strategy
            })
            return ToolResult(
                success=True,
                data={"backtest_result": result},
                metadata={"symbol": symbol, "strategy": strategy}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ============================================
# 通用工具
# ============================================

class WebSearchTool(BaseTool):
    """網路搜索工具"""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="在網路上搜索資訊",
            domains=["general"]
        )

    def execute(self, query: str, **kwargs) -> ToolResult:
        """執行搜索"""
        try:
            # 可以接入 Google Search API 或其他搜索服務
            # 目前返回模擬結果
            return ToolResult(
                success=True,
                data={"query": query, "results": []},
                metadata={"note": "需要接入實際搜索 API"}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class LLMTool(BaseTool):
    """LLM 調用工具（用於一般對話）"""

    def __init__(self, llm_client):
        super().__init__(
            name="llm_chat",
            description="使用 LLM 進行自然語言對話",
            domains=["general", "chat"]
        )
        self.llm_client = llm_client

    def execute(self, prompt: str, system_prompt: str = None, **kwargs) -> ToolResult:
        """執行 LLM 調用"""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = self.llm_client.invoke(messages)
            return ToolResult(
                success=True,
                data={"response": response.content},
                metadata={"prompt_length": len(prompt)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# ============================================
# 預設工具列表
# ============================================

def create_default_tools(llm_client=None) -> List[BaseTool]:
    """創建預設工具列表"""
    tools = [
        # 新聞工具
        GoogleNewsTool(),
        CryptoPanicTool(),
        MultiSourceNewsTool(),

        # 技術分析工具
        TechnicalAnalysisTool(),
        PriceDataTool(),

        # V1 工具包裝器
        CryptoPriceTool(),
        MarketMovementTool(),
        BacktestTool(),

        # 通用工具
        WebSearchTool(),
    ]

    # 如果有 LLM client，添加 LLM 工具
    if llm_client:
        tools.append(LLMTool(llm_client))

    return tools
