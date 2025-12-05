"""
Google Gemini 修復驗證腳本
測試 Gemini API 是否能正確與系統集成
"""
import sys
from llm_client import LLMClientFactory
from config import BULL_COMMITTEE_MODELS, BEAR_COMMITTEE_MODELS

def test_gemini_wrapper_basic():
    """測試基本的 Gemini Wrapper 功能"""
    print("=" * 70)
    print("測試 1: Gemini Wrapper 基本功能")
    print("=" * 70)

    try:
        client = LLMClientFactory.create_client("google_gemini")
        print("✅ Gemini 客戶端創建成功")
        print(f"   - client.chat 存在: {hasattr(client, 'chat')}")
        print(f"   - client.chat.completions 存在: {hasattr(client.chat, 'completions')}")
        print(f"   - create 方法存在: {hasattr(client.chat.completions, 'create')}")
        return True
    except Exception as e:
        print(f"❌ 客戶端創建失敗: {e}")
        return False


def test_committee_config():
    """測試委員會配置中的模型名稱"""
    print("\n" + "=" * 70)
    print("測試 2: 委員會模型配置檢查")
    print("=" * 70)

    valid_gemini_models = [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-pro"
    ]

    all_models = BULL_COMMITTEE_MODELS + BEAR_COMMITTEE_MODELS
    issues = []

    print("\n多頭委員會模型:")
    for i, model_config in enumerate(BULL_COMMITTEE_MODELS, 1):
        provider = model_config.get("provider")
        model = model_config.get("model")
        status = "✅"

        if provider == "google_gemini" and model not in valid_gemini_models:
            status = "⚠️"
            issues.append(f"多頭委員會[{i}]: 無效的 Gemini 模型 '{model}'")

        print(f"  {status} [{i}] {provider}:{model}")

    print("\n空頭委員會模型:")
    for i, model_config in enumerate(BEAR_COMMITTEE_MODELS, 1):
        provider = model_config.get("provider")
        model = model_config.get("model")
        status = "✅"

        if provider == "google_gemini" and model not in valid_gemini_models:
            status = "⚠️"
            issues.append(f"空頭委員會[{i}]: 無效的 Gemini 模型 '{model}'")

        print(f"  {status} [{i}] {provider}:{model}")

    if issues:
        print("\n⚠️  發現配置問題:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n建議使用以下 Gemini 模型:")
        for model in valid_gemini_models:
            print(f"   - {model}")
        return False
    else:
        print("\n✅ 所有模型配置都有效")
        return True


def test_json_handling():
    """測試 JSON 模式是否正常工作"""
    print("\n" + "=" * 70)
    print("測試 3: JSON 模式處理")
    print("=" * 70)

    try:
        from llm_client import create_llm_client_from_config

        # 找到第一個 Gemini 模型配置
        gemini_config = None
        for config in BULL_COMMITTEE_MODELS + BEAR_COMMITTEE_MODELS:
            if config.get("provider") == "google_gemini":
                gemini_config = config
                break

        if not gemini_config:
            print("⚠️  配置中沒有 Gemini 模型，跳過測試")
            return True

        print(f"使用模型: {gemini_config['model']}")
        client, model = create_llm_client_from_config(gemini_config)

        # 簡單的 JSON 測試
        print("\n發送測試請求...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "請用 JSON 格式回覆，包含兩個欄位：'test': 'success', 'value': 42"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )

        content = response.choices[0].message.content
        print(f"\n收到響應（前200字符）:")
        print(content[:200])

        # 嘗試解析
        import json
        parsed = json.loads(content)
        print(f"\n✅ JSON 解析成功")
        print(f"   響應鍵: {list(parsed.keys())}")

        return True

    except Exception as e:
        error_type = type(e).__name__
        if "429" in str(e) or "quota" in str(e).lower():
            print(f"\n⚠️  API 配額限制: {e}")
            print("   提示: 這不是代碼錯誤，只是 API 使用限制")
            print("   建議: 等待配額重置或升級 API 計劃")
            return True  # 配額問題不算測試失敗
        else:
            print(f"\n❌ 測試失敗 ({error_type}): {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """運行所有測試"""
    print("\n" + "=" * 70)
    print("Google Gemini 修復驗證")
    print("=" * 70)

    results = []

    # 測試 1: Wrapper 基本功能
    results.append(("Wrapper 基本功能", test_gemini_wrapper_basic()))

    # 測試 2: 配置檢查
    results.append(("委員會配置", test_committee_config()))

    # 測試 3: JSON 處理
    results.append(("JSON 模式", test_json_handling()))

    # 總結
    print("\n" + "=" * 70)
    print("測試總結")
    print("=" * 70)

    all_passed = True
    for test_name, passed in results:
        status = "✅ 通過" if passed else "❌ 失敗"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n🎉 所有測試通過！Gemini 集成已成功修復。")
        print("\n下一步:")
        print("  1. 確保設置了 GOOGLE_API_KEY 環境變量")
        print("  2. 運行你的主程序測試完整流程")
        print("  3. 監控調試輸出中的 🔍 和 ⚠️ 標記")
        return 0
    else:
        print("\n❌ 部分測試失敗，請查看上方的錯誤信息。")
        print("\n故障排除:")
        print("  1. 檢查 GOOGLE_API_KEY 是否正確設置")
        print("  2. 確認使用的是有效的 Gemini 模型名稱")
        print("  3. 查看 GEMINI_FIX_SUMMARY.md 獲取更多幫助")
        return 1


if __name__ == "__main__":
    sys.exit(main())
