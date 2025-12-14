import json
import os
from datetime import datetime
from okx_api_connector import OKXAPIConnector

def execute_trade_from_analysis(json_file_path: str):
    """
    從分析結果 JSON 文件執行交易
    
    Args:
        json_file_path: 分析結果 JSON 文件路徑
    """
    print(f"[TRADE] 讀取分析結果: {json_file_path}")
    
    # 讀取 JSON 分析結果
    with open(json_file_path, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)
    
    # 初始化 OKX API 連接器
    okx_api = OKXAPIConnector()
    
    # 檢查是否有 API 憑證
    if not all([okx_api.api_key, okx_api.secret_key, okx_api.passphrase]):
        print("[ERROR] 請先設置 OKX API 憑證")
        return False
    
    # 檢查連接
    if not okx_api.test_connection():
        print("[ERROR] 無法連接到 OKX API")
        return False
    
    print("[SUCCESS] OKX API 連接成功")
    
    # 執行每一個分析結果的交易
    for result in analysis_data.get("results", []):
        symbol = result.get("symbol", "")
        signal = result.get("signal", "")
        market_type = result.get("market_type", "spot")
        confidence = result.get("confidence", 0)
        entry_price = result.get("entry_price")
        stop_loss = result.get("stop_loss")
        take_profit = result.get("take_profit")
        position_size = result.get("position_size", 0.02)
        leverage = result.get("leverage", 1)
        
        print(f"\n[TRADE] 處理交易: {symbol} ({market_type}) - {signal}")
        print(f"       信心度: {confidence}%, 倉位大小: {position_size}")
        
        # 根據市場類型和訊號執行交易
        if market_type == "spot":
            success = execute_spot_trade(okx_api, symbol, signal, result)
        elif market_type == "futures":
            success = execute_futures_trade(okx_api, symbol, signal, result)
        else:
            print(f"[ERROR] 不支援的市場類型: {market_type}")
            continue
        
        if success:
            print(f"[SUCCESS] {market_type} 交易下單成功: {symbol}")
        else:
            print(f"[ERROR] {market_type} 交易下單失敗: {symbol}")

def execute_spot_trade(okx_api: OKXAPIConnector, symbol: str, signal: str, trade_data: dict):
    """
    執行現貨交易
    
    Args:
        okx_api: OKX API 連接器
        symbol: 交易對 (如 PI-USDT)
        signal: 交易訊號 (Buy/Sell/Hold)
        trade_data: 交易數據
    """
    if signal.lower() in ["buy", "long"]:
        side = "buy"
    elif signal.lower() in ["sell", "short"]:
        side = "sell"
    else:
        print(f"[INFO] 無需執行交易: {signal}")
        return True
    
    # 取得當前價格以計算數量
    ticker_result = okx_api.get_ticker(symbol)
    if ticker_result.get("code") != "0":
        print(f"[ERROR] 無法取得 {symbol} 行情: {ticker_result}")
        return False
    
    ticker_data = ticker_result.get("data", [{}])[0] if ticker_result.get("data") else {}
    current_price = float(ticker_data.get("last", 0))
    
    if current_price <= 0:
        print(f"[ERROR] 無效價格: {current_price}")
        return False
    
    # 計算交易數量 (基於倉位大小和當前價格)
    position_size = trade_data.get("position_size", 0.02)  # 2% 倉位
    usd_amount = 1000 * position_size  # 假設帳戶有 1000 USDT
    quantity = usd_amount / current_price
    
    print(f"[INFO] 執行現貨 {side.upper()}: {symbol}")
    print(f"       價格: {current_price}, 數量: {quantity:.6f}")
    
    # 下市價單
    order_result = okx_api.place_spot_order(
        instId=symbol,
        side=side,
        ordType="market",  # 市價單
        sz=f"{quantity:.6f}"  # 保留6位小數
    )
    
    print(f"[ORDER] 現貨訂單結果: {order_result}")
    
    return order_result.get("code") == "0"

