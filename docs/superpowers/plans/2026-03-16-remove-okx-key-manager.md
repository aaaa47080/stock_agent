# Remove OKX Key Manager & Assets Tab Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the OKX BYOK key management system and the Assets portfolio tab, since the trading module has been deleted and viewing exchange balance has no value to current users.

**Architecture:** Two-pass cleanup — backend first (API endpoint + model), then frontend (tab, JS files, nav). The `OKXAPIConnector` in `utils/` remains untouched as it still serves public market data.

**Tech Stack:** Python, FastAPI, vanilla JavaScript SPA

---

## Chunk 1: Backend Cleanup

### Task 1: Remove APIKeySettings model and OKX fields from UserSettings

**Files:**
- Modify: `api/models.py`
- Modify: `tests/test_api_models.py`

- [ ] **Step 1: Remove APIKeySettings class from models.py**

In `api/models.py`, delete the `APIKeySettings` class:
```python
# Remove this entire class:
class APIKeySettings(BaseModel):
    api_key: str
    secret_key: str
    passphrase: str
```

Also remove the OKX key fields from `UserSettings`:
```python
# Remove these 4 lines from UserSettings:

    # OKX Keys (可選，若要在這裡統一管理)
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None
```

- [ ] **Step 2: Remove APIKeySettings tests from test_api_models.py**

In `tests/test_api_models.py`:
1. Remove `APIKeySettings` from the import block at the top
2. Delete the entire `TestAPIKeySettings` class and its tests

- [ ] **Step 3: Verify models import cleanly**

```bash
.venv/bin/python -c "from api.models import QueryRequest, UserSettings; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_api_models.py -q
```

Expected: all pass, no `APIKeySettings` errors

- [ ] **Step 5: Commit**

```bash
git add api/models.py tests/test_api_models.py
git commit -m "Remove: APIKeySettings model and OKX fields from UserSettings"
```

---

### Task 2: Remove POST /api/settings/keys endpoint from system router

**Files:**
- Modify: `api/routers/system.py`

- [ ] **Step 1: Remove APIKeySettings from import**

In `api/routers/system.py`, change:
```python
from api.models import APIKeySettings, UserSettings, KeyValidationRequest
```
to:
```python
from api.models import UserSettings, KeyValidationRequest
```

- [ ] **Step 2: Remove the endpoint**

Delete the entire `update_api_keys` function and its decorator (around line 329–375):
```python
@router.post("/api/settings/keys")
@limiter.limit("5/minute")
async def update_api_keys(settings: APIKeySettings, request: Request, current_user: dict = Depends(get_current_user)):
    ...
```
(Delete from the `@router.post` decorator through the closing of the function body)

- [ ] **Step 3: Verify system router loads**

```bash
.venv/bin/python -c "from api.routers.system import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Verify api_server loads**

```bash
.venv/bin/python -c "from api_server import app; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add api/routers/system.py
git commit -m "Remove: POST /api/settings/keys OKX key management endpoint"
```

---

## Chunk 2: Frontend Cleanup

### Task 3: Delete OKX key manager and assets JS files

**Files:**
- Delete: `web/js/okxKeyManager.js`
- Delete: `web/js/assets.js`

- [ ] **Step 1: Delete the files**

```bash
rm web/js/okxKeyManager.js
rm web/js/assets.js
```

- [ ] **Step 2: Commit**

```bash
git add -u
git commit -m "Remove: okxKeyManager.js and assets.js frontend files"
```

---

### Task 4: Remove assets tab from index.html

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: Remove the assets-tab div**

In `web/index.html`, find and delete the entire assets tab section:
```html
<!-- Tab: Assets -->
<div id="assets-tab"
    class="tab-content hidden ...">
    ...all inner content including no-okx-key-overlay and assets-content divs...
</div>
```
(This is roughly lines 491–560. Delete from `<!-- Tab: Assets -->` through the closing `</div>` of the tab.)

- [ ] **Step 2: Remove okxKeyManager.js script tag**

Find and delete this line:
```html
<script defer src="/static/js/okxKeyManager.js?v=47"></script>
```

Note: `assets.js` script tag (`<script defer src="/static/js/assets.js?v=47"></script>`) — check if it exists in index.html and remove it too.

- [ ] **Step 3: Commit**

```bash
git add web/index.html
git commit -m "Remove: assets tab HTML and okxKeyManager script tag from index.html"
```

---

### Task 5: Remove assets from SPA router and nav config

**Files:**
- Modify: `web/js/spa.js`
- Modify: `web/js/nav-config.js`
- Modify: `web/js/app.js`

- [ ] **Step 1: Remove 'assets' from validTabs in spa.js**

In `web/js/spa.js`, there are multiple arrays/lists containing `'assets'` (lines 25, 75, 236, 671). Remove `'assets'` from each one.

Also remove the tab switch handler for assets (around line 236):
```javascript
if (tabId === 'assets' && typeof refreshAssets === 'function') refreshAssets();
```

- [ ] **Step 2: Remove assets from nav-config.js**

In `web/js/nav-config.js`, delete:
```javascript
{ id: 'assets', icon: 'wallet', label: 'Assets', i18nKey: 'nav.assets', defaultEnabled: true },
```

- [ ] **Step 3: Remove OKX key check from app.js**

In `web/js/app.js`, find and remove the OKX key check block (around line 355–410):
```javascript
// Check OKX Key
const hasOkxKey = window.OKXKeyManager?.hasCredentials();
...
// 3. Control Assets Tab Overlay (OKX Key)
const okxOverlay = document.getElementById('no-okx-key-overlay');
if (okxOverlay) {
    if (hasOkxKey) {
        ...
    }
}
```

- [ ] **Step 4: Verify no remaining references**

```bash
grep -r "okxKeyManager\|OKXKeyManager\|assets-tab\|refreshAssets\|no-okx-key" web/js/ --include="*.js"
grep -r "okxKeyManager\|assets-tab" web/index.html
```

Expected: no output

- [ ] **Step 5: Commit**

```bash
git add web/js/spa.js web/js/nav-config.js web/js/app.js
git commit -m "Remove: assets tab from SPA router, nav config, and app OKX key check"
```

---

## Final Verification

- [ ] **Verify no stale OKX key manager references**

```bash
grep -r "APIKeySettings\|settings/keys\|okxKeyManager\|OKXKeyManager\|no-okx-key-overlay" . \
  --include="*.py" --include="*.js" --include="*.html" | grep -v "__pycache__" | grep -v ".bak"
```

Expected: no output

- [ ] **Run backend tests**

```bash
.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/pw_test \
  --ignore=tests/test_agent_scenarios.py \
  --ignore=tests/test_pi_routing_fix.py \
  --ignore=tests/test_router_governance_routes.py \
  --ignore=tests/test_router_market.py \
  --ignore=tests/test_router_market_extended.py \
  --deselect=tests/test_bootstrap_runtime.py::test_language_aware_llm_ainvoke_injects_system_message \
  2>&1 | tail -5
```

Expected: all pass (no new failures)

- [ ] **Final cleanup commit if needed**

```bash
git add -u
git commit -m "Cleanup: final stale OKX key manager reference removal"
```
