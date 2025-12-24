# Pi Crypto Insight - 系統架構圖

## 1. 整體架構流程

```mermaid
flowchart TB
    subgraph Frontend["前端介面"]
        UI[Gradio Web UI / API Server]
        User((用戶))
    end

    subgraph Agent["ReAct Agent 層"]
        CA[CryptoAgent]
        LLM[GPT-4o LLM]

        subgraph Tools["工具集 @tool"]
            T1[get_crypto_price_tool<br/>即時價格查詢]
            T2[technical_analysis_tool<br/>純技術分析]
            T3[news_analysis_tool<br/>新聞面分析]
            T4[full_investment_analysis_tool<br/>完整投資分析]
        end
    end

    subgraph Backend["後端分析引擎"]
        subgraph LangGraph["LangGraph 工作流"]
            N1[prepare_data_node<br/>準備數據]
            N2[analyst_team_node<br/>4位分析師並行]
            N3[research_debate_node<br/>三方辯論]
            N4[trader_decision_node<br/>交易決策]
            N5[risk_management_node<br/>風險評估]
            N6[fund_manager_node<br/>最終審批]
        end

        subgraph DataLayer["數據層"]
            DF[DataFetcher<br/>Binance/OKX]
            IC[IndicatorCalculator<br/>技術指標計算]
            NF[NewsFetcher<br/>新聞聚合]
        end
    end

    User -->|輸入問題| UI
    UI -->|process_message| CA
    CA -->|判斷意圖| LLM
    LLM -->|選擇工具| Tools

    T1 -->|調用| DF
    T2 -->|調用| DF
    T2 -->|調用| IC
    T3 -->|調用| NF
    T4 -->|調用| LangGraph

    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 -->|批准| N6
    N5 -->|拒絕| N4

    Tools -->|返回結果| LLM
    LLM -->|生成回應| CA
    CA -->|串流輸出| UI
    UI -->|顯示結果| User
```

## 2. Agent 工具調用決策流程

```mermaid
flowchart TD
    Start([用戶輸入]) --> Parse[LLM 解析意圖]

    Parse --> Q1{需要即時數據?}
    Q1 -->|否| Direct[直接回答<br/>不調用工具]
    Q1 -->|是| Q2{問題類型?}

    Q2 -->|價格查詢| Price[get_crypto_price_tool]
    Q2 -->|技術指標| Tech[technical_analysis_tool]
    Q2 -->|新聞消息| News[news_analysis_tool]
    Q2 -->|投資建議| Full[full_investment_analysis_tool]

    Price -->|1-2秒| Result
    Tech -->|3-5秒| Result
    News -->|3-5秒| Result
    Full -->|30秒-2分鐘| Result
    Direct --> Result

    Result[整合結果] --> Response[生成回應]
    Response --> End([返回用戶])

    style Price fill:#90EE90
    style Tech fill:#87CEEB
    style News fill:#DDA0DD
    style Full fill:#FFB6C1
    style Direct fill:#F0E68C
```

## 3. 完整投資分析流程 (full_investment_analysis_tool)

```mermaid
flowchart TB
    subgraph Phase1["階段 1: 數據準備"]
        P1[獲取 K 線數據]
        P2[計算技術指標]
        P3[獲取新聞資訊]
        P4[多週期數據<br/>1h/4h/1d]
    end

    subgraph Phase2["階段 2: 分析師團隊 (並行)"]
        A1[技術分析師<br/>Technical]
        A2[情緒分析師<br/>Sentiment]
        A3[基本面分析師<br/>Fundamental]
        A4[新聞分析師<br/>News]
    end

    subgraph Phase3["階段 3: 三方辯論"]
        D1[多頭研究員<br/>Bull]
        D2[空頭研究員<br/>Bear]
        D3[中立研究員<br/>Neutral]
        D4[數據核查員<br/>FactChecker]
        D5[辯論裁判<br/>Judge]
    end

    subgraph Phase4["階段 4: 決策審批"]
        T[交易員決策]
        R[風險管理評估]
        F[基金經理審批]
    end

    P1 --> P2 --> P3 --> P4
    P4 --> A1 & A2 & A3 & A4

    A1 & A2 & A3 & A4 --> D1
    D1 --> D2 --> D3
    D3 --> D4 --> D5

    D5 --> T --> R
    R -->|批准| F
    R -->|拒絕| T
    F --> Result([最終報告])
```