def execute_futures_trade(okx_api: OKXAPIConnector, symbol: str, signal: str, trade_data: dict):
    """
    執行期貨交易
    
    Args:
        okx_api: OKX API 連接器
        symbol: 交易對 (如 PI-USDT-SWAP)
        signal: 交易訊號 (Long/Short/Hold)
        trade_data: 交易數據
    """
    if signal.lower() == "long":
        side = "buy"
        pos_side = "long"
    elif signal.lower() == "short":
        side = "sell"
        pos_side = "short"
    else:
        print(f"[INFO] 無需執行交易: {signal}")
        return True
    
    # 如果是 SWAP 格式，確保符號正確
    if not symbol.endswith("-SWAP"):
        futures_symbol = f"{symbol}-SWAP"
    else:
        futures_symbol = symbol
    
    # 取得當前價格以計算數量
    ticker_result = okx_api.get_ticker(futures_symbol)
    if ticker_result.get("code") != "0":
        print(f"[ERROR] 無法取得 {futures_symbol} 行情: {ticker_result}")
        return False
    
    ticker_data = ticker_result.get("data", [{}])[0] if ticker_result.get("data") else {}
    current_price = float(ticker_data.get("last", 0))
    
    if current_price <= 0:
        print(f"[ERROR] 無效價格: {current_price}")
        return False
    
    # 計算交易數量 (基於倉位大小、槓桿和當前價格)
    position_size = trade_data.get("position_size", 0.02)  # 2% 倉位
    leverage = trade_data.get("leverage", 5)
    usd_amount = 1000 * position_size * leverage  # 應用槓桿
    quantity = usd_amount / current_price
    
    print(f"[INFO] 執行期貨 {side.upper()} {pos_side.upper()}: {futures_symbol}")
    print(f"       價格: {current_price}, 數量: {quantity:.6f}, 槓桿: {leverage}x")
    
    # 在下單前設置槓桿
    leverage_result = okx_api.set_leverage(futures_symbol, str(leverage))
    print(f"[LEVERAGE] 槓桿設置結果: {leverage_result}")
    
    # 下期貨市價單
    order_result = okx_api.place_futures_order(
        instId=futures_symbol,
        side=side,
        ordType="market",
        sz=f"{quantity:.6f}",
        posSide=pos_side,
        lever=str(leverage)
    )
    
    print(f"[ORDER] 期貨訂單結果: {order_result}")
    
    return order_result.get("code") == "0"

def test_with_latest_reports():
    """
    使用最新的分析報告進行測試
    """
    import glob
    import os

    print("[AUTO-TRADE] 查找最新的分析報告...")

    # 在主目錄中查找最新的現貨和期貨報告
    spot_reports = glob.glob("../reports/report_*_spot_*.json")
    futures_reports = glob.glob("../reports/report_*_futures_*.json")

    # 如果在主目錄中沒找到，則檢查當前目錄
    if not spot_reports:
        spot_reports = glob.glob("reports/report_*_spot_*.json")
    if not futures_reports:
        futures_reports = glob.glob("reports/report_*_futures_*.json")

    if spot_reports:
        latest_spot = max(spot_reports, key=os.path.getctime)
        print(f"[INFO] 找到最新現貨報告: {latest_spot}")
        execute_trade_from_analysis(latest_spot)

    if futures_reports:
        latest_futures = max(futures_reports, key=os.path.getctime)
        print(f"[INFO] 找到最新期貨報告: {latest_futures}")
        execute_trade_from_analysis(latest_futures)

    if not spot_reports and not futures_reports:
        print("[WARNING] 未找到分析報告")

if __name__ == "__main__":
    print("="*60)
    print("OKX 自動交易執行器")
    print("="*60)
    
    # 測試連接
    okx_api = OKXAPIConnector()
    
    if not all([okx_api.api_key, okx_api.secret_key, okx_api.passphrase]):
        print("\n[INFO] 請先在 .env 文件中設置 OKX API 憑證，範例：")
        print("OKX_API_KEY=your_api_key")
        print("OKX_SECRET_KEY=your_secret_key") 
        print("OKX_PASSPHRASE=your_passphrase")
        print("\n然後重新運行此腳本")
    else:
        print("\n[INFO] 檢測到 API 憑證，開始自動交易...")
        test_with_latest_reports()
    
    print("\n" + "="*60)
    print("[END] 程序結束")
    print("="*60)