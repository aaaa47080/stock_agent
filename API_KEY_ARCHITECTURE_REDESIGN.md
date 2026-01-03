# API Key 架構重新設計 - 用戶自帶 Key 模式

**日期：** 2026-01-03
**狀態：** 🚧 前端完成 70% | 後端待實施
**目標：** 從服務器共用 key 轉變為用戶自帶 key

---

## 📋 問題描述

### 原始設計的問題：
1. ❌ 系統從 `.env` 讀取 API key，所有用戶共用同一個 key
2. ❌ 服務器承擔所有 API 費用
3. ❌ API 配額會很快耗盡
4. ❌ 無法擴展到多用戶場景
5. ❌ 不適合生產環境部署

### 正確的架構（SaaS 標準）：
✅ 每個用戶輸入自己的 API key
✅ Key 存儲在客戶端（localStorage）
✅ 每次請求時傳遞用戶的 key
✅ 後端使用用戶提供的 key 調用 LLM
✅ 用戶自己承擔 API 費用

---

## ✅ 已完成的工作

### 1. 前端 - API Key 管理系統
**創建的文件：**
- `web/js/apiKeyManager.js` - API key 管理模組
- `web/js/llmSettings.js` - 設定界面邏輯

**功能：**
- ✅ 支援 3 個 LLM 提供商（OpenAI、Google Gemini、OpenRouter）
- ✅ Key 存儲在 `localStorage`（僅存在用戶瀏覽器）
- ✅ 格式驗證（檢查 key 前綴和長度）
- ✅ 顯示/隱藏 key 功能
- ✅ 選擇當前使用的 provider

### 2. 前端 - 狀態檢查和顯示
**修改的文件：**
- `web/js/app.js` - 實時檢查用戶是否有 API key
- `web/index.html` - Header 顯示狀態（綠色=已設置 / 紅色=未設置）

**功能：**
- ✅ 頁面加載時自動檢查
- ✅ 每 10 秒自動更新狀態
- ✅ 點擊紅色狀態可開啟設定面板

### 3. 前端 - 發送請求時攜帶 Key
**修改的文件：**
- `web/js/chat.js` - `sendMessage()` 函數

**改動：**
```javascript
// 舊版（錯誤）：不檢查 key，直接發送
await fetch('/api/analyze', {
    body: JSON.stringify({ message: text })
});

// 新版（正確）：檢查 key，並攜帶發送
const userKey = APIKeyManager.getCurrentKey();
if (!userKey) {
    alert('請先設置 API Key');
    return;
}

await fetch('/api/analyze', {
    body: JSON.stringify({
        message: text,
        user_api_key: userKey.key,      // ⭐ 用戶的 key
        user_provider: userKey.provider  // ⭐ provider類型
    })
});
```

### 4. 前端 - 設定界面
**修改的文件：**
- `web/index.html` - 添加 LLM API Key 設定區塊

**功能：**
- ✅ 下拉選擇 provider
- ✅ 輸入 API key（支援顯示/隱藏）
- ✅ 測試連接按鈕
- ✅ 保存設置按鈕
- ✅ 狀態提示（成功/失敗）
- ✅ 幫助鏈接（如何獲取 key）

### 5. 後端 - API 模型修改
**修改的文件：**
- `api/models.py` - `QueryRequest` 模型

**改動：**
```python
class QueryRequest(BaseModel):
    message: str
    user_api_key: str        # ⭐ 新增：用戶的 API key
    user_provider: str       # ⭐ 新增：provider 類型
```

---

## 🚧 待完成的工作（關鍵！）

### ⚠️ 後端 - 使用用戶提供的 Key

**需要修改的核心文件：**

1. **`api/routers/analysis.py`**
   ```python
   @router.post("/api/analyze")
   async def analyze_crypto(request: QueryRequest):
       # ⭐ 使用用戶的 key 創建 LLM 客戶端
       from utils.llm_client import LLMClientFactory

       user_client = LLMClientFactory.create_client(
           provider=request.user_provider,
           api_key=request.user_api_key  # 使用用戶的 key
       )

       # 傳遞給 bot 使用
       bot.process_message(..., llm_client=user_client)
   ```

2. **`interfaces/chat_interface.py` - CryptoAnalysisBot**
   - 修改 `process_message()` 接受 `llm_client` 參數
   - 不再從 .env 讀取 key

3. **`core/graph.py` - 工作流節點**
   - 所有節點的 LLM 調用都需要使用用戶傳來的 client
   - `prepare_data_node`、`analysts_node` 等

4. **`core/agents.py` - 各種 Agent**
   - `TechnicalAnalyst`、`SentimentAnalyst` 等
   - 改為接受外部傳入的 client

5. **`analysis/market_pulse.py`**
   - `MarketPulseAnalyzer` 改為接受 client 參數
   - 不再在 `__init__` 中創建 client

6. **`utils/utils.py`**
   - `audit_news_with_llm()` 改為接受 client 參數

---

## 🎯 實施策略（建議）

