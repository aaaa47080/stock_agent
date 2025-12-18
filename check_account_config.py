"""檢查 OKX 賬戶配置,特別是持倉模式"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading.okx_api_connector import OKXAPIConnector

def check_account_config():
    """檢查賬戶配置"""
    print("="*60)
    print("檢查 OKX 賬戶配置")
    print("="*60)

    api = OKXAPIConnector()

    if not all([api.api_key, api.secret_key, api.passphrase]):
        print("[ERROR] OKX API credentials are not set.")
        return

    # 獲取賬戶配置
    print("\n[INFO] 獲取賬戶配置...")
    config_result = api.get_account_config()

    if config_result.get("code") == "0":
        config_data = config_result.get("data", [])
        if config_data:
            account_config = config_data[0]

            print("\n[SUCCESS] 賬戶配置信息:")
            print(f"  賬戶ID: {account_config.get('uid')}")
            print(f"  賬戶級別: {account_config.get('acctLv')}")
            print(f"  持倉模式 (posMode): {account_config.get('posMode')}")
            print(f"  自動借幣 (autoLoan): {account_config.get('autoLoan')}")

            # 重點檢查持倉模式
            pos_mode = account_config.get('posMode')
            print(f"\n[INFO] 當前持倉模式: {pos_mode}")

            if pos_mode == 'long_short_mode':
                print("  ✓ 雙向持倉模式 - 需要使用 posSide='long' 或 'short'")
            elif pos_mode == 'net_mode':
                print("  ✓ 單向持倉模式 - 不應該使用 posSide 參數,或使用 posSide='net'")
            else:
                print(f"  ? 未知的持倉模式: {pos_mode}")

            print(f"\n[RAW] 完整配置: {account_config}")
        else:
            print("[ERROR] No account config data returned")
    else:
        print(f"[ERROR] Failed to get account config: {config_result.get('msg')}")
        print(f"[RAW] Response: {config_result}")

if __name__ == "__main__":
    check_account_config()
