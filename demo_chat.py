#!/usr/bin/env python3
"""
聊天界面演示 - 不啟動服務器，僅展示對話功能
"""

from chat_interface import CryptoAnalysisBot

def demo_conversation():
    """演示對話功能"""
    print("=" * 70)
    print("💬 加密貨幣投資分析聊天機器人 - 演示模式")
    print("=" * 70)
    print("\n這是一個命令行演示版本，展示聊天機器人如何處理你的問題。")
    print("要使用完整的 Web 界面，請運行: python run_chat.py\n")

    bot = CryptoAnalysisBot()

    print("你可以輸入問題，例如:")
    print("  - PI 可以投資嗎?")
    print("  - BTCUSDT 分析")
    print("  - XRP, ETH, BTC 哪個好?")
    print("  - 輸入 'quit' 或 'exit' 退出\n")
    print("-" * 70)

    chat_history = []

    while True:
        try:
            user_input = input("\n你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                print("\n👋 再見！感謝使用加密貨幣投資分析助手。")
                break

            print("\n🤖 分析中...\n")

            # 處理消息
            response, chat_history = bot.process_message(user_input, chat_history)

            print(f"助手: {response}")
            print("\n" + "-" * 70)

        except KeyboardInterrupt:
            print("\n\n👋 再見！感謝使用加密貨幣投資分析助手。")
            break
        except Exception as e:
            print(f"\n❌ 發生錯誤: {e}")
            print("請重試或輸入 'quit' 退出。")

if __name__ == "__main__":
    demo_conversation()
