# Pi Crypto Insight - 系統架構文檔

## 1. 整體架構流程

本系統採用現代化的前後端分離架構，前端為 Mobile-First 的響應式 Web App (Pi Browser 相容)，後端為基於 FastAPI 的高效能非同步伺服器。系統核心設計理念為隱私優先 (Privacy-First) 與用戶自帶金鑰 (Bring Your Own Key, BYOK)。

```mermaid
flowchart TB
    subgraph Frontend["前端 (Web/Mobile)"]
        UI[HTML5 + TailwindCSS + JS]
        Store[LocalStorage (API Keys)]
        SSE[Server-Sent Events (串流接收)]
        User((用戶))
    end

    subgraph Backend["API Server (FastAPI)"]
        API[api_server.py]
        Auth[Auth Middleware (臨時憑證)]
        Cache[Market Pulse Cache]
    end

    subgraph External["外部服務"]
        LLM[LLM Provider (OpenAI/Gemini)]
        OKX[OKX Exchange API]
    end

    User -->|操作| UI
    UI -->|1. 請求 + API Keys| API
    
    API -->|2. 驗證 & 注入| Auth
    Auth -->|3. 臨時 Client| LLM
    Auth -->|3. 臨時 Connector| OKX
    
    API -->|查詢| Cache
    
    LLM -->|分析結果| API
    OKX -->|市場數據| API
    
    API -->|4. 串流回應| SSE
    SSE -->|更新| UI
```

## 2. 核心組件說明

### 前端 (Frontend)
- **技術棧**: 原生 HTML5, Tailwind CSS, Vanilla JavaScript (無大型框架依賴，輕量化)。
- **特色**: 
  - **Mobile-First**: 專為 Pi Browser 及行動裝置優化。
  - **Pi Design**: 深色模式 (Dark Mode)，符合 Pi Network 設計語言。
  - **安全存儲**: 所有的 API Keys (LLM & OKX) 僅存儲於瀏覽器 `localStorage`，伺服器不保存。

### 後端 (Backend API)
- **核心**: Python FastAPI，提供 REST API 與 WebSocket 服務。
- **架構特點**:
  - **無狀態 (Stateless) LLM Client**: 每個請求根據前端傳來的 Key 動態創建 Client。
  - **模組化路由**: `analysis` (AI), `market` (數據), `trading` (交易), `agents` (代理配置)。

### 智慧代理層 (Agent Layer)
- **Orchestrator**: `CryptoAnalysisBot` 負責協調對話。
- **ReAct 模式**: LLM 動態選擇工具 (價格查詢、技術分析、新聞)。
- **Deep Dive**: `full_investment_analysis_tool` 觸發 LangGraph 深度分析工作流。

## 3. 安全架構 (BYOK & OKX Security)

系統採用嚴格的「用戶自帶金鑰」模式，確保伺服器端零隱私風險。

### 3.1 LLM API Key 機制
1. **存儲**: 用戶在前端輸入 Key，存入 `localStorage`。
2. **傳輸**: 發起分析請求時，Key 隨 Header/Body 發送至後端。
3. **使用**: 後端 `user_client_factory.py` 驗證 Key 並創建臨時 Client。
4. **銷毀**: 請求結束後，Client 與 Key 立即從記憶體中釋放，不存入資料庫或日誌。

### 3.2 OKX 交易安全
1. **隔離**: OKX API Key/Secret/Passphrase 同樣僅存於前端。
2. **隱私**: 無痕視窗 (Incognito) 下無法讀取 Key，他人無法查看資產。
3. **認證**: 每次資產查詢或交易請求，必須透過 HTTP Header 攜帶認證資訊 (`X-OKX-API-KEY` 等)。
4. **執行**: 後端 `okx_auth.py` 攔截請求，建立一次性 `OKXAPIConnector` 執行操作。

## 4. 效能優化：市場脈動緩存 (Market Pulse)

為解決啟動慢與重複分析問題，系統實作了智能緩存層。

- **啟動優化**: 伺服器啟動時僅加載資料庫緩存，不立即執行昂貴的 LLM 分析。
- **定時更新**: 後台任務每小時 (可配置) 更新一次關注列表 (如 BTC, ETH, SOL) 的分析報告。
- **時效檢查**: 用戶請求時，系統檢查緩存時間戳。
  - **命中**: 若緩存 < 2小時，立即返回 (<100ms)。
  - **過期**: 若緩存 > 2小時，觸發即時 LLM 分析並更新緩存。
- **前端優化**: 移除無意義的 Cache Buster 參數，充分利用後端緩存。

## 5. 完整投資分析流程 (LangGraph)

當調用 `full_investment_analysis_tool` 時，系統執行以下任務：

```mermaid
flowchart TB
    subgraph Phase1["階段 1: 數據聚合"]
        D1[OHLCV K線數據]
        D2[技術指標計算 (RSI, MACD, BB)]
        D3[新聞與社群情緒]
    end

    subgraph Phase2["階段 2: 平行分析 (Committee)"]
        A1[技術分析師]
        A2[基本面分析師]
        A3[情緒分析師]
        A4[新聞分析師]
    end

    subgraph Phase3["階段 3: 辯論與決策"]
        Bull[多頭代表]
        Bear[空頭代表]
        Judge[裁判官]
        Decision[最終投資建議]
    end

    D1 & D2 & D3 --> A1 & A2 & A3 & A4
    A1 & A2 & A3 & A4 --> Bull & Bear
    Bull <--> Bear
    Bull & Bear --> Judge
    Judge --> Decision
```

## 6. 擴展性設計

- **自定義 Agent**: 透過 `/api/agents` 端點，支援動態註冊新的 Agent 行為與專屬工具。
- **Worker 模式**: 支援將耗時的市場掃描 (`market_scanner`) 拆分為獨立 Worker Process 運行。
