# Langfuse 監控系統指南

## 1. 系統概觀

本系統整合了 **Langfuse (V3)** 作為 LLM 應用程式的可觀測性與分析平台。透過 Langfuse，我們可以追蹤每一個 Agent 的執行軌跡（Trace）、監控 Token 消耗、分析延遲（Latency），並回溯完整的對話歷史。

### 儀表板存取
- **網址**: `http://172.23.53.2:3000` (內網位址)
- **用途**: 查看即時 Log、除錯、成本分析

---

## 2. 監控欄位說明 (Traces & Observations)

Langfuse 的核心概念是 **Trace** (軌跡)，一個 Trace 代表一次完整的使用者請求（從 Request 到 Response）。Trace 內部包含多個 **Observation** (觀察點)，如 Spans (跨度) 和 Generations (生成)。

以下是您在 Langfuse 儀表板上會看到的關鍵欄位及其意義：

### 2.1 基礎識別欄位 (Identity)

| 欄位名稱 (Field) | 程式碼對應變數 | 意義與用途 |
| :--- | :--- | :--- |
| **Trace Name** | `langchain_app` (預設) | 該次執行的名稱，通常對應到 LangGraph 的 Workflow 名稱。 |
| **User ID** | `langfuse_user_id` | **用戶唯一識別碼**。用於追蹤特定使用者的所有歷史行為，分析個別用戶的長期偏好或問題。 |
| **Session ID** | `langfuse_session_id` | **對話會話 ID**。將多輪對話歸類為同一個 Session。例如：使用者的一次完整諮詢過程。 |
| **Tags** | `langfuse_tags` | **標籤**。用於快速過濾與分類。例如：`["prod", "qwen-4b"]` (生產環境、使用模型版本)。 |

### 2.2 執行數據欄位 (Execution Data)

| 欄位名稱 | 意義 |
| :--- | :--- |
| **Input** | **輸入內容**。使用者的原始問題，或是某個中間步驟（Node）接收到的參數。 |
| **Output** | **輸出結果**。Agent 的最終回答，或是某個 Node 產生的結果（如檢索到的文件、Planning 的計畫）。 |
| **Metadata** | **元數據**。紀錄額外的上下文資訊，例如：<br>- `thread_id`: LangGraph 的執行緒 ID<br>- `source`: 觸發來源<br>- `model_params`: 模型參數 (temperature 等) |
| **Latency** | **延遲時間**。該步驟從開始到結束耗費的秒數。可用於找出系統瓶頸（例如：檢索太慢或生成太久）。 |
| **Start Time** | **開始時間**。請求發生的確切時間點。 |

### 2.3 消耗與成本 (Usage & Cost)

| 欄位名稱 | 意義 |
| :--- | :--- |
| **Model** | **模型名稱**。例如 `qwen3-4b-instruct`。 |
| **Token Usage** | **Token 用量**。細分為：<br>- `Input Tokens` (Prompt): 提示詞消耗量<br>- `Output Tokens` (Completion): 生成內容消耗量<br>- `Total Tokens`: 總消耗量 |
| **Cost** | **預估成本**。根據模型定價計算的費用（本地模型通常設為 0 或自訂費率）。 |

### 2.4 評估與反饋 (Scores & Evaluation)

| 欄位名稱 | 意義 |
| :--- | :--- |
| **Scores** | **評分**。對該次回答的品質評分 (0-1 或 1-5)。<br>- 可以是 LLM 自動評分 (如 `user_feedback`, `hallucination_score`)<br>- 也可以是人工在 UI 上標註的評分。 |

---

## 3. LangGraph 節點監控

由於系統使用 LangGraph，Langfuse 會自動將圖中的每個 **Node (節點)** 記錄為一個 **Span**。您可以在 Trace 的詳細視圖中看到樹狀結構：

```text
Trace: "Medical Inquiry" (總覽)
 ├── Span: extract_current_query (提取問題)
 ├── Span: retrieve_memory (讀取記憶)
 ├── Span: classify_query_type (問題分類 - 調用 LLM)
 │    └── Generation: Qwen3-4B (實際的模型生成)
 ├── Span: planning_node (規劃檢索路徑)
 ├── Span: retrieve_knowledge (檢索資料庫)
 │    └── Span: VectorStore Search (向量搜尋細節)
 └── Span: generate_response (生成最終回答 - 調用 LLM)
      └── Generation: Qwen3-4B
```

這樣您可以清楚看到：
1. **哪個節點花費時間最長？**
2. **Retrieve 到底撈到了什麼文件？** (點擊 retrieve_knowledge span 查看 output)
3. **LLM 的 Prompt 到底長什麼樣？** (點擊 Generation span 查看 input)

---

## 4. 如何在程式碼中注入資訊

在 `Agent_System/monitoring/langfuse_integration.py` 中，我們使用 `get_langfuse_config` 函數來注入識別資訊：

```python
# 範例：在呼叫 LangGraph 時傳入
config, handler = get_langfuse_config(
    user_id="user123",           # 對應 User ID 欄位
    session_id="session_abc",    # 對應 Session ID 欄位
    tags=["medical", "test"],    # 對應 Tags 欄位
    metadata={"source": "cli"}   # 對應 Metadata 欄位
)

# 執行 Graph
graph.invoke(inputs, config=config)
```

系統會自動將這些資訊傳送至 Langfuse 伺服器。
