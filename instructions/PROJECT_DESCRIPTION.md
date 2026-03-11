# Pi Crypto Insight - 專案描述

## 專案概述

Pi Crypto Insight 是一個結合 **AI 智能分析** 與 **Pi Network 支付** 的加密貨幣社群平台。透過 LangGraph 多 Agent 架構，提供跨市場（加密貨幣、美股、台股）的智能分析，並整合 PTT 風格的論壇系統與 Pi Network 原生支付。

---

## 核心技術棧

| 層級 | 技術 | 用途 |
|------|------|------|
| **後端框架** | FastAPI | 高效能非同步 API |
| **AI 編排** | LangGraph + LangChain | 多 Agent 工作流程 |
| **LLM 整合** | OpenRouter | 多模型支援 |
| **資料庫** | PostgreSQL | 結構化資料儲存 |
| **快取** | Redis | 市場資料快取 |
| **即時通訊** | WebSocket + SSE | 雙向即時推送 |
| **前端** | HTML5 + Tailwind CSS | 響應式介面 |
| **圖表** | Lightweight Charts | 金融級 K 線圖 |
| **支付** | Pi Network SDK | 原生 Pi 支付 |

---

## 專案結構

```
stock_agent/
├── api/                          # API 層
│   ├── main.py                   # FastAPI 入口
│   ├── routers/                  # 路由模組
│   │   ├── admin/               # 管理後台 API
│   │   ├── forum/               # 論壇 API
│   │   ├── market/              # 市場數據 API
│   │   ├── messages.py          # 私訊 API
│   │   ├── friends.py           # 好友 API
│   │   ├── notifications.py     # 通知 API
│   │   ├── governance.py        # 社群治理 API
│   │   ├── scam_tracker/        # 詐騙舉報 API
│   │   └── alerts.py            # 價格警報 API
│   └── middleware/              # 中介軟體
│
├── core/                         # 核心業務邏輯
│   ├── agents/                  # AI Agent 系統
│   │   ├── manager.py          # Manager Agent（協調中心）
│   │   ├── agents/             # 專業 Agent
│   │   │   ├── crypto_agent.py
│   │   │   ├── us_stock_agent.py
│   │   │   ├── tw_stock_agent.py
│   │   │   ├── forex_agent.py
│   │   │   └── economic_agent.py
│   │   ├── router.py           # Agent 路由
│   │   └── tool_registry.py    # 工具註冊
│   │
│   ├── tools/                   # Agent 工具
│   │   ├── crypto_tools.py     # 加密貨幣工具
│   │   ├── us_stock_tools.py   # 美股工具
│   │   ├── tw_stock_tools.py   # 台股工具
│   │   └── web_search.py       # 網頁搜尋
│   │
│   ├── database/               # 資料庫層
│   │   ├── schema.py          # 資料表定義
│   │   ├── user.py            # 用戶操作
│   │   ├── forum.py           # 論壇操作
│   │   ├── messages/          # 訊息系統
│   │   └── governance/        # 治理系統
│   │
│   └── validators/             # 驗證器
│
├── trading/                     # 交易模組
│   └── okx_api_connector.py    # OKX 交易所連接
│
├── web/                         # 前端資源
│   ├── js/                     # JavaScript 模組
│   └── styles.css              # 樣式表
│
└── scripts/                     # 維護腳本
```

---

## AI Agent 架構

### Manager Agent（協調中心）
- **開放式意圖理解** - 無硬編碼類別/關鍵字
- **Vending/Restaurant 雙模式** - 簡單任務快速路由
- **DAG 任務執行** - 支援垂直/水平任務
- **選擇性上下文傳輸** - Sub-Agent 只接收必要資訊
- **記憶整合** - 短期/長期記憶管理

### 專業 Agent

