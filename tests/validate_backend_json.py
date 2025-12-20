"""
驗證後台分析 JSON 輸出功能的腳本
"""
import json
import os
from datetime import datetime
from analysis.async_backend_analyzer import AsyncBackendAnalyzer

def validate_backend_json_output():
    """驗證後台分析系統的 JSON 輸出功能"""
    print("🔍 驗證後台分析 JSON 輸出功能...")
    
    analyzer = AsyncBackendAnalyzer()
    
    # 執行分析
    result = analyzer.analyze_symbol("BTCUSDT", exchange="binance", interval="1h", limit=30)
    
    # 驗證輸出結構
    required_keys = ['symbol', 'analysis_timestamp', 'exchange', 'current_price', 
                     'spot_decision', 'futures_decision']
    
    print(f"📊 驗證基本結構...")
    for key in required_keys:
        assert key in result, f"遺漏必要鍵值: {key}"
        print(f"  ✅ {key}: {type(result[key]).__name__}")
    
    # 驗證決策結構
    print(f"📊 驗證決策結構...")
    for market_type in ['spot_decision', 'futures_decision']:
        decision = result[market_type]
        decision_required_keys = [
            'should_trade', 'decision', 'action', 'position_size_percentage', 
            'confidence', 'reasoning', 'entry_price', 'stop_loss', 
            'take_profit', 'leverage', 'risk_level', 'market_type',
            'additional_params'
        ]
        
        for key in decision_required_keys:
            assert key in decision, f"{market_type} 遺漏必要鍵值: {key}"
            print(f"  ✅ {market_type}['{key}']: {type(decision[key]).__name__}")
    
    # 驗證額外參數結構
    print(f"📊 驗證額外參數結構...")
    for market_type in ['spot_decision', 'futures_decision']:
        additional_params = result[market_type]['additional_params']
        assert isinstance(additional_params, dict), f"{market_type} 額外參數必須是字典"
        print(f"  ✅ {market_type}['additional_params']: 字典結構")
    
    # 儲存 JSON 文件
    print(f"💾 儲存 JSON 輸出...")
    output_file = f"validation_result_{result['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    analyzer.save_decision_to_json(result, output_file)
    
    # 驗證 JSON 文件可讀取
    print(f"📊 驻載 JSON 文件...")
    with open(output_file, 'r', encoding='utf-8') as f:
        loaded_result = json.load(f)
    
    assert loaded_result['symbol'] == result['symbol']
    print(f"  ✅ JSON 讀寫驗證成功")
    
    print(f"✅ 後台分析 JSON 輸出驗證完成！")
    print(f"📈 分析結果：")
    print(f"   - 幣種: {result['symbol']}")
    print(f"   - 交易所: {result['exchange']}")
    print(f"   - 當前價格: {result['current_price']}")
    print(f"   - 現貨決策: {result['spot_decision']['decision']} (信心度: {result['spot_decision']['confidence']:.1f}%)")
    print(f"   - 合約決策: {result['futures_decision']['decision']} (信心度: {result['futures_decision']['confidence']:.1f}%)")
    
    return True

if __name__ == "__main__":
    try:
        success = validate_backend_json_output()
        if success:
            print("\n🎉 驗證成功！後台分析系統可以正確產生 JSON 輸出。")
        else:
            print("\n❌ 驗證失敗！")
    except Exception as e:
        print(f"\n❌ 驗證發生錯誤: {e}")
        import traceback
        traceback.print_exc()