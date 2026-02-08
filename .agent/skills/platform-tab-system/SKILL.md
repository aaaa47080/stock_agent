---
name: Platform Tab System
description: Complete checklist for adding new tabs/components to the PI CryptoMind platform SPA
---

# Platform Tab System - Adding New Features

This skill documents the complete process for adding a new tab or component to the main SPA (`web/index.html`).

## Overview

The platform uses a dynamic tab injection system where:
- Tab templates are stored in `web/js/components.js`
- Tab switching logic is in `web/js/app.js`
- User preferences are managed via localStorage with versioning

## Adding a New Tab - Complete Checklist

### 1. Update `web/js/app.js` - NAV_ITEMS Configuration

**Location**: Around line 10-30 in the `NAV_ITEMS` array

Add your tab to the navigation configuration:

```javascript
{
    id: 'mytab',                // Unique identifier (lowercase, no spaces)
    icon: 'icon-name',          // Lucide icon name
    label: 'My Tab',            // Display name in navigation
    defaultEnabled: true,       // Whether enabled by default for new users
    locked: false              // true = cannot be disabled by user
}
```

**Rules**:
- At least 2 items must have `locked: true` or `defaultEnabled: true`
- Common locked tabs: `market`, `pulse`
- `wallet` and `settings` are typically locked

### 2. Increment `PREFERENCES_VERSION`

**Location**: Around line 35-40 in `web/js/app.js`

```javascript
const PREFERENCES_VERSION = X; // Increment by 1
```

**When to bump**:
- Adding a new tab
- Changing default settings
- Modifying localStorage structure

**Why**: Forces migration of user preferences to include new defaults

### 3. Create Tab Template in `web/js/components.js`

**Location**: Add a new property to the `Components` object

```javascript
const Components = {
    // ... existing tabs ...
    
    mytab: `
        <div class="max-w-6xl mx-auto p-4">
            <h2 class="font-serif text-3xl text-secondary mb-8">My Tab</h2>
            <!-- Your content here -->
        </div>
    `,
    
    // ... rest of Components object ...
};
```

**Best practices**:
- Use consistent max-width containers (`max-w-6xl` or `max-w-2xl`)
- Follow existing dark theme patterns
- Use Lucide icons via `<i data-lucide="icon-name"></i>`
- Maintain responsive design with Tailwind classes

### 4. Add Tab Container in `web/index.html`

**Location**: Around line 150-200, inside `<div id="app-content">`

Add a placeholder div for your tab:

```html
<!-- My Tab -->
<div id="mytab-tab" class="content-section hidden">
    <!-- Content injected by Components.inject('mytab') -->
</div>
```

**Important**: 
- ID format: `{tabId}-tab`
- Include `content-section` class
- Start with `hidden` class

### 5. Update `executeTabSwitch()` in `web/js/app.js`

**Location**: Around line 300-500, in the `switch` statement

Add initialization logic for your tab:

```javascript
case 'mytab':
    await Components.inject('mytab');
    if (typeof MyTabModule !== 'undefined') {
        await MyTabModule.init();
    }
    break;
```

**Pattern**:
1. Inject component template
2. Call initialization function if module exists
3. Use `await` for async operations

### 6. Add to `validTabs` Array

**Location**: Around line 100 in `web/js/app.js`

```javascript
const validTabs = ['market', 'pulse', 'safety', 'forum', 'social', 'mytab', 'wallet', 'settings'];
```

**Purpose**: Validates URL hash navigation (`#mytab`)

### 7. Add Tab-Specific JavaScript (Optional)

If your tab requires logic, create `web/js/mytab.js`:

```javascript
const MyTabModule = {
    async init() {
        console.log('[MyTab] Initializing...');
        // Your initialization code
        this.loadData();
    },
    
    async loadData() {
        // Fetch data, set up event listeners, etc.
    }
};
```

**Load in `web/index.html`**:
```html
<script src="web/js/mytab.js?v=1"></script>
```

### 8. Update Cache Busters

**In `web/index.html`**:
- Increment `?v=N` for `components.js`
- Increment `?v=N` for `app.js`
- Add versioning for any new JS files

## Testing Checklist

- [ ] New tab appears in navigation customization menu
- [ ] Tab can be enabled/disabled (if not locked)
- [ ] Direct navigation via URL hash works (`#mytab`)
- [ ] Tab content loads correctly on first visit
- [ ] Re-visiting tab doesn't re-inject content
- [ ] Console shows no errors during tab switch
- [ ] Lucide icons render correctly
- [ ] Mobile responsive design works

## Common Pitfalls

### Issue: Tab content not appearing
**Solution**: Check if `Components.inject('mytab')` is called in `executeTabSwitch()`

### Issue: Preferences reset on every reload
**Solution**: Did you forget to bump `PREFERENCES_VERSION`?

### Issue: Tab always hidden
**Solution**: Ensure `validTabs` includes your tab ID

### Issue: Icons not rendering
**Solution**: Call `lucide.createIcons()` after DOM injection

## Example: Adding a "News" Tab

```javascript
// 1. NAV_ITEMS (app.js)
{ id: 'news', icon: 'newspaper', label: 'News', defaultEnabled: true, locked: false }

// 2. PREFERENCES_VERSION (app.js)
const PREFERENCES_VERSION = 3; // was 2

// 3. Components template (components.js)
news: `
    <div class="max-w-6xl mx-auto p-4">
        <h2 class="font-serif text-3xl text-secondary mb-8">Crypto News</h2>
        <div id="news-feed"></div>
    </div>
`,

// 4. index.html
<div id="news-tab" class="content-section hidden"></div>

// 5. executeTabSwitch (app.js)
case 'news':
    await Components.inject('news');
    if (typeof NewsModule !== 'undefined') {
        await NewsModule.init();
    }
    break;

// 6. validTabs (app.js)
const validTabs = ['market', 'pulse', 'safety', 'forum', 'social', 'news', 'wallet', 'settings'];
```

## Related Files

- `/web/index.html` - Main SPA structure
- `/web/js/app.js` - Tab switching logic & NAV_ITEMS
- `/web/js/components.js` - Tab templates
- `/web/js/*.js` - Tab-specific modules

## Version History

- v1.0: Initial documentation (2026-02-08)
