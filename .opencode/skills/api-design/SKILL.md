---
name: api-design
description: REST API design conventions for FastAPI routers
---
## API Design Conventions

### URL Structure
```
/api/{resource}           # Collection
/api/{resource}/{id}      # Specific item
/api/{resource}/{id}/{sub} # Sub-resource
```

### HTTP Methods
- GET: Read, never modify state
- POST: Create or trigger action
- PUT: Full update
- PATCH: Partial update
- DELETE: Remove

### Response Format
```python
from api.models import APIResponse

def get_user() -> APIResponse[UserSchema]:
    return APIResponse(success=True, data=user)
```

### Error Responses
```python
from fastapi import HTTPException, status
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

### Pagination
- Use `offset` and `limit` query params
- Default limit: 20, max: 100
- Return `has_more` boolean for infinite scroll

### Rate Limiting
- All public endpoints must have `@limiter.limit()`
- Add `Request` parameter when using rate limits
- Critical endpoints (login, payment, message): stricter limits

### Auth
- All endpoints (except login/dev-login) need `Depends(get_current_user)`
- Use `current_user["user_id"]` for identity
- Never trust client-provided user_id
