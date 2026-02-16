#!/usr/bin/env python3
"""
Agent V3 交互式聊天介面

運行方式：
    python3 chat_v3.py

功能：
- 真正的多 Agent 協作系統
- Manager Agent 統籌調度
- ReAct 循環（Reasoning + Acting）
- 智能化 HITL（由 LLM 決定何時詢問使用者）
- 工具註冊制
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from utils.llm_client import LLMClientFactory
from core.agents_v3 import (
    ManagerAgent,
    ToolRegistry,
    EnhancedHITLManager,
    create_agent_system,
    create_default_registry,
)


class ChatBotV3:
    """
    Agent V3 交互式聊天機器人

    特點：
    - Manager Agent 統籌調度
    - Sub-Agents 自主執行
    - 智能化 HITL
    - 完整對話記憶
    """

    def __init__(self, llm_client=None):
        """
        初始化 ChatBot V3

        Args:
            llm_client: LangChain LLM 客戶端（可選）
        """
        # LLM 客戶端
        self.llm_client = llm_client or LLMClientFactory.create_client("openai", "gpt-4o-mini")

        # 創建 Agent 系統
        self.manager = create_agent_system(
            llm_client=self.llm_client,
            enable_hitl=True,
            max_questions=5
        )

        # 會話資訊
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.message_count = 0

    def process(self, query: str) -> str:
        """
        處理使用者查詢

        Args:
            query: 使用者輸入

        Returns:
            回覆內容
        """
        self.message_count += 1
        return self.manager.process(query, self.session_id)

    def print_banner(self):
        """顯示歡迎訊息"""
        print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🤖 Agent V3 - 真正的多 Agent 協作系統                      ║
║                                                               ║
║     核心特性：                                                ║
║       • Manager Agent 統籌調度                               ║
║       • Sub-Agents 自主執行                                  ║
║       • ReAct 循環（Reasoning + Acting）                     ║
║       • 智能化 HITL                                          ║
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
📖 Agent V3 使用說明

基本使用：
  直接輸入問題，系統會自動判斷需要調度哪些 Agent

可用的 Sub-Agents：
  • NewsAgent - 新聞搜集和分析
  • TechAgent - 技術分析（RSI, MACD 等）
  • ChatAgent - 一般對話和問候

指令：
  /help     - 顯示此幫助
  /status   - 查看系統狀態
  /reset    - 重置當前會話
  /quit     - 退出程式

範例對話：
  > 你好
  > 請給我 BTC 最新新聞
  > 分析 ETH 技術面
  > PI Network 有什麼消息
  > 深度分析 SOL

提示：
  - 系統會根據你的問題自動選擇合適的 Agent
  - 如果資訊不足，系統可能會詢問你更多細節
  - 可以使用「它呢」來跟進之前討論的幣種
        """

    def show_status(self) -> str:
        """顯示系統狀態"""
        status = self.manager.get_status()

        agents_status = "\n".join([
            f"  {name}: {info['state']} (observations: {info['observations_count']})"
            for name, info in status.get('agents', {}).items()
        ])

        return f"""
📊 系統狀態

會話 ID: {self.session_id}
訊息數量: {self.message_count}

Sub-Agents 狀態:
{agents_status}

HITL 統計:
  總詢問次數: {status.get('hitl_stats', {}).get('total_questions', 0)}
  總回應次數: {status.get('hitl_stats', {}).get('total_responses', 0)}
        """

    def reset(self) -> str:
        """重置會話"""
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.message_count = 0
        # 重新創建 manager
        self.manager = create_agent_system(
            llm_client=self.llm_client,
            enable_hitl=True,
            max_questions=5
        )
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
                        print("\n👋 再見！感謝使用 Agent V3！")
                        break
                    else:
                        print(f"❓ 未知指令: {cmd}\n輸入 /help 查看可用指令")
                        continue

                # 處理查詢
                print()  # 空行
                result = self.process(query)
                print(result)

            except KeyboardInterrupt:
                print("\n\n👋 再見！")
                break
            except Exception as e:
                print(f"\n❌ 錯誤: {e}")


def main():
    """主函數"""
    bot = ChatBotV3()
    bot.run()


if __name__ == "__main__":
    main()
