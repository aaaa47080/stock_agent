---
name: cost-aware-llm-pipeline
description: Use when building LLM-powered features - model routing by task complexity, budget tracking, retry logic, and prompt caching
---
## Cost-Aware LLM Pipeline

### When to Activate
- Building features that call LLM APIs (Claude, GPT, etc.)
- Processing batches of items with varying complexity
- Need to stay within budget for API spend
- Optimizing cost without sacrificing quality on complex tasks

### Model Routing by Task Complexity

```python
MODEL_CHEAP = "claude-3-haiku-20240307"
MODEL_STANDARD = "claude-sonnet-4-20250514"
MODEL_POWERFUL = "claude-opus-4-20250514"

def route_model(task: dict) -> str:
    if task["complexity"] == "simple":
        return MODEL_CHEAP
    elif task["complexity"] == "standard":
        return MODEL_STANDARD
    return MODEL_POWERFUL
```

### Prompt Caching
- Structure prompts with static system prompt + dynamic user content
- Cache common prefixes (instructions, examples)
- Reuse conversation prefixes across requests

### Budget Tracking
```python
class BudgetTracker:
    def __init__(self, daily_limit_usd: float):
        self.daily_limit = daily_limit_usd
        self.spent_today = 0.0

    def check_budget(self, estimated_cost: float) -> bool:
        return self.spent_today + estimated_cost <= self.daily_limit
```

### Retry Logic
- Exponential backoff on rate limits (429)
- Don't retry on auth errors (401/403) or bad requests (400)
- Track retry costs separately

### Batch Processing
- Group simple tasks, route to cheap model
- Process complex tasks individually with powerful model
- Track per-task cost for optimization insights

### Cost Optimization Checklist
- [ ] Model routing by complexity implemented
- [ ] Prompt caching enabled
- [ ] Budget limits configured
- [ ] Retry logic with backoff
- [ ] Cost per task tracked
- [ ] Fallback to cheaper model on budget exhaustion
