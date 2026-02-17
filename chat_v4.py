#!/usr/bin/env python3
"""
Agent V4 交互式聊天介面

運行方式：
    python3 chat_v4.py

功能：
- Manager Agent 統籌調度
- 自動分類 → 規劃 → 執行 → 綜合
- Codebook 自學習
- 品質自動檢查
- 真正的 Human-In-The-Loop
"""
import sys
import os
import traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from utils.llm_client import LLMClientFactory
from core.agents import bootstrap, ManagerAgent


class ChatBotV4:
    """
    Agent V4 交互式聊天機器人

    特點：
    - Manager Agent 統籌調度
    - Codebook 自學習（重複問題自動加速）
    - 品質自動檢查 + 自我修正
    - Human-In-The-Loop 確認
    """

    def __init__(self, llm_client=None):
        """初始化 ChatBot V4"""
        self.llm_client = llm_client or LLMClientFactory.create_client("openai", "gpt-5-nano")
        self.manager = bootstrap(self.llm_client)
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.message_count = 0

    def process(self, query: str) -> str:
        """處理使用者查詢"""
        self.message_count += 1
        return self.manager.process(query, self.session_id)

    def print_banner(self):
        """顯示歡迎訊息"""
        print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🤖 Agent V4 - 自學習多 Agent 協作系統                      ║
║                                                               ║
║     核心特性：                                                ║
║       • Manager Agent 自動分類 → 規劃 → 執行                 ║
║       • Codebook 自學習（重複問題自動加速）                    ║
║       • 品質自檢 + 自我修正                                  ║
║       • Human-In-The-Loop 確認                                ║
║                                                               ║
║     指令：                                                    ║
║       /help     - 顯示幫助                                   ║
║       /status   - 查看系統狀態                               ║
║       /reset    - 重置會話                                   ║
║       /quit     - 退出                                       ║
║                                                               ║
║     示例：                                                    ║
║       "請給我 BTC 最新新聞"                                   ║
║       "分析 ETH 技術面"                                       ║
║       "你好"                                                  ║
║       "PI Network 有什麼消息"                                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
        """)

    def show_help(self) -> str:
        """顯示幫助"""
        return """
📖 Agent V4 使用說明

基本使用：
  直接輸入問題，系統會自動判斷需要調度哪些 Agent

可用的 Sub-Agents：
  • TechAgent  - 技術分析（RSI, MACD, 均線），含預計算訊號
  • NewsAgent  - 多來源新聞搜集和分析
  • ChatAgent  - 一般對話和問候

V4 新功能：
  • Codebook 自學習 - 類似問題會自動加速
  • 品質自檢 - 自動檢查 Agent 輸出品質
  • 自我修正 - 不滿意時自動重試

指令：
  /help     - 顯示此幫助
  /status   - 查看系統狀態
  /reset    - 重置當前會話
  /quit     - 退出程式

範例對話：
  > 你好
  > 請給我 BTC 最新新聞
  > 分析 ETH 技術面
  > 深度分析 SOL
        """

    def show_status(self) -> str:
        """顯示系統狀態"""
        status = self.manager.get_status()
        agents_list = ", ".join(status.get("agents", []))
        tools_list = ", ".join(status.get("tools", []))
        cb = status.get("codebook", {})

        return f"""
📊 系統狀態

會話 ID: {self.session_id}
訊息數量: {self.message_count}

Agents: {agents_list}
Tools: {tools_list}

Codebook: {cb.get('active', 0)} 條有效 / {cb.get('total', 0)} 條總計
        """

    def reset(self) -> str:
        """重置會話"""
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.message_count = 0
        self.manager = bootstrap(self.llm_client)
        return "🔄 會話已重置。開始新的對話吧！"

    def run(self):
        """運行交互循環"""
        self.print_banner()

        while True:
            try:
                query = input("\n💬 > ").strip()

                if not query:
                    continue

                # 處理指令
                if query.startswith("/"):
                    cmd = query.lower().strip()

                    if cmd == "/help":
                        print(self.show_help())
                        continue
                    elif cmd == "/status":
                        print(self.show_status())
                        continue
                    elif cmd == "/reset":
                        print(self.reset())
                        continue
                    elif cmd == "/quit":
                        print("\n👋 再見！感謝使用 Agent V4！")
                        break
                    else:
                        print(f"❓ 未知指令: {cmd}\n輸入 /help 查看可用指令")
                        continue

                # 處理查詢
                print()
                result = self.process(query)
                print(result)

            except KeyboardInterrupt:
                print("\n\n👋 再見！")
                break
            except Exception as e:
                traceback.print_exc()
                print(f"\n❌ 錯誤: {e}")


def main():
    """主函數"""
    bot = ChatBotV4()
    bot.run()


if __name__ == "__main__":
    main()
