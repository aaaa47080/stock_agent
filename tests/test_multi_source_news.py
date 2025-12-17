#!/usr/bin/env python3
"""
測試多來源新聞聚合系統
"""

import os
from dotenv import load_dotenv
from utils.utils import (
    get_crypto_news,
    get_crypto_news_cryptopanic,
    get_crypto_news_newsapi,
    get_crypto_news_coingecko
)

load_dotenv()

def test_individual_sources():
    """測試各個新聞來源"""
    print("=" * 80)
    print("📋 測試各個新聞來源")
    print("=" * 80)

    test_symbol = "BTC"

    # 測試 CryptoPanic
    print("\n1️⃣ 測試 CryptoPanic...")
    crypto_panic_news = get_crypto_news_cryptopanic(test_symbol, limit=3)
    print(f"   獲取 {len(crypto_panic_news)} 條新聞")

    # 測試 NewsAPI
    print("\n2️⃣ 測試 NewsAPI...")
    newsapi_news = get_crypto_news_newsapi(test_symbol, limit=3)
    print(f"   獲取 {len(newsapi_news)} 條新聞")

    # 測試 CoinGecko
    print("\n3️⃣ 測試 CoinGecko...")
    coingecko_news = get_crypto_news_coingecko(test_symbol, limit=3)
    print(f"   獲取 {len(coingecko_news)} 條新聞")

    return crypto_panic_news, newsapi_news, coingecko_news


def test_aggregated_news():
    """測試聚合新聞系統"""
    print("\n" + "=" * 80)
    print("🌐 測試多來源新聞聚合系統")
    print("=" * 80)

    test_symbol = "PI"
    aggregated_news = get_crypto_news(test_symbol, limit=5)

    print("\n📊 聚合結果:")
    print(f"總共獲取 {len(aggregated_news)} 條獨特新聞\n")

    # 顯示前 5 條新聞
    for i, news in enumerate(aggregated_news[:5], 1):
        print(f"{i}. [{news.get('source', 'Unknown')}] {news['title'][:80]}")
        print(f"   發布時間: {news['published_at']}")
        print(f"   情緒: {news['sentiment']}\n")

    return aggregated_news


def display_api_status():
    """顯示 API Key 配置狀態"""
    print("\n" + "=" * 80)
    print("🔑 API Key 配置狀態")
    print("=" * 80)

    api_keys = {
        "CryptoPanic (API_TOKEN)": os.getenv("API_TOKEN", ""),
        "NewsAPI (NEWSAPI_KEY)": os.getenv("NEWSAPI_KEY", ""),
        "OpenAI (OPENAI_API_KEY)": os.getenv("OPENAI_API_KEY", "")
    }

    for name, key in api_keys.items():
        status = "✅ 已設定" if key else "❌ 未設定"
        masked_key = f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else "N/A"
        print(f"{status} {name}: {masked_key}")

    print("\n💡 提示:")
    print("- CoinGecko 無需 API Key，完全免費")
    print("- 建議至少設定一個新聞源 API Key 以獲得更好的新聞覆蓋")
    print("- NewsAPI 免費版: 100 請求/天 (申請: https://newsapi.org/)")
    print("=" * 80)


if __name__ == "__main__":
    # 顯示 API 配置狀態
    display_api_status()

    # 測試各個來源
    test_individual_sources()

    # 測試聚合系統
    test_aggregated_news()

    print("\n✅ 測試完成！")
