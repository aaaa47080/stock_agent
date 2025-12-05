#!/usr/bin/env python3
"""
測試多交易所支持功能
"""

from chat_interface import CryptoAnalysisBot

def test_exchange_detection():
    """測試交易所自動檢測"""
    print("=" * 70)
    print("測試智能交易所檢測功能")
    print("=" * 70)

    bot = CryptoAnalysisBot()

    # 測試不同的符號
    test_symbols = [
        ("BTC", "Binance 上常見的幣種"),
        ("ETH", "Binance 上常見的幣種"),
        ("PI", "可能只在 OKX 上有的幣種"),
        ("XRP", "Binance 上常見的幣種"),
    ]

    print("\n--- 測試符號標準化 ---\n")

    for symbol, description in test_symbols:
        print(f"\n測試: {symbol} ({description})")

        # Binance 格式
        binance_format = bot.normalize_symbol(symbol, "binance")
        print(f"  Binance 格式: {binance_format}")

        # OKX 格式
        okx_format = bot.normalize_symbol(symbol, "okx")
        print(f"  OKX 格式: {okx_format}")

    print("\n\n" + "=" * 70)
    print("測試交易所可用性檢測")
    print("=" * 70)

    # 注意：這個測試會實際嘗試連接交易所 API
    print("\n⚠️  以下測試會實際連接交易所 API，可能需要一些時間...")
    print("如果不想執行，請按 Ctrl+C 退出\n")

    quick_test_symbols = ["BTC", "ETH"]

    for symbol in quick_test_symbols:
        print(f"\n--- 檢測 {symbol} ---")
        result = bot.find_available_exchange(symbol)

        if result:
            exchange, normalized = result
            print(f"✅ 結果: 在 {exchange.upper()} 找到，符號為 {normalized}")
        else:
            print(f"❌ 結果: 在所有交易所都找不到 {symbol}")

    print("\n" + "=" * 70)
    print("✅ 測試完成!")
    print("=" * 70)

    print("\n提示:")
    print("1. 符號標準化測試顯示了 Binance 和 OKX 的不同格式")
    print("2. 交易所檢測測試會自動找到可用的交易所")
    print("3. 在聊天界面中使用時，系統會自動選擇最佳交易所")
    print("\n要測試完整功能，請運行: python run_chat.py")

if __name__ == "__main__":
    test_exchange_detection()
