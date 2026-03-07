# Prompt 与 Agent 设计规则

> 本文档定义了设计 prompt 和 agent 时必须遵循的原则。所有新增或修改的 prompt/agent 都必须符合这些规则。

## 核心原则

### 边界条件 > 写死案例

LLM 已经有足够的知识来做分析和决策。我们的工作是**定义边界**，而不是**教它怎么做**。

| ✅ 正确：边界条件 | ❌ 错误：写死案例（Few-shot） |
|------------------|------------------------------|
| 根据标的类型选择对应 agent | BTC 用 crypto agent |
| 任务描述必须传达查询目的 | 写：综合分析（价格+技术指标+市场情绪+最新新闻） |
| 多个独立标的时创建并行任务 | BTC 和台积电要创建两个任务 |
| 不得跨类型路由 | 加密货币不要路由到 economic agent |

### 为什么避免 Few-shot？

1. **偏向性**：LLM 可能过度依赖特定案例，导致对其他标的处理不当
2. **不灵活**：写死的案例无法适应新的场景
3. **维护成本**：每次新增场景都要添加新的案例
4. **LLM 已经懂**：LLM 训练数据已经包含大量金融知识，不需要我们教

---

## Prompt 设计规则

### 1. 结构规范

每个 prompt 必须包含以下部分：

```yaml
prompt_name:
  description: "简短描述这个 prompt 的用途"
  template: |
    ## 角色
    [定义 agent 的角色，不要给具体案例]

    ## 输出格式
    [JSON 或其他格式规范]

    ## 边界规则
    ### [规则类别 1]
    - 边界条件 1
    - 边界条件 2

    ### [规则类别 2]
    - 边界条件 1
    - 边界条件 2

    ## 输入变量
    {variable_name}
```

### 2. 边界规则写法

**正确示例：**
```
### Status 边界
- direct_response: 打招呼、道謝、閒聊（不涉及數據查詢）
- clarify: 全新對話且無法從上下文推斷標的
- ready: 其他所有情況
```

**错误示例：**
```
### Status 示例
- 用户说「你好」→ direct_response
- 用户说「BTC 多少钱」→ ready
- 用户说「分析一下」但没说分析什么 → clarify
```

### 3. 禁止的内容

| 禁止 | 原因 |
|------|------|
| 特定股票/币种代号（BTC、2330、AAPL） | 导致偏向性 |
| 特定公司名称（台积电、特斯拉） | 导致偏向性 |
| 具体价格/数值示例 | 可能导致格式偏见 |
| 「如果用户问 X，就做 Y」式的条件 | 应该用边界条件替代 |
| 完整的 JSON 输出示例 | 可能导致输出格式僵化 |

### 4. 允许的内容

| 允许 | 说明 |
|------|------|
| 通用占位符（<标的>、<ASSET>） | 不指定具体值 |
| 边界条件（何时 A，何时 B） | 定义决策边界 |
| 格式规范（JSON 结构、字段名） | 确保输出可解析 |
| 角色定义（你是分析师、你是助手） | 设定上下文 |

---

## Agent 设计规则

### 1. Agent 注册规范

```python
agent_registry.register(agent, AgentMetadata(
    name="agent_name",           # 小写，下划线分隔
    display_name="Agent 名称",    # 中文显示名
    description="描述 agent 的能力范围",  # 不要列举具体案例
    capabilities=["能力1", "能力2"],      # 通用能力描述
    allowed_tools=_tools("agent_name"),   # 从 DB 或配置获取
    priority=10,                 # 优先级
))
```

### 2. Description 写法

**正确：**
```
加密貨幣專業分析師 — 提供即時價格、技術指標、市場情緒、最新新聞。不直接提供交易決策。
```

**错误：**
```
加密貨幣分析師 — 可以查詢 BTC、ETH、SOL 的價格，分析比特幣的 RSI 和 MACD。
```

### 3. Capabilities 写法

**正确：**
```python
capabilities=["技術分析", "市場情緒", "價格查詢", "新聞"]
```

**错误：**
```python
capabilities=["BTC分析", "ETH價格", "查詢比特幣新聞"]
```

---

## 检查清单

在提交任何 prompt 或 agent 修改前，请确认：

- [ ] 没有使用特定的股票代码或币种代号
- [ ] 没有使用特定的公司名称
- [ ] 规则用边界条件描述，而非具体案例
- [ ] 没有完整的输入/输出示例
- [ ] Agent description 描述能力范围，不列举具体标的
- [ ] Capabilities 是通用能力，不是特定操作

---

## 文件位置

| 内容 | 位置 |
|------|------|
| Agent prompts | `core/agents/prompts/<agent_name>.yaml` |
| Agent 实现 | `core/agents/agents/<agent_name>_agent.py` |
| Agent 注册 | `core/agents/bootstrap.py` |
| 工具定义 | `core/agents/tools.py` 或 `core/tools/<category>_tools.py` |

---

## 示例对比

### 错误的 Prompt（Few-shot 风格）

```yaml
intent_understanding:
  template: |
    分析用戶查詢，選擇正確的 agent：

    範例：
    - 用戶：「BTC 價格多少」→ crypto agent
    - 用戶：「台積電股價」→ tw_stock agent
    - 用戶：「蘋果財報」→ us_stock agent

    當用戶問「適合買嗎」時，任務描述要寫：
    「綜合分析 BTC：查詢即時價格、技術指標（RSI/MACD/均線）、市場恐慌貪婪指數」
```

### 正确的 Prompt（边界条件风格）

```yaml
intent_understanding:
  template: |
    根據用戶查詢，規劃需要執行的任務。

    ## 邊界規則

    ### Agent 路由邊界
    根據標的類型選擇對應的 agent，不得跨類型路由。

    ### 任務描述邊界
    任務描述必須明確傳達用戶的**查詢目的**，讓 agent 能夠自行決定使用哪些工具。

    ### 上下文推斷邊界
    當用戶問題沒有明確提到標的時：
    - 先從對話歷史推斷
    - 只有在**完全無法推斷**時才返回 clarify
```

---

## 更新记录

| 日期 | 修改内容 |
|------|---------|
| 2026-03-07 | 初版创建 |
