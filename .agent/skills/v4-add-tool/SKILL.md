---
name: Add V4 Tool
description: How to add a new @tool function to the Agent V4 system. Use when the user asks to add a new tool or capability.
---

# Add a New @tool to Agent V4

Follow these steps exactly to add a new tool.

## Step 1: Add @tool function to `core/agents/tools.py`

Add a new function with the `@tool` decorator. The docstring becomes the tool description used by the LLM classifier.

```python
@tool
def new_tool_name(param1: str = "default", param2: int = 5) -> dict:
    """清晰描述這個工具做什麼（中文或英文皆可）"""
    # Implementation here
    return {"result": ...}
```

**Rules:**
- Function name = tool name (snake_case)
- Docstring = LLM sees this to decide when to use the tool
- Parameters must have type hints and defaults
- Return type should be `dict`, `list`, or `str`

## Step 2: Add to ALL_TOOLS list

In the same `tools.py`, add the new tool to `ALL_TOOLS`:

```python
ALL_TOOLS = [
    google_news, aggregate_news,
    technical_analysis, price_data, get_crypto_price,
    new_tool_name,  # ← add here
]
```

## Step 3: Assign to agent(s) in `core/agents/bootstrap.py`

Import the tool and add it to the relevant agent's tool list:

```python
from .tools import ..., new_tool_name

# Add to the agent that should use it
tech = TechAgent(llm_client, [technical_analysis, price_data, get_crypto_price, new_tool_name], hitl)
```

## Step 4: Use in agent's execute() (if needed)

In the agent's `execute()` method, call the tool:

```python
result = self._use_tool("new_tool_name", {"param1": "value"})
if result.success:
    data = result.data
```

## Step 5: Verify

Run:
```bash
python -c "from core.agents.bootstrap import bootstrap; from utils.llm_client import LLMClientFactory; llm = LLMClientFactory.create_client('openai', 'gpt-4o-mini'); m = bootstrap(llm); print('Tools:', [t.name for t in m.all_tools])"
```

## Files Changed

| File | Change |
|---|---|
| `core/agents/tools.py` | Add `@tool` function + `ALL_TOOLS` |
| `core/agents/bootstrap.py` | Add tool to agent's list |
| `core/agents/agents/xxx_agent.py` | Optional: `_use_tool()` call |
| **prompts** | **No change needed** |
| **manager.py** | **No change needed** |
