#!/usr/bin/env python3
"""
快速啟動聊天界面
使用方式: python run_chat.py
"""

from chat_interface import create_chat_interface

if __name__ == "__main__":
    print("🚀 正在啟動加密貨幣投資分析聊天界面...")
    print("請稍候...")

    demo = create_chat_interface()

    print("\n✅ 聊天界面已啟動！")
    print("📱 請在瀏覽器中打開顯示的網址")
    print("💡 按 Ctrl+C 停止服務\n")

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )