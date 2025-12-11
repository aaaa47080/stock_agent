import os
import json
import time
import requests
from urllib.parse import urlparse

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

def get_crypto_news(symbol: str = "BTC", limit: int = 5):
    """
    從 CryptoPanic 獲取指定幣種的最新新聞
    需先申請 API Key: https://cryptopanic.com/developers/api/
    """
    # 請替換為你的 CryptoPanic API Token
    API_TOKEN = os.getenv("API_TOKEN", "")
    
    if API_TOKEN == "":
        print("⚠️ 警告：未設定 CryptoPanic API Token，無法獲取真實新聞")
        return []

    print(f"📰 正在從 CryptoPanic 撈取 {symbol} 的真實新聞...")
    
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
                        "description": item.get("description", ""),
                        "published_at": item.get("published_at", "N/A"),
                        "sentiment": sentiment
                    })
            
            if not news_list:
                print("⚠️ 未找到相關新聞")
                
            return news_list

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and i < retries - 1:
                print(f"⚠️ API rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            else:
                print(f"❌ 獲取新聞失敗: {str(e)}")
                return []
        except Exception as e:
            print(f"❌ 獲取新聞失敗: {str(e)}")
            return []
    
    return []
