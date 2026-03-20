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
