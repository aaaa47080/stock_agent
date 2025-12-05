"""
數據處理模組
將數據準備邏輯從 graph.py 中分離出來，提高可維護性
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from data_fetcher import get_data_fetcher
from indicator_calculator import add_technical_indicators
from utils import get_crypto_news


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
            "開盤": float(day_data['Open']),
            "最高": float(day_data['High']),
            "最低": float(day_data['Low']),
            "收盤": float(day_data['Close']),
            "交易量": float(day_data['Volume'])
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
        f"{period}天最高價": float(recent['High'].max()),
        f"{period}天最低價": float(recent['Low'].min()),
        "支撐位": float(recent['Low'].quantile(0.25)),
        "壓力位": float(recent['High'].quantile(0.75)),
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
        "波動率": float(price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
        "平均交易量": float(df['Volume'].tail(7).mean()),
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
        "RSI_14": float(latest_data.get('RSI_14', 0)),
        "MACD_線": float(latest_data.get('MACD_12_26_9', 0)),
        "布林帶上軌": float(latest_data.get('BB_upper_20_2', 0)),
        "布林帶下軌": float(latest_data.get('BB_lower_20_2', 0)),
        "MA_7": float(latest_data.get('MA_7', 0)),
        "MA_25": float(latest_data.get('MA_25', 0)),
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
    current_price = float(latest['Close'])

    # 計算7天價格變化
    price_change_7d = 0
    if len(df) >= 7:
        price_7d_ago = df.iloc[-7]['Close']
        price_change_7d = float(((latest['Close'] / price_7d_ago) - 1) * 100)

    return {
        "當前價格": current_price,
        "7天價格變化百分比": price_change_7d,
    }


def fetch_and_process_klines(
    symbol: str,
    interval: str,
    limit: int,
    market_type: str,
    exchange: str
) -> Tuple[pd.DataFrame, Dict]:
    """
    獲取並處理 K線數據

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
    funding_rate_info: Dict
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

    Returns:
        完整的市場數據字典
    """
    latest = df.iloc[-1]

    # 提取基礎貨幣名稱（用於新聞搜尋）
    base_currency = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")
    print(f"📰 正在從 CryptoPanic 撈取 {base_currency} 的真實新聞...")
    news_data = get_crypto_news(symbol=base_currency, limit=5)

    return {
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
