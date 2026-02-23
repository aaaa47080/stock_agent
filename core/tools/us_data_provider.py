"""
US Stock Data Provider - Yahoo Finance Implementation

Provides comprehensive US stock data using Yahoo Finance as the primary data source.
Includes caching mechanism to reduce API calls and improve response time.

Data Sources:
- Primary: Yahoo Finance (yfinance) - Free, comprehensive data
- Future: Alpha Vantage, Finnhub (backup sources)

Features:
- Real-time price data (15-min delayed)
- Technical indicators (calculated from historical data)
- Fundamentals (P/E, EPS, ROE, etc.)
- Earnings data and calendar
- News aggregation
- Institutional holdings
- Insider transactions
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np


# ============ 數據源介面 ============

class StockDataProvider(ABC):
    """數據提供者抽象介面"""
    
    @abstractmethod
    async def get_price(self, symbol: str) -> Dict:
        """獲取價格數據"""
        pass
    
    @abstractmethod
    async def get_technicals(self, symbol: str) -> Dict:
        """獲取技術指標"""
        pass
    
    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> Dict:
        """獲取基本面數據"""
        pass
    
    @abstractmethod
    async def get_news(self, symbol: str, limit: int = 5) -> List[Dict]:
        """獲取新聞"""
        pass
    
    @abstractmethod
    async def get_earnings(self, symbol: str) -> Dict:
        """獲取財報數據"""
        pass


# ============ Yahoo Finance 實現 ============

class YahooFinanceProvider(StockDataProvider):
    """
    Yahoo Finance 數據提供者（主要數據源）
    
    快取策略：
    - 價格數據：60 秒（避免短時間重複請求）
    - 技術指標：5 分鐘（計算耗時）
    - 基本面數據：1 小時（變動少）
    - 新聞數據：5 分鐘（時效性高）
    - 財報數據：24 小時（季報更新）
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_duration = {
            "price": 60,        # 60 秒
            "technicals": 300,  # 5 分鐘
            "fundamentals": 3600,  # 1 小時
            "news": 300,        # 5 分鐘
            "earnings": 86400,  # 24 小時
            "institutional": 86400,  # 24 小時
            "insider": 86400,   # 24 小時
        }
    
    async def get_price(self, symbol: str) -> Dict:
        """
        獲取價格數據（含快取）
        
        Args:
            symbol: 股票代號（如 AAPL, TSLA）
        
        Returns:
            價格數據字典
        """
        cache_key = f"yahoo_price_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 檢查是否有有效數據
            if not info or info.get("currentPrice") is None:
                raise ValueError(f"無法獲取 {symbol} 的價格數據")
            
            last_price = info.get("currentPrice", 0)
            prev_close = info.get("previousClose", 0)
            
            data = {
                "symbol": symbol,
                "price": last_price,
                "change": last_price - prev_close if prev_close else 0,
                "change_percent": ((last_price - prev_close) / prev_close * 100) if prev_close else 0,
                "previous_close": prev_close,
                "open": info.get("open", 0),
                "day_high": info.get("dayHigh", 0),
                "day_low": info.get("dayLow", 0),
                "volume": info.get("volume", 0),
                "avg_volume": info.get("averageVolume", 0),
                "market_cap": info.get("marketCap", 0),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
                "bid": info.get("bid", 0),
                "ask": info.get("ask", 0),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", "US"),
                "quote_type": info.get("quoteType", "EQUITY"),
                "timestamp": datetime.now().isoformat(),
                "delayed": True,  # Yahoo 延遲 15 分鐘
                "market_state": "REGULAR",
            }
            
            # 添加漲跌狀態
            if data["change"] > 0:
                data["market_state"] = "UP"
            elif data["change"] < 0:
                data["market_state"] = "DOWN"
            
            self._set_cache(cache_key, data, "price")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 價格獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_technicals(self, symbol: str) -> Dict:
        """
        獲取技術指標（自行計算）
        
        計算指標：
        - RSI (14 日相對強弱指標)
        - MACD (移動平均收斂發散)
        - MA (20/50/200 日移動平均)
        - 布林帶
        - 成交量均線
        
        Args:
            symbol: 股票代號
        
        Returns:
            技術指標字典
        """
        cache_key = f"yahoo_tech_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            # 獲取 6 個月歷史數據以計算 200 日均線
            df = ticker.history(period="6mo")
            
            if len(df) < 200:
                # 數據不足，使用可用數據計算
                df = ticker.history(period="3mo")
            
            data = self._calculate_technicals(df)
            data["symbol"] = symbol
            data["data_points"] = len(df)
            
            self._set_cache(cache_key, data, "technicals")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 技術指標計算失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_fundamentals(self, symbol: str) -> Dict:
        """
        獲取基本面數據
        
        包含：
        - 估值指標（P/E, P/B, PEG）
        - 獲利能力（ROE, ROA, 利潤率）
        - 財務健康（負債比，流動比）
        - 成長指標（營收成長，獲利成長）
        - 分析師評級和目標價
        
        Args:
            symbol: 股票代號
        
        Returns:
            基本面數據字典
        """
        cache_key = f"yahoo_fund_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info:
                raise ValueError(f"無法獲取 {symbol} 的基本面數據")
            
            data = {
                # 估值指標
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "enterprise_value": info.get("enterpriseValue"),
                "ev_to_revenue": info.get("enterpriseToRevenue"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),
                
                # 每股數據
                "eps": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "book_value": info.get("bookValue"),
                "revenue_per_share": info.get("revenuePerShare"),
                "cash_per_share": info.get("totalCashPerShare"),
                
                # 股息數據
                "dividend_yield": info.get("dividendYield"),
                "dividend_rate": info.get("dividendRate"),
                "payout_ratio": info.get("payoutRatio"),
                "ex_dividend_date": info.get("exDividendDate"),
                
                # 風險指標
                "beta": info.get("beta"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                
                # 獲利能力
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "gross_margin": info.get("grossMargins"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "roic": info.get("returnOnInvestedCapital"),
                
                # 財務健康
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "total_debt": info.get("totalDebt"),
                "total_cash": info.get("totalCash"),
                
                # 現金流
                "free_cashflow": info.get("freeCashflow"),
                "operating_cashflow": info.get("operatingCashflow"),
                
                # 成長指標
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
                
                # 分析師評級
                "analyst_target_price": info.get("targetHighPrice"),
                "analyst_target_low": info.get("targetLowPrice"),
                "analyst_target_mean": info.get("targetMeanPrice"),
                "analyst_recommendation": info.get("recommendationKey"),
                "analyst_num_ratings": info.get("numberOfAnalystOpinions"),
                
                # 公司資訊
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "employees": info.get("fullTimeEmployees"),
                "website": info.get("website"),
                "description": info.get("longBusinessSummary"),
                
                # 交易資訊
                "shares_outstanding": info.get("sharesOutstanding"),
                "float_shares": info.get("floatShares"),
                "shares_short": info.get("sharesShort"),
                "short_ratio": info.get("shortRatio"),
                "short_percent_of_float": info.get("shortPercentOfFloat"),
            }
            
            # 清理 None 值
            data = {k: v for k, v in data.items() if v is not None and v != 'N/A'}
            
            self._set_cache(cache_key, data, "fundamentals")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 基本面數據獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_news(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        獲取新聞
        
        Args:
            symbol: 股票代號
            limit: 新聞數量上限
        
        Returns:
            新聞列表
        """
        cache_key = f"yahoo_news_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news or []
            
            data = []
            for item in news[:limit]:
                news_item = {
                    "title": item.get("title", "無標題"),
                    "url": item.get("link", ""),
                    "source": item.get("publisher", "未知來源"),
                    "published_at": item.get("providerPublishTime"),
                    "published_at_str": datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime("%Y-%m-%d %H:%M") if item.get("providerPublishTime") else None,
                    "thumbnail": None,
                }
                
                # 獲取縮圖
                thumbnail = item.get("thumbnail", {})
                if thumbnail and isinstance(thumbnail, dict):
                    resolutions = thumbnail.get("resolutions", [])
                    if resolutions and len(resolutions) > 0:
                        news_item["thumbnail"] = resolutions[0].get("url")
                
                data.append(news_item)
            
            self._set_cache(cache_key, data, "news")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 新聞獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_earnings(self, symbol: str) -> Dict:
        """
        獲取財報數據
        
        包含：
        - 下次財報日期
        - 財報歷史
        - EPS 預估值和實際值
        
        Args:
            symbol: 股票代號
        
        Returns:
            財報數據字典
        """
        cache_key = f"yahoo_earnings_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            
            # 財報日曆
            earnings_calendar = ticker.earnings_dates
            earnings_history = ticker.get_earnings_dates() if hasattr(ticker, 'get_earnings_dates') else None
            
            data = {
                "symbol": symbol,
                "next_earnings_date": None,
                "next_earnings_date_str": None,
                "earnings_history": [],
            }
            
            # 處理下次財報日期
            if earnings_calendar is not None and len(earnings_calendar) > 0:
                try:
                    next_date = earnings_calendar.index[0]
                    data["next_earnings_date"] = next_date.strftime("%Y-%m-%d") if hasattr(next_date, "strftime") else str(next_date)
                    data["next_earnings_date_str"] = next_date.strftime("%Y 年 %m 月 %d 日") if hasattr(next_date, "strftime") else str(next_date)
                except:
                    pass
            
            # 處理財報歷史
            if earnings_history is not None:
                try:
                    for _, row in earnings_history.head(4).iterrows():
                        history_item = {
                            "date": row.get("Earnings Date", "").strftime("%Y-%m-%d") if hasattr(row.get("Earnings Date", ""), "strftime") else str(row.get("Earnings Date", "")),
                            "eps_estimate": row.get("EPS Estimate"),
                            "eps_actual": row.get("Reported EPS"),
                            "surprise": row.get("Surprise(%)"),
                        }
                        
                        # 計算驚喜百分比
                        if history_item["eps_estimate"] and history_item["eps_actual"]:
                            try:
                                surprise_pct = ((history_item["eps_actual"] - history_item["eps_estimate"]) / history_item["eps_estimate"]) * 100
                                history_item["surprise_percent"] = round(surprise_pct, 2)
                            except:
                                history_item["surprise_percent"] = None
                        
                        data["earnings_history"].append(history_item)
                except:
                    pass
            
            self._set_cache(cache_key, data, "earnings")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 財報數據獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_institutional_holders(self, symbol: str) -> Dict:
        """
        獲取機構持倉數據
        
        Args:
            symbol: 股票代號
        
        Returns:
            機構持倉字典
        """
        cache_key = f"yahoo_inst_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            institutional = ticker.institutional_holders
            
            data = {
                "symbol": symbol,
                "holders": [],
                "total_shares_held": 0,
                "percent_held": 0,
            }
            
            if institutional is not None and len(institutional) > 0:
                try:
                    for _, row in institutional.iterrows():
                        holder = {
                            "holder": row.get("Holder", ""),
                            "shares": row.get("Shares", 0),
                            "date_reported": row.get("Date Reported", "").strftime("%Y-%m-%d") if hasattr(row.get("Date Reported", ""), "strftime") else str(row.get("Date Reported", "")),
                            "percent_out": row.get("% Out", 0),
                            "value": row.get("Value", 0),
                        }
                        data["holders"].append(holder)
                        data["total_shares_held"] += holder["shares"] if holder["shares"] else 0
                    
                    # 計算總持股比例
                    info = ticker.info
                    shares_outstanding = info.get("sharesOutstanding", 0)
                    if shares_outstanding:
                        data["percent_held"] = round((data["total_shares_held"] / shares_outstanding) * 100, 2)
                except:
                    pass
            
            self._set_cache(cache_key, data, "institutional")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 機構持倉數據獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    async def get_insider_transactions(self, symbol: str) -> Dict:
        """
        獲取內部人交易數據
        
        Args:
            symbol: 股票代號
        
        Returns:
            內部人交易字典
        """
        cache_key = f"yahoo_insider_{symbol}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            ticker = yf.Ticker(symbol)
            insider = ticker.insider_transactions
            
            data = {
                "symbol": symbol,
                "transactions": [],
            }
            
            if insider is not None and len(insider) > 0:
                try:
                    for _, row in insider.head(10).iterrows():
                        transaction = {
                            "insider": row.get("Insider", ""),
                            "relation": row.get("Relation", ""),
                            "date": row.get("Latest Trans Date", "").strftime("%Y-%m-%d") if hasattr(row.get("Latest Trans Date", ""), "strftime") else str(row.get("Latest Trans Date", "")),
                            "transaction_type": row.get("Transaction", ""),
                            "shares": row.get("Shares", 0),
                            "value": row.get("Value", 0),
                            "shares_total": row.get("Shares Total", 0),
                        }
                        data["transactions"].append(transaction)
                except:
                    pass
            
            self._set_cache(cache_key, data, "insider")
            return data
            
        except Exception as e:
            error_msg = f"Yahoo Finance 內部人交易數據獲取失敗 ({symbol}): {str(e)}"
            raise Exception(error_msg) from e
    
    def _calculate_technicals(self, df: pd.DataFrame) -> Dict:
        """
        計算技術指標
        
        使用指標：
        - RSI (14 日相對強弱指標)
        - MACD (12/26/9)
        - 移動平均 (20/50/200 日)
        - 布林帶 (20 日，2 標準差)
        - 成交量均線 (20 日)
        
        Args:
            df: 歷史價格數據（包含 Close, Volume）
        
        Returns:
            技術指標字典
        """
        if len(df) < 50:
            return {
                "error": "數據不足",
                "data_points": len(df),
                "min_required": 50,
            }
        
        # 收盤價和成交量
        close = df["Close"]
        volume = df["Volume"]
        
        # ============ RSI (14 日) ============
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # ============ MACD ============
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        
        # ============ 移動平均 ============
        ma20 = close.rolling(window=20).mean()
        ma50 = close.rolling(window=50).mean()
        ma200 = close.rolling(window=200).mean() if len(df) >= 200 else pd.Series([np.nan] * len(df))
        
        # ============ 布林帶 ============
        std20 = close.rolling(window=20).std()
        bb_upper = ma20 + (std20 * 2)
        bb_middle = ma20
        bb_lower = ma20 - (std20 * 2)
        
        # ============ 成交量均線 ============
        vol_ma20 = volume.rolling(window=20).mean()
        
        # ============ 當前值 ============
        current_price = close.iloc[-1]
        current_volume = volume.iloc[-1]
        
        # ============ 綜合訊號分析 ============
        signals = []
        bullish_count = 0
        bearish_count = 0
        
        # RSI 訊號
        rsi_current = rsi.iloc[-1]
        rsi_signal = "neutral"
        if rsi_current > 70:
            signals.append("RSI 超買")
            bearish_count += 1
            rsi_signal = "overbought"
        elif rsi_current < 30:
            signals.append("RSI 超賣")
            bullish_count += 1
            rsi_signal = "oversold"
        else:
            signals.append("RSI 中性")
        
        # MACD 訊號
        macd_current = macd.iloc[-1]
        signal_current = signal.iloc[-1]
        macd_signal = "neutral"
        if macd_current > signal_current:
            signals.append("MACD 多頭")
            bullish_count += 1
            macd_signal = "bullish"
        else:
            signals.append("MACD 空頭")
            bearish_count += 1
            macd_signal = "bearish"
        
        # 均線訊號
        ma_signal = "neutral"
        if current_price > ma200.iloc[-1]:
            signals.append("價格在 200 日均線上")
            bullish_count += 1
            ma_signal = "bullish"
        else:
            signals.append("價格在 200 日均線下")
            bearish_count += 1
            ma_signal = "bearish"
        
        # 布林帶訊號
        bb_signal = "neutral"
        if current_price > bb_upper.iloc[-1]:
            signals.append("價格突破布林帶上軌")
            bearish_count += 1  # 可能回調
            bb_signal = "overbought"
        elif current_price < bb_lower.iloc[-1]:
            signals.append("價格跌破布林帶下軌")
            bullish_count += 1  # 可能反彈
            bb_signal = "oversold"
        
        # 成交量訊號
        vol_signal = "normal"
        if current_volume > vol_ma20.iloc[-1] * 1.5:
            signals.append("成交量放大 (>150%)")
            vol_signal = "high"
        elif current_volume < vol_ma20.iloc[-1] * 0.5:
            signals.append("成交量萎縮 (<50%)")
            vol_signal = "low"
        
        # 綜合判斷
        if bullish_count > bearish_count:
            summary = "多頭"
            summary_en = "Bullish"
        elif bearish_count > bullish_count:
            summary = "空頭"
            summary_en = "Bearish"
        else:
            summary = "中性"
            summary_en = "Neutral"
        
        return {
            # RSI
            "rsi": round(float(rsi_current), 2) if not pd.isna(rsi_current) else None,
            "rsi_signal": rsi_signal,
            
            # MACD
            "macd": round(float(macd_current), 4) if not pd.isna(macd_current) else None,
            "macd_signal": round(float(signal_current), 4) if not pd.isna(signal_current) else None,
            "macd_histogram": round(float(histogram.iloc[-1]), 4) if not pd.isna(histogram.iloc[-1]) else None,
            "macd_trend": macd_signal,
            
            # 移動平均
            "ma_20": round(float(ma20.iloc[-1]), 2) if not pd.isna(ma20.iloc[-1]) else None,
            "ma_50": round(float(ma50.iloc[-1]), 2) if not pd.isna(ma50.iloc[-1]) else None,
            "ma_200": round(float(ma200.iloc[-1]), 2) if len(ma200) >= 200 and not pd.isna(ma200.iloc[-1]) else None,
            "ma_signal": ma_signal,
            
            # 布林帶
            "bb_upper": round(float(bb_upper.iloc[-1]), 2) if not pd.isna(bb_upper.iloc[-1]) else None,
            "bb_middle": round(float(bb_middle.iloc[-1]), 2) if not pd.isna(bb_middle.iloc[-1]) else None,
            "bb_lower": round(float(bb_lower.iloc[-1]), 2) if not pd.isna(bb_lower.iloc[-1]) else None,
            "bb_signal": bb_signal,
            
            # 成交量
            "volume": int(current_volume) if not pd.isna(current_volume) else None,
            "vol_ma20": round(float(vol_ma20.iloc[-1]), 0) if not pd.isna(vol_ma20.iloc[-1]) else None,
            "vol_signal": vol_signal,
            
            # 綜合
            "current_price": round(float(current_price), 2),
            "signals": signals,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "summary": summary,
            "summary_en": summary_en,
        }
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """檢查快取是否有效"""
        if cache_key not in self.cache:
            return False
        
        cache_entry = self.cache[cache_key]
        now = datetime.now()
        age = (now - cache_entry["timestamp"]).total_seconds()
        
        return age < cache_entry["duration"]
    
    def _set_cache(self, cache_key: str, data: any, data_type: str):
        """設置快取"""
        self.cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now(),
            "duration": self.cache_duration.get(data_type, 300),
        }
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除快取
        
        Args:
            symbol: 指定股票代號，若為 None 則清除所有快取
        """
        if symbol:
            # 清除特定股票的所有快取
            keys_to_remove = [k for k in self.cache.keys() if symbol in k]
            for key in keys_to_remove:
                del self.cache[key]
        else:
            # 清除所有快取
            self.cache.clear()


# ============ 統一數據提供者 ============

class USDataProvider:
    """
    美股數據提供者（統一介面）
    
    使用 Yahoo Finance 作為主要數據源，
    未來可擴展添加備用數據源。
    """
    
    def __init__(self):
        self.yahoo = YahooFinanceProvider()
        # 未來可以添加其他數據源
        # self.alpha_vantage = AlphaVantageProvider()
        # self.finnhub = FinnhubProvider()
    
    async def get_price(self, symbol: str) -> Dict:
        """獲取價格（自動選擇最佳數據源）"""
        try:
            return await self.yahoo.get_price(symbol)
        except Exception as e:
            # 未來可以切換到其他數據源
            raise e
    
    async def get_technicals(self, symbol: str) -> Dict:
        """獲取技術指標"""
        try:
            return await self.yahoo.get_technicals(symbol)
        except Exception as e:
            raise e
    
    async def get_fundamentals(self, symbol: str) -> Dict:
        """獲取基本面數據"""
        try:
            return await self.yahoo.get_fundamentals(symbol)
        except Exception as e:
            raise e
    
    async def get_news(self, symbol: str, limit: int = 5) -> List[Dict]:
        """獲取新聞"""
        try:
            return await self.yahoo.get_news(symbol, limit)
        except Exception as e:
            raise e
    
    async def get_earnings(self, symbol: str) -> Dict:
        """獲取財報數據"""
        try:
            return await self.yahoo.get_earnings(symbol)
        except Exception as e:
            raise e
    
    async def get_institutional_holders(self, symbol: str) -> Dict:
        """獲取機構持倉"""
        try:
            return await self.yahoo.get_institutional_holders(symbol)
        except Exception as e:
            raise e
    
    async def get_insider_transactions(self, symbol: str) -> Dict:
        """獲取內部人交易"""
        try:
            return await self.yahoo.get_insider_transactions(symbol)
        except Exception as e:
            raise e
    
    def clear_cache(self, symbol: Optional[str] = None):
        """清除快取"""
        self.yahoo.clear_cache(symbol)


# ============ 單例實例 ============

# 全局數據提供者實例
_us_data_provider: Optional[USDataProvider] = None

def get_us_data_provider() -> USDataProvider:
    """獲取全局 USDataProvider 單例"""
    global _us_data_provider
    if _us_data_provider is None:
        _us_data_provider = USDataProvider()
    return _us_data_provider
