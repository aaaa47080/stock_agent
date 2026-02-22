"""
Taiwan Stock Tools — 5 @tool functions for TWStockAgent.

Data sources (free-first):
  - yfinance: price + OHLCV + basic fundamentals (15min delay)
  - TWSE openapi: institutional (3-party) data
  - Google News RSS: TW-specific news
  - FinMind: richer fundamentals (free tier, rate-limited)
"""
from langchain_core.tools import tool
from typing import Optional


# ── Price ──────────────────────────────────────────────────────────────────

@tool
def tw_stock_price(ticker: str) -> dict:
    """獲取台股即時（15分鐘延遲）及近期 OHLCV 價格資料。
    ticker 格式：2330.TW 或 6666.TWO"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="5d")

        current_price = getattr(info, "last_price", None)
        prev_close    = getattr(info, "previous_close", None)
        change_pct    = None
        if current_price and prev_close and prev_close != 0:
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        recent_ohlcv = []
        if not hist.empty:
            for idx, row in hist.tail(5).iterrows():
                recent_ohlcv.append({
                    "date":   str(idx.date()),
                    "open":   round(float(row["Open"]),  2),
                    "high":   round(float(row["High"]),  2),
                    "low":    round(float(row["Low"]),   2),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

        return {
            "ticker":        ticker,
            "current_price": round(current_price, 2) if current_price else None,
            "prev_close":    round(prev_close, 2)    if prev_close    else None,
            "change_pct":    change_pct,
            "recent_ohlcv":  recent_ohlcv,
            "note":          "價格為即時（約15分鐘延遲）",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Technical Analysis ──────────────────────────────────────────────────────

@tool
def tw_technical_analysis(ticker: str, period: str = "3mo") -> dict:
    """計算台股技術指標：RSI(14)、MACD、KD(9,3,3)、MA5/20/60。
    ticker: 2330.TW；period: 1mo/3mo/6mo/1y"""
    try:
        import yfinance as yf
        import pandas_ta as ta

        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty or len(hist) < 30:
            return {"ticker": ticker, "error": "歷史資料不足（需至少30天）"}

        df = hist.copy()

        # RSI(14)
        rsi = ta.rsi(df["Close"], length=14)
        rsi_val = round(float(rsi.iloc[-1]), 2) if rsi is not None and not rsi.empty else None

        # MACD(12,26,9)
        macd_df = ta.macd(df["Close"])
        macd_val = macd_sig = macd_hist_val = None
        if macd_df is not None and not macd_df.empty:
            macd_val      = round(float(macd_df.iloc[-1, 0]), 4)
            macd_sig      = round(float(macd_df.iloc[-1, 1]), 4)
            macd_hist_val = round(float(macd_df.iloc[-1, 2]), 4)

        # KD (Stochastic 9,3,3)
        stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=9, d=3, smooth_k=3)
        k_val = d_val = None
        if stoch is not None and not stoch.empty:
            k_val = round(float(stoch.iloc[-1, 0]), 2)
            d_val = round(float(stoch.iloc[-1, 1]), 2)

        # Moving Averages
        def ma(n):
            s = df["Close"].rolling(n).mean()
            return round(float(s.iloc[-1]), 2) if not s.empty and not s.isna().iloc[-1] else None

        close_now = round(float(df["Close"].iloc[-1]), 2)

        return {
            "ticker":    ticker,
            "period":    period,
            "close":     close_now,
            "rsi_14":    rsi_val,
            "macd":      {"macd": macd_val, "signal": macd_sig, "histogram": macd_hist_val},
            "kd":        {"k": k_val, "d": d_val},
            "ma":        {"ma5": ma(5), "ma20": ma(20), "ma60": ma(60)},
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Fundamentals ────────────────────────────────────────────────────────────

@tool
def tw_fundamentals(ticker: str) -> dict:
    """獲取台股基本面資料：本益比(P/E)、股價淨值比(P/B)、殖利率、EPS 等。
    資料來源：yfinance（延遲非即時，適合參考）"""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        return {
            "ticker":              ticker,
            "company_name":        info.get("longName") or info.get("shortName"),
            "pe_ratio":            info.get("trailingPE"),
            "pb_ratio":            info.get("priceToBook"),
            "dividend_yield_pct":  round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "eps_ttm":             info.get("trailingEps"),
            "revenue_growth":      info.get("revenueGrowth"),
            "profit_margins":      info.get("profitMargins"),
            "market_cap":          info.get("marketCap"),
            "52w_high":            info.get("fiftyTwoWeekHigh"),
            "52w_low":             info.get("fiftyTwoWeekLow"),
            "note":                "基本面資料來自 yfinance，可能有延遲",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── Institutional (三大法人) ────────────────────────────────────────────────

@tool
def tw_institutional(ticker: str) -> dict:
    """獲取台股三大法人籌碼資料（外資、投信、自營商買賣超）。
    資料來源：TWSE 官方 openapi"""
    try:
        import httpx

        # Extract code from ticker (e.g., "2330.TW" → "2330")
        code = ticker.split(".")[0]
        url = f"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY?stockNo={code}"
        resp = httpx.get(url, timeout=10, verify=False)

        # TWSE institutional API (3-party)
        inst_url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX3"
        inst_resp = httpx.get(inst_url, timeout=10, params={"stockNo": code}, verify=False)

        if inst_resp.status_code == 200:
            data = inst_resp.json()
            matching = [d for d in data if d.get("證券代號", "") == code]
            if matching:
                d = matching[0]
                return {
                    "ticker":           ticker,
                    "date":             d.get("日期", ""),
                    "foreign_net":      d.get("外陸資買賣超股數(不含外資自營商)", ""),
                    "investment_trust": d.get("投信買賣超股數", ""),
                    "dealer_net":       d.get("自營商買賣超股數", ""),
                    "total_3party_net": d.get("三大法人買賣超股數", ""),
                    "source":           "TWSE openapi",
                }

        # Fallback: just return basic info
        return {
            "ticker": ticker,
            "note":   "TWSE 法人 API 目前維護中或無法連線。若需外資或三大法人買賣超資訊，建議直接使用 web_search 工具搜尋「(股票代號或名稱) 外資買賣超」。",
            "source": "TWSE openapi (失敗)",
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# ── News ────────────────────────────────────────────────────────────────────

@tool
def tw_news(ticker: str, company_name: str = "", limit: int = 8) -> list:
    """從 Google News RSS 獲取台股相關新聞。
    company_name: 公司中文名稱（如「台積電」），提升新聞相關性"""
    try:
        import httpx
        import xml.etree.ElementTree as ET
        from urllib.parse import quote

        # Search term: prefer Chinese company name for better results
        search_term = company_name if company_name else ticker
        query = quote(f"{search_term} 股票")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

        resp = httpx.get(rss_url, timeout=10, follow_redirects=True, verify=False)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns   = {"media": "http://search.yahoo.com/mrss/"}
        items = []

        for item in root.findall(".//item")[:limit]:
            title   = item.findtext("title", "")
            link    = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source  = item.findtext("source", "")
            items.append({
                "title":      title,
                "url":        link,
                "published":  pub_date,
                "source":     source,
            })

        return items
    except Exception as e:
        return [{"error": str(e)}]


# ── TWSE OpenAPI Tools ────────────────────────────────────────────────────────

TWSE_BASE = "https://openapi.twse.com.tw/v1"

@tool
def tw_major_news(limit: int = 10) -> list:
    """獲取上市公司今日重大訊息（公告）清單。
    資料來源：TWSE OpenAPI t187ap04_L。
    包含公司代號、公司名稱、主旨、發言時間等。
    limit: 回傳筆數上限（預設10）"""
    try:
        import httpx
        resp = httpx.get(f"{TWSE_BASE}/opendata/t187ap04_L", timeout=15, verify=False)
        data = resp.json() if resp.status_code == 200 else []
        results = []
        for item in (data or [])[:limit]:
            subject = item.get("主旨 ", "").strip() or item.get("主旨", "").strip()
            results.append({
                "date":    item.get("發言日期", ""),
                "time":    item.get("發言時間", ""),
                "code":    item.get("公司代號", ""),
                "name":    item.get("公司名稱", ""),
                "subject": subject,
                "rule":    item.get("符合條款", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


@tool
def tw_pe_ratio(code: str) -> dict:
    """獲取台股個股本益比(P/E)、殖利率、股價淨值比(PBR)。
    資料來源：TWSE OpenAPI BWIBBU_d（今日數據）。
    code: 股票代號，如 '2330'（台積電）、'2317'（鴻海）"""
    try:
        import httpx
        resp = httpx.get(f"{TWSE_BASE}/exchangeReport/BWIBBU_d", timeout=15, verify=False)
        data = resp.json() if resp.status_code == 200 else []
        matching = [d for d in (data or []) if d.get("Code", "") == code]
        if not matching:
            resp2 = httpx.get(f"{TWSE_BASE}/exchangeReport/BWIBBU_ALL", timeout=15, verify=False)
            data2 = resp2.json() if resp2.status_code == 200 else []
            matching = [d for d in (data2 or []) if d.get("Code", "") == code]
        if not matching:
            return {"code": code, "error": f"查無 {code} 的本益比資料（可能非上市股票）"}
        d = matching[0]
        return {
            "code":           d.get("Code", code),
            "name":           d.get("Name", ""),
            "date":           d.get("Date", ""),
            "pe_ratio":       d.get("PEratio", "N/A"),
            "dividend_yield": d.get("DividendYield", "N/A"),
            "pb_ratio":       d.get("PBratio", "N/A"),
            "dividend_year":  d.get("DividendYear", ""),
            "source":         "TWSE OpenAPI",
        }
    except Exception as e:
        return {"code": code, "error": str(e)}


@tool
def tw_monthly_revenue(code: str = "") -> list:
    """獲取台股上市公司月營業收入資料。
    資料來源：TWSE OpenAPI t187ap05_L。
    包含當月營收、月增率、年增率、累計營收。
    code: 股票代號（如 '2330'），若為空字串則返回全市場前30筆"""
    try:
        import httpx
        resp = httpx.get(f"{TWSE_BASE}/opendata/t187ap05_L", timeout=15, verify=False)
        data = resp.json() if resp.status_code == 200 else []
        if code:
            data = [d for d in (data or []) if d.get("公司代號", "") == code]
        else:
            data = (data or [])[:30]
        results = []
        for item in data:
            results.append({
                "code":            item.get("公司代號", ""),
                "name":            item.get("公司名稱", ""),
                "industry":        item.get("產業別", ""),
                "ym":              item.get("資料年月", ""),
                "current_revenue": item.get("營業收入-當月營收", ""),
                "mom_pct":         item.get("營業收入-上月比較增減(%)", ""),
                "yoy_pct":         item.get("營業收入-去年當月增減(%)", ""),
                "ytd_revenue":     item.get("累計營業收入-當月累計營收", ""),
                "ytd_yoy_pct":     item.get("累計營業收入-前期比較增減(%)", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


@tool
def tw_dividend_info(code: str = "") -> list:
    """獲取台股上市公司股利分派情形。
    資料來源：TWSE OpenAPI t187ap45_L。
    包含現金股利、配股、股東會日期等。
    code: 股票代號（如 '2330'），若為空字串則返回近期所有公司前30筆"""
    try:
        import httpx
        resp = httpx.get(f"{TWSE_BASE}/opendata/t187ap45_L", timeout=15, verify=False)
        data = resp.json() if resp.status_code == 200 else []
        if code:
            data = [d for d in (data or []) if d.get("公司代號", "") == code]
        else:
            data = (data or [])[:30]
        results = []
        for item in data:
            results.append({
                "code":            item.get("公司代號", ""),
                "name":            item.get("公司名稱", ""),
                "year":            item.get("股利年度", ""),
                "progress":        item.get("決議（擬議）進度", ""),
                "board_date":      item.get("董事會（擬議）股利分派日", ""),
                "shareholder_mtg": item.get("股東會日期", ""),
                "cash_dividend":   item.get("股東配發-盈餘分配之現金股利(元/股)", ""),
                "stock_dividend":  item.get("股東配發-盈餘轉增資配股(元/股)", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


@tool
def tw_foreign_holding_top20() -> list:
    """獲取集中市場外資及陸資持股前 20 名彙總表。
    資料來源：TWSE OpenAPI MI_QFIIS_sort_20。
    包含持股比率、尚可投資比率、法令投資上限等。
    適合用來了解外資最集中持股的台股標的。"""
    try:
        import httpx
        resp = httpx.get(f"{TWSE_BASE}/fund/MI_QFIIS_sort_20", timeout=15, verify=False)
        data = resp.json() if resp.status_code == 200 else []
        results = []
        for item in (data or []):
            results.append({
                "rank":          item.get("Rank", ""),
                "code":          item.get("Code", ""),
                "name":          item.get("Name", ""),
                "held_pct":      item.get("SharesHeldPer", ""),
                "available_pct": item.get("AvailableInvestPer", ""),
                "upper_limit":   item.get("Upperlimit", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]