### 階段 1：創建用戶 Client 工廠（優先）
```python
# utils/user_client_factory.py
def create_user_llm_client(provider: str, api_key: str):
    """
    根據用戶提供的 key 創建 LLM 客戶端
    ⭐ 重要：不從 .env 讀取，完全使用用戶的 key
    """
    if provider == "openai":
        return openai.OpenAI(api_key=api_key)
    elif provider == "google_gemini":
        genai.configure(api_key=api_key)
        return GeminiWrapper(genai)
    elif provider == "openrouter":
        return openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
```

### 階段 2：修改 CryptoAnalysisBot
```python
class CryptoAnalysisBot:
    def process_message(self, message, user_client=None):
        # 使用用戶的 client 而不是全局的
        if not user_client:
            raise ValueError("需要用戶提供 API key")

        # 傳遞給所有子流程
        self.run_analysis(message, llm_client=user_client)
```

### 階段 3：修改所有 Agent
每個 Agent 的 `__init__` 改為接受 client：
```python
class TechnicalAnalyst:
    def __init__(self, client):
        self.client = client  # 使用傳入的 client

    def analyze(self, market_data):
        response = self.client.chat.completions.create(...)
```

### 階段 4：測試和驗證
- ✅ 測試未輸入 key 時是否正確阻止
- ✅ 測試使用 OpenAI key 是否正常
- ✅ 測試使用 Gemini key 是否正常
- ✅ 測試切換 provider 是否正常

---

## 📊 進度總結

| 模組 | 狀態 | 完成度 |
|------|------|--------|
| 前端 - API Key 管理 | ✅ 完成 | 100% |
| 前端 - 狀態檢查 | ✅ 完成 | 100% |
| 前端 - 請求攜帶 Key | ✅ 完成 | 100% |
| 前端 - 設定界面 | ✅ 完成 | 100% |
| 後端 - API 模型 | ✅ 完成 | 100% |
| 後端 - Client 工廠 | ❌ 待實施 | 0% |
| 後端 - Bot 改造 | ❌ 待實施 | 0% |
| 後端 - Agent 改造 | ❌ 待實施 | 0% |
| 後端 - Graph 改造 | ❌ 待實施 | 0% |

**總體進度：** 約 50%（前端完成，後端待實施）

---

## 🛡️ 安全考量

### ✅ 已實施的安全措施：
1. Key 僅存儲在用戶瀏覽器（localStorage）
2. 不會上傳到服務器數據庫
3. 每個用戶使用自己的 key，互不影響
4. 格式驗證防止無效 key

### ⚠️ 需要注意的安全問題：
1. **HTTPS 必須**：生產環境必須使用 HTTPS，防止 key 在傳輸中被竊取
2. **Rate Limiting**：後端應該添加速率限制，防止濫用
3. **Key 驗證**：後端應該驗證 key 的有效性（調用 `/api/settings/validate-key`）
4. **錯誤處理**：不要在錯誤訊息中暴露完整的 key

---

## 🎓 給開發者的建議

### 如果你想快速測試當前進度：
1. 打開前端設定頁面
2. 輸入你自己的 OpenAI API key
3. 點擊「測試連接」
4. 點擊「保存設置」
5. 回到聊天頁面，你會看到綠色狀態「AI Ready (OpenAI)」

**⚠️ 但是：** 目前發送分析請求仍會失敗，因為後端還沒有實施使用用戶 key 的邏輯！

### 下一步行動：
1. **優先級 1（必須）：** 實施後端 Client 工廠
2. **優先級 2（必須）：** 修改 CryptoAnalysisBot 接受用戶 client
3. **優先級 3（必須）：** 修改所有 Agent 使用傳入的 client
4. **優先級 4（可選）：** 添加更多安全措施（HTTPS、Rate Limiting）

---

## 📝 配置文件變更

### `.env` 文件的新角色：
```env
# ⚠️ 重要：這些 key 僅用於系統管理，不再用於用戶請求
# 用戶必須輸入自己的 API key 才能使用

# OKX 交易所 API（系統用）
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_PASSPHRASE=...

# 新聞 API（系統用）
NEWSAPI_KEY=...
CRYPTOPANIC_API_KEY=...

# ❌ 不再需要（用戶自帶）
# OPENAI_API_KEY=...
# GOOGLE_API_KEY=...
```

---

## 🎉 完成後的效果

**用戶體驗流程：**
1. 用戶打開網站
2. 看到紅色狀態「請設置 API Key」
3. 點擊狀態或前往設定
4. 選擇 provider（OpenAI/Gemini/OpenRouter）
5. 輸入自己的 API key
6. 測試連接（可選）
7. 保存設置
8. 看到綠色狀態「AI Ready」
9. 開始使用分析功能
10. 所有 API 調用使用用戶自己的 key 和配額

**服務器端優勢：**
- ✅ 零 LLM API 成本
- ✅ 無配額限制
- ✅ 可擴展到無限用戶
- ✅ 符合 SaaS 最佳實踐

---

**作者：** Claude Assistant
**最後更新：** 2026-01-03
