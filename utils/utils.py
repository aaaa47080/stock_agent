import os
import json
import time
import requests
import pandas as pd
import numpy as np
from urllib.parse import urlparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import concurrent.futures
from cachetools import cached, TTLCache

# Cache for CryptoPanic API calls, 5-minute TTL (reduced from 1 hour for real-time)
cryptopanic_cache = TTLCache(maxsize=100, ttl=300)

class DataFrameEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle pandas DataFrame, Timestamps, and NumPy types.
    It converts a DataFrame to a list of dictionaries and NumPy types to native Python types.
    """
    def default(self, obj):
        if isinstance(obj, pd.DataFrame):
            # Create a copy to avoid modifying the original DataFrame in place
            df_copy = obj.copy()
            # Convert all datetime-like columns to ISO 8601 strings.
            for col in df_copy.select_dtypes(include=['datetime64[ns]', 'datetimetz']).columns:
                df_copy[col] = df_copy[col].dt.isoformat()
            return df_copy.to_dict(orient='records')
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

def safe_float(value, default=0.0):
    """
    Safely converts a value to a float.
    
    Args:
        value: The value to convert.
        default: The default value to return if conversion fails.
        
    Returns:
        The float value or the default.
    """
    try:
        return float(value)
    except (ValueError, TypeError, SystemError):
        return default

@cached(cryptopanic_cache)
def get_crypto_news_cryptopanic(symbol: str = "BTC", limit: int = 5) -> List[Dict]:
    """
    從 CryptoPanic 獲取指定幣種的最新新聞 (有1小時快取)
    需先申請 API Key: https://cryptopanic.com/developers/api/
    """
    # 增加延遲以符合 API Rate Limit (2 req/sec)
    time.sleep(0.5)

    # 請替換為你的 CryptoPanic API Token
    API_TOKEN = os.getenv("API_TOKEN", "")
    
    if API_TOKEN == "":
        print(">> 警告：未設定 CryptoPanic API Token，無法獲取真實新聞")
        return []

    print(f">> 正在從 CryptoPanic API 撈取 {symbol} 的真實新聞 (快取 TTL: 5分鐘)...")
    
    # CryptoPanic API 請求
    url = "https://cryptopanic.com/api/developer/v2/posts/"
    params = {
        "auth_token": API_TOKEN,
        "currencies": symbol,
        # "filter": "important",  # 暫時移除 "important" 過濾，以獲取更多新聞
        "kind": "news",         # 排除媒體影片，只抓新聞
        "public": "true"
    }

    retries = 3
    delay = 5  # seconds
    for i in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            news_list = []
            if "results" in data:
                for item in data["results"][:limit]:
                    # 加入情緒標籤 (如果有)
                    sentiment = "中性"
                    if "votes" in item:
                        if item["votes"]["positive"] > item["votes"]["negative"]:
                            sentiment = "看漲"
                        elif item["votes"]["negative"] > item["votes"]["positive"]:
                            sentiment = "看跌"

                    news_list.append({
                        "title": item.get("title", "No Title"),
                        "description": item.get("title", ""), # CryptoPanic often has empty description, use title as fallback
                        "published_at": item.get("published_at", "N/A"),
                        "sentiment": sentiment,
                        "url": item.get("url", ""), # Extract URL
                        "source": item.get("domain", "CryptoPanic")
                    })
            
            if not news_list:
                print(">> CryptoPanic: 未找到相關新聞")
                
            return news_list

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and i < retries - 1:
                print(f">> CryptoPanic API rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            else:
                print(f">> CryptoPanic 獲取新聞失敗: {str(e)}")
                return []
        except Exception as e:
            print(f">> CryptoPanic 獲取新聞失敗: {str(e)}")
            return []

    return []


def get_crypto_news_newsapi(symbol: str = "BTC", limit: int = 5) -> List[Dict]:
    """
    從 NewsAPI 獲取加密貨幣相關新聞
    申請免費 API Key: https://newsapi.org/
    免費版: 100 請求/天
    """
    API_KEY = os.getenv("NEWSAPI_KEY", "")

    if not API_KEY:
        print(">> 警告：未設定 NewsAPI Key")
        return []

    print(f">> 正在從 NewsAPI 撈取 {symbol} 相關新聞...")

    # 常見加密貨幣名稱映射
    crypto_names = {
        "BTC": "Bitcoin", "ETH": "Ethereum", "XRP": "Ripple",
        "BNB": "Binance", "SOL": "Solana", "ADA": "Cardano",
        "DOGE": "Dogecoin", "PI": "Pi Network", "MATIC": "Polygon"
    }

    search_term = crypto_names.get(symbol.upper(), symbol)

    url = "https://newsapi.org/v2/everything"
    params = {
        "apiKey": API_KEY,
        "q": f"{search_term} OR {symbol}",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": limit,
        "from": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        news_list = []
        if data.get("status") == "ok" and "articles" in data:
            for article in data["articles"][:limit]:
                news_list.append({
                    "title": article.get("title", "No Title"),
                    "description": article.get("description", ""),
                    "published_at": article.get("publishedAt", "N/A"),
                    "sentiment": "中性",  # NewsAPI 不提供情緒分析
                    "source": f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                    "url": article.get("url", "") # Extract URL
                })

        return news_list

    except Exception as e:
        print(f">> NewsAPI 獲取失敗: {str(e)}")
        return []


def get_crypto_news_coingecko(symbol: str = "BTC", limit: int = 5) -> List[Dict]:
    """
    從 CoinGecko 獲取加密貨幣市場資訊（無需 API Key）
    完全免費，提供市場概況和社群數據
    """
    print(f">> 正在從 CoinGecko 撈取 {symbol} 市場資訊...")

    # CoinGecko 需要幣種 ID（小寫）
    coin_id_map = {
        "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple",
        "BNB": "binancecoin", "SOL": "solana", "ADA": "cardano",
        "DOGE": "dogecoin", "PI": "pi-network", "MATIC": "matic-network",
        "AVAX": "avalanche-2", "DOT": "polkadot", "LINK": "chainlink"
    }

    coin_id = coin_id_map.get(symbol.upper(), symbol.lower())

    try:
        # 獲取幣種詳細資訊
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        coin_data = response.json()

        news_list = []

        # 1. 市場趨勢摘要
        if "market_data" in coin_data:
            market = coin_data["market_data"]
            price_change_24h = market.get("price_change_percentage_24h", 0)
            price_change_7d = market.get("price_change_percentage_7d", 0)

            trend = "上漲" if price_change_24h > 0 else "下跌"
            news_list.append({
                "title": f"{symbol} 24小時市場趨勢: {trend} {abs(price_change_24h):.2f}%",
                "description": f"24小時變化: {price_change_24h:.2f}%, 7天變化: {price_change_7d:.2f}%, 市值排名: #{market.get('market_cap_rank', 'N/A')}",
                "published_at": datetime.now().isoformat(),
                "sentiment": "看漲" if price_change_24h > 5 else ("看跌" if price_change_24h < -5 else "中性"),
                "source": "CoinGecko (Market Data)",
                "url": f"https://www.coingecko.com/en/coins/{coin_id}"
            })

        # 2. 社群活動概況
        if "community_data" in coin_data:
            community = coin_data["community_data"]
            twitter = community.get('twitter_followers', 0)
            reddit = community.get('reddit_subscribers', 0)

            if twitter > 0 or reddit > 0:
                news_list.append({
                    "title": f"{symbol} 社群活躍度數據",
                    "description": f"Twitter 關注者: {twitter:,}, Reddit 訂閱者: {reddit:,}, Telegram 用戶: {community.get('telegram_channel_user_count', 0):,}",
                    "published_at": datetime.now().isoformat(),
                    "sentiment": "中性",
                    "source": "CoinGecko (Community)",
                    "url": f"https://www.coingecko.com/en/coins/{coin_id}#social"
                })

        # 3. 開發活動（如果有）
        if "developer_data" in coin_data:
            dev = coin_data["developer_data"]
            if dev.get("stars", 0) > 0:
                news_list.append({
                    "title": f"{symbol} 開發活動",
                    "description": f"GitHub Stars: {dev.get('stars', 0):,}, Forks: {dev.get('forks', 0):,}, 最近提交: {dev.get('commit_count_4_weeks', 0)}",
                    "published_at": datetime.now().isoformat(),
                    "sentiment": "中性",
                    "source": "CoinGecko (Developer)",
                    "url": f"https://www.coingecko.com/en/coins/{coin_id}#developer"
                })

        # 4. 流通量資訊
        if "market_data" in coin_data:
            market = coin_data["market_data"]
            circulating = market.get("circulating_supply", 0)
            total = market.get("total_supply", 0)

            if circulating > 0:
                circ_percent = (circulating / total * 100) if total > 0 else 0
                news_list.append({
                    "title": f"{symbol} 供應量資訊",
                    "description": f"流通量: {circulating:,.0f}, 總供應量: {total:,.0f} ({circ_percent:.1f}% 已流通)",
                    "published_at": datetime.now().isoformat(),
                    "sentiment": "中性",
                    "source": "CoinGecko (Supply)",
                    "url": f"https://www.coingecko.com/en/coins/{coin_id}#tokenomics"
                })

        return news_list[:limit]

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f">> CoinGecko 找不到幣種: {coin_id}")
        else:
            print(f">> CoinGecko 獲取失敗: {str(e)}")
        return []
    except Exception as e:
        print(f">> CoinGecko 獲取失敗: {str(e)}")
        return []


def get_crypto_news_google(symbol: str = "BTC", limit: int = 5) -> List[Dict]:
    """
    從 Google News RSS 獲取最新新聞（無限量、無 API Key 限制）
    """
    import xml.etree.ElementTree as ET
    print(f">> 正在從 Google News 撈取 {symbol} 的即時新聞...")
    
    url = f"https://news.google.com/rss/search?q={symbol}+crypto+when:24h&hl=en-US&gl=US&ceid=US:en"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        news_list = []
        for item in root.findall('.//item')[:limit]:
            title = item.find('title').text if item.find('title') is not None else "No Title"
            link = item.find('link').text if item.find('link') is not None else ""
            source_name = item.find('source').text if item.find('source') is not None else "Google News"
            
            news_list.append({
                "title": title,
                "description": title,
                "published_at": item.find('pubDate').text if item.find('pubDate') is not None else "N/A",
                "sentiment": "中性",
                "source": f"Google ({source_name})",
                "url": link
            })
        return news_list
    except Exception as e:
        print(f">> Google News 獲取失敗: {str(e)}")
        return []

def get_crypto_news_cryptocompare(symbol: str = "BTC", limit: int = 5) -> List[Dict]:
    """
    從 CryptoCompare 獲取專業新聞（免費額度極高）
    """
    print(f">> 正在從 CryptoCompare 撈取 {symbol} 的專業報導...")
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    params = {"categories": symbol, "excludeCategories": "Sponsored", "lang": "EN"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        news_list = []
        if data.get("Data"):
            for item in data["Data"][:limit]:
                news_list.append({
                    "title": item.get("title", "No Title"),
                    "description": item.get("body", ""),
                    "published_at": datetime.fromtimestamp(item.get("published_on", 0)).isoformat(),
                    "sentiment": "中性",
                    "source": f"CryptoCompare ({item.get('source', 'Unknown')})",
                    "url": item.get("url", "")
                })
        return news_list
    except Exception as e:
        print(f">> CryptoCompare 獲取失敗: {str(e)}")
        return []

def get_crypto_news(symbol: str = "BTC", limit: int = 5, enabled_sources: List[str] = None) -> List[Dict]:
    """
    🔥 多來源新聞聚合器（已增強版）
    
    支援來源 ID: ['google', 'cryptocompare', 'cryptopanic', 'newsapi']
    """
    print(f"\n>> 啟動多來源新聞聚合系統 (目標: {symbol})...")

    # 如果沒有指定來源，預設啟用所有（或穩定來源）
    if not enabled_sources:
        enabled_sources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']

    all_news = []
    source_map = {
        'google': (get_crypto_news_google, "Google News (無限)"),
        'cryptocompare': (get_crypto_news_cryptocompare, "CryptoCompare (高額度)"),
        'cryptopanic': (get_crypto_news_cryptopanic, "CryptoPanic (專業)"),
        'newsapi': (get_crypto_news_newsapi, "NewsAPI (主流)")
    }

    # 使用並行處理
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(enabled_sources)) as executor:
        futures = {}
        for src_id in enabled_sources:
            if src_id in source_map:
                func, name = source_map[src_id]
                futures[executor.submit(func, symbol, limit)] = name

        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                news = future.result()
                if news:
                    all_news.extend(news)
                    print(f">> {name}: 獲取 {len(news)} 條新聞")
                else:
                    print(f">> {name}: 無新聞")
            except Exception as e:
                print(f">> {name} 發生錯誤: {e}")

    # 去重（根據標題相似度）
    unique_news = []
    seen_titles = set()

    for news_item in all_news:
        title_lower = news_item["title"].lower()[:50]
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            unique_news.append(news_item)

    # 排序並返回
    try:
        unique_news.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    except:
        pass

    result = unique_news[:limit * 3]
    print(f"\n>> 聚合完成: 總共獲取 {len(result)} 條獨特新聞\n")
    return result