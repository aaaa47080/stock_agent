---
name: Platform Database Pattern
description: Database function conventions for the db parameter and connection management
---

# Platform Database Pattern - `db` Parameter Convention

This skill documents the standard pattern for database functions in the PI CryptoMind codebase to prevent common bugs.

## The Problem

**Incorrect**:
```python
def create_user(username, wallet_address):
    conn = get_connection()
    # ... use conn ...
    conn.close()
```

When called from async context (FastAPI routers), this creates connection pool exhaustion.

## The Solution: `db` Parameter Pattern

### Standard Function Signature

```python
def my_function(db=None, param1, param2):
    """
    Args:
        db: Database connection object (optional)
        param1: First parameter
        param2: Second parameter
    """
    conn = db or get_connection()
    try:
        cursor = conn.cursor()
        # ... execute queries ...
        cursor.close()
        return result
    finally:
        if not db:
            conn.close()
```

### Key Rules

1. **First parameter must be `db`** (can be `None`)
2. **Use `conn = db or get_connection()`** to get connection
3. **Only close if `db` was `None`**: `if not db: conn.close()`
4. **Always use `finally` block** for cleanup

## Calling from FastAPI Routers

### Using `run_in_executor` (Async Context)

```python
from functools import partial

@router.get("/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    result = await asyncio.get_event_loop().run_in_executor(
        None,  # Use default thread pool
        partial(db_function, None, arg1, arg2)  # First arg MUST be None for db
    )
    return result
```

**Critical**: First argument to `partial` must be `None` (for `db` param)

### Wrong Examples

❌ **Missing `None` for `db` param**:
```python
partial(db_function, arg1, arg2)  # WRONG: db gets arg1 value
```

❌ **Direct function call in async**:
```python
result = db_function(arg1, arg2)  # WRONG: Blocks event loop
```

## Database Connection Patterns

### Getting a Connection

```python
from database.db import get_connection

conn = get_connection()  # Use pool connection
```

### Using psycopg2 Cursors

```python
cursor = conn.cursor()
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
result = cursor.fetchone()
cursor.close()
```

**Always use**:
- `%s` placeholders (never string formatting)
- Tuple for parameters: `(value,)` or `(val1, val2)`

### Handling Timestamps

```python
# Wrong: datetime objects may fail strftime
updated_at = row[5].strftime('%Y-%m-%d %H:%M:%S')  # May error if None

# Correct: Check type first
updated_at = row[5].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[5], datetime) else row[5]
```

## Transaction Management

### Auto-commit (Default)

```python
def create_post(db=None, title, content):
    conn = db or get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posts (title, content) VALUES (%s, %s) RETURNING id",
            (title, content)
        )
        post_id = cursor.fetchone()[0]
        cursor.close()
        conn.commit()  # Commit automatically
        return post_id
    finally:
        if not db:
            conn.close()
```

### Manual Transaction (Multiple Operations)

```python
def transfer_pi(db=None, from_user, to_user, amount):
    conn = db or get_connection()
    try:
        cursor = conn.cursor()
        
        # Deduct from sender
        cursor.execute(
            "UPDATE users SET balance = balance - %s WHERE id = %s",
            (amount, from_user)
        )
        
        # Add to receiver
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s",
            (amount, to_user)
        )
        
        cursor.close()
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise
    finally:
        if not db:
            conn.close()
```

## Common Bugs & Solutions

### Bug: `IntegrityError` with boolean fields

**Problem**:
```python
cursor.execute(
    "SELECT * FROM users WHERE is_active = %s",
    (1,)  # PostgreSQL expects boolean, not int
)
```

**Solution**:
```python
cursor.execute(
    "SELECT * FROM users WHERE is_active = %s",
    (True,)  # Use Python boolean
)
```

### Documented Issues

See `GEMINI_CODEBOOK.txt` for known issues:

```txt
# ❌ BAD
"WHERE is_premium = %s", (1,)

# ✅ GOOD
"WHERE is_premium = %s", (True,)
```

### Bug: Connection pool exhaustion

**Symptoms**: `PoolError: connection pool exhausted`

**Cause**: Forgetting to close connections in non-`db` param calls

**Solution**: Always use `if not db: conn.close()` in `finally`

### Bug: Datetime formatting errors

**Symptoms**: `AttributeError: 'str' object has no attribute 'strftime'`

**Cause**: Row already contains formatted string, not datetime

**Solution**:
```python
if isinstance(timestamp, datetime):
    formatted = timestamp.strftime('%Y-%m-%d %H:%M:%S')
else:
    formatted = timestamp  # Already a string
```

## Template: New Database Function

```python
def my_new_function(db=None, param1, param2, param3=None):
    """
    Brief description of what this function does.
    
    Args:
        db: Database connection (optional, from pool if None)
        param1: Description
        param2: Description
        param3: Optional description
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something is invalid
    """
    conn = db or get_connection()
    try:
        cursor = conn.cursor()
        
        # Execute query
        cursor.execute(
            "SELECT * FROM table WHERE col1 = %s AND col2 = %s",
            (param1, param2)
        )
        
        result = cursor.fetchall()
        cursor.close()
        
        # Process and return
        return process_result(result)
        
    except Exception as e:
        logger.error(f"Error in my_new_function: {e}")
        raise
    finally:
        if not db:
            conn.close()
```

## Router Integration Example

```python
# routers/users.py
from functools import partial
import asyncio
from fastapi import APIRouter, Depends
from database.users import get_user_by_id
from auth import get_current_user

router = APIRouter()

@router.get("/users/{user_id}")
async def read_user(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get user by ID (async)."""
    user = await asyncio.get_event_loop().run_in_executor(
        None,
        partial(get_user_by_id, None, user_id)  # None for db param
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
```

## Related Files

- `/database/db.py` - Connection pool setup
- `/database/*.py` - Database modules (users, posts, forum, etc.)
- `/routers/*.py` - FastAPI routers
- `/GEMINI_CODEBOOK.txt` - Known bug patterns

## Checklist for New DB Functions

- [ ] First parameter is `db=None`
- [ ] Uses `conn = db or get_connection()`
- [ ] Has `try/finally` block
- [ ] Closes connection in `finally` only if `db` was `None`
- [ ] Uses `%s` placeholders (never f-strings in queries)
- [ ] Boolean values use `True/False`, not `1/0`
- [ ] Datetime formatting checks `isinstance()`
- [ ] Router calls use `partial(func, None, ...)`

## Version History

- v1.0: Initial documentation (2026-02-08)
