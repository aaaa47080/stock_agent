# 開發指南：新增 Tool 或 Agent

本文檔說明如何在系統中新增工具 (Tool) 或代理 (Agent)。
大致摘要：

1.新增 Tool 需修改的檔案

1. core/tools/schemas.py - 定義輸入參數
2. core/tools/crypto_tools.py - 實現 tool 邏輯（用 @tool 裝飾器）
3. core/tools/__init__.py - 註冊到 TOOL_MAP 和 get_crypto_tools()
4. core/agent_registry.py - 分配給指定 Agent（可選）

2.新增 Agent 需修改的檔案

1. core/agent_registry.py - 在 DEFAULT_AGENT_REGISTRY 加入新 Agent 配置

或者用 API 動態管理

- POST /agents/ - 新增 Agent
- PATCH /agents/{id}/tools - 更新 Agent 的工具列表

系統會根據 Agent 的 description 自動路由，所以只要定義好描述，Admin Agent 就會自動選擇合適的 Agent 處理用戶請求。
---

## 新增 Tool

### 步驟 1：定義輸入參數

修改 `core/tools/schemas.py`：

```python
class MyNewToolInput(BaseModel):
    """新工具的輸入參數"""
    symbol: str = Field(description="幣種符號")
    param2: int = Field(default=10, description="參數2說明")
```

### 步驟 2：實現 Tool 邏輯

修改 `core/tools/crypto_tools.py`（或新建檔案）：

```python
from langchain_core.tools import tool
from .schemas import MyNewToolInput

@tool(args_schema=MyNewToolInput)
def my_new_tool(symbol: str, param2: int = 10) -> str:
    """
    工具功能描述（這段會被 LLM 看到用於判斷何時使用）

    適用情境：
    - 當用戶詢問 XXX 時使用
    - 當需要 YYY 功能時使用
    """
    # 實現邏輯
    result = f"處理 {symbol} 的結果"
    return result
```

### 步驟 3：註冊到工具系統

修改 `core/tools/__init__.py`：

```python
# 1. 導入
from .crypto_tools import my_new_tool

# 2. 加入 get_crypto_tools()
def get_crypto_tools() -> List:
    return [
        # ... 現有工具
        my_new_tool,  # 加這行
    ]

# 3. 加入 TOOL_MAP
TOOL_MAP = {
    # ... 現有工具
    "my_new_tool": my_new_tool,  # 加這行
}
```

### 步驟 4：分配給 Agent（可選）

修改 `core/agent_registry.py` 的 `DEFAULT_AGENT_REGISTRY`：

```python
"shallow_crypto_agent": {
    "tools": [
        # ... 現有工具
        "my_new_tool",  # 加這行
    ],
}
```

或透過 API 動態更新：

```bash
PATCH /agents/{agent_id}/tools
{
    "tools": ["get_crypto_price_tool", "my_new_tool"]
}
```

---

## 新增 Agent

### 步驟 1：定義 Agent 配置

修改 `core/agent_registry.py` 的 `DEFAULT_AGENT_REGISTRY`：

```python
DEFAULT_AGENT_REGISTRY: Dict[str, dict] = {
    # ... 現有 Agents

    "my_new_agent": {
        "name": "我的新 Agent",
        "description": """處理特定任務的 Agent：
- 當用戶詢問 XXX 時使用
- 當需要 YYY 功能時使用
適合需要 ZZZ 的場景。""",
        "tools": [
            "get_current_time_tool",
            "my_new_tool",
        ],
        "enabled": True,
        "use_debate_system": False,  # 是否啟用會議討論機制
    },
}
```

### 或透過 API 動態新增

```bash
POST /agents/
{
    "agent_id": "my_new_agent",
    "config": {
        "name": "我的新 Agent",
        "description": "描述...",
        "tools": ["tool1", "tool2"],
        "enabled": true,
        "use_debate_system": false
    }
}
```

---

## 現有架構參考

### 目錄結構

```
core/tools/
├── __init__.py      # 工具註冊表（TOOL_MAP, get_crypto_tools）
├── schemas.py       # Pydantic 輸入參數定義
├── helpers.py       # 輔助函數（符號標準化等）
├── formatters.py    # 輸出格式化
├── utility_tools.py # 通用工具
└── crypto_tools.py  # 加密貨幣分析工具

core/
├── agent_registry.py  # Agent 註冊表管理
├── admin_agent.py     # Admin Agent（路由中樞）
└── agents.py          # 內部分析師團隊
```

### 現有 Tools

| Tool 名稱 | 功能 |
|----------|------|
| `get_current_time_tool` | 獲取當前時間 |
| `get_crypto_price_tool` | 查詢即時價格 |
| `technical_analysis_tool` | 技術分析 |
| `news_analysis_tool` | 新聞分析 |
| `full_investment_analysis_tool` | 完整投資分析 |
| `explain_market_movement_tool` | 解釋市場脈動 |
| `backtest_strategy_tool` | 策略回測 |
| `extract_crypto_symbols_tool` | 提取幣種符號 |

### 現有 Agents

| Agent ID | 功能 | 使用工具 |
|----------|------|---------|
| `shallow_crypto_agent` | 快速查詢（價格、技術指標） | 5 個基礎工具 |
| `deep_crypto_agent` | 深度分析（多空辯論、投資建議） | 2 個深度工具 |
| `admin_chat_agent` | 閒聊、系統說明 | 僅時間工具 |

### Agent 管理 API

| 方法 | 端點 | 功能 |
|------|------|------|
| GET | `/agents/` | 列出所有 Agent |
| GET | `/agents/tools` | 列出所有可用工具 |
| POST | `/agents/` | 新增 Agent |
| PUT | `/agents/{id}` | 更新 Agent |
| DELETE | `/agents/{id}` | 刪除 Agent |
| PATCH | `/agents/{id}/tools` | 更新工具列表 |
| PATCH | `/agents/{id}/enable` | 啟用 Agent |
| PATCH | `/agents/{id}/disable` | 禁用 Agent |

---

## 工作流程

```
用戶輸入
    ↓
Admin Agent（分析意圖、選擇 Agent）
    ↓
選中的 Agent（使用 TOOL_MAP 獲取工具）
    ↓
LangChain ReAct Agent 執行工具
    ↓
返回結果
```

---

## 重點提醒

1. **Tool 描述很重要**：`@tool` 裝飾器下的 docstring 會被 LLM 用於判斷何時使用此工具
2. **Agent 描述很重要**：description 欄位會被 Admin Agent 用於選擇最適合的 Agent
3. **工具需註冊**：新工具必須加入 `TOOL_MAP` 才能被 Agent 使用
4. **動態管理**：可透過 API 在運行時新增/修改 Agent 和工具配置
