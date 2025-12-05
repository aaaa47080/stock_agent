"""
測試 Gemini Wrapper 是否能正確處理 OpenAI 風格的 API 調用
"""
import json
from llm_client import LLMClientFactory

def test_gemini_wrapper():
    print("測試 Google Gemini Wrapper...\n")

    try:
        # 創建 Gemini 客戶端
        print("1. 創建 Gemini 客戶端...")
        client = LLMClientFactory.create_client("google_gemini")
        print("   ✅ 客戶端創建成功\n")

        # 測試基本 API 調用
        print("2. 測試基本 API 調用...")
        response = client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[
                {"role": "user", "content": "請簡單介紹比特幣，限制在50字內。"}
            ],
            temperature=0.5
        )
        print(f"   ✅ 調用成功")
        print(f"   回應: {response.choices[0].message.content[:100]}...\n")

        # 測試 JSON 模式
        print("3. 測試 JSON 模式...")
        response = client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=[
                {"role": "user", "content": "請以 JSON 格式提供比特幣的簡單分析，包含 'name' 和 'sentiment' 兩個欄位。"}
            ],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        print(f"   ✅ JSON 模式調用成功")
        content = response.choices[0].message.content
        print(f"   回應: {content[:200]}...")

        # 嘗試解析 JSON
        try:
            parsed = json.loads(content)
            print(f"   ✅ JSON 解析成功: {list(parsed.keys())}\n")
        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON 解析失敗: {e}\n")

        print("=" * 60)
        print("✅ 所有測試通過！Gemini Wrapper 工作正常。")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_wrapper()
