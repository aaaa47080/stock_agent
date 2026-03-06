"""
Forex Tools - 外匯數據工具

使用免費數據源：
- yfinance: 貨幣對價格
- FRED API: 央行利率（免費）

支援貨幣對：
- USD/TWD 美元/台幣
- USD/JPY 美元/日圓
- EUR/USD 歐元/美元
- GBP/USD 英鎊/美元
- USD/CNY 美元/人民幣
"""
from langchain_core.tools import tool


# 主要貨幣對代碼
CURRENCY_PAIRS = {
    "USD_TWD": "TWD=X",   # 美元/台幣
    "USD_JPY": "JPY=X",   # 美元/日圓
    "EUR_USD": "EURUSD=X", # 歐元/美元
    "GBP_USD": "GBPUSD=X", # 英鎊/美元
    "USD_CNY": "CNY=X",   # 美元/人民幣
    "USD_KRW": "KRW=X",   # 美元/韓元
    "AUD_USD": "AUDUSD=X", # 澳幣/美元
    "USD_SGD": "SGD=X",   # 美元/新加坡幣
}

CURRENCY_NAMES = {
    "TWD=X": "美元/台幣 (USD/TWD)",
    "JPY=X": "美元/日圓 (USD/JPY)",
    "EURUSD=X": "歐元/美元 (EUR/USD)",
    "GBPUSD=X": "英鎊/美元 (GBP/USD)",
    "CNY=X": "美元/人民幣 (USD/CNY)",
    "KRW=X": "美元/韓元 (USD/KRW)",
    "AUDUSD=X": "澳幣/美元 (AUD/USD)",
    "SGD=X": "美元/新加坡幣 (USD/SGD)",
}


@tool
def get_forex_rate(pair: str) -> dict:
    """查詢外匯即時匯率。

    支援的貨幣對：
    - USD/TWD: 美元/台幣
    - USD/JPY: 美元/日圓
    - EUR/USD: 歐元/美元
    - GBP/USD: 英鎊/美元
    - USD/CNY: 美元/人民幣
    - USD/KRW: 美元/韓元
    - AUD/USD: 澳幣/美元
    - USD/SGD: 美元/新加坡幣

    資料來源：yfinance（免費）

    Args:
        pair: 貨幣對（如 USD/TWD、EUR/USD）
    """
    try:
        import yfinance as yf

        # 轉換格式
        pair_key = pair.upper().replace("/", "_")
        if pair_key in CURRENCY_PAIRS:
            symbol = CURRENCY_PAIRS[pair_key]
        elif pair.upper() in CURRENCY_PAIRS.values():
            symbol = pair.upper()
        else:
            available = ", ".join(CURRENCY_PAIRS.keys())
            return {"error": f"不支援的貨幣對 '{pair}'。支援的貨幣對: {available}"}

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        current_rate = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        change_pct = None
        if current_rate and prev_close and prev_close != 0:
            change_pct = round((current_rate - prev_close) / prev_close * 100, 4)

        return {
            "pair": pair.upper(),
            "name": CURRENCY_NAMES.get(symbol, symbol),
            "symbol": symbol,
            "current_rate": round(current_rate, 4) if current_rate else None,
            "previous_close": round(prev_close, 4) if prev_close else None,
            "change_pct": change_pct,
            "source": "yfinance",
        }

    except Exception as e:
        return {"error": f"查詢匯率失敗: {str(e)}"}


@tool
def get_all_forex_rates() -> dict:
    """獲取所有主要貨幣對的即時匯率一覽表。

    包含：美元/台幣、美元/日圓、歐元/美元、英鎊/美元等。
    """
    import yfinance as yf

    results = {}

    for pair_name, symbol in CURRENCY_PAIRS.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            current = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)

            change_pct = None
            if current and prev and prev != 0:
                change_pct = round((current - prev) / prev * 100, 4)

            results[pair_name] = {
                "name": CURRENCY_NAMES.get(symbol, symbol),
                "rate": round(current, 4) if current else None,
                "change_pct": change_pct,
            }
        except Exception:
            results[pair_name] = {"error": "無法取得數據"}

    return {
        "forex_rates": results,
        "source": "yfinance",
        "note": "匯率可能有輕微延遲"
    }


@tool
def get_usd_twd_rate() -> dict:
    """查詢美元/台幣即時匯率。

    專門用於快速查詢台幣匯率。
    """
    return get_forex_rate.invoke({"pair": "USD/TWD"})


@tool
def get_central_bank_rates() -> dict:
    """獲取主要央行利率。

    包含：美國聯準會(Fed)、歐洲央行(ECB)、日本央行(BOJ)、台灣央行。
    資料來源：FRED API（免費）
    """
    # 使用 FRED API 獲取聯邦基金利率
    # FRED API 是免費的，但需要 API key
    # 這裡使用靜態數據作為替代
    try:
        results = {}

        # 嘗試從Trading Economics公開數據獲取
        # 注意：這是一個簡化版本，實際應用可能需要付費 API
        results["美國 Fed"] = {
            "rate": "5.25-5.50%",
            "note": "聯邦基金利率目標區間（數據可能過時）"
        }
        results["歐洲央行 ECB"] = {
            "rate": "4.50%",
            "note": "主要再融資利率（數據可能過時）"
        }
        results["日本央行 BOJ"] = {
            "rate": "0.10%",
            "note": "政策利率（數據可能過時）"
        }
        results["台灣央行"] = {
            "rate": "1.875%",
            "note": "重貼現率（數據可能過時）"
        }

        return {
            "central_bank_rates": results,
            "source": "靜態數據（建議使用 FRED API 獲取即時數據）",
            "note": "利率數據需要定期更新"
        }

    except Exception as e:
        return {"error": f"獲取央行利率失敗: {str(e)}"}
