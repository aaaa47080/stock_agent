# Agent Chat 架構報告

> 最後更新: 2026-03-06

---

## 📋 目錄

1. [系統概述](#系統概述)
2. [架構圖](#架構圖)
3. [核心組件](#核心組件)
4. [Agent 詳細說明](#agent-詳細說明)
5. [工具清單](#工具清單)
6. [數據流向](#數據流向)
7. [擴展指南](#擴展指南)

---

## 系統概述

Agent Chat 系統是一個多市場 AI 分析平台，採用 **Manager-Agent** 架構模式，透過意圖分類自動將用戶查詢路由到對應的專業 Agent。

### 支援市場

| 市場 | Agent | 說明 |
|------|-------|------|
| 加密貨幣 | CryptoAgent | BTC、ETH、PI 等 |
| 台股 | TWStockAgent | 台積電、鴻海、聯發科等 |
| 美股 | USStockAgent | AAPL、TSLA、NVDA 等 |
| 一般對話 | ChatAgent | 閒聊、問候、平台說明 |

---

## 架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                         用戶請求                                 │
│                    "台積電今天股價?"                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ManagerAgent                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              意圖分類 (Intent Classification)             │   │
│  │   1. 市場識別: Crypto / TW Stock / US Stock / Chat       │   │
│  │   2. 查詢類型: 價格 / 技術分析 / 新聞 / 基本面            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                       │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Agent Router (路由器)                        │   │
│  │   根據意圖選擇對應 Agent                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  Crypto  │    │ TWStock  │    │ USStock  │    │   Chat   │
   │  Agent   │    │  Agent   │    │  Agent   │    │  Agent   │
   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
   ┌─────────────────────────────────────────────────────────┐
   │                    ToolRegistry                          │
   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │
   │   │ Price   │ │Technical│ │  News   │ │  ...    │      │
   │   │  Tool   │ │Analysis │ │  Tool   │ │  Tool   │      │
   │   └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
   └─────────────────────────────────────────────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
   ┌─────────────────────────────────────────────────────────┐
   │                    外部 API / 數據源                      │
   │   OKX API │ Yahoo Finance │ TWSE OpenAPI │ CoinGecko   │
   └─────────────────────────────────────────────────────────┘
```

---

## 核心組件

### 1. ManagerAgent

**位置**: `core/agents/manager.py`

ManagerAgent 是系統的核心控制器，負責：
- 接收用戶輸入
- 進行意圖分類（使用 LLM）
- 路由到對應的專業 Agent
- 整合工具執行結果
- 生成最終回應

```python
class ManagerAgent:
    def __init__(
        self,
        llm_client,          # LLM 客戶端
        agent_registry,      # Agent 註冊表
        tool_registry,       # 工具註冊表
        web_mode=False       # 是否為網頁模式
    ):
        ...
```

### 2. AgentRegistry

**位置**: `core/agents/agent_registry.py`

管理所有註冊的 Agent，每個 Agent 包含：
- `name`: 唯一識別符
- `display_name`: 顯示名稱
- `description`: 功能描述
- `capabilities`: 能力關鍵字列表
- `allowed_tools`: 允許使用的工具列表
- `priority`: 優先級

### 3. ToolRegistry

**位置**: `core/agents/tool_registry.py`

管理所有註冊的工具，每個工具包含：
- `name`: 工具名稱
- `description`: 功能描述
- `input_schema`: 輸入參數定義
- `handler`: 執行函數
- `allowed_agents`: 允許使用的 Agent 列表

### 4. AgentRouter

**位置**: `core/agents/router.py`

負責根據用戶意圖選擇最合適的 Agent。

---

## Agent 詳細說明

### CryptoAgent

**位置**: `core/agents/agents/crypto_agent.py`

**描述**: 加密貨幣專業分析師

**能力關鍵字**:
```
RSI, MACD, MA, technical analysis, crypto news, 加密貨幣,
技術指標, 資金費率, 恐慌貪婪指數, 熱門幣種, 多空情緒,
TVL, 板塊, 時間, 解鎖, unlock, 流通量, 發行量, supply
```

**優先級**: 10

---

### TWStockAgent

**位置**: `core/agents/agents/tw_stock_agent.py`

**描述**: 台灣股市全方位分析

**能力關鍵字**:
```
台股, 台灣股市, 上市, 上櫃, 股票代號, RSI, MACD, KD,
均線, 本益比, EPS, 外資, 投信, 法人, 籌碼, 股價
```

**優先級**: 10

---

### USStockAgent

**位置**: `core/agents/agents/us_stock_agent.py`

**描述**: 美股全方位分析

**能力關鍵字**:
```
美股, US stock, NYSE, NASDAQ, AAPL, TSLA, NVDA, TSM,
MSFT, AMZN, GOOGL, META, 標普500, 道瓊, 那斯達克
```

**優先級**: 8

---

### ChatAgent

**位置**: `core/agents/agents/chat_agent.py`

**描述**: 一般對話助手

**能力關鍵字**:
```
conversation, greeting, help, general knowledge,
price lookup, 即時價格, 平台說明, 閒聊, 時間
```

**優先級**: 1

---

## 工具清單

### 加密貨幣工具 (CryptoAgent)

| 工具名 | 描述 | 輸入參數 |
|--------|------|----------|
| `technical_analysis` | 技術指標 (RSI, MACD, 均線) | `symbol`, `interval` |
| `price_data` | 即時和歷史價格 | `symbol` |
| `get_crypto_price` | 即時價格 | `symbol` |
| `google_news` | Google News 新聞 | `symbol`, `limit` |
| `aggregate_news` | 多來源新聞聚合 | `symbol`, `limit` |
| `get_fear_and_greed_index` | 恐慌貪婪指數 | 無 |
| `get_trending_tokens` | 熱門幣種 | 無 |
| `get_futures_data` | 合約資金費率 | `symbol` |
| `get_defillama_tvl` | TVL 鎖倉量 | `protocol_name` |
| `get_crypto_categories_and_gainers` | 熱門板塊 | 無 |
| `get_token_unlocks` | 代幣解鎖日程 | `symbol` |
| `get_token_supply` | 代幣供應量 | `symbol` |
| `get_gas_fees` | Gas 費用 | 無 |
| `get_whale_transactions` | 鯨魚交易 | `symbol`, `min_value_usd` |
| `get_exchange_flow` | 交易所資金流向 | `symbol` |
| `get_current_time_taipei` | 台北時間 | 無 |
| `web_search` | 網絡搜索 | `query`, `purpose` |

### 台股工具 (TWStockAgent)

| 工具名 | 描述 | 輸入參數 |
|--------|------|----------|
| `tw_stock_price` | 即時價格和 OHLCV | `ticker` |
| `tw_technical_analysis` | 技術指標 RSI/MACD/KD/MA | `ticker` |
| `tw_fundamentals` | 基本面 P/E, EPS, ROE | `ticker` |
| `tw_institutional` | 三大法人籌碼 | `ticker` |
| `tw_news` | Google News 新聞 | `ticker`, `company_name` |
| `tw_major_news` | 上市公司重大訊息 (TWSE) | `limit` |
| `tw_pe_ratio` | 本益比/殖利率/股價淨值比 | `code` |
| `tw_monthly_revenue` | 月營收資料 | `code` |
| `tw_dividend` | 股利分派資訊 | `code` |
| `tw_foreign_top20` | 外資持股前20名 | 無 |
| `get_current_time_taipei` | 台北時間 | 無 |
| `web_search` | 網絡搜索 | `query`, `purpose` |

### 美股工具 (USStockAgent)

| 工具名 | 描述 | 輸入參數 |
|--------|------|----------|
| `us_stock_price` | 即時價格 (15分鐘延遲) | `symbol` |
| `us_technical_analysis` | 技術指標 RSI/MACD/布林帶 | `symbol` |
| `us_fundamentals` | 基本面 P/E, EPS, ROE | `symbol` |
| `us_earnings` | 財報數據和日曆 | `symbol` |
| `us_news` | 最新新聞 | `symbol`, `limit` |
| `us_institutional_holders` | 機構持倉 | `symbol` |
| `us_insider_transactions` | 內部人交易 | `symbol` |
| `get_current_time_taipei` | 台北時間 | 無 |

### 通用工具 (ChatAgent)

| 工具名 | 描述 | 輸入參數 |
|--------|------|----------|
| `get_current_time_taipei` | 台北時間 | 無 |
| `get_crypto_price` | 加密貨幣即時價格 | `symbol` |
| `web_search` | 網絡搜索 | `query`, `purpose` |
| `get_pi_price` | Pi Network 價格 | 無 |
| `get_pi_network_info` | Pi Network 資訊 | 無 |
| `get_pi_ecosystem` | Pi 生態系統資訊 | 無 |

---

## 數據流向

### 1. 請求處理流程

```
用戶輸入
    │
    ▼
┌─────────────────┐
│   API Endpoint  │  POST /api/chat
│   (analysis.py) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ManagerAgent   │  意圖分類 + Agent 路由
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Specialist     │  CryptoAgent / TWStockAgent / ...
│  Agent          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ToolRegistry   │  工具調用
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  External API   │  OKX / Yahoo Finance / TWSE / CoinGecko
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Response   │  生成最終回應
└─────────────────┘
```

### 2. 工具調用流程

```python
# 1. ManagerAgent 決定需要調用工具
tool_name = "tw_stock_price"
tool_args = {"ticker": "2330"}

# 2. 從 ToolRegistry 獲取工具
tool = tool_registry.get_tool(tool_name)

# 3. 執行工具
result = tool.handler(**tool_args)

# 4. 將結果返回給 Agent 處理
```

---

## 擴展指南

### 新增 Agent

1. 在 `core/agents/agents/` 創建新的 Agent 類別
2. 繼承基礎結構並實現 `process` 方法
3. 在 `bootstrap.py` 中註冊 Agent

```python
# core/agents/agents/new_agent.py
class NewAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tools = tool_registry

    def process(self, query: str, context: dict) -> str:
        # 實現邏輯
        pass

# core/agents/bootstrap.py
from .agents.new_agent import NewAgent

new = NewAgent(lang_llm, tool_registry)
agent_registry.register(new, AgentMetadata(
    name="new_agent",
    display_name="New Agent",
    description="描述",
    capabilities=["keyword1", "keyword2"],
    allowed_tools=["tool1", "tool2"],
    priority=5,
))
```

### 新增工具

1. 在 `core/tools/` 創建工具函數
2. 在 `core/agents/tools.py` 添加 wrapper
3. 在 `bootstrap.py` 中註冊工具

```python
# core/tools/new_tools.py
@tool
def new_tool(param: str) -> dict:
    """工具描述"""
    # 實現邏輯
    return {"result": "data"}

# core/agents/bootstrap.py
tool_registry.register(ToolMetadata(
    name="new_tool",
    description="工具描述",
    input_schema={"param": "str"},
    handler=new_tool,
    allowed_agents=["agent_name"],
))
```

---

## 檔案結構

```
core/agents/
├── __init__.py              # 模組導出
├── bootstrap.py             # 啟動配置、Agent/Tool 註冊
├── manager.py               # ManagerAgent 核心控制器
├── router.py                # Agent 路由器
├── agent_registry.py        # Agent 註冊表
├── tool_registry.py         # 工具註冊表
├── models.py                # 數據模型
├── watcher.py               # 觀察者 Agent
└── agents/                  # 專業 Agent 目錄
    ├── __init__.py
    ├── crypto_agent.py      # 加密貨幣 Agent
    ├── tw_stock_agent.py    # 台股 Agent
    ├── us_stock_agent.py    # 美股 Agent
    ├── chat_agent.py        # 對話 Agent
    ├── tech_agent.py        # (Legacy) 技術分析
    └── news_agent.py        # (Legacy) 新聞分析

core/tools/
├── __init__.py              # 模組導出
├── crypto_tools.py          # 加密貨幣工具
├── tw_stock_tools.py        # 台股工具
├── us_stock_tools.py        # 美股工具
├── pi_tools.py              # Pi Network 工具
└── utility_tools.py         # 通用工具
```

---

## 統計

| 項目 | 數量 |
|------|------|
| 活躍 Agent | 4 |
| 註冊工具 | 37 |
| 支援市場 | 3 |
| 數據源 | 10+ |

---

## 相關文件

- [API 文檔](./api/README.md)
- [數據庫結構](./DATABASE_SCHEMA.md)
- [安全架構](./security/SECURITY.md)
