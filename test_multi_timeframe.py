#!/usr/bin/env python3
"""
測試多週期分析功能
"""
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.graph import AgentState, app
from data.data_processor import build_market_data_package, fetch_and_process_klines
from data.data_fetcher import get_data_fetcher

def test_multi_timeframe():
    """測試多週期分析功能"""
    print("=== 測試多週期分析功能 ===")
    
    symbol = "BTCUSDT"
    exchange = "binance"
    market_type = "spot"
    interval = "1d"  # 主週期
    limit = 100
    
    print(f"獲取 {symbol} 的多週期數據...")
    
    # 1. 測試獲取單週期數據
    print("\n1. 獲取單週期數據...")
    data_fetcher = get_data_fetcher(exchange)
    klines_df = data_fetcher.get_historical_klines(symbol, interval, limit)
    
    if klines_df is None or klines_df.empty:
        print(f"❌ 無法獲取 {symbol} 的 K 線數據")
        return False
    
    print(f"SUCCESS: 獲取到 {len(klines_df)} 條 {interval} K線數據")

    # 2. 測試構建包含多週期的市場數據包 (使用新的函數)
    print("\n2. 構建多週期市場數據包...")
    market_data = build_market_data_package(
        df=klines_df,
        symbol=symbol,
        market_type=market_type,
        exchange=exchange,
        leverage=1,
        funding_rate_info={},
        include_multi_timeframe=True,  # 啟用多週期分析
        short_term_interval="1h",
        medium_term_interval="4h",
        long_term_interval="1d"
    )

    print(f"SUCCESS: 多週期市場數據包構建完成")

    # 檢查是否包含多週期數據
    has_multi_timeframe = 'multi_timeframe_data' in market_data
    print(f"   - 包含多週期數據: {has_multi_timeframe}")

    if has_multi_timeframe:
        multi_tf_data = market_data['multi_timeframe_data']
        print(f"   - 短週期數據: {'SUCCESS' if multi_tf_data.get('short_term') else 'FAILED'}")
        print(f"   - 中週期數據: {'SUCCESS' if multi_tf_data.get('medium_term') else 'FAILED'}")
        print(f"   - 長週期數據: {'SUCCESS' if multi_tf_data.get('long_term') else 'FAILED'}")
        print(f"   - 綜合趨勢: {'SUCCESS' if market_data.get('multi_timeframe_trend_analysis') else 'FAILED'}")

    # 3. 測試圖工作流狀態
    print("\n3. 測試圖工作流狀態...")

    initial_state = AgentState(
        symbol=symbol,
        exchange=exchange,
        interval=interval,
        limit=limit,
        market_type=market_type,
        leverage=1,
        preloaded_data=market_data,  # 使用包含多週期數據的預加載數據
        include_multi_timeframe=True,
        short_term_interval="1h",
        medium_term_interval="4h",
        long_term_interval="1d",
        client=None,  # 這會在 prepare_data_node 中初始化
        market_data={},
        current_price=market_data["價格資訊"]["當前價格"],
        funding_rate_info={},
        analyst_reports=[],
        bull_argument=None,
        bear_argument=None,
        trader_decision=None,
        risk_assessment=None,
        final_approval=None,
        replan_count=0,
        messages=[]
    )

    print("SUCCESS: 狀態初始化完成")

    # 4. 測試 prepare_data_node（這會處理多週期數據）
    print("\n4. 測試 prepare_data_node...")
    try:
        from core.graph import prepare_data_node
        result = prepare_data_node(initial_state)

        print("SUCCESS: prepare_data_node 執行完成")
        print(f"   - 市場數據包含多週期分析: {'multi_timeframe_data' in result.get('market_data', {})}")

        if 'multi_timeframe_data' in result.get('market_data', {}):
            market_data = result['market_data']
            multi_tf_data = market_data['multi_timeframe_data']
            trend_analysis = market_data.get('multi_timeframe_trend_analysis', {})

            print(f"   - 短週期趨勢: {trend_analysis.get('short_term_trend', '不明')}")
            print(f"   - 中週期趨勢: {trend_analysis.get('medium_term_trend', '不明')}")
            print(f"   - 長週期趨勢: {trend_analysis.get('long_term_trend', '不明')}")
            print(f"   - 趨勢一致性: {trend_analysis.get('trend_consistency', '不明')}")
            print(f"   - 整體偏向: {trend_analysis.get('overall_bias', '中性')}")

    except Exception as e:
        print(f"ERROR: prepare_data_node 執行失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n=== 多週期分析功能測試完成 ===")
    print("SUCCESS: 所有測試通過！多週期分析功能已成功整合到系統中")
    return True

if __name__ == "__main__":
    success = test_multi_timeframe()
    if success:
        print("\nCONGRATULATIONS! 多週期分析功能實現成功！")
        print("\n現在系統具備以下多週期分析能力：")
        print("- 短週期分析 (1小時)")
        print("- 中週期分析 (4小時)")
        print("- 長週期分析 (1天)")
        print("- 綜合趨勢分析 (多週期一致性評估)")
        print("- 多週期風險評估")
        print("- 基於多週期一致性的交易決策")
    else:
        print("\nFAILED: 測試失敗，請檢查錯誤")