# Google Gemini API 兼容性修復

## 問題描述

### 錯誤 1: AttributeError
```
AttributeError: module 'google.generativeai' has no attribute 'chat'
```

**原因**:
- Google Gemini API 的接口與 OpenAI API 完全不同
- 程式碼嘗試在 Gemini 客戶端上調用 `client.chat.completions.create()`
- 但 Gemini 沒有 `.chat` 屬性

### 錯誤 2: ValidationError
```
pydantic_core._pydantic_core.ValidationError: 4 validation errors for ResearcherDebate
researcher_stance: Field required
argument: Field required
...
```

**原因**:
- Gemini 返回的 JSON 結構不符合預期
- 可能包含包裝鍵（如 'task'）或額外內容
- 模型配置使用了不存在的模型名稱（如 "gemini-2.5-pro"）

## 解決方案

創建了 `GeminiWrapper` 類來包裝 Google Gemini API，提供 OpenAI 兼容的接口。

### 主要改動

#### 1. llm_client.py - GeminiWrapper 類增強

**新增 GeminiWrapper 類**:
- ✅ 提供 `chat.completions.create()` 方法
- ✅ 自動轉換 OpenAI 格式的請求到 Gemini 格式
- ✅ 自動轉換 Gemini 響應到 OpenAI 格式
- ✅ 支持 JSON 模式輸出 (`response_mime_type`)
- ✅ 系統指令強制純 JSON 輸出
- ✅ 自動檢測和移除 markdown 代碼塊
- ✅ 自動解包常見的包裝鍵（task, response, output, result, data）
- ✅ 智能 JSON 提取（處理混合內容）
- ✅ 詳細的調試日誌

**修改客戶端創建邏輯**:
```python
# 之前
return genai  # 直接返回模組

# 現在
return GeminiWrapper(genai)  # 返回包裝器
```

#### 2. config.py - 模型配置修正

**修正前**:
```python
{"provider": "google_gemini", "model": "gemini-2.5-pro"}  # ❌ 不存在
{"provider": "openai", "model": "gpt-5-mini"}  # ❌ 不存在
```

**修正後**:
```python
{"provider": "google_gemini", "model": "gemini-1.5-flash"}  # ✅ 存在且穩定
{"provider": "openai", "model": "gpt-4o-mini"}  # ✅ 存在
```

### 功能特點

- ✅ OpenAI 風格 API 調用: `client.chat.completions.create()`
- ✅ 自動消息格式轉換
- ✅ JSON 模式支持 (使用 `response_mime_type`)
- ✅ 溫度和其他參數配置
- ✅ 響應格式統一

### 使用方式

現在可以像使用 OpenAI API 一樣使用 Gemini:

```python
from llm_client import LLMClientFactory

# 創建 Gemini 客戶端
client = LLMClientFactory.create_client("google_gemini")

# 使用 OpenAI 風格的 API
response = client.chat.completions.create(
    model="gemini-2.0-flash-exp",
    messages=[{"role": "user", "content": "Hello!"}],
    response_format={"type": "json_object"},
    temperature=0.5
)

# 訪問響應
content = response.choices[0].message.content
```

### 注意事項

1. **API 配額**: Google Gemini 免費版有嚴格的速率限制
   - 如果遇到 429 錯誤，表示超過配額
   - 需要等待或升級到付費版

2. **模型名稱**: 使用正確的 Gemini 模型名稱（截至 2024-12）
   - ✅ `gemini-1.5-pro` (推薦 - 高質量)
   - ✅ `gemini-1.5-flash` (推薦 - 快速且穩定)
   - ✅ `gemini-2.0-flash-exp` (實驗版 - 可能不穩定)
   - ✅ `gemini-pro` (舊版)
   - ❌ `gemini-2.5-pro` (不存在)
   - ❌ `gemini-2.0-pro` (不存在)

3. **JSON 模式**: Gemini 使用 `response_mime_type` 而非 OpenAI 的 `response_format`
   - 包裝器自動處理此轉換

## 測試

運行測試腳本驗證修復:
```bash
python test_gemini_wrapper.py
```

## 配置示例

在 `config.py` 中配置 Gemini 模型:

```python
BULL_COMMITTEE_MODELS = [
    {"provider": "openai", "model": "gpt-4o"},
    {"provider": "google_gemini", "model": "gemini-2.0-flash-exp"},
    {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b:free"},
]
```

確保設置了環境變量:
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

## 故障排除

### 如果仍然遇到 ValidationError

1. **檢查調試日誌**：
   - 查找 `🔍 Gemini JSON 響應鍵:` 訊息
   - 確認返回的鍵是否與模型期望的匹配

2. **查看包裝鍵警告**：
   - 如果看到 `⚠️ 檢測到 Gemini 包裝鍵`，wrapper 會自動處理
   - 如果解包失敗，可能需要手動調整提示詞

3. **使用不同的 Gemini 模型**：
   ```python
   # 嘗試更穩定的模型
   {"provider": "google_gemini", "model": "gemini-1.5-pro"}

   # 或更快的模型
   {"provider": "google_gemini", "model": "gemini-1.5-flash"}
   ```

4. **臨時禁用 Gemini**：
   如果問題持續，可以暫時移除 Gemini 模型：
   ```python
   BULL_COMMITTEE_MODELS = [
       {"provider": "openai", "model": "gpt-4o-mini"},
       # {"provider": "google_gemini", "model": "gemini-1.5-flash"},  # 暫時註解
       {"provider": "openrouter", "model": "qwen/qwen3-235b-a22b:free"},
   ]
   ```

### 調試輸出說明

- `🔍 Gemini JSON 響應鍵: ['key1', 'key2', ...]` - 成功解析 JSON
- `⚠️ 檢測到 Gemini 包裝鍵 'task'` - 檢測到包裝，嘗試解包
- `✅ 解包成功` - 成功提取內部 JSON
- `✅ JSON 提取成功` - 從混合內容中提取 JSON
- `⚠️ Gemini JSON 解析失敗` - JSON 格式錯誤（會顯示前500字符）

### 最佳實踐

1. **優先使用穩定模型**：`gemini-1.5-flash` 或 `gemini-1.5-pro`
2. **監控 API 配額**：訪問 https://ai.dev/usage 查看使用情況
3. **混合使用多個提供商**：不要完全依賴單一 LLM 提供商
4. **查看日誌輸出**：調試信息會幫助診斷問題

## 總結

這個修復允許系統無縫使用 Google Gemini API，同時保持代碼的一致性。所有 Agent (分析師、研究員、交易員等) 現在都可以使用任何支持的 LLM 提供商，無需修改 Agent 代碼。

### 已修復的問題

- ✅ AttributeError: 'genai' 模組沒有 'chat' 屬性
- ✅ ValidationError: Gemini 返回不正確的 JSON 結構
- ✅ 模型名稱錯誤（gemini-2.5-pro, gpt-5-mini）
- ✅ JSON 包裝鍵處理
- ✅ Markdown 代碼塊自動移除
- ✅ 混合內容 JSON 提取

### 現在支持的 LLM 提供商

- ✅ OpenAI (GPT-4o, GPT-4o-mini, etc.)
- ✅ Google Gemini (gemini-1.5-pro, gemini-1.5-flash, etc.)
- ✅ OpenRouter (Claude, Llama, Qwen, etc.)
