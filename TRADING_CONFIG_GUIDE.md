# 交易類型配置指南

## 概述

現在您可以在 `core/config.py` 中靈活控制要執行的交易類型。系統支援獨立啟用或停用現貨交易和合約交易。

## 配置選項

在 `core/config.py` 中找到以下配置:

```python
# === 交易類型選擇 ===
# 控制是否執行現貨交易和合約交易
# True: 啟用該類型的交易 / False: 停用該類型的交易
ENABLE_SPOT_TRADING = True      # 是否執行現貨交易
ENABLE_FUTURES_TRADING = True   # 是否執行合約交易
```

## 使用場景

### 場景 1: 同時執行現貨和合約交易 (預設)
```python
ENABLE_SPOT_TRADING = True
ENABLE_FUTURES_TRADING = True
```
- 系統會分析並執行現貨和合約兩種市場的交易決策
- 適合希望在兩個市場都進行交易的情況

### 場景 2: 只執行現貨交易
```python
ENABLE_SPOT_TRADING = True
ENABLE_FUTURES_TRADING = False
```
- 系統只會執行現貨交易
- 合約交易決策會被跳過
- 適合保守型交易者或不想使用槓桿的情況

### 場景 3: 只執行合約交易
```python
ENABLE_SPOT_TRADING = False
ENABLE_FUTURES_TRADING = True
```
- 系統只會執行合約交易
- 現貨交易決策會被跳過
- 適合希望利用槓桿效應的進階交易者

### 場景 4: 停用所有自動交易
```python
ENABLE_SPOT_TRADING = False
ENABLE_FUTURES_TRADING = False
```
- 系統不會執行任何交易
- 只會生成分析報告
- 適合只想進行市場分析而不實際交易的情況

## 執行流程

當您運行批量分析時 (例如 `python analysis/async_backend_analyzer.py`):

1. 系統會讀取配置文件
2. 顯示當前配置狀態:
   ```
   [CONFIG] Spot Trading: Enabled
   [CONFIG] Futures Trading: Enabled
   ```
3. 根據配置執行相應的交易類型
4. 跳過被停用的交易類型，並顯示提示訊息

## 日誌輸出範例

### 兩種交易都啟用
```
[TRADE] Processing 1 trade decisions.
[CONFIG] Spot Trading: Enabled
[CONFIG] Futures Trading: Enabled
[TRADE] Executing spot trade for PI-USDT
[TRADE] Executing futures trade for PI-USDT-SWAP
```

### 只啟用合約交易
```
[TRADE] Processing 1 trade decisions.
[CONFIG] Spot Trading: Disabled
[CONFIG] Futures Trading: Enabled
[INFO] Spot trading is disabled in config. Skipping spot decision.
[TRADE] Executing futures trade for PI-USDT-SWAP
```

## 注意事項

1. **即時生效**: 修改配置後不需要重啟，下次執行時會自動使用新配置
2. **獨立控制**: 兩個選項完全獨立，可以自由組合
3. **安全性**: 即使啟用交易，仍然需要在執行時明確指定 `live_trading=True` 才會真正執行交易
4. **分析不受影響**: 無論配置如何，系統都會完成完整的市場分析，只是執行階段會根據配置決定是否實際下單

## 測試配置

您可以使用以下命令測試當前配置:

```bash
python test_trading_config.py
```

這會顯示當前的配置狀態，幫助您確認設置是否正確。

## 建議

- **初學者**: 建議先設置 `ENABLE_FUTURES_TRADING = False`，只進行現貨交易
- **進階用戶**: 可以根據市場情況和風險偏好靈活調整
- **測試階段**: 建議先關閉實際交易，使用分析模式觀察系統決策
