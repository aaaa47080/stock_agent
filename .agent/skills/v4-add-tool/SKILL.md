---
name: Add V4 Tool
description: How to add a new tool function to the Agent V4 system. Use when the user asks to add a new tool or capability.
---

# Add a New Tool to Agent V4

Follow these steps to add a new tool using the `ToolRegistry`.

## Step 1: Add tool function to `core/agents/tools.py`

Define a standard Python function. Type hints and docstrings are crucial.

```python
def new_tool_name(param1: str, param2: int = 5) -> dict:
    """
    清晰描述這個工具做什麼。
    LLM 會閱讀此描述來決定是否使用。
    """
    # Implementation here
    return {"result": f"processed {param1}"}
```

**Rules:**
- Function name = snake_case
- Docstring = Tool description for LLM
- Arguments = Must have type hints

## Step 2: Register in `core/agents/bootstrap.py`

Import the function and register it with `ToolMetadata`.

```python
from .tools import ..., new_tool_name

def bootstrap(...):
    # ...
    # Register the tool
    tool_registry.register(ToolMetadata(
        name="new_tool_name",
        description="描述工具用途（通常複製 docstring）",
        input_schema={"param1": "str", "param2": "int"},
        handler=new_tool_name,
        allowed_agents=["technical", "full_analysis"], # 限制哪些 Agent 可用
    ))
```

## Step 3: Update Agent Capability (Optional)

If this is a major new capability, update the Agent's description in `bootstrap.py` so the Manager knows to route relevant queries to it.

```python
agent_registry.register(tech, AgentMetadata(
    # ...
    allowed_tools=["technical_analysis", "new_tool_name"], # Ensure it's in allowed list (if strict check enabled)
))
```
*Note: `ToolRegistry` checks `allowed_agents` on the tool side, but keeping AgentMetadata aligned is good practice.*

## Step 4: Use in Agent (if custom logic needed)

Agents can call tools via `self._use_tool()`:

```python
result = self._use_tool("new_tool_name", {"param1": "value"})
if result.success:
    data = result.data
```

## Step 5: Verify

```bash
python -c "from core.agents.bootstrap import bootstrap; from utils.llm_client import LLMClientFactory; llm = LLMClientFactory.create_client('openai', 'gpt-4o-mini'); m = bootstrap(llm); print('Tools:', [t.name for t in m.tool_registry.list_all_tools()])"
```
