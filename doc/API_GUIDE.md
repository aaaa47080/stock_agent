# 醫療諮詢系統 API 使用指南

## 目錄
- [基本資訊](#基本資訊)
- [快速開始](#快速開始)
- [API 端點](#api-端點)
- [使用範例](#使用範例)
- [進階配置](#進階配置)

---

## 基本資訊

**服務地址**: `http://172.23.37.2:8100`

**API 特點**:
- 智能醫療問答系統
- 支援多輪對話記憶
- 整合多個醫療知識庫
- 支援即時搜尋補充
- 用戶資料隔離保護
- 支援表格圖片和衛教圖片返回

---

## 可用資料源說明

在使用 `/chat` 接口時，可以透過 `datasource_ids` 參數指定要檢索的資料庫。以下為系統支援的資料源：

| 資料源 ID | 名稱 | 內容說明 |
|-----------|------|----------|
| `medical_kb_jsonl` | 醫療知識庫(JSONL) | 核心問答庫，包含感染控制、傳染病處理指引。支援動態 PDF 關聯檢索。 |
| `public_health` | 衛教園地 | 醫院官方衛教單張內容，涵蓋慢性病管理、用藥指導、檢查流程等。 |
| `dialysis_education` | 洗腎衛教專區 | 針對血液透析、腹膜透析患者的專業照護指引與營養建議（含表格）。 |
| `educational_images` | 衛教圖片檢索 | 檢索相關的視覺化衛教圖片，提供步驟圖示或症狀對照。 |

> 💡 **提示**：若 `datasource_ids` 設為 `null`，系統將根據問題自動選擇適用的資料源（預設包含 `public_health` 與 `educational_images`）。

---

## 快速開始

### 1. 健康檢查
```bash
curl http://172.23.37.2:8100/
```
**回應**:
```json
{
  "status": "ok",
  "timestamp": "2025-12-30T12:00:00"
}
```

### 2. 最簡單的問答
```bash
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "什麼是高血壓？"
  }'
```

---

## API 端點

### 1. GET `/` - 健康檢查
檢查服務是否正常運行。

#### 請求參數
無

#### 回應參數
| 參數 | 類型 | 說明 |
|------|------|------|
| `status` | string | 服務狀態 (`"ok"` 表示正常) |
| `timestamp` | string | 當前時間（ISO 8601 格式） |

#### 回應範例
```json
{
  "status": "ok",
  "timestamp": "2025-12-30T12:00:00"
}
```

---

### 2. GET `/test` - 測試頁面
提供互動式測試頁面，方便在瀏覽器中測試 API。

#### 請求參數
無

#### 回應
返回 HTML 測試頁面

#### 使用方式
直接在瀏覽器中訪問：`http://172.23.37.2:8100/test`

---

### 3. GET `/api/config` - 獲取系統配置
查看可用的知識庫、工具和記憶選項。

#### 請求參數
無

#### 回應參數
| 參數 | 類型 | 說明 |
|------|------|------|
| `datasources` | object | 知識庫資料源配置 |
| `datasources.available` | array | 所有可用的知識庫列表 |
| `datasources.enabled_ids` | string[] | 已啟用的知識庫 ID 列表 |
| `datasources.default_ids` | string[] | 系統預設使用的知識庫 ID |
| `tools` | object | 外部工具配置 |
| `tools.available` | array | 所有可用的工具列表 |
| `tools.enabled_ids` | string[] | 已啟用的工具 ID 列表 |
| `tools.default_ids` | string[] | 系統預設使用的工具 ID |
| `memory_options` | object | 記憶系統配置選項 |
| `privacy_protection` | object | 隱私保護機制說明 |
| `default_settings` | object | 系統預設設定 |

#### 回應範例
```json
{
  "datasources": {
    "available": [
      {
        "id": "dialysis_education",
        "name": "洗腎衛教專區",
        "description": "洗腎衛教專區 - PDF 格式",
        "enabled": true,
        "default_k": 3,
        "support_medical": true,
        "support_procedure": true,
        "metadata": {"disease_category": "kidney", "data_source": "ocr"}
      },
      {
        "id": "medical_kb_jsonl",
        "name": "醫療知識庫(JSONL)",
        "description": "醫療知識庫(JSONL) - JSONL 格式",
        "enabled": true,
        "default_k": 3,
        "support_medical": true,
        "support_procedure": true,
        "metadata": {"has_reference": true}
      }
    ],
    "enabled_ids": ["dialysis_education", "medical_kb_jsonl", "public_health", "educational_images"],
    "default_ids": ["public_health", "educational_images"],
    "description": "可用的知識庫資料源，可在請求中透過 datasource_ids 參數指定"
  },
  "tools": {
    "available": [
      {
        "id": "cdc_realtime_search",
        "name": "CDC 即時搜尋",
        "description": "即時搜尋台灣 CDC 網站，獲取最新疫情資訊、防疫政策、統計數據",
        "enabled": true,
        "support_medical": true,
        "support_general": false,
        "timeout": 30,
        "metadata": {"category": "external_search", "data_source": "taiwan_cdc", "search_type": "realtime"}
      }
    ],
    "enabled_ids": ["cdc_realtime_search"],
    "default_ids": ["cdc_realtime_search"],
    "description": "可用的外部工具（如即時搜尋），可在請求中透過 enabled_tool_ids 參數指定"
  },
  "memory_options": {
    "short_term_memory": {
      "description": "短期記憶（對話歷史），保留當前會話的問答記錄",
      "default": true,
      "privacy": "隔離：每個 session_id 獨立，不跨會話共享"
    },
    "long_term_memory": {
      "description": "長期記憶（個人病史），記錄用戶的健康資訊（如過敏史、病史）",
      "default": false,
      "privacy": "隔離：每個 user_id 獨立，不跨用戶共享",
      "note": "目前預設停用，如需使用請聯繫管理員"
    }
  },
  "privacy_protection": {
    "cache_strategy": {
      "query_cache": "完全隔離（包含 user_id）",
      "planning_cache": "完全隔離（包含 user_id）",
      "retrieval_cache": "主問題不快取，子問題可跨用戶共享（僅快取公開醫療知識）"
    },
    "description": "系統已實施三層快取隱私保護機制，確保用戶個人信息不會泄露"
  },
  "default_settings": {
    "enable_short_term_memory": true,
    "enable_long_term_memory": false,
    "datasource_ids": ["public_health", "educational_images"],
    "enabled_tool_ids": ["cdc_realtime_search"]
  }
}
```

---

### 4. POST `/chat` - 一般問答（完整回應）
發送問題並一次性接收完整回答。

#### 請求參數（Request Body）
| 參數 | 類型 | 必填 | 說明 | 預設值 |
|------|------|------|------|--------|
| `user_id` | string | 是 | 用戶唯一識別碼，用於隔離不同用戶的資料 | - |
| `message` | string | 是 | 用戶問題（支援中英文） | - |
| `session_id` | string | 否 | 對話會話 ID，用於追蹤多輪對話 | `"default_session"` |
| `enable_short_term_memory` | boolean | 否 | 是否啟用短期記憶（對話歷史） | `true` |
| `enable_long_term_memory` | boolean | 否 | 是否啟用長期記憶（個人病史） | `false` |
| `datasource_ids` | string[] | 否 | 指定使用的知識庫 ID 列表，`null` 使用系統預設 | `null` |
| `enabled_tool_ids` | string[] | 否 | 指定使用的外部工具 ID 列表，`null` 使用系統預設 | `null` |

#### 回應參數（Response）
| 參數 | 類型 | 說明 |
|------|------|------|
| `status` | string | 回應狀態 (`"success"` 或 `"error"`) |
| `answer` | string | AI 生成的完整回答 |
| `query_type` | string | 問題類型（如 `medical_knowledge`、`greet`、`out_of_scope`） |
| `matched_table_images` | array | 相關的醫療表格圖片列表 |
| `matched_table_images[].image_path` | string | 表格圖片檔名 |
| `matched_table_images[].similarity` | number | 相似度分數 (0-1) |
| `matched_table_images[].source` | string | 來源類型 |
| `matched_educational_images` | array | 相關的衛教圖片列表 |
| `matched_educational_images[].filename` | string | 衛教圖片檔名 |
| `matched_educational_images[].image_path` | string | 圖片路徑 |
| `matched_educational_images[].health_topic` | string | 健康主題 |
| `matched_educational_images[].core_message` | string | 核心訊息 |
| `matched_educational_images[].score` | number | 匹配分數 (0-1) |
| `structured_response` | object | 結構化回應（如果可解析） |
| `structured_response.summary` | string | 綜合建議：對問題的完整回答和建議 |
| `structured_response.references` | array | 參考依據列表 |
| `structured_response.references[].filename` | string | 文件檔名 |
| `structured_response.references[].content` | string | 提取的內容 |

#### 回應範例
```json
{
  "status": "success",
  "answer": "高血壓是指血壓持續高於正常值...",
  "query_type": "medical_knowledge",
  "matched_table_images": [
    {
      "image_path": "高血壓衛教_p3_t1.jpg",
      "similarity": 0.95,
      "source": "matching"
    }
  ],
  "matched_educational_images": [
    {
      "filename": "高血壓預防_p1_img1.jpg",
      "image_path": "/path/to/image",
      "health_topic": "高血壓預防",
      "core_message": "定期量血壓，預防高血壓",
      "score": 0.92
    }
  ],
  "structured_response": {
    "summary": "高血壓是指血壓持續高於正常值...建議定期監測血壓...",
    "references": [
      {
        "filename": "高血壓防治指南.pdf",
        "content": "高血壓定義為收縮壓 >= 140 mmHg...",
        "page": "3"
      }
    ],
    "query_type": "medical_knowledge",
    "matched_table_images": [],
    "matched_educational_images": []
  }
}
```

---

### 5. POST `/chat/stream` - 串流問答（即時回應）
發送問題並即時接收回答（逐字輸出）。

#### 請求參數（Request Body）
與 `/chat` 完全相同：

| 參數 | 類型 | 必填 | 說明 | 預設值 |
|------|------|------|------|--------|
| `user_id` | string | 是 | 用戶唯一識別碼 | - |
| `message` | string | 是 | 用戶問題 | - |
| `session_id` | string | 否 | 對話會話 ID | `"default_session"` |
| `enable_short_term_memory` | boolean | 否 | 啟用對話歷史 | `true` |
| `enable_long_term_memory` | boolean | 否 | 啟用個人病史記憶 | `false` |
| `datasource_ids` | string[] | 否 | 指定使用的知識庫 | `null` |
| `enabled_tool_ids` | string[] | 否 | 指定使用的外部工具 | `null` |

#### 回應格式（SSE - Server-Sent Events）

每個事件格式為：`data: {"type": "事件類型", "content": "內容"}\n\n`

**事件類型及參數**:

| 事件類型 | content 類型 | 說明 | 何時發送 |
|----------|--------------|------|----------|
| `token` | string | 單個文字字符 | 每生成一個字就發送 |
| `table_images` | string (JSON array) | 相關表格圖片列表 | 生成完整回答後 |
| `educational_images` | string (JSON array) | 相關衛教圖片列表 | 生成完整回答後 |
| `structured_data` | string (JSON object) | 結構化回應資料 | 生成完整回答後 |
| `done` | string | 完成狀態 (`"success"`) | 所有內容發送完畢 |
| `error` | string | 錯誤訊息 | 發生錯誤時 |

#### 回應範例
```
data: {"type": "structured_data", "content": "{\"summary\":\"高血壓是指...\",\"references\":[...]}"}

data: {"type": "table_images", "content": "[{\"image_path\":\"高血壓衛教_p3_t1.jpg\",\"similarity\":0.95}]"}

data: {"type": "educational_images", "content": "[{\"filename\":\"高血壓預防_p1_img1.jpg\",\"health_topic\":\"高血壓預防\",\"score\":0.92}]"}

data: {"type": "token", "content": "高"}

data: {"type": "token", "content": "血"}

data: {"type": "token", "content": "壓"}

data: {"type": "token", "content": "是"}

data: {"type": "token", "content": "..."}

data: {"type": "done", "content": "success"}

```

---

### 6. GET `/api/table-image/{filename}` - 獲取表格圖片
獲取回答中提到的醫療表格圖片。

#### 請求參數（Path Parameter）
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `filename` | string | 是 | 圖片檔名（如 `高血壓衛教_p3_t1.jpg`） |

#### 回應
- **成功**: 返回圖片檔案（JPEG/PNG）
- **失敗**: HTTP 404（檔案不存在）或 HTTP 400（無效檔名）

#### 使用範例
```bash
curl http://172.23.37.2:8100/api/table-image/高血壓衛教_p3_t1.jpg \
  --output image.jpg
```

---

### 7. GET `/api/educational-image/{filename}` - 獲取衛教圖片
獲取回答中提到的衛教圖片。

#### 請求參數（Path Parameter）
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `filename` | string | 是 | 衛教圖片檔名（如 `B型肝炎衛教_p1_img1.jpg`） |

#### 回應
- **成功**: 返回圖片檔案（JPEG/PNG）
- **失敗**: HTTP 404（檔案不存在）或 HTTP 400（無效檔名）

#### 使用範例
```bash
curl http://172.23.37.2:8100/api/educational-image/B型肝炎衛教_p1_img1.jpg \
  --output edu_image.jpg
```

---

### 8. DELETE `/memory/clear/short_term` - 清除對話歷史
清除指定用戶的短期記憶（對話歷史）。

#### 請求參數（Query Parameter）
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `user_id` | string | 是 | 要清除記憶的用戶 ID |

#### 回應參數
| 參數 | 類型 | 說明 |
|------|------|------|
| `status` | string | 操作狀態 (`"success"`) |

#### 使用範例
```bash
curl -X DELETE "http://172.23.37.2:8100/memory/clear/short_term?user_id=user123"
```

#### 回應範例
```json
{
  "status": "success"
}
```

---

### 9. DELETE `/memory/clear/long_term` - 清除長期記憶
清除指定用戶的長期記憶（個人病史）。

#### 請求參數（Query Parameter）
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `user_id` | string | 是 | 要清除記憶的用戶 ID |

#### 回應參數
| 參數 | 類型 | 說明 |
|------|------|------|
| `status` | string | 操作狀態 |
| `message` | string | 操作結果訊息 |

#### 使用範例
```bash
curl -X DELETE "http://172.23.37.2:8100/memory/clear/long_term?user_id=user123"
```

#### 回應範例
```json
{
  "status": "success",
  "message": "長期記憶已清除"
}
```

---

### 10. DELETE `/memory/clear/all` - 清除所有記憶
清除指定用戶的所有記憶（短期+長期）。

#### 請求參數（Query Parameter）
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `user_id` | string | 是 | 要清除記憶的用戶 ID |

#### 回應參數
| 參數 | 類型 | 說明 |
|------|------|------|
| `status` | string | 操作狀態 |
| `message` | string | 操作結果訊息 |

#### 使用範例
```bash
curl -X DELETE "http://172.23.37.2:8100/memory/clear/all?user_id=user123"
```

#### 回應範例
```json
{
  "status": "success",
  "message": "所有記憶已清除"
}
```

---

## 使用範例

### 範例 1: 基本問答
```bash
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "糖尿病患者可以吃什麼水果？"
  }'
```

### 範例 2: 多輪對話
```bash
# 第一輪
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "session_id": "session_001",
    "message": "什麼是糖尿病？"
  }'

# 第二輪（系統會記住前一輪對話）
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "session_id": "session_001",
    "message": "它有什麼症狀？"
  }'
```

### 範例 3: 指定知識庫
```bash
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "洗腎患者飲食建議",
    "datasource_ids": ["dialysis_education"]
  }'
```

### 範例 4: 啟用即時搜尋
```bash
curl -X POST http://172.23.37.2:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "message": "最新的流感疫情如何？",
    "enabled_tool_ids": ["cdc_realtime_search"]
  }'
```

### 範例 5: 串流回應（Python）
```python
import requests
import json

def chat_stream(user_id, message):
    url = "http://172.23.37.2:8100/chat/stream"
    data = {
        "user_id": user_id,
        "message": message
    }

    response = requests.post(url, json=data, stream=True)

    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                event_data = json.loads(line_str[6:])

                if event_data['type'] == 'token':
                    print(event_data['content'], end='', flush=True)
                elif event_data['type'] == 'table_images':
                    images = json.loads(event_data['content'])
                    print(f'\n[表格圖片: {len(images)} 張]')
                elif event_data['type'] == 'educational_images':
                    images = json.loads(event_data['content'])
                    print(f'\n[衛教圖片: {len(images)} 張]')
                elif event_data['type'] == 'done':
                    print('\n完成！')
                    break

# 使用範例
chat_stream("user123", "什麼是高血壓？")
```

### 範例 6: 串流回應（JavaScript）
```javascript
async function chatStream(userId, message) {
  const response = await fetch('http://172.23.37.2:8100/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      message: message
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const eventData = JSON.parse(line.slice(6));

        if (eventData.type === 'token') {
          process.stdout.write(eventData.content);
        } else if (eventData.type === 'table_images') {
          const images = JSON.parse(eventData.content);
          console.log(`\n[表格圖片: ${images.length} 張]`);
        } else if (eventData.type === 'educational_images') {
          const images = JSON.parse(eventData.content);
          console.log(`\n[衛教圖片: ${images.length} 張]`);
        } else if (eventData.type === 'done') {
          console.log('\n完成！');
          return;
        }
      }
    }
  }
}

// 使用範例
chatStream('user123', '什麼是高血壓？');
```

### 範例 7: 顯示衛教圖片（HTML）
```html
<!DOCTYPE html>
<html>
<head>
  <title>醫療諮詢系統</title>
</head>
<body>
  <div id="answer"></div>
  <div id="images"></div>

  <script>
    async function askQuestion(message) {
      const response = await fetch('http://172.23.37.2:8100/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'user123',
          message: message
        })
      });

      const data = await response.json();

      // 顯示回答
      document.getElementById('answer').innerText = data.answer;

      // 顯示表格圖片
      const imagesDiv = document.getElementById('images');
      imagesDiv.innerHTML = '';

      if (data.matched_table_images) {
        data.matched_table_images.forEach(img => {
          const imgEl = document.createElement('img');
          imgEl.src = `http://172.23.37.2:8100/api/table-image/${img.image_path}`;
          imgEl.style.maxWidth = '100%';
          imagesDiv.appendChild(imgEl);
        });
      }

      // 顯示衛教圖片
      if (data.matched_educational_images) {
        data.matched_educational_images.forEach(img => {
          const imgEl = document.createElement('img');
          imgEl.src = `http://172.23.37.2:8100/api/educational-image/${img.filename}`;
          imgEl.style.maxWidth = '100%';
          imgEl.title = img.health_topic + ': ' + img.core_message;
          imagesDiv.appendChild(imgEl);
        });
      }
    }

    // 使用範例
    askQuestion('B型肝炎的預防方法？');
  </script>
</body>
</html>
```

---

## 進階配置

### 知識庫選擇策略
```json
{
  "datasource_ids": null,                        // 使用系統預設的所有知識庫
  "datasource_ids": [],                          // 不使用任何知識庫（不推薦）
  "datasource_ids": ["dialysis_education"],      // 只使用洗腎衛教知識庫
  "datasource_ids": ["dialysis_education", "medical_kb_jsonl"]    // 使用多個知識庫
}
```

### 記憶管理最佳實踐

#### 用戶識別設計
- **`user_id`**: 用於識別不同的真實用戶（跨會話）
- **`session_id`**: 用於識別同一用戶的不同對話（單次會話）

```
用戶 A (user_id: "alice")
  |-- 對話 1 (session_id: "alice_2025_12_30_morning")
  |-- 對話 2 (session_id: "alice_2025_12_30_afternoon")
  +-- 對話 3 (session_id: "alice_2025_12_31")

用戶 B (user_id: "bob")
  |-- 對話 1 (session_id: "bob_2025_12_30")
  +-- 對話 2 (session_id: "bob_2025_12_31")
```

#### 記憶隔離機制
- **短期記憶**: 按 `session_id` 隔離（不跨對話）
- **長期記憶**: 按 `user_id` 隔離（跨對話，但不跨用戶）
- **快取**: 完全隔離，包含 `user_id` 確保隱私

### 隱私保護說明

系統實施三層隱私保護：

1. **查詢分析快取**: 完全隔離（包含 user_id）
2. **規劃快取**: 完全隔離（包含 user_id）
3. **檢索快取**:
   - 主問題不快取（保護隱私）
   - 子問題可共享（僅公開醫療知識）

---

## 常見問題

### Q1: 如何實現多輪對話？
保持相同的 `user_id` 和 `session_id`，系統會自動記住對話歷史。

### Q2: 如何開始新的對話？
使用新的 `session_id` 即可。

### Q3: 回答中的圖片如何獲取？
- **表格圖片**: 從 `matched_table_images` 中獲取 `image_path`，然後調用 `/api/table-image/{filename}` 下載
- **衛教圖片**: 從 `matched_educational_images` 中獲取 `filename`，然後調用 `/api/educational-image/{filename}` 下載

### Q4: 串流和非串流有什麼區別？
- **非串流** (`/chat`): 等待完整回答後一次性返回，適合後端處理
- **串流** (`/chat/stream`): 逐字返回，適合即時聊天界面

### Q5: 如何知道系統支援哪些知識庫？
調用 `GET /api/config` 查看所有可用的 `datasources` 和 `tools`。

### Q6: 如何測試 API？
1. 使用瀏覽器訪問 `http://172.23.37.2:8100/test` 進入測試頁面
2. 使用 Swagger 文檔: `http://172.23.37.2:8100/docs`
3. 使用 ReDoc 文檔: `http://172.23.37.2:8100/redoc`

---

## 技術支援

如有問題，請聯繫系統管理員或查看詳細 API 文檔。

**Swagger 文檔**: `http://172.23.37.2:8100/docs`
**ReDoc 文檔**: `http://172.23.37.2:8100/redoc`
**測試頁面**: `http://172.23.37.2:8100/test`
