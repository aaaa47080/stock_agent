# 成功的交易方法與注意事項

## 重要發現

根據測試結果，我們發現了以下關鍵信息：

1. **PI-USDT 現貨交易對可用**：狀態為 "live"，最小訂單量為 1.0
2. **PI 期貨合約實際存在**：PI-USDT-SWAP 狀態為 "live"，所以之前的錯誤是因為嘗試使用了錯誤的合約
3. **帳戶餘額充足**：USDT 可用餘額為 505.26+，可以進行交易

## 正確的交易方式

### 1. 現貨交易 (PI-USDT)
```python
# 現貨交易使用 place_spot_order 方法
order_result = connector.place_spot_order(
    instId="PI-USDT",      # 現貨交易對
    side="buy",            # "buy" 或 "sell"
    ordType="market",      # "market" 或 "limit"
    sz="5",                # 數量（大於最小訂單量 1.0）
    px="0.2054"            # 價格（市價單時可設為 None）
)
```

### 2. 期貨交易 (PI-USDT-SWAP)
```python
# 首先設置槓桿（如果需要）
leverage_result = connector.set_leverage(
    instId="PI-USDT-SWAP",  # 期貨合約
    lever="3",              # 槓桿倍數
    mgnMode="cross"         # "cross" 或 "isolated"
)

# 然後下單
order_result = connector.place_futures_order(
    instId="PI-USDT-SWAP",  # 期貨合約
    side="buy",             # "buy" 或 "sell"（對於永續合約，buy=sell/long, sell=short）
    ordType="market",       # "market" 或 "limit"
    sz="1",                 # 合約數量
    tdMode="cross"          # 保证金模式
)
```

## 修正自動交易腳本

之前的錯誤是因為：
1. 嘗試使用 "PIUSDT-SWAP" 而不是 "PI-USDT-SWAP"
2. PI 期貨合約實際上是存在的

## 完整交易流程示例

```python
from trading.okx_api_connector import OKXAPIConnector

def execute_successful_trade():
    connector = OKXAPIConnector()
    
    # 1. 檢查餘額
    balance = connector.get_account_balance("USDT")
    if balance.get("code") == "0":
        available = float(balance["data"][0]["details"][0].get("availEq", 0))
        print(f"可用 USDT: {available}")
    
    # 2. 獲取價格
    ticker = connector.get_ticker("PI-USDT")
    if ticker.get("code") == "0":
        price = float(ticker["data"][0]["last"])
        print(f"PI-USDT 當前價格: {price}")
        
        # 3. 下單（現貨）
        amount = min(available * 0.1, 5)  # 用 10% 餘額或最多 5 USDT
        order_result = connector.place_spot_order(
            instId="PI-USDT",
            side="buy",
            ordType="market",
            sz=str(amount / price)  # 轉換為 PI 數量
        )
        print(f"現貨訂單結果: {order_result}")

# 執行交易
execute_successful_trade()
```

## 關鍵要點

1. **正確的合約名稱**：PI-USDT（現貨），PI-USDT-SWAP（期貨）
2. **最少訂單量**：PI-USDT 最小訂單量為 1.0
3. **API 錯誤處理**：使用正確的 API 方法和參數
4. **風險控制**：始終檢查餘額和價格，避免過度交易

## 修正建議

1. 更新交易決策系統，確保 PI 的期貨合約名稱正確
2. 檢查現貨最小訂單量要求後再執行交易
3. 在下單前驗證合約狀態和可用性
4. 增加更詳細的錯誤處理和重試機制