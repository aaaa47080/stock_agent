#!/usr/bin/env python3
"""快速測試 PI 分析功能"""

from chat_interface import CryptoAnalysisBot

def test_pi_analysis():
    """測試 PI 幣種分析"""
    print("🔍 正在測試 PI 分析功能...\n")

    bot = CryptoAnalysisBot()

    # 測試查找交易所
    print("1️⃣ 測試查找 PI 交易對...")
    try:
        result = bot.find_available_exchange("PI")
        if result:
            exchange, symbol = result
            print(f"   ✅ 找到交易對: {symbol} 在 {exchange.upper()}")
        else:
            print(f"   ❌ 未找到 PI 交易對")
            return
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return

    # 測試分析功能（簡化版，不實際運行完整分析）
    print("\n2️⃣ 測試符號標準化...")
    normalized = bot.normalize_symbol("PI", exchange)
    print(f"   ✅ 標準化後: {normalized}")

    print("\n✅ 所有基礎測試通過！")
    print("\n💡 現在您可以在 Gradio 界面中輸入 'PI 可以投資嗎？' 進行完整分析")

if __name__ == "__main__":
    test_pi_analysis()
