---
name: frontend-debug
description: Debug frontend vanilla JS issues - console errors, rendering bugs, SPA navigation, WebSocket
---
## Frontend Debug Patterns

### Project Frontend Stack
- Vanilla JS (no framework) in `web/js/`
- SPA router in `web/js/spa.js`
- i18n via `web/js/i18n.js` with `data-i18n` attributes
- WebSocket in `web/js/market-ws.js`
- Market pages: crypto, twstock, usstock, forex, commodity
- No jQuery, no React, no build step

### Common Issues & Solutions

#### Console Errors
1. Check browser DevTools Console (F12)
2. Common causes:
   - Undefined variable → check if file loaded in `index.html`
   - `Cannot read property of null` → element not in DOM yet
   - CORS → API base URL mismatch

#### SPA Navigation Issues
- Router in `spa.js` handles page switching
- `tabsWithSidebar` controls chat sidebar visibility
- Page modules loaded via dynamic import or script tags
- Check `index.html` for correct script loading order

#### i18n Issues
- Pattern: `window.I18n ? window.I18n.t('key') : 'fallback'`
- HTML: `data-i18n="key"` attributes
- Check `web/js/i18n/en.json` and `zh-TW.json` for missing keys
- Missing keys show the raw key string

#### WebSocket Issues
- Mock WebSocket class used in tests
- Real WebSocket needs running server
- Check `market-ws.js` for connection handling
- Reconnection logic may need debugging

#### XSS Prevention
- All user content must go through `escapeHtml()`
- URLs through `sanitizeUrl()`
- Check `safetyTab.js` for clipboard XSS patterns

#### Market Page Issues
- `market-screener.js` is the ACTIVE file (not `market.js` which was deleted)
- Each market has: data fetch, table render, chart, status bar
- "上次更新" uses live 1-second clock via `market-status.js`
- `markSynced()` called before fetch to prevent time jump

### Debugging Workflow
1. Reproduce in browser (F12 → Console + Network tab)
2. Check Network tab for failed API calls
3. Add `console.warn("DEBUG:", value)` in JS
4. Use `page.evaluate()` in Playwright for automated debugging
5. Check `index.html` for correct file references

### File Map
| File | Purpose |
|------|---------|
| `web/js/spa.js` | SPA router, page switching |
| `web/js/components.js` | Shared UI components |
| `web/js/i18n.js` | i18n library |
| `web/js/market-screener.js` | Market screener (active) |
| `web/js/market-chart.js` | Chart rendering |
| `web/js/market-ws.js` | WebSocket handler |
| `web/js/market-status.js` | Live clock, sync status |
| `web/js/friends.js` | Friends page |
| `web/js/messages.js` | Messages page |
| `web/js/safetyTab.js` | Safety/reporting |

---

## ⚠️ Pi SDK 載入檢查清單 (MANDATORY)

**所有需要用戶認證的頁面都必須載入 Pi SDK！**

### 必須在 `<head>` 中加入：

```html
<!-- Pi Network SDK (REQUIRED for Pi Browser authentication) -->
<script src="https://sdk.minepi.com/pi-sdk.js"></script>
```

### 需要載入 Pi SDK 的頁面類型：

| 頁面類型 | 需要載入 | 原因 |
|---------|---------|------|
| 主應用入口 (`index.html`) | ✅ 是 | 登入/認證 |
| 論壇頁面 (`forum/*.html`) | ✅ 是 | 發文/評論/支付 |
| 治理頁面 (`governance/*.html`) | ✅ 是 | PRO 會員功能 |
| 詐騙追蹤 (`scam-tracker/*.html`) | ✅ 是 | 提交報告 |
| 法律頁面 (`legal/*.html`) | ❌ 否 | 靜態內容，無需認證 |

### Pi Browser 檢測邏輯

```javascript
// auth.js Line 39-54
const PiEnvironment = {
    isSafeSdkContext() {
        // 必須是 HTTPS 且非 localhost
        return window.location.protocol === 'https:' && !this.isLocalhost();
    },
    hasPiSdk() {
        // Pi SDK 必須已載入
        return typeof window.Pi !== 'undefined' &&
               typeof window.Pi.authenticate === 'function' &&
               typeof window.Pi.init === 'function';
    },
    isPiBrowser() {
        return this.isSafeSdkContext() && this.hasPiSdk();
    }
};
```

### 常見錯誤排除

| 問題 | 原因 | 解決方案 |
|-----|------|---------|
| 「請使用 Pi Browser」但已在 Pi Browser 中 | Pi SDK 未載入 | 確認 HTML 有 `<script src="https://sdk.minepi.com/pi-sdk.js"></script>` |
| `window.Pi is undefined` | SDK script 未執行 | 檢查 CSP 是否允許 `sdk.minepi.com` |
| 認證後無反應 | SDK 載入但 `Pi.init()` 未呼叫 | 確認 `auth.js` 正確初始化 |

### 新增頁面檢查清單

建立新 HTML 頁面時，確認：

- [ ] 頁面需要用戶認證？ → **必須加入 Pi SDK**
- [ ] Pi SDK script tag 在 `</head>` 之前
- [ ] 測試：在 Pi Browser 中開啟頁面，確認 `window.Pi` 存在
