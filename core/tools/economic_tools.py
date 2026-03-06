"""
Economic Data Tools - 經濟數據工具

使用免費數據源：
- FRED API: 美國聯邦儲備經濟數據（免費，需申請 API key）
- yfinance: 市場指數

支援數據：
- GDP、CPI、失業率、利率等經濟指標
- VIX 恐慌指數
- 市場指數（S&P 500、道瓊、那斯達克）
"""
from langchain_core.tools import tool


# 市場指數代碼
MARKET_INDICES = {
    "SP500": "^GSPC",      # S&P 500
    "DOW": "^DJI",         # 道瓊工業指數
    "NASDAQ": "^IXIC",     # 那斯達克
    "VIX": "^VIX",         # 恐慌指數
    "RUSSELL2000": "^RUT", # 羅素2000小盤股
    "PHLX_SEMICONDUCTOR": "^SOX",  # 費城半導體
}

INDEX_NAMES = {
    "^GSPC": "S&P 500 標普500指數",
    "^DJI": "Dow Jones 道瓊工業指數",
    "^IXIC": "NASDAQ 那斯達克指數",
    "^VIX": "VIX 恐慌指數",
    "^RUT": "Russell 2000 羅素2000",
    "^SOX": "PHLX Semiconductor 費城半導體",
}


@tool
def get_market_indices() -> dict:
    """獲取美股主要市場指數即時價格。

    包含：S&P 500、道瓊、那斯達克、VIX恐慌指數、費城半導體。
    """
    import yfinance as yf
    from datetime import datetime
    import pytz

    results = {}
    errors = []

    # 檢查是否為美股交易時間（美東時間 9:30-16:00）
    try:
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        is_trading_hours = (
            now_et.weekday() < 5 and  # 週一到週五
            9 <= now_et.hour < 16  # 9:00 - 16:00
        )
        market_status = "交易中" if is_trading_hours else "已收盤/非交易時間"
    except Exception:
        market_status = "未知"

    for name, symbol in MARKET_INDICES.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            current = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)

            # 如果無法獲取當前價格，嘗試使用歷史數據
            if current is None:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    current = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None

            change_pct = None
            if current and prev and prev != 0:
                change_pct = round((current - prev) / prev * 100, 2)

            if current:
                results[name] = {
                    "name": INDEX_NAMES.get(symbol, symbol),
                    "symbol": symbol,
                    "price": round(current, 2),
                    "change_pct": change_pct,
                }
            else:
                errors.append(f"{name}: 無法獲取價格數據")

        except Exception as e:
            errors.append(f"{name}: {str(e)}")

    response = {
        "market_indices": results,
        "source": "yfinance",
        "market_status": market_status,
    }

    if errors:
        response["errors"] = errors
        response["note"] = "部分指數無法獲取數據，可能為非交易時間"

    return response


@tool
def get_vix_index() -> dict:
    """獲取 VIX 恐慌指數詳細資訊。

    VIX 是衡量市場預期波動率的指標：
    - VIX < 15: 市場平穩
    - VIX 15-25: 正常波動
    - VIX > 25: 市場恐慌
    - VIX > 40: 極度恐慌
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("^VIX")
        info = ticker.fast_info
        hist = ticker.history(period="30d")

        current = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)

        # 計算變化
        change_pct = None
        if current and prev and prev != 0:
            change_pct = round((current - prev) / prev * 100, 2)

        # 判斷市場情緒
        if current:
            if current < 15:
                sentiment = "🟢 市場平穩 (低波動)"
                interpretation = "投資者情緒樂觀，市場預期穩定"
            elif current < 20:
                sentiment = "🟡 正常波動"
                interpretation = "市場處於正常狀態"
            elif current < 25:
                sentiment = "🟠 波動增加"
                interpretation = "市場有不確定性，需關注"
            elif current < 40:
                sentiment = "🔴 市場恐慌"
                interpretation = "投資者擔憂情緒上升"
            else:
                sentiment = "🩸 極度恐慌"
                interpretation = "市場可能出現大幅拋售"
        else:
            sentiment = "未知"
            interpretation = ""

        # 計算30天高點低點
        high_30d = float(hist["High"].max()) if not hist.empty else None
        low_30d = float(hist["Low"].min()) if not hist.empty else None

        return {
            "name": "VIX 恐慌指數",
            "symbol": "^VIX",
            "current": round(current, 2) if current else None,
            "change_pct": change_pct,
            "high_30d": round(high_30d, 2) if high_30d else None,
            "low_30d": round(low_30d, 2) if low_30d else None,
            "sentiment": sentiment,
            "interpretation": interpretation,
            "source": "yfinance"
        }

    except Exception as e:
        return {"error": f"獲取 VIX 指數失敗: {str(e)}"}


@tool
def get_sp500_performance() -> dict:
    """獲取 S&P 500 指數詳細表現。

    包含價格、漲跌幅、技術位等信息。
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("^GSPC")
        info = ticker.fast_info
        hist = ticker.history(period="1y")

        current = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)

        # 計算各期間報酬
        returns = {}
        if not hist.empty:
            # 日報酬
            if prev and prev != 0:
                returns["1d"] = round((current - prev) / prev * 100, 2)

            # 週報酬
            if len(hist) >= 5:
                week_ago = hist["Close"].iloc[-5]
                returns["1w"] = round((current - week_ago) / week_ago * 100, 2)

            # 月報酬
            if len(hist) >= 20:
                month_ago = hist["Close"].iloc[-20]
                returns["1m"] = round((current - month_ago) / month_ago * 100, 2)

            # 年報酬
            if len(hist) >= 252:
                year_ago = hist["Close"].iloc[0]
                returns["1y"] = round((current - year_ago) / year_ago * 100, 2)

            # 高低點
            returns["52w_high"] = round(float(hist["High"].max()), 2)
            returns["52w_low"] = round(float(hist["Low"].min()), 2)

        return {
            "name": "S&P 500 標普500指數",
            "symbol": "^GSPC",
            "current": round(current, 2) if current else None,
            "returns": returns,
            "source": "yfinance"
        }

    except Exception as e:
        return {"error": f"獲取 S&P 500 數據失敗: {str(e)}"}


