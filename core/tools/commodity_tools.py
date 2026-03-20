"""
Commodity Tools - 大宗商品數據工具

使用免費數據源：
- yfinance: 黃金、石油、白銀 ETF
- FRED API: 聯邦儲備經濟數據（免費）

支援商品：
- 黃金 (Gold): GLD ETF
- 白銀 (Silver): SLV ETF
- 石油 (Oil): USO ETF / CL 原油期貨
- 天然氣 (Natural Gas): UNG ETF
- 銅 (Copper): CPER ETF
"""

from langchain_core.tools import tool

# ============================================
# 商品 ETF 代碼對照表 (yfinance)
# ============================================
COMMODITY_ETFS = {
    "gold": {"symbol": "GLD", "name": "黃金 ETF", "description": "SPDR Gold Shares"},
    "silver": {
        "symbol": "SLV",
        "name": "白銀 ETF",
        "description": "iShares Silver Trust",
    },
    "oil": {
        "symbol": "USO",
        "name": "原油 ETF",
        "description": "United States Oil Fund",
    },
    "natural_gas": {
        "symbol": "UNG",
        "name": "天然氣 ETF",
        "description": "United States Natural Gas Fund",
    },
    "copper": {"symbol": "CPER", "name": "銅 ETF", "description": "Copper Path ETN"},
    "wheat": {
        "symbol": "WEAT",
        "name": "小麥 ETF",
        "description": "Teucrium Wheat Fund",
    },
    "corn": {"symbol": "CORN", "name": "玉米 ETF", "description": "Teucrium Corn Fund"},
    "soybean": {
        "symbol": "SOYB",
        "name": "黃豆 ETF",
        "description": "Teucrium Soybean Fund",
    },
}

# 期貨代碼
FUTURES_SYMBOLS = {
    "crude_oil": "CL=F",  # WTI 原油期貨
    "brent_oil": "BZ=F",  # 布蘭特原油期貨
    "gold_futures": "GC=F",  # 黃金期貨
    "silver_futures": "SI=F",  # 白銀期貨
    "natural_gas_futures": "NG=F",  # 天然氣期貨
    "copper_futures": "HG=F",  # 銅期貨
}


@tool
def get_commodity_price(commodity: str) -> dict:
    """查詢大宗商品的即時價格。

    支援的商品：
    - gold: 黃金
    - silver: 白銀
    - oil: 石油/原油
    - natural_gas: 天然氣
    - copper: 銅
    - wheat: 小麥
    - corn: 玉米
    - soybean: 黃豆

    資料來源：yfinance（ETF 價格）

    Args:
        commodity: 商品名稱（英文）
    """
    commodity = commodity.lower().strip()

    if commodity not in COMMODITY_ETFS:
        available = ", ".join(COMMODITY_ETFS.keys())
        return {"error": f"不支援的商品 '{commodity}'。支援的商品: {available}"}

    try:
        import yfinance as yf

        etf_info = COMMODITY_ETFS[commodity]
        symbol = etf_info["symbol"]

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        current_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        change_pct = None
        if current_price and prev_close and prev_close != 0:
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "commodity": commodity,
            "name": etf_info["name"],
            "description": etf_info["description"],
            "etf_symbol": symbol,
            "current_price": round(current_price, 2) if current_price else None,
            "previous_close": round(prev_close, 2) if prev_close else None,
            "change_pct": change_pct,
            "currency": "USD",
            "source": "yfinance ETF",
        }

    except Exception as e:
        return {"error": f"查詢商品價格失敗: {str(e)}"}


@tool
def get_commodity_futures_price(futures_type: str) -> dict:
    """查詢商品期貨的即時價格。

    支援的期貨：
    - crude_oil: WTI 原油期貨
    - brent_oil: 布蘭特原油期貨
    - gold: 黃金期貨
    - silver: 白銀期貨
    - natural_gas: 天然氣期貨
    - copper: 銅期貨

    資料來源：yfinance（期貨價格）

    Args:
        futures_type: 期貨類型
    """
    futures_type = futures_type.lower().strip()

    # 處理別名
    aliases = {
        "gold": "gold_futures",
        "silver": "silver_futures",
        "oil": "crude_oil",
        "crude": "crude_oil",
        "wti": "crude_oil",
        "brent": "brent_oil",
        "natgas": "natural_gas_futures",
        "natural_gas": "natural_gas_futures",
    }
    futures_type = aliases.get(futures_type, futures_type)

    if futures_type not in FUTURES_SYMBOLS:
        available = ", ".join(FUTURES_SYMBOLS.keys())
        return {"error": f"不支援的期貨類型 '{futures_type}'。支援的類型: {available}"}

    try:
        import yfinance as yf

        symbol = FUTURES_SYMBOLS[futures_type]
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        current_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        change_pct = None
        if current_price and prev_close and prev_close != 0:
            change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        # 期貨名稱對照
        futures_names = {
            "crude_oil": "WTI 原油期貨",
            "brent_oil": "布蘭特原油期貨",
            "gold_futures": "黃金期貨",
            "silver_futures": "白銀期貨",
            "natural_gas_futures": "天然氣期貨",
            "copper_futures": "銅期貨",
        }

        return {
            "futures_type": futures_type,
            "name": futures_names.get(futures_type, futures_type),
            "symbol": symbol,
            "current_price": round(current_price, 2) if current_price else None,
            "previous_close": round(prev_close, 2) if prev_close else None,
            "change_pct": change_pct,
            "currency": "USD",
            "source": "yfinance Futures",
        }

    except Exception as e:
        return {"error": f"查詢期貨價格失敗: {str(e)}"}


