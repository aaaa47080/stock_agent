# 💬 加密貨幣投資分析聊天界面

一個智能的對話式加密貨幣投資分析系統,支持自然語言查詢和智能幣種識別。

## ✨ 功能特色

- 🤖 **自然語言對話**: 使用 LLM 智能解析用戶問題
- 🎯 **智能幣種識別**: 自動提取加密貨幣代號 (BTC, ETH, PI, PIUSDT 等)
- 📊 **雙市場分析**: 同時分析現貨市場和合約市場
- 🔍 **多維度分析**: 技術分析、情緒分析、基本面分析、新聞分析
- ⚖️ **多空辯論**: 多方和空方研究員進行辯論
- 🛡️ **風險評估**: 專業的風險管理評估
- 💰 **投資建議**: 基於多層決策的投資建議

## 🚀 快速開始

### 1. 安裝依賴

```bash
# 激活虛擬環境
source .venv/bin/activate

# 安裝 Gradio (如果還沒安裝)
pip install gradio
```

### 2. 配置環境變量

確保 `.env` 文件中包含必要的 API 密鑰:

```env
OPENAI_API_KEY=your_openai_api_key
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
```

### 3. 啟動聊天界面

```bash
python run_chat.py
```

或者直接執行:

```bash
python chat_interface.py
```

### 4. 訪問界面

啟動後,在瀏覽器中打開顯示的網址 (通常是 `http://localhost:7860`)

## 💡 使用範例

### 單個幣種分析

```
你: PI 可以投資嗎?
```

```
你: PIUSDT 值得買入嗎?
```

```
你: 比特幣現在適合進場嗎?
```

### 多幣種比較

```
你: XRP, PI, ETH 哪些可以投資?
```

```
你: BTC 和 ETH 哪個更值得投資?
```

### 支持的查詢格式

- **直接幣種代號**: `PI`, `BTC`, `ETH`, `XRP`
- **帶 USDT 後綴**: `PIUSDT`, `BTCUSDT`, `ETHUSDT`
- **中文名稱**: `比特幣`, `以太坊` (會自動轉換為代號)
- **自然語言**: `PI 可以投資嗎?`, `值得買入嗎?`

## 🏗️ 系統架構

### 核心組件

1. **CryptoQueryParser**: 使用 GPT-4o 解析自然語言查詢
   - 識別用戶意圖 (投資分析/一般問題/打招呼)
   - 提取加密貨幣代號
   - 確定動作類型 (分析/比較/對話)

2. **CryptoAnalysisBot**: 主要的分析機器人
   - 標準化幣種符號
   - 調用雙市場分析系統
   - 生成分析摘要

3. **Gradio 界面**: 對話式 UI
   - 聊天記錄
   - 實時響應
   - 錯誤處理

### 分析流程

```
用戶輸入
    ↓
LLM 解析 (提取幣種和意圖)
    ↓
符號標準化 (添加 USDT 後綴)
    ↓
雙市場分析
    ├─ 現貨市場 (1x 槓桿)
    └─ 合約市場 (5x 槓桿)
    ↓
生成分析報告
    ├─ 技術分析
    ├─ 情緒分析
    ├─ 基本面分析
    ├─ 新聞分析
    ├─ 多空辯論
    ├─ 風險評估
    └─ 最終決策
    ↓
返回給用戶
```

## 🔧 技術細節

### LLM 模型配置

- **查詢解析**: GPT-4o (快速響應,高準確度)
- **投資分析**: 使用 config.py 中配置的模型
  - `FAST_THINKING_MODEL`: gpt-4o (數據收集)
  - `DEEP_THINKING_MODEL`: o4-mini (深度推理)

### 數據源

- **交易所**: Binance (預設)
- **數據範圍**: 最近 100 天
- **時間間隔**: 1 天 (日線)

### 風險參數

- **現貨市場**: 1x 槓桿
- **合約市場**: 5x 槓桿 (可在代碼中調整)

## 📝 注意事項

1. **API 密鑰**: 確保 `.env` 文件中配置正確的 API 密鑰
2. **網絡連接**: 需要穩定的網絡連接訪問交易所 API 和 OpenAI API
3. **幣種支持**: 僅支持在 Binance 上架的幣種
4. **投資風險**: 本系統僅供參考,不構成投資建議,投資有風險請謹慎

## 🐛 故障排除

### 找不到交易對

```
錯誤: ❌ 找不到交易對 PIUSDT
```

**解決方案**:
- 檢查幣種符號是否正確
- 確認該幣種在 Binance 上已上架
- 嘗試不同的符號格式 (如 PI 或 PIUSDT)

### API 錯誤

```
錯誤: 分析時發生錯誤
```

**解決方案**:
- 檢查 `.env` 文件中的 API 密鑰是否正確
- 確認 API 密鑰有足夠的權限
- 檢查網絡連接

### LLM 解析失敗

如果 LLM 解析失敗,系統會自動退回到正則表達式提取:
- 使用標準的幣種代號 (如 BTC, ETH)
- 使用帶 USDT 後綴的格式 (如 BTCUSDT)

## 🔄 自定義配置

### 修改槓桿倍數

編輯 `chat_interface.py` 中的 `analyze_crypto` 方法:

```python
futures_initial_state = {
    ...
    "leverage": 10,  # 修改為你想要的槓桿倍數
}
```

### 修改數據範圍

```python
spot_initial_state = {
    ...
    "interval": "4h",  # 修改時間間隔 (1m, 5m, 1h, 4h, 1d, 1w)
    "limit": 200,      # 修改數據量
}
```

### 修改交易所

```python
def analyze_crypto(self, symbol: str, exchange: str = "okx"):  # 改為 okx 或其他
```

## 📚 相關文件

- `chat_interface.py`: 主要的聊天界面代碼
- `run_chat.py`: 快速啟動腳本
- `graph.py`: LangGraph 分析工作流
- `agents.py`: 各種分析代理
- `reporting.py`: 報告生成模組

## 🤝 貢獻

歡迎提交問題和改進建議!

## 📄 許可證

本項目僅供學習和研究使用。