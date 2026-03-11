"""
驗證 PI 工具描述更新是否生效

直接讀取工具定義，不需要啟動 Manager
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_pi_tool_description():
    """檢查 get_pi_price 工具的描述"""
    print("=" * 60)
    print("🔍 驗證 PI 工具描述")
    print("=" * 60)

    # 直接讀取工具定義
    with open("core/tools/pi_tools.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 提取 get_pi_price 的 docstring
    import re
    match = re.search(
        r'@tool\s*def get_pi_price\(\).*?"""(.*?)"""',
        content,
        re.DOTALL
    )

    if match:
        docstring = match.group(1).strip()
        print("\n📝 get_pi_price 工具描述:")
        print("-" * 60)
        print(docstring)
        print("-" * 60)

        # 檢查關鍵詞
        checks = {
            "⚠️ 重要": "⚠️ 重要" in docstring,
            "不在 Binance": "Binance" in docstring or "主流交易所" in docstring,
            "必須使用此專用工具": "必須使用此專用工具" in docstring or "必須使用此工具" in docstring,
            "CoinGecko": "CoinGecko" in docstring,
        }

        print("\n✅ 關鍵檢查點:")
        all_passed = True
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'通過' if passed else '失敗'}")
            if not passed:
                all_passed = False

        return all_passed
    else:
        print("❌ 無法提取工具描述")
        return False


def check_crypto_price_tool_description():
    """檢查 get_crypto_price_tool 的描述"""
    print("\n" + "=" * 60)
    print("🔍 驗證 get_crypto_price_tool 工具描述")
    print("=" * 60)

    # 直接讀取工具定義
    with open("core/tools/crypto_modules/analysis.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 提取 get_crypto_price_tool 的 docstring
    import re
    match = re.search(
        r'@tool.*?def get_crypto_price_tool\(.*?\).*?"""(.*?)"""',
        content,
        re.DOTALL
    )

    if match:
        docstring = match.group(1).strip()
        print("\n📝 get_crypto_price_tool 工具描述:")
        print("-" * 60)
        print(docstring)
        print("-" * 60)

        # 檢查關鍵詞
        checks = {
            "⚠️ 此工具不支持 PI": "PI" in docstring and "不支持" in docstring,
            "請使用 get_pi_price": "get_pi_price" in docstring,
            "主流交易所": "Binance" in docstring or "主流交易所" in docstring,
        }

        print("\n✅ 關鍵檢查點:")
        all_passed = True
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'通過' if passed else '失敗'}")
            if not passed:
                all_passed = False

        return all_passed
    else:
        print("❌ 無法提取工具描述")
        return False


def main():
    print("\n🚀 開始驗證 PI 工具描述更新...")

    result1 = check_pi_tool_description()
    result2 = check_crypto_price_tool_description()

    print("\n" + "=" * 60)
    print("📊 驗證結果總結")
    print("=" * 60)

    if result1 and result2:
        print("✅ 所有工具描述已正確更新")
        print("\n📝 說明:")
        print("- get_pi_price: 說明了 PI 不在主流交易所，必須使用此工具")
        print("- get_crypto_price: 說明了不支持 PI，建議使用 get_pi_price")
        print("\n🔄 請重啟服務使修改生效:")
        print("   1. 停止當前運行的服務")
        print("   2. 重新啟動: python tests/test_interactive_user.py")
        print("   3. 輸入: pi network目前價格多少")
        return 0
    else:
        print("❌ 部分工具描述未正確更新")
        print("請檢查上述失敗項目")
        return 1


if __name__ == "__main__":
    sys.exit(main())
