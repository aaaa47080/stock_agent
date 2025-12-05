#!/usr/bin/env python3
"""
測試聊天界面的核心功能
"""

from chat_interface import CryptoQueryParser, CryptoAnalysisBot

def test_query_parser():
    """測試查詢解析器"""
    print("=" * 60)
    print("測試 LLM 查詢解析器")
    print("=" * 60)

    parser = CryptoQueryParser()

    test_queries = [
        "PI 可以投資嗎?",
        "PIUSDT 值得買入嗎?",
        "XRP, PI, ETH 哪些可以投資?",
        "比特幣最近表現如何?",
        "你好",
    ]

    for query in test_queries:
        print(f"\n輸入: {query}")
        try:
            result = parser.parse_query(query)
            print(f"解析結果:")
            print(f"  - 意圖: {result.get('intent')}")
            print(f"  - 幣種: {result.get('symbols')}")
            print(f"  - 動作: {result.get('action')}")
            print(f"  - 問題摘要: {result.get('user_question')}")
        except Exception as e:
            print(f"  ❌ 解析失敗: {e}")

def test_symbol_normalization():
    """測試符號標準化"""
    print("\n" + "=" * 60)
    print("測試符號標準化")
    print("=" * 60)

    bot = CryptoAnalysisBot()

    test_symbols = [
        "BTC",
        "PI",
        "PIUSDT",
        "ETH",
        "ETHUSDT",
        "xrp",
    ]

    for symbol in test_symbols:
        normalized = bot.normalize_symbol(symbol)
        print(f"{symbol:15} -> {normalized}")

if __name__ == "__main__":
    print("\n🧪 開始測試聊天界面核心功能\n")

    # 測試查詢解析
    test_query_parser()

    # 測試符號標準化
    test_symbol_normalization()

    print("\n" + "=" * 60)
    print("✅ 測試完成!")
    print("=" * 60)
    print("\n提示: 如果查詢解析測試成功,說明 LLM 集成正常")
    print("提示: 如果符號標準化測試成功,說明基礎功能正常")
    print("\n要測試完整功能,請運行: python run_chat.py")