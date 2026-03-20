---
name: i18n
description: Add internationalization for new Chinese strings in JS files
---
## i18n Workflow

### File Locations
- English translations: `web/js/i18n/en.json`
- Chinese translations: `web/js/i18n/zh-TW.json`
- i18n library: `web/js/i18n.js`
- Usage in JS: `window.I18n ? window.I18n.t('key') : 'fallback'`

### Step 1: Find Hardcoded Chinese
Scan JS files for Chinese characters:
```bash
rg "[\u4e00-\u9fff]" web/js/<file>.js
```

### Step 2: Create Translation Keys
- Use namespace format: `<section>.<element>` (e.g., `settings.save`, `forum.postSuccess`)
- Reuse existing keys from en.json/zh-TW.json when possible
- Keep keys descriptive and consistent

### Step 3: Replace in JS
```javascript
// Before
element.textContent = '載入中...';

// After
element.textContent = window.I18n ? window.I18n.t('common.loading') : '載入中...';
```

For HTML attributes:
```html
<h2 data-i18n="nav.forex">外匯市場</h2>
```

### Step 4: Add to Both JSON Files
Always add the key to BOTH `en.json` AND `zh-TW.json` simultaneously.

### Existing Namespaces
- `common` — shared (loading, error, save, cancel, etc.)
- `nav` — navigation labels
- `sidebar` — chat sidebar
- `chat` — chat interface
- `market` — crypto market overview
- `pulse` — AI pulse/analysis
- `status` — market status bar
- `marketPage` — market page shared strings
- `forex` — forex page
- `commodity` — commodity page
- `twstock` — Taiwan stock page
- `usstock` — US stock page
- `crypto` — crypto page
- `forum` — forum page
- `friends` — friends page
- `messages` — messages page
- `safety` — safety/scam tracker
- `settings` — settings page
- `modals` — modal dialogs

### Do NOT Translate
- console.log messages
- Code comments
- Signal matching conditions (e.g., `sig.includes('突破')`)
- Server-returned data strings
