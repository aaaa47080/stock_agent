# Agent Chat 交互式測試指南

> 最後更新: 2026-03-08

---

## ⚠️ 重要說明

### 測試方式

**必須使用交互式測試，不可使用自動化腳本！**

```bash
python tests/test_interactive_user.py
```

### 測試原則

1. **問題不限於下列 10 題** - 這些只是參考範例，測試者應自由發問各種問題
2. **探索邊界案例** - 嘗試各種奇怪的輸入、模糊的問題、跨市場查詢
3. **多輪對話測試** - 測試上下文記憶，連續追問
4. **即時記錄問題** - 發現 Bug 立即記錄，不要等到測試結束
5. **禁止 Hardcode** - 修復問題時只能改邏輯邊界，不能針對特定案例寫死

### 測試流程

```
啟動交互測試
    ↓
輸入問題（自由發問，不限題目）
    ↓
觀察回應（檢查正確性、完整性）
    ↓
發現問題？
    ├─ 是 → 記錄問題 → 診斷原因 → 修復（不改 hardcode）
    └─ 否 → 繼續下一題
    ↓
結束測試 → 儲存結果 → 撰寫報告
```

---

## 📋 目錄

1. [測試目標](#測試目標)
2. [測試執行方式](#測試執行方式)
3. [參考題目（由簡到難）](#參考題目由簡到難)
4. [Bug 修復原則](#bug-修復原則)
5. [評分標準](#評分標準)
6. [常見問題診斷](#常見問題診斷)

---

## 測試目標

驗證 Agent Chat 系統的以下能力：
- ✅ **意圖分類準確性**: 正確識別用戶查詢的市場和意圖
- ✅ **Agent 路由正確性**: 將查詢路由到正確的專業 Agent
- ✅ **工具調用有效性**: 正確調用對應工具並獲取數據
- ✅ **回應品質**: 回應內容準確、完整、有用
- ✅ **多輪對話記憶**: 能記住上下文並進行連續對話
- ✅ **邊界處理**: 正確處理模糊查詢、跨市場查詢、錯誤輸入

---

## 測試執行方式

### 啟動測試

```bash
# 確保環境變數已設置
export ENABLE_MANAGER_V2=true
export OPENAI_API_KEY=your_key  # 或 OPENROUTER_API_KEY

# 執行交互式測試
python tests/test_interactive_user.py
```

### 測試指令

| 指令 | 說明 |
|------|------|
| `quit` / `exit` | 結束測試並儲存結果 |
| `save` | 儲存當前對話記錄 |
| `clear` | 開始新對話（舊對話會儲存） |
| `help` | 顯示幫助資訊 |

---

## 參考題目（由簡到難）

> ⚠️ **注意**: 以下題目僅供參考，測試者應自由發問各種問題，不限於這 10 題！

---

## 測試題目（由簡到難）

### 🟢 Level 1: 基礎價格查詢（簡單）

#### Test 1.1: 加密貨幣即時價格
```
BTC 價格
```
**預期結果**:
- 正確路由到 `chat` 或 `crypto` Agent
- 回傳 BTC 當前價格（數值）
- 包含價格變化資訊（漲跌幅）

**通過標準**: 價格數值準確（與 CoinGecko/OKX 誤差 < 1%）

---

#### Test 1.2: 台股即時價格
```
台積電股價
```
或
```
2330 股價
```
**預期結果**:
- 正確路由到 `tw_stock` Agent
- 能識別「台積電」=「2330」
- 回傳即時價格和漲跌幅

**通過標準**: 正確識別公司名稱或代碼，價格準確

---

#### Test 1.3: 美股即時價格
```
TSLA 價格
```
**預期結果**:
- 正確路由到 `us_stock` Agent
- 回傳 TSLA 當前價格（注意：15分鐘延遲）
- 包含基本市場資訊

**通過標準**: 識別為美股，回傳價格數據

---

### 🟡 Level 2: 單一市場分析（中等）

#### Test 2.1: 加密貨幣技術分析
```
ETH 技術分析
```
**預期結果**:
- 路由到 `crypto` Agent
- 調用 `technical_analysis` 工具
- 包含 RSI、MACD、MA 等指標
- 提供技術面解讀

**通過標準**: 包含至少 2 個技術指標，並有趨勢判斷

---

#### Test 2.2: 台股基本面分析
```
鴻海的本益比和 EPS
```
**預期結果**:
- 路由到 `tw_stock` Agent
- 識別「鴻海」=「2317」
- 回傳 P/E ratio、EPS 數據
- 提供基本面評估

**通過標準**: 數據準確，包含解讀

---

#### Test 2.3: 新聞查詢
```
比特幣最新新聞
```
**預期結果**:
- 路由到 `crypto` Agent
- 調用 `google_news` 或 `aggregate_news` 工具
- 回傳近期新聞摘要
- 新聞內容相關且即時

**通過標準**: 新聞時間在 7 天內，與 BTC 相關

---

### 🟠 Level 3: 多市場與上下文（困難）

#### Test 3.1: 跨市場比較
```
台積電 ADR 和台股的價差
```
**預期結果**:
- 識別需要同時查詢美股（TSM）和台股（2330）
- 調用多個工具
- 計算價差或溢價/折價
- 提供套利或投資建議

**通過標準**: 正確識別兩個市場，提供比較分析

---

#### Test 3.2: 多輪對話記憶
```
第一輪: BTC 現在多少錢？
第二輪: 它的技術面怎麼樣？
第三輪: 有什麼新聞嗎？
```
**預期結果**:
- 第二輪能記住「它」=「BTC」
- 第三輪仍記得上下文
- 每輪調用正確工具
- 回應連貫

**通過標準**: 第二、三輪無需重新指定標的，正確理解代詞

---

#### Test 3.3: 模糊查詢處理
```
黃金價格
```
**預期結果**:
- 識別為大宗商品查詢
- 路由到 `commodity` Agent
- 回傳黃金（XAU）即時價格
- 提供相關資訊

**通過標準**: 正確識別為商品而非股票或加密貨幣

---

### 🔴 Level 4: 複雜綜合分析（專家）

#### Test 4.1: 完整投資分析
```
我想投資輝達，給我完整分析
```
**預期結果**:
- 識別「輝達」=「NVDA」
- 路由到 `us_stock` Agent
- 執行多維度分析：
  - 技術面（RSI, MACD, 趨勢）
  - 基本面（P/E, EPS, 營收）
  - 新聞面（近期消息）
  - 機構持倉
- 綜合評估投資風險與機會

**通過標準**: 包含至少 3 個維度的分析，有明確結論

---

#### Test 4.2: 市場情緒與大盤分析
```
現在加密貨幣市場整體情緒如何？
```
**預期結果**:
- 路由到 `crypto` Agent
- 調用多個工具：
  - `get_fear_and_greed_index`（恐慌貪婪指數）
  - `get_trending_tokens`（熱門幣種）
  - `get_crypto_categories_and_gainers`（板塊表現）
- 綜合判斷市場情緒
- 提供操作建議

**通過標準**: 包含量化指標（恐慌指數）和質化分析

---

## Bug 修復原則

### ⛔ 禁止的修改方式（Hardcode）

```python
# ❌ 錯誤：針對特定名詞 hardcode
if query == "台積電":
    ticker = "2330"

# ❌ 錯誤：針對特定案例修補
if "輝達" in query and "分析" in query:
    return special_nvidia_analysis()

# ❌ 錯誤：寫死特定問題的答案
QA_DATABASE = {
    "BTC 價格": "目前比特幣價格是 $50,000",
}
```

### ✅ 正確的修改方式（邊界與邏輯）

```python
# ✅ 正確：擴充通用映射表
COMPANY_NAME_TO_TICKER = {
    "台積電": "2330",
    "鴻海": "2317",
    "輝達": "NVDA",
    # ... 系統化擴充
}

# ✅ 正確：建立通用的模糊匹配機制
class SymbolResolver:
    def resolve(self, input_str: str) -> str:
        # 1. 精確匹配
        if input_str in self.exact_map:
            return self.exact_map[input_str]

        # 2. 模糊匹配（Levenshtein distance）
        return self.fuzzy_match(input_str, threshold=0.8)

# ✅ 正確：擴充 Agent 能力描述
AgentMetadata(
    capabilities=[
        "技術分析", "基本面", "新聞",  # 原有
        "機構持倉", "內部人交易",       # 新增通用能力
    ]
)

# ✅ 正確：建立通用的意圖識別邏輯
def classify_intent(query: str) -> str:
    patterns = {
        "price": r"(價格|多少錢|現在)",
        "technical": r"(技術|RSI|MACD|走勢)",
        "news": r"(新聞|消息|最新)",
    }
    for intent, pattern in patterns.items():
        if re.search(pattern, query):
            return intent
    return "unknown"
```

### 修改決策樹

```
發現 Bug
    │
    ├─ 是否為「特定名詞識別失敗」？
    │   └─ ✅ 擴充 universal_resolver 或 symbol_map
    │
    ├─ 是否為「意圖分類錯誤」？
    │   └─ ✅ 改進 prompt 或增加 capability 關鍵字
    │
    ├─ 是否為「工具調用失敗」？
    │   └─ ✅ 檢查工具的 input_schema 和邊界條件
    │
    ├─ 是否為「上下文記憶失效」？
    │   └─ ✅ 檢查 history 傳遞邏輯
    │
    └─ 是否為「回應品質不佳」？
        └─ ✅ 改進 Agent 的 system prompt
```

---

## 評分標準

### 每題評分（0-10 分）

| 分數 | 標準 |
|------|------|
| 10 | 完美：正確路由、數據準確、回應完整 |
| 8-9 | 優秀：路由正確，小瑕疵（如格式問題） |
| 6-7 | 及格：核心功能正常，但缺少細節 |
| 4-5 | 不及格：路由錯誤或數據不準確 |
| 0-3 | 失敗：無回應、報錯、或完全錯誤 |

### 總體評估

| 總分 | 等級 | 說明 |
|------|------|------|
| 90-100 | A+ | 生產環境就緒 |
| 80-89 | A | 可上線，需小幅優化 |
| 70-79 | B | 核心功能正常，需改進細節 |
| 60-69 | C | 有功能缺陷，需修復 |
| < 60 | F | 重大問題，需全面檢討 |

---

## 常見問題診斷

### Q1: Agent 路由錯誤

**症狀**: 查詢「台積電」卻路由到 Crypto Agent

**診斷步驟**:
1. 檢查 `agent_registry.py` 中各 Agent 的 `capabilities`
2. 確認 `router.py` 的分類邏輯
3. 查看 Manager Agent 的意圖分類 prompt

**修復方向**:
- 擴充 TW Stock Agent 的能力關鍵字
- 改進 symbol resolver 的優先級邏輯
- 優化分類 prompt 的邊界條件

---

### Q2: 工具調用失敗

**症狀**: 返回 "Tool not found" 或參數錯誤

**診斷步驟**:
1. 檢查 `tool_registry.py` 中工具是否正確註冊
2. 確認工具的 `allowed_agents` 包含當前 Agent
3. 檢查工具的 `input_schema` 定義

**修復方向**:
- 確保工具在 `bootstrap.py` 中註冊
- 檢查 Agent 的 `allowed_tools` 列表
- 驗證工具參數的類型和必填項

---

### Q3: 上下文記憶失效

**症狀**: 第二輪對話忘記第一輪的標的

**診斷步驟**:
1. 檢查 `history` 是否正確傳遞
2. 確認 session_id 是否一致
3. 查看 LLM prompt 中是否包含歷史

**修復方向**:
- 確保每次調用都傳遞 `history_text`
- 檢查 LangGraph 的 state 管理
- 優化 prompt 以強調上下文重要性

---

### Q4: 符號解析失敗

**症狀**: 「台積電」無法識別為「2330」

**診斷步驟**:
1. 檢查 `universal_resolver.py` 的解析邏輯
2. 確認 `tw_symbol_resolver.py` 的映射表
3. 測試 fuzzy match 的 threshold

**修復方向**:
- 擴充公司名稱映射表（通用化）
- 調整 fuzzy match 的相似度閾值
- 建立別名系統（如「台積電」=「TSMC」=「2330」）

---

### Q5: 回應品質不佳

**症狀**: 回應過於簡略或不相關

**診斷步驟**:
1. 檢查 Agent 的 system prompt
2. 確認工具返回的數據品質
3. 查看 LLM 的溫度和參數設定

**修復方向**:
- 優化 Agent 的 system prompt（增加結構化要求）
- 改進工具的錯誤處理和數據格式
- 調整 LLM 參數（temperature, max_tokens）

---

## 測試結果記錄模板

```json
{
  "test_date": "2026-03-08",
  "tester": "用戶名",
  "model": "gpt-4o-mini",
  "results": [
    {
      "test_id": "1.1",
      "query": "BTC 價格",
      "expected": "回傳價格數值",
      "actual": "目前 BTC 價格為 $67,234，24h 漲幅 +2.3%",
      "score": 10,
      "notes": "完美"
    },
    {
      "test_id": "1.2",
      "query": "台積電股價",
      "expected": "識別為 2330 並回傳價格",
      "actual": "無法識別「台積電」",
      "score": 0,
      "notes": "Bug: symbol resolver 缺少映射",
      "bug_reported": true
    }
  ],
  "total_score": 85,
  "grade": "A"
}
```

---

## 快速測試清單

執行測試時，可直接複製以下問題：

### 基礎測試（3 題）
```
1. BTC 價格
2. 台積電股價
3. TSLA 價格
```

### 中級測試（3 題）
```
4. ETH 技術分析
5. 鴻海的本益比和 EPS
6. 比特幣最新新聞
```

### 高級測試（4 題）
```
7. 台積電 ADR 和台股的價差
8. [多輪] BTC 現在多少錢？ -> 它的技術面怎麼樣？ -> 有什麼新聞嗎？
9. 黃金價格
10. 我想投資輝達，給我完整分析
```

---

## 相關文件

- [Agent Chat 架構](./AGENT_CHAT_ARCHITECTURE.md)
- [測試代碼](../tests/test_interactive_user.py)
- [Agent 註冊表](../core/agents/agent_registry.py)
- [工具註冊表](../core/agents/tool_registry.py)
- [符號解析器](../core/tools/universal_resolver.py)

---

**測試愉快！** 🚀
