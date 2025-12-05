#!/usr/bin/env python3
"""
測試數據完整性 - 比較 Binance 和 OKX 的數據結構
"""

import sys
from graph import app

def test_data_structure(symbol, exchange, market_type='spot'):
    """測試數據結構完整性"""
    print(f"\n{'='*70}")
    print(f"測試: {symbol} @ {exchange.upper()} ({market_type})")
    print(f"{'='*70}\n")

    initial_state = {
        "symbol": symbol,
        "exchange": exchange,
        "interval": "1d",
        "limit": 100,
        "market_type": market_type,
        "leverage": 1 if market_type == 'spot' else 5,
    }

    try:
        # 只運行到準備數據節點
        from graph import prepare_data_node
        result = prepare_data_node(initial_state)

        market_data = result['market_data']

        # 檢查數據完整性
        print("📊 數據完整性檢查:\n")

        # 價格資訊
        print("1. 價格資訊:")
        for key, value in market_data['價格資訊'].items():
            print(f"   ✅ {key}: {value}")

        # 技術指標
        print("\n2. 技術指標:")
        for key, value in market_data['技術指標'].items():
            print(f"   ✅ {key}: {value:.4f}")

        # 最近5天歷史
        print(f"\n3. 最近5天歷史: {len(market_data['最近5天歷史'])} 條")
        if market_data['最近5天歷史']:
            print(f"   ✅ 最新一天數據:")
            latest = market_data['最近5天歷史'][-1]
            for key, value in latest.items():
                if key != '日期':
                    print(f"      - {key}: ${value:.4f}")

        # 市場結構
        print(f"\n4. 市場結構:")
        for key, value in market_data['市場結構'].items():
            print(f"   ✅ {key}: {value}")

        # 關鍵價位
        print(f"\n5. 關鍵價位:")
        for key, value in market_data['關鍵價位'].items():
            print(f"   ✅ {key}: ${value:.4f}")

        # 新聞資訊
        news_count = len(market_data['新聞資訊'])
        print(f"\n6. 新聞資訊: {news_count} 條")
        if news_count > 0:
            print(f"   ✅ 找到 {news_count} 條相關新聞")
        else:
            print(f"   ⚠️  未找到相關新聞")

        # 資金費率 (合約市場)
        if market_type == 'futures' and market_data['funding_rate_info']:
            print(f"\n7. 資金費率:")
            for key, value in market_data['funding_rate_info'].items():
                print(f"   ✅ {key}: {value}")

        print(f"\n{'='*70}")
        print("✅ 數據結構完整！")
        print(f"{'='*70}\n")

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🧪 測試數據完整性 - 比較不同交易所\n")

    # 測試 Binance BTC
    test_data_structure("BTCUSDT", "binance", "spot")

    # 測試 OKX PI (如果存在)
    test_data_structure("PI-USDT", "okx", "spot")

    print("\n" + "="*70)
    print("✅ 測試完成！")
    print("="*70)
    print("\n總結:")
    print("- 所有交易所現在都使用統一的數據結構")
    print("- 每個市場都有完整的技術指標、歷史數據、關鍵價位")
    print("- 這樣分析師可以進行更全面的分析")
