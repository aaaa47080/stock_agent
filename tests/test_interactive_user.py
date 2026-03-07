"""
互動式使用者測試 - 模擬真實使用者操作

使用方式:
    python tests/test_interactive_user.py

特色:
- 即時輸入問題，像真實使用者一樣測試
- 支援單輪、多輪、淺到深的問題
- 自動記錄對話歷史
- 測試完成後自動儲存結果
"""
import os
import sys
import asyncio
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils.settings import Settings  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results")


class InteractiveSession:
    """互動式測試 Session"""
    
    def __init__(self, manager, session_id: str):
        self.manager = manager
        self.session_id = session_id
        self.history = []
        self.conversation_log = []
        self.pending_hitl = None
        self.round_count = 0
    
    async def send(self, message: str, is_resume: bool = False) -> dict:
        """發送訊息"""
        from langgraph.types import Command
        
        config = {"configurable": {"thread_id": self.session_id}}
        history_text = "\n".join(self.history[-12:]) if self.history else ""
        
        self.round_count += 1
        start_time = time.time()
        
        # 判斷是否為確認詞
        confirm_keywords = ["好", "確認", "執行", "同意", "可以", "ok", "OK", "Yes", "yes", "開始", "請執行"]
        is_confirm_message = any(kw in message for kw in confirm_keywords)
        
        if is_resume and self.pending_hitl and is_confirm_message:
            graph_input = Command(resume=message)
            self.pending_hitl = None
        else:
            if self.pending_hitl:
                self.pending_hitl = None
            graph_input = {
                "session_id": self.session_id,
                "query": message,
                "history": history_text,
                "language": "zh-TW",
            }
        
        result = await self.manager.graph.ainvoke(graph_input, config)
        duration = time.time() - start_time
        
        self.history.append(f"使用者: {message}")
        
        interrupt_events = result.get("__interrupt__", [])
        hitl_data = None
        if interrupt_events:
            hitl_data = interrupt_events[0].value
            self.pending_hitl = hitl_data
        
        response = result.get("final_response", "無回應")
        if response and response != "無回應":
            self.history.append(f"助手: {response[:400]}...")
        
        log_entry = {
            "round": self.round_count,
            "user": message,
            "assistant": response,
            "mode": result.get("execution_mode", "unknown"),
            "hitl": hitl_data,
            "duration": round(duration, 2),
            "is_resume": is_resume,
        }
        self.conversation_log.append(log_entry)
        
        return log_entry
    
    def print_round(self, result: dict):
        """印出單輪結果"""
        print(f"\n{'─' * 60}")
        print(f"[第 {result['round']} 輪] ⏱️ {result['duration']}s | 模式: {result['mode']}")
        print(f"{'─' * 60}")
        
        if result['hitl']:
            print("📋 系統規劃了以下任務，需要確認：")
            for task in result['hitl'].get('plan', []):
                print(f"   • [{task['agent']}] {task['name']}")
            print("\n💬 輸入「好」、「確認」、「執行」來執行，或輸入其他問題修改計劃")
        else:
            print(f"🤖 {result['assistant']}")
    
    def save_results(self):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"interactive_test_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        result = {
            "scenario": "interactive_user_test",
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "conversation": self.conversation_log,
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 測試結果已儲存: {filepath}")
        return filepath


def print_banner():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "🎮 互動式使用者測試模式" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    print("📝 測試指南：")
    print("   • 單輪問題：直接輸入問題，如「BTC 多少錢？」")
    print("   • 多輪對話：連續問相關問題，測試上下文記憶")
    print("   • 深入追問：從簡單問題開始，逐步深入細節")
    print("   • 跨主題：中途切換話題，測試狀態管理")
    print()
    print("⚡ 指令：")
    print("   • 輸入 'quit' 或 'exit' 結束測試")
    print("   • 輸入 'save' 儲存當前對話")
    print("   • 輸入 'clear' 開始新對話")
    print()


async def interactive_test():
    """互動式測試主程式"""
    
    if not Settings.ENABLE_MANAGER_V2:
        print("❌ 請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return
    
    from core.agents.bootstrap_v2 import bootstrap_v2
    from utils.user_client_factory import create_user_llm_client
    
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 缺少 API Key")
        return
    
    provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
    print(f"\n🔧 初始化 LLM ({provider})...")
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )
    
    print("🔧 初始化 ManagerAgent V2...")
    manager = bootstrap_v2(llm, web_mode=False, language="zh-TW")
    
    print_banner()
    
    # 建立新的 session
    session = InteractiveSession(manager, f"interactive_{int(time.time())}")
    
    print("🚀 開始互動測試！請輸入您的問題：\n")
    
    while True:
        try:
            # 取得使用者輸入
            user_input = input("👤 你: ").strip()
            
            if not user_input:
                continue
            
            # 處理指令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 結束測試...")
                session.save_results()
                break
            
            if user_input.lower() == 'save':
                session.save_results()
                continue
            
            if user_input.lower() == 'clear':
                print("\n🔄 開始新對話...")
                session.save_results()
                session = InteractiveSession(manager, f"interactive_{int(time.time())}")
                continue
            
            if user_input.lower() == 'help':
                print_banner()
                continue
            
            # 發送訊息
            is_resume = session.pending_hitl is not None
            result = await session.send(user_input, is_resume=is_resume)
            session.print_round(result)
            
        except KeyboardInterrupt:
            print("\n\n👋 測試中斷，儲存結果...")
            session.save_results()
            break
        except Exception as e:
            print(f"\n❌ 錯誤: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(interactive_test())
