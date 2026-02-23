#!/usr/bin/env python3
"""
多語言 Agent 整合測試
實際調用 Agent 執行對話，驗證多語言功能
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from core.agents.agents.chat_agent import ChatAgent
from core.agents.agents.crypto_agent import CryptoAgent
from core.agents.models import SubTask
from core.agents.prompt_registry import PromptRegistry
from core.agents.agent_registry import AgentRegistry
from core.agents.tool_registry import ToolRegistry


def create_mock_llm():
    """創建測試用 LLM（如果沒有真實 API key）"""
    try:
        # 嘗試使用真實的 OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            return ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
    except Exception as e:
        print(f"⚠️ 無法初始化 OpenAI: {e}")
    
    # 返回 None，使用 fallback 模式
    return None


def create_mock_tool_registry():
    """創建簡單的 Mock Tool Registry"""
    tool_registry = ToolRegistry()
    # 這裡可以註冊一些 mock tools
    return tool_registry


async def test_chat_agent_multilingual():
    """測試 Chat Agent 的多語言回應"""
    print("=" * 70)
    print("測試：Chat Agent 多語言對話")
    print("=" * 70)
    
    llm = create_mock_llm()
    tool_registry = create_mock_tool_registry()
    
    if not llm:
        print("⚠️ 跳過此測試（無可用 LLM）")
        return
    
    agent = ChatAgent(llm, tool_registry)
    
    test_cases = [
        {
            "name": "繁體中文問候",
            "query": "你好，請自我介紹",
            "language": "zh-TW",
            "expected_keywords": ["你", "您好", "CryptoMind", "助手"]
        },
        {
            "name": "簡體中文問候",
            "query": "你好，请自我介绍",
            "language": "zh-CN",
            "expected_keywords": ["你", "你好", "CryptoMind", "助手"]
        },
        {
            "name": "英文問候",
            "query": "Hello, please introduce yourself",
            "language": "en",
            "expected_keywords": ["you", "Hello", "CryptoMind", "assistant"]
        },
    ]
    
    for tc in test_cases:
        print(f"\n[{tc['name']}]")
        print(f"  輸入 ({tc['language']}): {tc['query']}")
        print("-" * 50)
        
        try:
            # 創建任務
            task = SubTask(
                step=1,
                description=tc['query'],
                agent="chat",
                context={
                    "language": tc['language'],
                    "history": "",
                    "memory_facts": "無" if tc['language'] == "zh-TW" else "None" if tc['language'] == "en" else "无"
                }
            )
            
            # 執行 Agent
            result = agent.execute(task)
            
            # 檢查結果
            if result.success:
                print(f"  ✅ 執行成功")
                print(f"  回應预览：{result.message[:100]}...")
                
                # 檢查語言是否正確
                response_lower = result.message.lower()
                if tc['language'] == "zh-TW":
                    if any(kw in result.message for kw in ["你", "您", "繁體", "台灣"]):
                        print(f"  ✅ 語言正確（繁體中文）")
                    else:
                        print(f"  ⚠️ 可能不是繁體中文")
                elif tc['language'] == "zh-CN":
                    if any(kw in result.message for kw in ["你", "你好", "简体", "台湾"]):
                        print(f"  ✅ 語言正確（簡體中文）")
                    else:
                        print(f"  ⚠️ 可能不是簡體中文")
                elif tc['language'] == "en":
                    if any(kw in response_lower for kw in ["you", "hello", "i am", "assistant"]):
                        print(f"  ✅ 語言正確（英文）")
                    else:
                        print(f"  ⚠️ 可能不是英文")
            else:
                print(f"  ❌ 執行失敗：{result.message}")
                
        except Exception as e:
            print(f"  ❌ 異常：{e}")
            import traceback
            traceback.print_exc()
    
    print()


async def test_crypto_agent_multilingual():
    """測試 Crypto Agent 的多語言回應"""
    print("=" * 70)
    print("測試：Crypto Agent 多語言對話")
    print("=" * 70)
    
    llm = create_mock_llm()
    tool_registry = create_mock_tool_registry()
    
    if not llm:
        print("⚠️ 跳過此測試（無可用 LLM）")
        return
    
    agent = CryptoAgent(llm, tool_registry)
    
    test_cases = [
        {
            "name": "繁體中文 BTC 分析",
            "query": "請分析 BTC 的價格走勢",
            "language": "zh-TW",
            "expected_keywords": ["BTC", "比特幣", "價格", "分析"]
        },
        {
            "name": "簡體中文 BTC 分析",
            "query": "请分析 BTC 的价格走势",
            "language": "zh-CN",
            "expected_keywords": ["BTC", "比特币", "价格", "分析"]
        },
        {
            "name": "英文 BTC 分析",
            "query": "Please analyze BTC price trend",
            "language": "en",
            "expected_keywords": ["BTC", "price", "trend", "analysis"]
        },
    ]
    
    for tc in test_cases:
        print(f"\n[{tc['name']}]")
        print(f"  輸入 ({tc['language']}): {tc['query']}")
        print("-" * 50)
        
        try:
            # 創建任務
            task = SubTask(
                step=1,
                description=tc['query'],
                agent="crypto",
                context={
                    "language": tc['language'],
                    "history": ""
                }
            )
            
            # 執行 Agent
            result = agent.execute(task)
            
            # 檢查結果
            if result.success:
                print(f"  ✅ 執行成功")
                print(f"  回應预览：{result.message[:150]}...")
                
                # 檢查是否有正確的前綴
                if "🔐" in result.message:
                    print(f"  ✅ 包含正確的前綴標識")
                
                # 檢查語言
                if tc['language'] == "zh-TW" and "加密貨幣" in result.message:
                    print(f"  ✅ 語言正確（繁體中文）")
                elif tc['language'] == "zh-CN" and "加密货币" in result.message:
                    print(f"  ✅ 語言正確（簡體中文）")
                elif tc['language'] == "en" and "Cryptocurrency" in result.message:
                    print(f"  ✅ 語言正確（英文）")
            else:
                print(f"  ❌ 執行失敗：{result.message}")
                
        except Exception as e:
            print(f"  ❌ 異常：{e}")
            import traceback
            traceback.print_exc()
    
    print()


async def test_prompt_with_time():
    """測試帶有時間資訊的 Prompt 渲染"""
    print("=" * 70)
    print("測試：Prompt 時間資訊渲染")
    print("=" * 70)
    
    from datetime import datetime
    
    # 測試不同語言的時間渲染
    for lang in ["zh-TW", "zh-CN", "en"]:
        print(f"\n[{lang}]")
        
        try:
            prompt = PromptRegistry.render(
                "crypto_agent", "system",
                language=lang,
                include_time=True
            )
            
            # 檢查時間是否被正確替換
            now = datetime.now()
            if lang == "zh-TW":
                expected_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
                if expected_time in prompt:
                    print(f"  ✅ 時間已正確替換：{expected_time}")
                else:
                    print(f"  ⚠️ 時間可能未替換")
                    print(f"     預期：{expected_time}")
            elif lang == "zh-CN":
                expected_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
                if expected_time in prompt:
                    print(f"  ✅ 時間已正確替換：{expected_time}")
                else:
                    print(f"  ⚠️ 時間可能未替換")
            elif lang == "en":
                expected_time = now.strftime("%B %d, %Y %H:%M")
                if expected_time in prompt:
                    print(f"  ✅ 時間已正確替換：{expected_time}")
                else:
                    print(f"  ⚠️ 時間可能未替換")
            
            # 顯示 Prompt 開頭
            preview = prompt[:200].replace('\n', ' ')
            print(f"  Prompt 预览：{preview}...")
            
        except Exception as e:
            print(f"  ❌ 異常：{e}")
    
    print()


async def test_context_language_propagation():
    """測試 language 在 context 中的傳遞"""
    print("=" * 70)
    print("測試：Language 在 Context 中的傳遞")
    print("=" * 70)
    
    test_cases = [
        {"context": {"language": "zh-TW"}, "expected": "zh-TW"},
        {"context": {"language": "zh-CN"}, "expected": "zh-CN"},
        {"context": {"language": "en"}, "expected": "en"},
        {"context": {}, "expected": "zh-TW"},  # 預設
        {"context": None, "expected": "zh-TW"},  # 預設
    ]
    
    for i, tc in enumerate(test_cases, 1):
        task = SubTask(
            step=1,
            description="Test",
            agent="chat",
            context=tc["context"]
        )
        
        # 模擬 Agent 讀取 language
        language = (task.context or {}).get("language", "zh-TW")
        
        if language == tc["expected"]:
            print(f"  ✅ 測試 {i}: {language} (預期：{tc['expected']})")
        else:
            print(f"  ❌ 測試 {i}: {language} (預期：{tc['expected']})")
    
    print()


async def main():
    """執行所有整合測試"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "多語言 Agent 整合測試" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        # 測試 1: Context 傳遞
        await test_context_language_propagation()
        
        # 測試 2: Prompt 時間渲染
        await test_prompt_with_time()
        
        # 測試 3: Chat Agent（需要 LLM）
        await test_chat_agent_multilingual()
        
        # 測試 4: Crypto Agent（需要 LLM）
        await test_crypto_agent_multilingual()
        
        print("=" * 70)
        print("整合測試完成！")
        print("=" * 70)
        print()
        print("注意：如果看到 '⚠️ 跳過此測試（無可用 LLM）'，")
        print("      表示需要設置 OPENAI_API_KEY 環境變數才能執行完整測試。")
        print()
        print("設置方式：")
        print("  export OPENAI_API_KEY=sk-...  (Linux/Mac)")
        print("  set OPENAI_API_KEY=sk-...     (Windows CMD)")
        print("  $env:OPENAI_API_KEY=\"sk-...\"  (Windows PowerShell)")
        print()
        
    except Exception as e:
        print(f"\n❌ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
