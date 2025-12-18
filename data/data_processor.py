"""
數據處理模組
將數據準備邏輯從 graph.py 中分離出來，提高可維護性
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from data.data_fetcher import get_data_fetcher
from data.indicator_calculator import add_technical_indicators
from utils.utils import get_crypto_news, safe_float


def prepare_recent_history(df: pd.DataFrame, days: int = 5) -> List[Dict]:
    """
    準備最近 N 天的歷史數據

    Args:
        df: K線數據 DataFrame
        days: 天數

    Returns:
        歷史數據列表
    """
    recent_history = []
    recent_days = min(days, len(df))

    for i in range(-recent_days, 0):
        day_data = df.iloc[i]
        recent_history.append({
            "日期": i,
            "開盤": safe_float(day_data['Open']),
            "最高": safe_float(day_data['High']),
            "最低": safe_float(day_data['Low']),
            "收盤": safe_float(day_data['Close']),
            "交易量": safe_float(day_data['Volume'])
        })

    return recent_history


def calculate_key_levels(df: pd.DataFrame, period: int = 30) -> Dict[str, float]:
    """
    計算關鍵價位（支撐位、壓力位等）

    Args:
        df: K線數據 DataFrame
        period: 計算週期

    Returns:
        關鍵價位字典
    """
    recent = df.tail(period) if len(df) >= period else df

    return {
        f"{period}天最高價": safe_float(recent['High'].max()),
        f"{period}天最低價": safe_float(recent['Low'].min()),
        "支撐位": safe_float(recent['Low'].quantile(0.25)),
        "壓力位": safe_float(recent['High'].quantile(0.75)),
    }


def analyze_market_structure(df: pd.DataFrame) -> Dict:
    """
    分析市場結構（趨勢、波動率等）

    Args:
        df: K線數據 DataFrame

    Returns:
        市場結構分析結果
    """
    price_changes = df['Close'].pct_change()

    return {
        "趨勢": "上漲" if price_changes.tail(7).mean() > 0 else "下跌",
        "波動率": safe_float(price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
        "平均交易量": safe_float(df['Volume'].tail(7).mean()),
    }


def extract_technical_indicators(latest_data: pd.Series) -> Dict[str, float]:
    """
    提取最新的技術指標

    Args:
        latest_data: 最新一筆 K線數據

    Returns:
        技術指標字典
    """
    return {
        "RSI_14": safe_float(latest_data.get('RSI_14', 0)),
        "MACD_線": safe_float(latest_data.get('MACD_12_26_9', 0)),
        "布林帶上軌": safe_float(latest_data.get('BB_upper_20_2', 0)),
        "布林帶下軌": safe_float(latest_data.get('BB_lower_20_2', 0)),
        "MA_7": safe_float(latest_data.get('MA_7', 0)),
        "MA_25": safe_float(latest_data.get('MA_25', 0)),
    }


def calculate_price_info(df: pd.DataFrame) -> Dict:
    """
    計算價格資訊

    Args:
        df: K線數據 DataFrame

    Returns:
        價格資訊字典
    """
    latest = df.iloc[-1]
    current_price = safe_float(latest['Close'])

    # 計算7天價格變化
    price_change_7d = 0
    if len(df) >= 7:
        price_7d_ago = df.iloc[-7]['Close']
        price_change_7d = safe_float(((latest['Close'] / price_7d_ago) - 1) * 100)

    return {
        "當前價格": current_price,
        "7天價格變化百分比": price_change_7d,
    }


def fetch_multi_timeframe_data(
    symbol: str,
    exchange: str,
    market_type: str,
    short_term_interval: str = "1h",
    medium_term_interval: str = "4h",
    long_term_interval: str = "1d",
    limit: int = 100
) -> Dict[str, Dict]:
    """
    獲取多週期數據

    Args:
        symbol: 交易對符號
        exchange: 交易所
        market_type: 市場類型（spot/futures）
        short_term_interval: 短週期時間間隔
        medium_term_interval: 中週期時間間隔
        long_term_interval: 長週期時間間隔
        limit: 數據條數

    Returns:
        包含多週期數據的字典
    """
    data_fetcher = get_data_fetcher(exchange)
    multi_timeframe_data = {}

    # 定義要獲取的週期
    intervals = {
        "short_term": short_term_interval,
        "medium_term": medium_term_interval,
        "long_term": long_term_interval
    }

    # 獲取每個時間週期的數據
    for timeframe, interval in intervals.items():
        try:
            print(f"[CHART] 獲取 {symbol} {timeframe}({interval}) K線數據...")

            # 根據市場類型獲取數據
            if market_type == 'futures':
                klines_df, funding_rate_info = data_fetcher.get_futures_data(symbol, interval, limit)
            else:
                klines_df = data_fetcher.get_historical_klines(symbol, interval, limit)

            if klines_df is None or klines_df.empty:
                print(f"⚠️  {timeframe}({interval}) 數據獲取失敗")
                multi_timeframe_data[timeframe] = None
                continue

            # 添加技術指標
            df_with_indicators = add_technical_indicators(klines_df)

            # 準備多週期數據包
            latest = df_with_indicators.iloc[-1]

            timeframe_data = {
                "timeframe": interval,
                "market_type": market_type,
                "exchange": exchange,
                "funding_rate_info": funding_rate_info if market_type == 'futures' else {},
                "價格資訊": calculate_price_info(df_with_indicators),
                "技術指標": extract_technical_indicators(latest),
                "最近5天歷史": prepare_recent_history(df_with_indicators, days=5),
                "市場結構": analyze_market_structure(df_with_indicators),
                "關鍵價位": calculate_key_levels(df_with_indicators, period=30),
                # "dataframe": df_with_indicators  # 已移除，避免傳遞過大的原始數據
            }

            multi_timeframe_data[timeframe] = timeframe_data
            print(f"SUCCESS: {timeframe}({interval}) 數據獲取完成")

        except Exception as e:
            print(f"ERROR: 獲取 {timeframe}({interval}) 數據時發生錯誤: {e}")
            multi_timeframe_data[timeframe] = None

    return multi_timeframe_data


def analyze_multi_timeframe_trend(multi_timeframe_data: Dict[str, Dict]) -> Dict:
    """
    分析多週期趨勢一致性

    Args:
        multi_timeframe_data: 多週期數據

    Returns:
        綜合趨勢分析
    """
    trend_analysis = {
        "short_term_trend": "不明",
        "medium_term_trend": "不明",
        "long_term_trend": "不明",
        "trend_consistency": "不一致",  # 一致/部分一致/不一致
        "overall_bias": "中性",  # 偏多頭/偏空頭/中性
        "confidence_score": 0.0,  # 0-100 的信心分數
        "key_levels": {}  # 重要價位水平
    }

    # 分析每個週期的趨勢
    for timeframe, data in multi_timeframe_data.items():
        if data is not None and "市場結構" in data:
            trend = data["市場結構"]["趨勢"]
            trend_analysis[f"{timeframe}_trend"] = trend

    # 計算趨勢一致性
    valid_trends = []
    for timeframe in ["short_term", "medium_term", "long_term"]:
        if multi_timeframe_data.get(timeframe) is not None:
            trend = multi_timeframe_data[timeframe]["市場結構"]["趨勢"]
            valid_trends.append(trend)

    if len(valid_trends) > 0:
        # 計算趨勢一致性
        unique_trends = set(valid_trends)
        if len(unique_trends) == 1:
            trend_analysis["trend_consistency"] = "一致"
            trend_analysis["overall_bias"] = list(unique_trends)[0]
            trend_analysis["confidence_score"] = 85.0
        elif len(unique_trends) == 2:
            trend_analysis["trend_consistency"] = "部分一致"
            # 看哪種趨勢佔多數
            if valid_trends.count(valid_trends[0]) > valid_trends.count(valid_trends[1]):
                trend_analysis["overall_bias"] = valid_trends[0]
                trend_analysis["confidence_score"] = 65.0
            else:
                trend_analysis["overall_bias"] = valid_trends[1]
                trend_analysis["confidence_score"] = 65.0
        else:
            trend_analysis["trend_consistency"] = "不一致"
            trend_analysis["overall_bias"] = "中性"
            trend_analysis["confidence_score"] = 40.0

    return trend_analysis


def fetch_and_process_klines(
    symbol: str,
    interval: str,
    limit: int,
    market_type: str,
    exchange: str
) -> Tuple[pd.DataFrame, Dict]:
    """
    獲取並處理 K線數據 (保持向後兼容性)

    Args:
        symbol: 交易對符號
        interval: 時間間隔
        limit: 數據條數
        market_type: 市場類型（spot/futures）
        exchange: 交易所

    Returns:
        (處理後的 K線數據, 資金費率資訊)
    """
    data_fetcher = get_data_fetcher(exchange)
    funding_rate_info = {}

    # 根據市場類型獲取數據
    if market_type == 'futures':
        klines_df, funding_rate_info = data_fetcher.get_futures_data(symbol, interval, limit)
    else:
        klines_df = data_fetcher.get_historical_klines(symbol, interval, limit)

    if klines_df is None or klines_df.empty:
        raise ValueError(f"❌ 數據獲取失敗: {symbol} @ {exchange}")

    # 添加技術指標
    df_with_indicators = add_technical_indicators(klines_df)

    return df_with_indicators, funding_rate_info


def build_market_data_package(
    df: pd.DataFrame,
    symbol: str,
    market_type: str,
    exchange: str,
    leverage: int,
    funding_rate_info: Dict,
    include_multi_timeframe: bool = False,
    short_term_interval: str = "1h",
    medium_term_interval: str = "4h",
    long_term_interval: str = "1d"
) -> Dict:
    """
    構建完整的市場數據包

    Args:
        df: 帶指標的 K線數據
        symbol: 交易對符號
        market_type: 市場類型
        exchange: 交易所
        leverage: 槓桿倍數
        funding_rate_info: 資金費率資訊
        include_multi_timeframe: 是否包含多週期數據
        short_term_interval: 短週期時間間隔
        medium_term_interval: 中週期時間間隔
        long_term_interval: 長週期時間間隔

    Returns:
        完整的市場數據字典
    """
    latest = df.iloc[-1]

    # 提取基礎貨幣名稱（用於新聞搜尋）
    base_currency = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")
    print(f"[NEWS] 正在從 CryptoPanic 撈取 {base_currency} 的真實新聞...")
    news_data = get_crypto_news(symbol=base_currency, limit=5)

    # 基礎數據包
    market_data = {
        "market_type": market_type,
        "exchange": exchange,
        "leverage": leverage,
        "funding_rate_info": funding_rate_info,
        "價格資訊": calculate_price_info(df),
        "技術指標": extract_technical_indicators(latest),
        "最近5天歷史": prepare_recent_history(df, days=5),
        "市場結構": analyze_market_structure(df),
        "關鍵價位": calculate_key_levels(df, period=30),
        "新聞資訊": news_data
    }

    # 如果需要多週期分析，獲取並添加多週期數據
    if include_multi_timeframe:
        print(f"[REFRESH] 準備獲取多週期數據 ({short_term_interval}/{medium_term_interval}/{long_term_interval})...")
        multi_timeframe_data = fetch_multi_timeframe_data(
            symbol, exchange, market_type,
            short_term_interval, medium_term_interval, long_term_interval
        )

        # 分析多週期趨勢一致性
        trend_analysis = analyze_multi_timeframe_trend(multi_timeframe_data)

        # 將多週期數據添加到市場數據包中
        market_data["multi_timeframe_data"] = multi_timeframe_data
        market_data["multi_timeframe_trend_analysis"] = trend_analysis
        print("SUCCESS: 多週期數據準備完成")

    return market_data
