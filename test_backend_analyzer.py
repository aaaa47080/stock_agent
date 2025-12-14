"""
測試後台分析系統
驗證JSON輸出格式和交易決策功能
"""

import json
import os
from datetime import datetime
from backend_analyzer import BackendAnalyzer, run_backend_analysis, run_batch_backend_analysis

def test_single_symbol_analysis():
    """測試單一幣種分析功能"""
    print(">> 測試單一幣種分析功能")

    analyzer = BackendAnalyzer()

    try:
        # 測試一個較為常用的幣種，避免可能無法獲取的幣種
        result = analyzer.analyze_symbol("BTCUSDT", exchange="binance", interval="1h", limit=50)

        print(f"> 分析完成: {result['symbol']}")
        print(f"> 交易所: {result['exchange']}")
        print(f"> 當前價格: {result['current_price']}")

        # 檢查現貨決策
        spot = result['spot_decision']
        print(f"> 現貨是否交易: {spot['should_trade']}")
        print(f"> 現貨決策: {spot['decision']}")
        print(f"> 現貨部位大小: {spot['position_size']}")
        print(f"> 現貨槓桿: {spot['leverage']}")

        # 檢查合約決策
        futures = result['futures_decision']
        print(f"> 合約是否交易: {futures['should_trade']}")
        print(f"> 合約決策: {futures['decision']}")
        print(f"> 合約部位大小: {futures['position_size']}")
        print(f"> 合約槓桿: {futures['leverage']}")

        # 保存結果到JSON文件
        output_file = f"test_result_{result['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        analyzer.save_decision_to_json(result, output_file)

        # 驗證JSON結構
        validate_json_structure(result)

        print(f"> 測試結果已保存至: {output_file}")
        return True

    except Exception as e:
        print(f"> 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_batch_analysis():
    """測試批量分析功能"""
    print("\n>> 測試批量分析功能")

    try:
        # 使用常見的幾個幣種進行測試
        symbols = ["BTCUSDT", "ETHUSDT"]  # 只用2個幣種來加快測試

        results = run_batch_backend_analysis(
            symbols=symbols,
            exchange="binance",
            interval="1h",
            limit=50
        )

        print(f"> 批量分析完成，分析了 {len(results)} 個幣種")

        for result in results:
            print(f"  - {result['symbol']}: 現貨={result['spot_decision']['decision']}, "
                  f"合約={result['futures_decision']['decision']}")

        # 驗證每個結果的結構
        for result in results:
            validate_json_structure(result)

        print(f"> 所有結果結構驗證通過")
        return True

    except Exception as e:
        print(f"> 批量測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def validate_json_structure(result: dict):
    """驗證JSON結構是否符合預期"""
    required_keys = ['symbol', 'analysis_timestamp', 'exchange', 'current_price',
                     'spot_decision', 'futures_decision']

    for key in required_keys:
        assert key in result, f"缺少必要鍵值: {key}"

    # 驗證決策結構
    for decision_type in ['spot_decision', 'futures_decision']:
        decision = result[decision_type]
        required_decision_keys = ['should_trade', 'decision', 'action', 'position_size',
                                  'confidence', 'reasoning', 'entry_price', 'stop_loss',
                                  'take_profit', 'leverage', 'risk_level', 'market_type',
                                  'additional_params']

        for key in required_decision_keys:
            assert key in decision, f"{decision_type} 缺少必要鍵值: {key}"

    print(f"> JSON結構驗證通過: {result['symbol']}")


def test_json_output_format():
    """測試JSON輸出格式"""
    print("\n>> 測試JSON輸出格式")

    try:
        result = run_backend_analysis(
            symbol="BTCUSDT",
            exchange="binance",
            interval="1h",
            limit=30,
            output_file="test_json_format.json"
        )

        # 讀取生成的JSON文件並驗證
        with open("test_json_format.json", 'r', encoding='utf-8') as f:
            loaded_result = json.load(f)

        assert loaded_result['symbol'] == result['symbol']
        assert 'analysis_timestamp' in loaded_result
        assert 'spot_decision' in loaded_result
        assert 'futures_decision' in loaded_result

        print("> JSON文件讀寫測試通過")
        return True

    except Exception as e:
        print(f"> JSON格式測試失敗: {str(e)}")
        return False


def main():
    """主測試函數"""
    print(">> 開始後台分析系統測試")
    print("=" * 60)

    tests = [
        ("單一幣種分析", test_single_symbol_analysis),
        ("批量分析", test_batch_analysis),
        ("JSON格式測試", test_json_output_format),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n> 執行 {test_name}...")
        try:
            if test_func():
                print(f">> {test_name} - 通過")
                passed += 1
            else:
                print(f">> {test_name} - 失敗")
        except Exception as e:
            print(f">> {test_name} - 錯誤: {str(e)}")

    print("\n" + "=" * 60)
    print(f"測試完成: {passed}/{total} 個測試通過")

    if passed == total:
        print(">> 所有測試通過！後台分析系統運作正常。")
    else:
        print(">> 部分測試失敗，需要檢查問題。")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)