| Agent | 職責 |
|-------|------|
| **Crypto Agent** | 加密貨幣市場數據、鏈上分析、Web3 新聞 |
| **US Stock Agent** | NYSE/NASDAQ 市場數據、SEC 文件、企業新聞 |
| **TW Stock Agent** | 台股市場數據、本地法人動向、財經新聞 |
| **Forex Agent** | 外匯市場分析 |
| **Economic Agent** | 經濟指標分析 |
| **Commodity Agent** | 商品期貨分析 |

### 工作流程

```
用戶查詢 → [Manager Agent 分類]
                ↓
        [自動預研資料收集]
                ↓
    [提出多步驟執行計畫] ↔ 用戶協商/修改計畫
                ↓
[Agent 執行計畫: 技術面 / 基本面 / 新聞]
                ↓
          [綜合最終報告]
```

---

## 功能模組

### 1. 論壇系統（PTT 風格）
- **看板分類**: Crypto / 美股 / 台股
- **文章分類**: 分析 / 提問 / 教學 / 新聞 / 討論 / 洞見
- **標籤系統**: #BTC #ETH #SOL 快速篩選
- **投票機制**: 推 (👍) / 噓 (👎) 影響作者聲譽
- **Pi 打賞**: 直接 P2P 轉帳給作者

### 2. 社交功能
- 好友系統（新增、封鎖、查看狀態）
- 私訊系統（PRO 會員即時聊天）
- 通知中心（好友請求、打賞、系統公告）
- 關注清單（追蹤喜愛的加密貨幣）

### 3. 市場數據
- 即時報價（WebSocket）
- 多交易所整合（OKX + Binance）
- 專業圖表（金融級 K 線圖）
- 資金費率（期貨市場數據）

### 4. 管理與治理
- 管理後台（用戶管理、內容審核、統計儀表板）
- 詐騙追蹤器（社群舉報可疑內容）
- 治理投票（社群決策）
- 審計日誌（完整操作記錄）

### 5. 會員系統
- 免費會員 / PRO 會員分級
- Pi Network 支付整合
- API Key 管理（用戶自備 LLM Key）

---

## API 端點概覽

### 市場數據
- `GET /api/market/ticker` - 即時報價
- `GET /api/market/klines` - K 線數據
- `WS /ws/market` - 即時市場串流

### AI 分析
- `POST /api/analysis/chat` - AI 對話分析
- `POST /api/analysis/stream` - 串流分析（SSE）

### 論壇
- `GET /api/forum/boards` - 看板列表
- `GET /api/forum/posts` - 文章列表
- `POST /api/forum/posts` - 發布文章
- `POST /api/forum/tips` - 打賞

### 用戶
- `GET /api/user/profile` - 用戶資料
- `POST /api/user/api-keys` - 管理 API Key

---

## 環境配置

### 必要環境變數
```env
# 資料庫
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=redis://...

# LLM
OPENROUTER_API_KEY=...

# Pi Network
PI_API_KEY=...

# 交易所
OKX_API_KEY=...
OKX_SECRET_KEY=...
OKX_PASSPHRASE=...
```

### 測試模式
```env
TEST_MODE=true
TEST_MODE_CONFIRMATION=I_UNDERSTAND_THE_RISKS
ENVIRONMENT=development
```

---

## 部署架構

```
┌─────────────────────────────────────────────────────┐
│                  Frontend Layer                      │
│           Web UI / Pi Browser + Pi SDK              │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   API Layer                          │
│        FastAPI Gateway + WebSocket + SSE            │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│              Business Logic Layer                    │
│   AI Agents │ Forum │ Social │ Trading │ Admin     │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  Data Layer                          │
│         PostgreSQL │ Redis │ Message Queue          │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│               External Services                      │
│   LLM APIs │ OKX │ Binance │ Pi Network            │
└─────────────────────────────────────────────────────┘
```

---

## 啟動方式

```bash
# 開發環境
python api_server.py

# 生產環境（Gunicorn）
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Docker
docker-compose up -d
```

---

## 授權

Apache License 2.0

---

*最後更新: 2025-03*
