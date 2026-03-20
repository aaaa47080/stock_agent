---
name: security-audit
description: Security audit: check secrets, XSS, auth, rate limits
---
## Security Audit Checklist

### 1. Secret Detection
```bash
rg -i "password|api_key|secret|token|credential" --type py -l
rg "sk-|ghp_|gho_|xoxb-" --type-add 'env:.env*' -l
```
Verify no secrets in code. Check `.gitignore` includes `.env*`.

### 2. SQL Injection Check
Search for string concatenation in SQL:
```bash
rg "f\".*SELECT|f\".*INSERT|f\".*UPDATE|f\".*DELETE" --type py
```
All queries should use parameterized (`%s`) placeholders.

### 3. XSS Check
Search for innerHTML with user data:
```bash
rg "innerHTML.*\+" web/js/ --type js
```
User-provided content must go through `escapeHtml()`.

### 4. Auth Check
- All endpoints (except login/dev-login) must have `Depends(get_current_user)`
- Rate limits on public endpoints
- `TEST_MODE` guards in dev-only code

### 5. Rate Limiting
```bash
rg "@limiter.limit" api/routers/ --type py -l
```
Critical endpoints (login, payment, message send) must be rate-limited.

### 6. CORS Check
```bash
rg "allow_origins|CORSMiddleware" api_server.py
```
Production should NOT use `*` for allowed origins.

### 7. Dependency Audit
```bash
pip-audit
pip-audit --desc
```

### 8. File Permission Check
```bash
rg -i "chmod|777|666" --type py
```
No overly permissive file operations.
