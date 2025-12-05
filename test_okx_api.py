#!/usr/bin/env python3
"""
測試 OKX API 實際功能
"""

from data_fetcher import OkxDataFetcher, SymbolNotFoundError

def test_okx_spot():
    """測試 OKX 現貨數據獲取"""
    print("=" * 70)
    print("測試 OKX 現貨 API")
    print("=" * 70)

    fetcher = OkxDataFetcher()

    # 測試常見幣種
    test_symbols = [
        ("BTC-USDT", "比特幣"),
        ("ETH-USDT", "以太坊"),
        ("PI-USDT", "PI Network (可能不存在)"),
    ]

    for symbol, name in test_symbols:
        print(f"\n--- 測試 {symbol} ({name}) ---")
        try:
            df = fetcher.get_historical_klines(symbol, "1d", limit=5)

            if df is not None and not df.empty:
                print(f"✅ 成功獲取數據，共 {len(df)} 條")
                print(f"   最新價格: ${float(df.iloc[-1]['Close']):.4f}")
                print(f"   24h 高: ${float(df.iloc[-1]['High']):.4f}")
                print(f"   24h 低: ${float(df.iloc[-1]['Low']):.4f}")
                print(f"   交易量: {float(df.iloc[-1]['Volume']):.2f}")
            else:
                print(f"❌ 數據為空")

        except SymbolNotFoundError as e:
            print(f"⚠️  交易對不存在: {e}")
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")

def test_okx_futures():
    """測試 OKX 合約數據獲取"""
    print("\n\n" + "=" * 70)
    print("測試 OKX 合約 API")
    print("=" * 70)

    fetcher = OkxDataFetcher()

    # 測試合約
    test_symbols = [
        ("BTC-USDT", "比特幣永續合約"),
        ("ETH-USDT", "以太坊永續合約"),
    ]

    for symbol, name in test_symbols:
        print(f"\n--- 測試 {symbol} ({name}) ---")
        try:
            df, funding_rate = fetcher.get_futures_data(symbol, "1d", limit=5)

            if df is not None and not df.empty:
                print(f"✅ 成功獲取 K 線數據，共 {len(df)} 條")
                print(f"   最新價格: ${float(df.iloc[-1]['Close']):.4f}")

                if funding_rate:
                    print(f"\n📊 資金費率信息:")
                    print(f"   當前費率: {funding_rate.get('current_funding_rate', 0) * 100:.4f}%")
                    print(f"   下次費率: {funding_rate.get('next_funding_rate', 0) * 100:.4f}%")
                else:
                    print(f"⚠️  未獲取到資金費率")
            else:
                print(f"❌ 數據為空")

        except SymbolNotFoundError as e:
            print(f"⚠️  交易對不存在: {e}")
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")

def test_interval_conversion():
    """測試時間間隔轉換"""
    print("\n\n" + "=" * 70)
    print("測試時間間隔轉換")
    print("=" * 70)

    fetcher = OkxDataFetcher()

    intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']

    print("\nBinance 格式 → OKX 格式:")
    for interval in intervals:
        okx_interval = fetcher._convert_interval(interval)
        print(f"  {interval:5} → {okx_interval}")

if __name__ == "__main__":
    print("\n🧪 開始測試 OKX API 功能\n")

    # 測試時間間隔轉換
    test_interval_conversion()

    # 測試現貨 API
    test_okx_spot()

    # 測試合約 API
    test_okx_futures()

    print("\n" + "=" * 70)
    print("✅ 測試完成!")
    print("=" * 70)
    print("\n提示:")
    print("1. 如果所有測試通過，OKX API 集成正常")
    print("2. 現在可以使用聊天界面查詢 OKX 上的幣種")
    print("3. 系統會自動在 Binance 和 OKX 之間切換")
