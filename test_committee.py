"""
測試委員會模式
驗證多模型委員會辯論功能
"""

import sys
from model_parser import parse_model_string, parse_committee_models, print_config_summary

def test_model_parsing():
    """測試模型字符串解析"""
    print("\n" + "="*70)
    print("🧪 測試 1: 模型字符串解析")
    print("="*70)

    test_cases = [
        "openai:gpt-4o",
        "openai:o4-mini",
        "openrouter:anthropic/claude-3.5-sonnet",
        "openrouter:google/gemini-pro-1.5",
    ]

    for case in test_cases:
        try:
            result = parse_model_string(case)
            print(f"\n✅ {case}")
            print(f"   Provider: {result['provider']}")
            print(f"   Model: {result['model']}")
            print(f"   Name: {result['name']}")
        except Exception as e:
            print(f"\n❌ {case}")
            print(f"   Error: {e}")
            return False

    return True

def test_committee_parsing():
    """測試委員會模型列表解析"""
    print("\n" + "="*70)
    print("🧪 測試 2: 委員會模型列表解析")
    print("="*70)

    committee_models = [
        "openai:gpt-4o",
        "openrouter:anthropic/claude-3.5-sonnet",
        "openrouter:google/gemini-pro-1.5",
    ]

    try:
        result = parse_committee_models(committee_models)
        print(f"\n✅ 成功解析 {len(result)} 個委員會成員:")
        for i, model in enumerate(result, 1):
            print(f"   {i}. {model['name']} ({model['provider']})")
        return True
    except Exception as e:
        print(f"\n❌ 解析失敗: {e}")
        return False

def test_config_loading():
    """測試配置加載"""
    print("\n" + "="*70)
    print("🧪 測試 3: 配置文件加載")
    print("="*70)

    try:
        from model_parser import load_simple_config
        config = load_simple_config()

        print(f"\n✅ 配置加載成功")
        print(f"   多模型辯論: {'啟用' if config['enable_multi_model'] else '停用'}")
        print(f"   委員會模式: {'啟用' if config['enable_committee'] else '停用'}")

        if config['enable_committee']:
            print(f"   多頭委員會: {len(config['bull_committee'])} 位專家")
            print(f"   空頭委員會: {len(config['bear_committee'])} 位專家")

        return True
    except Exception as e:
        print(f"\n❌ 配置加載失敗: {e}")
        return False

def test_graph_integration():
    """測試 graph.py 集成"""
    print("\n" + "="*70)
    print("🧪 測試 4: Graph 工作流集成")
    print("="*70)

    try:
        # 嘗試導入 graph 模組
        import graph
        print("\n✅ graph.py 導入成功")

        # 檢查 research_debate_node 函數存在
        if hasattr(graph, 'research_debate_node'):
            print("✅ research_debate_node 函數存在")
        else:
            print("❌ research_debate_node 函數不存在")
            return False

        # 檢查 workflow 已編譯
        if hasattr(graph, 'app'):
            print("✅ LangGraph workflow 已編譯")
        else:
            print("❌ LangGraph workflow 未編譯")
            return False

        return True
    except Exception as e:
        print(f"\n❌ Graph 集成測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """運行所有測試"""
    print("\n🚀 開始委員會模式測試套件")
    print("="*70)

    tests = [
        ("模型解析", test_model_parsing),
        ("委員會解析", test_committee_parsing),
        ("配置加載", test_config_loading),
        ("Graph集成", test_graph_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 測試 '{name}' 發生異常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 總結
    print("\n" + "="*70)
    print("📊 測試總結")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}: {name}")

    print("\n" + "-"*70)
    print(f"通過: {passed}/{total} ({passed/total*100:.1f}%)")
    print("="*70)

    # 打印當前配置摘要
    print_config_summary()

    if passed == total:
        print("\n🎉 所有測試通過！委員會模式已準備就緒。")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 個測試失敗，請檢查上述錯誤訊息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
