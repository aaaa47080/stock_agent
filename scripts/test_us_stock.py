#!/usr/bin/env python3
"""
美股功能整合測試
測試 Yahoo Finance 數據層、工具集、Agent 的完整功能
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tools.us_data_provider import get_us_data_provider
from core.tools.us_stock_tools import (
    us_stock_price,
    us_technical_analysis,
    us_fundamentals,
    us_earnings,
    us_news,
)
from core.agents.agents.us_stock_agent import USStockAgent
from core.agents.models import SubTask
from langchain_openai import ChatOpenAI


def test_data_provider():
    """測試數據提供者"""
    print("=" * 70)
    print("測試 1: Yahoo Finance 數據提供者")
    print("=" * 70)
    
    provider = get_us_data_provider()
    
    async def run_tests():
        # 測試價格
        print("\n[1.1] 測試價格數據 (AAPL)")
        try:
            data = await provider.get_price("AAPL")
            print(f"  ✅ 價格：${data.get('price', 'N/A')}")
            print(f"  ✅ 漲跌：{data.get('change', 0):+.2f} ({data.get('change_percent', 0):+.2f}%)")
            print(f"  ✅ 成交量：{data.get('volume', 'N/A'):,}")
            print(f"  ✅ 市值：${data.get('market_cap', 0):,}")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
        
        # 測試技術指標
        print("\n[1.2] 測試技術指標 (AAPL)")
        try:
            data = await provider.get_technicals("AAPL")
            print(f"  ✅ RSI: {data.get('rsi', 'N/A')}")
            print(f"  ✅ MACD: {data.get('macd', 'N/A')}")
            print(f"  ✅ 綜合訊號：{data.get('summary', 'N/A')}")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
        
        # 測試基本面
        print("\n[1.3] 測試基本面數據 (AAPL)")
        try:
            data = await provider.get_fundamentals("AAPL")
            print(f"  ✅ P/E: {data.get('pe_ratio', 'N/A')}")
            print(f"  ✅ EPS: {data.get('eps', 'N/A')}")
            print(f"  ✅ ROE: {data.get('roe', 'N/A')}")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
        
        # 測試新聞
        print("\n[1.4] 測試新聞獲取 (AAPL)")
        try:
            data = await provider.get_news("AAPL", limit=3)
            print(f"  ✅ 獲取 {len(data)} 則新聞")
            if data:
                print(f"  ✅ 最新：{data[0].get('title', 'N/A')}")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
        
        # 測試財報
        print("\n[1.5] 測試財報數據 (AAPL)")
        try:
            data = await provider.get_earnings("AAPL")
            print(f"  ✅ 下次財報：{data.get('next_earnings_date_str', 'N/A')}")
            print(f"  ✅ 財報歷史：{len(data.get('earnings_history', []))} 筆")
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
    
    asyncio.run(run_tests())
    print()


def test_tools():
    """測試 LangChain 工具"""
    print("=" * 70)
    print("測試 2: LangChain 工具")
    print("=" * 70)
    
    tools = [
        ("us_stock_price", us_stock_price, {"symbol": "AAPL"}),
        ("us_technical_analysis", us_technical_analysis, {"symbol": "AAPL"}),
        ("us_fundamentals", us_fundamentals, {"symbol": "AAPL"}),
        ("us_news", us_news, {"symbol": "AAPL", "limit": 2}),
    ]
    
    for name, tool, args in tools:
        print(f"\n[{name}]")
        try:
            result = tool.invoke(args)
            if isinstance(result, dict):
                if "error" in result:
                    print(f"  ❌ 錯誤：{result['error']}")
                else:
                    print(f"  ✅ 成功獲取數據")
            elif isinstance(result, list):
                print(f"  ✅ 獲取 {len(result)} 筆數據")
        except Exception as e:
            print(f"  ❌ 異常：{e}")
    
    print()


def test_agent():
    """測試 US Stock Agent"""
    print("=" * 70)
    print("測試 3: US Stock Agent")
    print("=" * 70)
    
    # 檢查是否有 OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  ⚠️ 跳過此測試（無 OPENAI_API_KEY 環境變數）")
        print("  設置方式：")
        print("    export OPENAI_API_KEY=sk-...  (Linux/Mac)")
        print("    set OPENAI_API_KEY=sk-...     (Windows CMD)")
        print("    $env:OPENAI_API_KEY=\"sk-...\"  (Windows PowerShell)")
        print()
        return
    
    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
        
        # 創建 mock tool registry
        from core.agents.tool_registry import ToolRegistry
        tool_registry = ToolRegistry()
        
        # 註冊美股工具
        from core.tools.us_stock_tools import register_us_stock_tools
        register_us_stock_tools(tool_registry)
        
        # 創建 Agent
        agent = USStockAgent(llm, tool_registry)
        
        # 測試用例
        test_cases = [
            {
                "name": "繁體中文 - AAPL 分析",
                "query": "請分析 AAPL 的投資價值",
                "language": "zh-TW",
            },
            {
                "name": "簡體中文 - 特斯拉分析",
                "query": "请分析特斯拉的投资价值",
                "language": "zh-CN",
            },
            {
                "name": "英文 - NVDA Analysis",
                "query": "Please analyze NVDA for investment",
                "language": "en",
            },
        ]
        
        for tc in test_cases:
            print(f"\n[{tc['name']}]")
            print(f"  輸入 ({tc['language']}): {tc['query']}")
            print("-" * 50)
            
            task = SubTask(
                step=1,
                description=tc['query'],
                agent="us_stock",
                context={
                    "language": tc['language'],
                    "history": "",
                }
            )
            
            try:
                result = agent.execute(task)
                if result.success:
                    print(f"  ✅ 執行成功")
                    print(f"  回應预览：{result.message[:150]}...")
                    
                    # 檢查語言
                    if tc['language'] == "zh-TW" and "美股分析" in result.message:
                        print(f"  ✅ 語言正確（繁體中文）")
                    elif tc['language'] == "zh-CN" and "美股分析" in result.message:
                        print(f"  ✅ 語言正確（簡體中文）")
                    elif tc['language'] == "en" and "US Stock Analysis" in result.message:
                        print(f"  ✅ 語言正確（英文）")
                else:
                    print(f"  ❌ 執行失敗：{result.message}")
            except Exception as e:
                print(f"  ❌ 異常：{e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"  ⚠️ 測試失敗：{e}")
    
    print()


def test_ticker_extraction():
    """測試股票代號識別"""
    print("=" * 70)
    print("測試 4: 股票代號識別")
    print("=" * 70)
    
    from core.agents.agents.us_stock_agent import USStockAgent
    
    # 創建 mock agent
    class MockLLM:
        def invoke(self, messages):
            pass
    
    class MockToolRegistry:
        def get(self, name, caller_agent):
            return None
    
    agent = USStockAgent(MockLLM(), MockToolRegistry())
    
    test_cases = [
        ("分析 AAPL", "AAPL"),
        ("Apple 股價如何", "AAPL"),
        ("微軟股票值得買嗎", "MSFT"),
        ("Tesla 走勢", "TSLA"),
        ("NVDA 技術分析", "NVDA"),
        ("Google 母公司", "GOOGL"),
        ("Unknown word", "UNKNOWN"),
    ]
    
    for query, expected in test_cases:
        result = agent._extract_ticker(query)
        status = "✅" if result == expected else "❌"
        print(f"  {status} \"{query}\" → {result} (預期：{expected})")
    
    print()


def main():
    """執行所有測試"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "美股功能整合測試" + " " * 30 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        # 測試 1: 數據提供者
        test_data_provider()
        
        # 測試 2: 工具
        test_tools()
        
        # 測試 3: 代號識別
        test_ticker_extraction()
        
        # 測試 4: Agent（需要 API Key）
        test_agent()
        
        print("=" * 70)
        print("測試完成！")
        print("=" * 70)
        print()
        
    except Exception as e:
        print(f"\n❌ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
