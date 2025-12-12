# 📰 多來源新聞聚合系統使用指南

## 🌟 系統概述

本系統已升級為**多來源新聞聚合器**，自動從多個數據源獲取加密貨幣新聞，大幅提高信息覆蓋率和可靠性。

### 📊 支持的新聞來源

| 來源 | 類型 | API Key | 免費額度 | 特點 |
|------|------|---------|----------|------|
| **CryptoPanic** | 專業加密貨幣新聞 | ✅ 需要 | 有限 | 包含情緒分析、多源聚合 |
| **NewsAPI** | 主流媒體報導 | ✅ 需要 | 100 請求/天 | 覆蓋主流財經媒體 |
| **CoinGecko** | 市場數據 | ❌ 免費 | 無限制 | 市場趨勢、社群數據、供應量 |

---

## 🚀 快速開始

### 1. 配置 API Keys（可選但推薦）

複製 `.env.example` 為 `.env`，然後填入您的 API Keys：

```bash
cp .env.example .env
```

編輯 `.env` 文件：

```env
# CryptoPanic API（專業加密貨幣新聞）
# 申請地址: https://cryptopanic.com/developers/api/
API_TOKEN=your_cryptopanic_token_here

# NewsAPI（主流媒體新聞）
# 申請地址: https://newsapi.org/
NEWSAPI_KEY=your_newsapi_key_here

# OpenAI API（必須）
OPENAI_API_KEY=your_openai_key_here
```

### 2. API Key 申請指南

#### CryptoPanic（推薦）
- 📍 網址: https://cryptopanic.com/developers/api/
- 💰 價格: 免費版有限額度
- ⭐ 特點: 專業加密貨幣新聞，包含情緒分析

#### NewsAPI（強烈推薦）
- 📍 網址: https://newsapi.org/
- 💰 價格: 免費 100 請求/天
- ⭐ 特點: 覆蓋主流財經媒體如 Bloomberg, Reuters

#### CoinGecko（自動啟用）
- 📍 網址: https://www.coingecko.com/
- 💰 價格: 完全免費，無需 API Key
- ⭐ 特點: 市場數據、社群活動、供應量資訊

---

## 💡 使用方式

### 方式 1: 自動聚合（推薦）

系統會**自動並行**從所有可用來源獲取新聞：

```python
from utils import get_crypto_news

# 自動從 CryptoPanic + NewsAPI + CoinGecko 獲取新聞
news = get_crypto_news("BTC", limit=5)

for item in news:
    print(f"[{item['source']}] {item['title']}")
    print(f"情緒: {item['sentiment']}")
```

### 方式 2: 單一來源

如果需要測試特定來源：

```python
from utils import (
    get_crypto_news_cryptopanic,
    get_crypto_news_newsapi,
    get_crypto_news_coingecko
)

# 只從 CryptoPanic 獲取
news = get_crypto_news_cryptopanic("ETH", limit=5)

# 只從 NewsAPI 獲取
news = get_crypto_news_newsapi("BTC", limit=5)

# 只從 CoinGecko 獲取（無需 API Key）
news = get_crypto_news_coingecko("SOL", limit=5)
```

---

## 🎯 系統特性

### ✅ 優勢

1. **容錯性強**: 即使某個來源失效，其他來源仍可提供數據
2. **並行處理**: 同時從多個來源抓取，速度快
3. **自動去重**: 智能識別重複新聞
4. **情緒分析**: 提供看漲/看跌/中性標籤
5. **零配置可用**: 至少 CoinGecko 始終可用（無需 API Key）

### 📈 新聞數據格式

```python
{
    "title": "新聞標題",
    "description": "新聞描述",
    "published_at": "2025-12-12T10:00:00Z",
    "sentiment": "看漲",  # 看漲/看跌/中性
    "source": "NewsAPI (Bloomberg)"
}
```

---

## 🧪 測試系統

運行測試腳本檢查各來源狀態：

```bash
source .venv/bin/activate
python3 test_multi_source_news.py
```

輸出示例：

```
🔑 API Key 配置狀態
================================================================================
✅ 已設定 CryptoPanic (API_TOKEN): 0e58ba04...76e3
✅ 已設定 NewsAPI (NEWSAPI_KEY): a1b2c3d4...xyz9
✅ 已設定 OpenAI (OPENAI_API_KEY): sk-proj-...aCMA

🌐 啟動多來源新聞聚合系統 (目標: BTC)...
✅ CryptoPanic: 獲取 5 條新聞
✅ NewsAPI: 獲取 5 條新聞
✅ CoinGecko: 獲取 3 條新聞

📊 聚合完成: 總共獲取 10 條獨特新聞
```

---

## ⚙️ 進階配置

### 調整來源優先級

編輯 `utils.py` 中的 `get_crypto_news` 函數，調整並行執行順序：

```python
futures = {
    executor.submit(get_crypto_news_cryptopanic, symbol, limit): "CryptoPanic",
    executor.submit(get_crypto_news_newsapi, symbol, limit): "NewsAPI",
    executor.submit(get_crypto_news_coingecko, symbol, limit): "CoinGecko"
}
```

### 添加更多幣種支持

編輯 `coin_id_map` 添加更多幣種映射：

```python
coin_id_map = {
    "BTC": "bitcoin",
    "YOUR_COIN": "coingecko-id",  # 添加您的幣種
}
```

---

## 🔍 故障排除

### 問題 1: CryptoPanic Rate Limit

**症狀**: `429 Too Many Requests`

**解決方案**:
- 等待幾分鐘後重試
- 升級到付費版以獲得更高額度
- 暫時停用 CryptoPanic，使用 NewsAPI + CoinGecko

### 問題 2: NewsAPI 無新聞

**症狀**: 返回空列表

**解決方案**:
- 檢查 API Key 是否正確設定
- 確認未超過 100 請求/天限制
- 嘗試更通用的搜尋詞（如 "Bitcoin" 而非 "BTC"）

### 問題 3: CoinGecko 找不到幣種

**症狀**: `404 Not Found`

**解決方案**:
- 檢查幣種是否在 CoinGecko 上市
- 訪問 https://www.coingecko.com/ 搜尋幣種 ID
- 更新 `coin_id_map` 添加正確的映射

---

## 📝 最佳實踐

1. **至少設定一個 API Key**: 建議設定 NewsAPI（免費 100 請求/天）
2. **定期更新 coin_id_map**: 為新幣種添加 CoinGecko ID
3. **監控 Rate Limit**: 避免短時間內大量請求
4. **使用緩存**: 系統已內建緩存機制（5分鐘 TTL）

---

## 🎁 額外功能

### 新聞情緒統計

```python
from collections import Counter

news = get_crypto_news("BTC", limit=20)
sentiments = [n['sentiment'] for n in news]
print(Counter(sentiments))
# 輸出: Counter({'中性': 12, '看漲': 5, '看跌': 3})
```

### 按來源分類

```python
from itertools import groupby

news = get_crypto_news("ETH", limit=15)
news_by_source = groupby(sorted(news, key=lambda x: x['source']), key=lambda x: x['source'])

for source, items in news_by_source:
    print(f"\n{source}:")
    for item in items:
        print(f"  - {item['title']}")
```

---

## 📞 支援

如有問題，請檢查：
1. `.env` 文件是否正確配置
2. 運行 `test_multi_source_news.py` 查看詳細錯誤
3. 查看終端輸出的詳細日誌

---

**版本**: 2.0
**更新日期**: 2025-12-12
**作者**: Claude Code
**許可**: MIT