## 4. 檔案結構與依賴關係

```mermaid
flowchart LR
    subgraph Interfaces["interfaces/"]
        CI[chat_interface.py]
        AS[api_server.py]
    end

    subgraph Core["core/"]
        AG[agent.py<br/>CryptoAgent]
        TL[tools.py<br/>@tool 定義]
        GR[graph.py<br/>LangGraph 流程]
        AGS[agents.py<br/>分析師類別]
        MD[models.py<br/>數據模型]
        CF[config.py<br/>配置]
    end

    subgraph Data["data/"]
        DF[data_fetcher.py]
        DP[data_processor.py]
        IC[indicator_calculator.py]
    end

    subgraph Utils["utils/"]
        UT[utils.py<br/>新聞聚合]
        LC[llm_client.py]
    end

    AS --> CI
    CI --> AG
    AG --> TL
    TL --> GR
    TL --> DF
    TL --> DP
    GR --> AGS
    GR --> DP
    AGS --> MD
    DP --> IC
    DP --> UT
    AGS --> LC

    style AG fill:#FFD700
    style TL fill:#98FB98
    style GR fill:#87CEFA
```

## 5. 數據流向

```mermaid
sequenceDiagram
    participant U as 用戶
    participant UI as Web UI
    participant CA as CryptoAgent
    participant LLM as GPT-4o
    participant Tool as Tools
    participant API as 交易所 API

    U->>UI: "BTC 可以投資嗎？"
    UI->>CA: process_message()
    CA->>LLM: 解析意圖 + 選擇工具
    LLM-->>CA: 調用 full_investment_analysis_tool

    CA->>Tool: invoke tool
    Tool->>API: 獲取 K 線數據
    API-->>Tool: 返回數據

    Note over Tool: 執行 LangGraph 工作流
    Note over Tool: 4 位分析師並行分析
    Note over Tool: 三方辯論
    Note over Tool: 交易決策 + 風險評估

    Tool-->>CA: 返回完整分析報告
    CA->>LLM: 整理最終回應
    LLM-->>CA: 生成回應文字
    CA-->>UI: 串流輸出
    UI-->>U: 顯示分析結果
```

## 6. 工具選擇策略

```mermaid
flowchart TD
    Input[用戶輸入] --> Analyze{分析問題類型}

    Analyze -->|"現在多少錢?"<br/>"價格是多少?"| P[get_crypto_price_tool]
    Analyze -->|"RSI 是多少?"<br/>"MACD 如何?"<br/>"趨勢?"| T[technical_analysis_tool]
    Analyze -->|"最新新聞?"<br/>"有什麼消息?"| N[news_analysis_tool]
    Analyze -->|"可以投資嗎?"<br/>"應該買嗎?"<br/>"完整分析"| F[full_investment_analysis_tool]
    Analyze -->|"什麼是 RSI?"<br/>"你好"<br/>一般問題| D[直接回答]

    P -->|最快| R1[1-2 秒]
    T -->|快| R2[3-5 秒]
    N -->|快| R3[3-5 秒]
    F -->|慢| R4[30秒-2分鐘]
    D -->|即時| R5[即時]

    R1 & R2 & R3 & R4 & R5 --> Output[返回結果]

    style P fill:#90EE90
    style T fill:#87CEEB
    style N fill:#DDA0DD
    style F fill:#FFB6C1
    style D fill:#F0E68C
```

---

## 快速參考

| 工具名稱 | 功能 | 速度 | 調用場景 |
|---------|------|------|---------|
| `get_crypto_price_tool` | 即時價格 | 1-2秒 | 價格查詢 |
| `technical_analysis_tool` | 技術指標 | 3-5秒 | RSI/MACD/趨勢 |
| `news_analysis_tool` | 新聞分析 | 3-5秒 | 新聞/情緒 |
| `full_investment_analysis_tool` | 完整分析 | 30秒-2分 | 投資建議 |
| (無工具) | 直接回答 | 即時 | 知識問答/聊天 |
