---
name: root-cause-tracing
description: Trace issues backward through the call stack to find the true root cause, not just symptoms
---
## Root Cause Tracing

### When to Use
- Bug reports where the symptom is clear but cause is unknown
- Test failures that don't point to the real issue
- Performance problems with unclear bottleneck
- Data corruption or unexpected state changes

### Method: Backward Tracing

#### Step 1: Identify the Symptom
- What is the observable failure?
- Where does it manifest? (API response, DB state, UI, log)

#### Step 2: Find the Symptom Code
```bash
# Search for error message
rg "error message" --type py

# Search for the function/endpoint
rg "def endpoint_name" --type py
```

#### Step 3: Trace Backward Through Call Stack
For each layer, ask: "What feeds into this?"

```
UI Error → API Response → Router Handler → Service/DB function → Raw Query → Schema
```

Trace ONE path at a time. Don't branch until current path is dead.

#### Step 4: Check Data Flow
- What data enters the function?
- What transformations happen?
- Where does the data come from originally?

#### Step 5: Verify at Each Layer
```bash
# Add temporary logging at boundaries
logger.info(f"TRACE: variable={value}, type={type(value)}")
```

### Common Root Causes in This Project

| Symptom | Likely Root Cause | Where to Check |
|---------|------------------|----------------|
| 500 on endpoint | DB query failure | `core/database/` functions |
| Wrong user data | Client-side user_id still passed | `api/routers/` params |
| Rate limit miss | Missing `Request` param | Router function signature |
| XSS in output | Unescaped user content | `web/js/` render functions |
| Connection timeout | Pool exhaustion | `core/database/connection.py` |
| ORM session closed | Missing `using_session()` | `api/routers/` using repos |
| Asyncpg error | Sync call in async context | `core/orm/` or `core/database/` |

### Anti-Patterns
- Fixing the symptom instead of the cause
- Adding try/except to hide errors
- "It works on my machine" — check environment differences
- Changing multiple things at once