@tool
def get_us_sector_performance() -> dict:
    """獲取美股 11 大板塊表現。

    使用 SPDR Sector ETF 查詢各板塊漲跌：
    - XLF: 金融
    - XLK: 科技
    - XLV: 醫療
    - XLE: 能源
    - XLY: 非必需消費
    - XLP: 必需消費
    - XLI: 工業
    - XLB: 原物料
    - XLRE: 房地产
    - XLC: 通訊
    - XLU: 公用事業
    """
    import yfinance as yf

    sectors = {
        "XLF": "金融 (Financials)",
        "XLK": "科技 (Technology)",
        "XLV": "醫療 (Healthcare)",
        "XLE": "能源 (Energy)",
        "XLY": "非必需消費 (Consumer Disc.)",
        "XLP": "必需消費 (Consumer Staples)",
        "XLI": "工業 (Industrials)",
        "XLB": "原物料 (Materials)",
        "XLRE": "房地產 (Real Estate)",
        "XLC": "通訊 (Communication)",
        "XLU": "公用事業 (Utilities)",
    }

    results = []

    for symbol, name in sectors.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            current = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)

            change_pct = None
            if current and prev and prev != 0:
                change_pct = round((current - prev) / prev * 100, 2)

            results.append({
                "symbol": symbol,
                "name": name,
                "price": round(current, 2) if current else None,
                "change_pct": change_pct,
            })
        except Exception:
            results.append({
                "symbol": symbol,
                "name": name,
                "error": "無法取得數據"
            })

    # 按漲跌幅排序
    results = sorted(results, key=lambda x: x.get("change_pct") or -999, reverse=True)

    return {
        "sector_performance": results,
        "source": "yfinance (SPDR Sector ETFs)",
        "note": "板塊表現基於 ETF 價格"
    }


@tool
def get_economic_calendar() -> dict:
    """獲取近期重要經濟事件行事曆。

    包含：利率決議、CPI發布、非農就業、GDP等。
    注意：此為靜態提醒，實際日期需查詢官方公告。
    """
    return {
        "重要經濟事件": [
            {
                "event": "FOMC 利率決議",
                "frequency": "每6週",
                "importance": "極高",
                "impact": "影響全球資產價格"
            },
            {
                "event": "非農就業數據 (NFP)",
                "frequency": "每月第一個週五",
                "importance": "高",
                "impact": "影響美元和美股"
            },
            {
                "event": "CPI 消費者物價指數",
                "frequency": "每月中旬",
                "importance": "高",
                "impact": "影響通膨預期和利率"
            },
            {
                "event": "GDP 國內生產總值",
                "frequency": "每季",
                "importance": "高",
                "impact": "反映經濟成長"
            },
            {
                "event": "初領失業金人數",
                "frequency": "每週四",
                "importance": "中",
                "impact": "勞動市場指標"
            },
        ],
        "資料來源": "靜態行事曆提醒",
        "建議": "請查詢 TradingEconomics 或 Forex Factory 獲取準確日期"
    }