@tool
def get_all_commodities_prices() -> dict:
    """獲取所有主要大宗商品的即時價格一覽表。

    包含：黃金、白銀、原油、天然氣、銅
    """
    import yfinance as yf

    results = {}

    # 主要商品期貨
    main_futures = ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F"]
    futures_names = {
        "GC=F": "黃金",
        "SI=F": "白銀",
        "CL=F": "WTI原油",
        "NG=F": "天然氣",
        "HG=F": "銅",
    }
    futures_units = {
        "GC=F": "美元/盎司",
        "SI=F": "美元/盎司",
        "CL=F": "美元/桶",
        "NG=F": "美元/MMBtu",
        "HG=F": "美元/磅",
    }

    for symbol in main_futures:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            current = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)

            change_pct = None
            if current and prev and prev != 0:
                change_pct = round((current - prev) / prev * 100, 2)

            results[futures_names[symbol]] = {
                "symbol": symbol,
                "price": round(current, 2) if current else None,
                "change_pct": change_pct,
                "unit": futures_units[symbol],
            }
        except Exception:
            results[futures_names[symbol]] = {"error": "無法取得數據"}

    return {"commodities": results, "source": "yfinance", "note": "期貨價格可能有延遲"}


@tool
def get_gold_silver_ratio() -> dict:
    """獲取金銀比（Gold-Silver Ratio）。

    金銀比 = 黃金價格 / 白銀價格
    是重要的市場情緒指標：
    - 比率高（>80）：黃金相對昂貴，可能預示經濟不確定性
    - 比率低（<60）：白銀相對強勢，可能預示經濟好轉
    """
    import yfinance as yf

    try:
        gold_ticker = yf.Ticker("GC=F")
        silver_ticker = yf.Ticker("SI=F")

        gold_price = getattr(gold_ticker.fast_info, "last_price", None)
        silver_price = getattr(silver_ticker.fast_info, "last_price", None)

        if not gold_price or not silver_price:
            return {"error": "無法取得金銀價格"}

        ratio = gold_price / silver_price

        # 判斷市場情緒
        if ratio > 80:
            sentiment = "偏高（市場避險情緒濃厚）"
            interpretation = "黃金相對昂貴，投資者傾向避險"
        elif ratio < 60:
            sentiment = "偏低（風險偏好上升）"
            interpretation = "白銀相對強勢，工業需求可能增加"
        else:
            sentiment = "正常區間"
            interpretation = "金銀價格關係相對平衡"

        return {
            "gold_price": round(gold_price, 2),
            "silver_price": round(silver_price, 2),
            "ratio": round(ratio, 2),
            "sentiment": sentiment,
            "interpretation": interpretation,
            "historical_range": "通常在 60-80 之間波動",
            "source": "yfinance",
        }

    except Exception as e:
        return {"error": f"計算金銀比失敗: {str(e)}"}


@tool
def get_oil_price_analysis() -> dict:
    """獲取原油價格綜合分析。

    包含 WTI 和布蘭特原油的價格比較。
    """
    import yfinance as yf

    try:
        wti_ticker = yf.Ticker("CL=F")
        brent_ticker = yf.Ticker("BZ=F")

        wti_price = getattr(wti_ticker.fast_info, "last_price", None)
        brent_price = getattr(brent_ticker.fast_info, "last_price", None)

        wti_prev = getattr(wti_ticker.fast_info, "previous_close", None)
        brent_prev = getattr(brent_ticker.fast_info, "previous_close", None)

        wti_change = None
        brent_change = None
        if wti_price and wti_prev:
            wti_change = round((wti_price - wti_prev) / wti_prev * 100, 2)
        if brent_price and brent_prev:
            brent_change = round((brent_price - brent_prev) / brent_prev * 100, 2)

        spread = None
        if wti_price and brent_price:
            spread = round(brent_price - wti_price, 2)

        return {
            "wti_crude": {
                "name": "WTI 原油（美國）",
                "price": round(wti_price, 2) if wti_price else None,
                "change_pct": wti_change,
                "unit": "美元/桶",
            },
            "brent_crude": {
                "name": "布蘭特原油（北海）",
                "price": round(brent_price, 2) if brent_price else None,
                "change_pct": brent_change,
                "unit": "美元/桶",
            },
            "spread": spread,
            "spread_note": "布蘭特通常比 WTI 貴，反映運輸和品質差異",
            "source": "yfinance",
        }

    except Exception as e:
        return {"error": f"獲取原油價格失敗: {str(e)}"}
