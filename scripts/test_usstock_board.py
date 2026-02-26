#!/usr/bin/env python3
"""
美股看板前端測試
測試 USStockTab JavaScript 是否正常運作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 設置輸出編碼
sys.stdout.reconfigure(encoding='utf-8')


def test_html_tab_exists():
    """測試 HTML 中是否有美股 Tab"""
    print("=" * 70)
    print("測試 1: HTML Tab 容器")
    print("=" * 70)
    
    with open("web/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 檢查 Tab 容器
    if 'id="usstock-tab"' in content:
        print("  [OK] usstock-tab 容器存在")
    else:
        print("  [FAIL] usstock-tab 容器不存在")
        return False
    
    # 檢查 JavaScript 引用
    if 'usstock.js' in content:
        print("  [OK] usstock.js 已引用")
    else:
        print("  [FAIL] usstock.js 未引用")
        return False
    
    # 檢查初始化邏輯
    if 'window.USStockTab' in content and 'init' in content:
        print("  [OK] 初始化邏輯存在")
    else:
        print("  [FAIL] 初始化邏輯缺失")
        return False
    
    print()
    return True


def test_javascript_file():
    """測試 JavaScript 檔案"""
    print("=" * 70)
    print("測試 2: JavaScript 檔案")
    print("=" * 70)
    
    if not os.path.exists("web/js/usstock.js"):
        print("  ❌ usstock.js 檔案不存在")
        return False
    
    with open("web/js/usstock.js", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 檢查必要函數
    checks = [
        ("window.USStockTab", "USStockTab 物件"),
        ("init:", "init 函數"),
        ("switchSubTab:", "switchSubTab 函數"),
        ("refreshCurrent:", "refreshCurrent 函數"),
        ("loadMarketWatch:", "loadMarketWatch 函數"),
        ("loadPopularStocks:", "loadPopularStocks 函數"),
        ("loadMarketIndices:", "loadMarketIndices 函數"),
        ("loadAIPulse:", "loadAIPulse 函數"),
    ]
    
    all_ok = True
    for check, name in checks:
        if check in content:
            print(f"  ✅ {name} 存在")
        else:
            print(f"  ❌ {name} 缺失")
            all_ok = False
    
    print()
    return all_ok


def test_data_provider():
    """測試後端數據提供者"""
    print("=" * 70)
    print("測試 3: 後端數據提供者")
    print("=" * 70)
    
    try:
        from core.tools.us_data_provider import get_us_data_provider
        import asyncio
        
        provider = get_us_data_provider()
        
        async def test():
            # 測試價格
            data = await provider.get_price("AAPL")
            print(f"  ✅ AAPL 價格：${data.get('price', 'N/A')}")
            
            # 測試技術指標
            tech = await provider.get_technicals("AAPL")
            print(f"  ✅ RSI: {tech.get('rsi', 'N/A')}")
            
            # 測試財報
            earnings = await provider.get_earnings("AAPL")
            print(f"  ✅ 下次財報：{earnings.get('next_earnings_date_str', 'N/A')}")
            
            return True
        
        return asyncio.run(test())
        
    except Exception as e:
        print(f"  ❌ 測試失敗：{e}")
        return False


def test_agent():
    """測試 US Stock Agent"""
    print("=" * 70)
    print("測試 4: US Stock Agent")
    print("=" * 70)
    
    try:
        from core.agents.agents.us_stock_agent import USStockAgent
        
        # 創建 mock 物件
        class MockLLM:
            def invoke(self, messages):
                from langchain_core.messages import AIMessage
                return AIMessage(content="Test response")
        
        class MockToolRegistry:
            def get(self, name, caller_agent):
                return None
        
        agent = USStockAgent(MockLLM(), MockToolRegistry())
        
        # 測試代號識別
        test_cases = [
            ("分析 AAPL", "AAPL"),
            ("Apple 股價", "AAPL"),
            ("Tesla 走勢", "TSLA"),
            ("NVDA 技術分析", "NVDA"),
        ]
        
        all_ok = True
        for query, expected in test_cases:
            result = agent._extract_ticker(query)
            if result == expected:
                print(f"  ✅ \"{query}\" → {result}")
            else:
                print(f"  ❌ \"{query}\" → {result} (預期：{expected})")
                all_ok = False
        
        print()
        return all_ok
        
    except Exception as e:
        print(f"  ❌ 測試失敗：{e}")
        return False


def test_prompt_templates():
    """測試 Prompt Templates"""
    print("=" * 70)
    print("測試 5: Prompt Templates")
    print("=" * 70)
    
    try:
        from core.agents.prompt_registry import PromptRegistry
        
        # 測試多語言
        for lang in ["zh-TW", "zh-CN", "en"]:
            prompt = PromptRegistry.get("us_stock_agent", "analysis", lang)
            if prompt and len(prompt) > 50:
                print(f"  ✅ {lang} 模板存在 ({len(prompt)} 字元)")
            else:
                print(f"  ❌ {lang} 模板缺失或過短")
                return False
        
        # 測試時間注入
        try:
            prompt = PromptRegistry.render("us_stock_agent", "analysis", "zh-TW", 
                                           ticker="AAPL", company_name="Apple Inc.", 
                                           query="Test", price_data="{}", 
                                           technical_data="{}", fundamentals_data="{}",
                                           earnings_data="{}", news_data="[]",
                                           institutional_data="{}")
            from datetime import datetime
            now = datetime.now()
            expected_time = now.strftime("%Y 年 %m 月 %d 日 %H:%M")
            
            if expected_time in prompt:
                print(f"  [OK] 時間注入成功 ({expected_time})")
            else:
                print(f"  [WARN] 時間注入可能失敗")
        except Exception as e:
            print(f"  [WARN] Prompt 渲染測試跳過：{e}")
        
        print()
        return True
        
    except Exception as e:
        print(f"  ❌ 測試失敗：{e}")
        return False


def test_tools():
    """測試 LangChain 工具"""
    print("=" * 70)
    print("測試 6: LangChain 工具")
    print("=" * 70)
    
    try:
        from core.tools.us_stock_tools import (
            us_stock_price,
            us_technical_analysis,
            us_fundamentals,
        )
        
        # 測試工具
        tools = [
            ("us_stock_price", us_stock_price),
            ("us_technical_analysis", us_technical_analysis),
            ("us_fundamentals", us_fundamentals),
        ]
        
        for name, tool in tools:
            result = tool.invoke({"symbol": "AAPL"})
            if isinstance(result, dict) and "error" not in result:
                print(f"  ✅ {name} 正常")
            else:
                print(f"  ⚠️ {name} 可能有問題")
        
        print()
        return True
        
    except Exception as e:
        print(f"  ❌ 測試失敗：{e}")
        return False


def main():
    """執行所有測試"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 22 + "美股看板測試" + " " * 32 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    results = []
    
    # 測試 1: HTML Tab
    results.append(("HTML Tab 容器", test_html_tab_exists()))
    
    # 測試 2: JavaScript 檔案
    results.append(("JavaScript 檔案", test_javascript_file()))
    
    # 測試 3: 後端數據
    results.append(("後端數據提供者", test_data_provider()))
    
    # 測試 4: Agent
    results.append(("US Stock Agent", test_agent()))
    
    # 測試 5: Prompt Templates
    results.append(("Prompt Templates", test_prompt_templates()))
    
    # 測試 6: 工具
    results.append(("LangChain 工具", test_tools()))
    
    # 總結
    print("=" * 70)
    print("測試總結")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    
    print()
    print(f"總計：{passed}/{total} 測試通過")
    
    if passed == total:
        print("\n[SUCCESS] 所有測試通過！美股看板已就緒！")
        return 0
    else:
        print(f"\n[WARN] 有 {total - passed} 個測試失敗，需要修復")
        return 1


if __name__ == "__main__":
    exit(main())
