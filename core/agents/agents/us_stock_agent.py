"""
Agent V4 — US Stock Agent (Full Implementation)

Multi-language US stock analysis with real-time data,
technicals, fundamentals, earnings, and news.

Supports:
- Real-time price data (15-min delayed via Yahoo Finance)
- Technical indicators (RSI, MACD, MA, Bollinger Bands)
- Fundamental analysis (P/E, EPS, ROE, etc.)
- Earnings data and calendar
- Latest news aggregation
- Institutional holdings
- Insider transactions

Languages: zh-TW, zh-CN, en
"""
import json
from langchain_core.messages import HumanMessage

from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class USStockAgent:
    """
    美股分析 Agent
    
    提供完整的美股分析功能，包括：
    - 即時價格
    - 技術指標
    - 基本面分析
    - 財報數據
    - 新聞聚合
    """
    
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "us_stock"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute US stock analysis."""
        language = (task.context or {}).get("language", "zh-TW")
        
        # 1. Extract ticker
        ticker = self._extract_ticker(task.description)
        if not ticker or ticker == "UNKNOWN":
            msg_map = {
                "zh-TW": "無法識別美股代號，請提供股票代號（如 AAPL）或公司名稱（如 Apple）。",
                "zh-CN": "无法识别美股代号，请提供股票代号（如 AAPL）或公司名称（如 Apple）。",
                "en": "Unable to recognize US stock ticker. Please provide stock symbol (e.g., AAPL) or company name (e.g., Apple).",
            }
            return AgentResult(
                success=False,
                message=msg_map.get(language, msg_map["zh-TW"]),
                agent_name=self.name,
                quality="fail",
            )

        company_name = self._get_company_name(ticker)

        # 2. Classify intent
        intent = self._classify_intent(task.description)

        # 3. Fetch data
        price_data = self._run_tool("us_stock_price", {"symbol": ticker}) if intent.get("price") else {}
        technical_data = self._run_tool("us_technical_analysis", {"symbol": ticker}) if intent.get("technical") else {}
        fundamentals_data = self._run_tool("us_fundamentals", {"symbol": ticker}) if intent.get("fundamentals") else {}
        earnings_data = self._run_tool("us_earnings", {"symbol": ticker}) if intent.get("earnings") else {}
        news_data = self._run_tool("us_news", {"symbol": ticker, "limit": 5}) if intent.get("news") else []
        institutional_data = self._run_tool("us_institutional_holders", {"symbol": ticker}) if intent.get("institutional") else {}

        # Check if all data fetching failed
        all_empty = not any([
            price_data and not price_data.get("error"),
            technical_data and not technical_data.get("error"),
            fundamentals_data and not fundamentals_data.get("error"),
            earnings_data and not earnings_data.get("error"),
            news_data,
        ])
        
        if all_empty:
            msg_map = {
                "zh-TW": f"無法獲取 {ticker} 的資料，請稍後再試。",
                "zh-CN": f"无法获取 {ticker} 的资料，请稍后再试。",
                "en": f"Unable to fetch data for {ticker}. Please try again later.",
            }
            return AgentResult(
                success=False,
                message=msg_map.get(language, msg_map["zh-TW"]),
                agent_name=self.name,
                quality="fail",
            )

        # 4. Format data for prompt
        def fmt(d):
            if not d:
                return "(Not fetched)" if language == "en" else "（未抓取）"
            if isinstance(d, dict) and d.get("error"):
                error_msg = d.get("error", "Unknown error")
                return f"(Error: {error_msg})" if language == "en" else f"（錯誤：{error_msg}）"
            if isinstance(d, list):
                if not d:
                    return "(No data)" if language == "en" else "（無資料）"
                return "\n".join(
                    f"- [{item.get('title','')} ({item.get('source','')})]({item.get('url','')})"
                    for item in d[:5]
                )
            return json.dumps(d, ensure_ascii=False, indent=2, default=str)

        # 5. Render prompt with multi-language support
        prompt = PromptRegistry.render(
            "us_stock_agent", "analysis", language,
            ticker=ticker,
            company_name=company_name,
            query=task.description,
            price_data=fmt(price_data) if price_data and not price_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            technical_data=fmt(technical_data) if technical_data and not technical_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            fundamentals_data=fmt(fundamentals_data) if fundamentals_data and not fundamentals_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            earnings_data=fmt(earnings_data) if earnings_data and not earnings_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
            news_data=fmt(news_data),
            institutional_data=fmt(institutional_data) if institutional_data and not institutional_data.get("error") else "(Data error)" if language == "en" else "（數據錯誤）",
        )

        # 6. Generate response
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            # Multi-language prefix
            prefix_map = {
                "zh-TW": f"🇺🇸 **{company_name or ticker} 美股分析**",
                "zh-CN": f"🇺🇸 **{company_name or ticker} 美股分析**",
                "en": f"🇺🇸 **{company_name or ticker} US Stock Analysis**",
            }
            prefix = prefix_map.get(language, prefix_map["zh-TW"])
            
            # Add disclaimer about delayed data
            disclaimer_map = {
                "zh-TW": "\n\n> ⚠️ 註：價格數據延遲 15 分鐘",
                "zh-CN": "\n\n> ⚠️ 注：价格数据延迟 15 分钟",
                "en": "\n\n> ⚠️ Note: Price data is delayed by 15 minutes",
            }
            disclaimer = disclaimer_map.get(language, disclaimer_map["zh-TW"])
            
            analysis_text = f"{prefix}\n\n{response.content}{disclaimer}"
        except Exception as e:
            analysis_text = f"Analysis generation failed: {e}" if language == "en" else f"分析生成失敗：{e}"

        return AgentResult(
            success=True,
            message=analysis_text,
            agent_name=self.name,
            data={"ticker": ticker, "company_name": company_name},
            quality="pass",
        )

    def _extract_ticker(self, description: str) -> str:
        """
        Extract US stock ticker from description.
        
        Strategy:
        1. Try direct match for uppercase letters (e.g., AAPL, TSLA)
        2. Try company name lookup (case-insensitive, longer names first)
        3. Return UNKNOWN if not found
        """
        import re
        
        # Try direct match for uppercase letters (2-5 chars)
        match = re.search(r'\b([A-Z]{2,5})\b', description)
        if match:
            candidate = match.group(1)
            # Filter out common words
            stopwords = {
                "A", "I", "IS", "IN", "OF", "THE", "AND", "OR", "FOR", 
                "BTC", "ETH", "SOL", "ADA", "DOT", "PI", "USD", "EUR",
                "RSI", "MACD", "MA", "KD", "PE", "EPS", "ROE", "CEO", "CFO",
            }
            if candidate not in stopwords:
                return candidate
        
        # Try company name lookup (case-insensitive)
        company_names = {
            "APPLE": "AAPL",
            "MICROSOFT": "MSFT",
            "GOOGLE": "GOOGL",
            "ALPHABET": "GOOGL",
            "AMAZON": "AMZN",
            "TESLA": "TSLA",
            "META": "META",
            "FACEBOOK": "META",
            "NVIDIA": "NVDA",
            "NETFLIX": "NFLX",
            "INTEL": "INTC",
            "AMD": "AMD",
            "ADVANCED MICRO DEVICES": "AMD",
            "JPMORGAN": "JPM",
            "JPMORGAN CHASE": "JPM",
            "BANK OF AMERICA": "BAC",
            "WALMART": "WMT",
            "EXXON": "XOM",
            "EXXON MOBIL": "XOM",
            "JOHNSON & JOHNSON": "JNJ",
            "J&J": "JNJ",
            "VISA": "V",
            "PROCTER & GAMBLE": "PG",
            "P&G": "PG",
            "BERKSHIRE HATHAWAY": "BRK",
            "UNITEDHEALTH": "UNH",
            "HOME DEPOT": "HD",
            "MASTERCARD": "MA",
            "CHEVRON": "CVX",
            "COCA COLA": "KO",
            "COCA-COLA": "KO",
            "PEPSI": "PEP",
            "PEPSICO": "PEP",
            "ABBVIE": "ABBV",
            "PFIZER": "PFE",
            "MERCK": "MRK",
            "DISNEY": "DIS",
            "WALT DISNEY": "DIS",
            "CISCO": "CSCO",
            "VERIZON": "VZ",
            "COMCAST": "CMCSA",
            "ADOBE": "ADBE",
            "SALESFORCE": "CRM",
            "ORACLE": "ORCL",
            "IBM": "IBM",
            "BOEING": "BA",
            "GOLDMAN SACHS": "GS",
            "MORGAN STANLEY": "MS",
            "AMERICAN EXPRESS": "AXP",
            "AMEX": "AXP",
            "MCDONALD": "MCD",
            "MCDONALD'S": "MCD",
            "NIKE": "NKE",
            "STARBUCKS": "SBUX",
            "COSTCO": "COST",
            "TARGET": "TGT",
        }
        
        desc_upper = description.upper()
        # Sort by length (longer names first) to avoid partial matches
        for name in sorted(company_names.keys(), key=len, reverse=True):
            if name in desc_upper:
                return company_names[name]
        
        return "UNKNOWN"

    def _get_company_name(self, ticker: str) -> str:
        """Lookup company name from ticker."""
        company_map = {
            "AAPL": "Apple Inc.",
            "MSFT": "Microsoft Corporation",
            "GOOGL": "Alphabet Inc. Class A",
            "GOOG": "Alphabet Inc. Class C",
            "AMZN": "Amazon.com Inc.",
            "TSLA": "Tesla Inc.",
            "META": "Meta Platforms Inc.",
            "NVDA": "NVIDIA Corporation",
            "NFLX": "Netflix Inc.",
            "INTC": "Intel Corporation",
            "AMD": "Advanced Micro Devices Inc.",
            "JPM": "JPMorgan Chase & Co.",
            "BAC": "Bank of America Corporation",
            "WMT": "Walmart Inc.",
            "XOM": "Exxon Mobil Corporation",
            "JNJ": "Johnson & Johnson",
            "V": "Visa Inc.",
            "PG": "Procter & Gamble Co.",
            "BRK": "Berkshire Hathaway Inc.",
            "UNH": "UnitedHealth Group Inc.",
            "HD": "Home Depot Inc.",
            "MA": "Mastercard Inc.",
            "CVX": "Chevron Corporation",
            "KO": "Coca-Cola Company",
            "PEP": "PepsiCo Inc.",
            "ABBV": "AbbVie Inc.",
            "PFE": "Pfizer Inc.",
            "MRK": "Merck & Co. Inc.",
            "DIS": "Walt Disney Company",
            "CSCO": "Cisco Systems Inc.",
            "VZ": "Verizon Communications Inc.",
            "CMCSA": "Comcast Corporation",
            "ADBE": "Adobe Inc.",
            "CRM": "Salesforce Inc.",
            "ORCL": "Oracle Corporation",
            "IBM": "International Business Machines",
            "BA": "Boeing Company",
            "GS": "Goldman Sachs Group Inc.",
            "MS": "Morgan Stanley",
            "AXP": "American Express Company",
            "MCD": "McDonald's Corporation",
            "NKE": "Nike Inc.",
            "SBUX": "Starbucks Corporation",
            "COST": "Costco Wholesale Corporation",
            "TGT": "Target Corporation",
        }
        return company_map.get(ticker, "")

    def _classify_intent(self, query: str) -> dict:
        """
        Determine which data categories are relevant to the query.
        
        Keywords for each category:
        - technical: RSI, MACD, MA, trend, chart, 技術，技术
        - fundamental: PE, EPS, revenue, 基本面，估值，financial
        - earnings: earning, 财报，財報，EPS, revenue
        - news: news, 消息，新闻，動態，动态
        - price: price, 價格，价格，quote, 股價，股价
        - institutional: institutional, 機構，机构，holding, 持倉
        """
        q = query.lower()
        
        tech_kw = [
            "technical", "rsi", "macd", "ma", "trend", "chart", 
            "技術", "技术", "指標", "指标", "均線", "均线", "kd", "bollinger"
        ]
        fund_kw = [
            "fundamental", "pe", "eps", "revenue", "基本面", "估值",
            "financial", "profit", "margin", "roe", "roa", "debt",
            "價值", "价值", "評估", "评估"
        ]
        earn_kw = ["earning", "财报", "財報", "eps", "revenue", "quarterly", "quarter"]
        news_kw = ["news", "消息", "新闻", "動態", "动态", "latest", "recent"]
        price_kw = ["price", "價格", "价格", "quote", "股價", "股价", "current", "now"]
        inst_kw = ["institutional", "機構", "机构", "holding", "持倉", "持仓", "fund"]
        
        has_tech = any(k in q for k in tech_kw)
        has_fund = any(k in q for k in fund_kw)
        has_earn = any(k in q for k in earn_kw)
        has_news = any(k in q for k in news_kw)
        has_price = any(k in q for k in price_kw)
        has_inst = any(k in q for k in inst_kw)
        
        # Default: fetch price + technical + news (most common use case)
        if not any([has_tech, has_fund, has_earn, has_news, has_price, has_inst]):
            return {
                "price": True,
                "technical": True,
                "fundamentals": False,
                "earnings": False,
                "news": True,
                "institutional": False,
            }
        
        return {
            "price": has_price or has_tech,  # Always need price for technical analysis
            "technical": has_tech,
            "fundamentals": has_fund,
            "earnings": has_earn,
            "news": has_news,
            "institutional": has_inst,
        }

    def _run_tool(self, tool_name: str, args: dict):
        """
        Run a registered tool.
        
        Args:
            tool_name: Name of the tool to run
            args: Arguments to pass to the tool
        
        Returns:
            Tool result or None if failed
        """
        tool = self.tool_registry.get(tool_name, caller_agent=self.name)
        if not tool:
            return None
        try:
            return tool.handler.invoke(args)
        except Exception as e:
            # Return error info for debugging
            return {"error": str(e)}
