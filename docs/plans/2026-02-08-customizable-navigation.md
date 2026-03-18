# Customizable Bottom Navigation Feature Plan

## Overview
Allow users to customize which features appear in their bottom navigation bar through a feature menu/settings interface.

## Current State Analysis
- **Location**: `web/index.html` lines 174-261
- **Framework**: Vanilla JavaScript + Tailwind CSS
- **Current Items**: 8 hardcoded buttons (Chat, Market, Pulse, Wallet, Assets, Friends, Forum, Settings)
- **Storage**: Uses localStorage for nav position, collapse state, active tab

## Feature Requirements
1. **Feature Menu**: A settings interface where users can enable/disable navigation items
2. **Persistence**: User's navigation preferences saved to localStorage
3. **Dynamic Rendering**: Navigation bar updates based on user selections
4. **Minimum Items**: Ensure at least 2-3 items always visible (prevent empty nav)
5. **Default State**: All items visible by default for new users
6. **Accessible UI**: Clear visual feedback for enabled/disabled state

## Implementation Tasks

### Task 1: Create Navigation Configuration Structure
**File**: `web/js/nav-config.js` (new file)

1. Define a navigation items configuration object:
   ```javascript
   const NAV_ITEMS = [
       { id: 'chat', icon: 'message-circle', label: 'Chat', defaultEnabled: true },
       { id: 'market', icon: 'bar-chart-2', label: 'Market', defaultEnabled: true },
       { id: 'pulse', icon: 'activity', label: 'Pulse', defaultEnabled: true },
       { id: 'wallet', icon: 'credit-card', label: 'Wallet', defaultEnabled: true },
       { id: 'assets', icon: 'wallet', label: 'Assets', defaultEnabled: true },
       { id: 'friends', icon: 'users', label: 'Friends', defaultEnabled: true },
       { id: 'forum', icon: 'messages-square', label: 'Forum', defaultEnabled: true },
       { id: 'settings', icon: 'settings-2', label: 'Settings', defaultEnabled: true }
   ];
   ```

2. Create a `NavPreferences` class/module:
   - `getEnabledItems()`: Retrieve user's enabled nav items
   - `setItemEnabled(itemId, enabled)`: Enable/disable a nav item
   - `resetToDefaults()`: Reset all items to default state
   - `validate()`: Ensure minimum 2 items are always enabled

3. localStorage key: `userNavPreferences`

**Verification**: Check file exists and contains proper structure with all 8 items defined.

---

### Task 2: Create Feature Menu UI Component
**File**: `web/js/components.js` (add to existing file)

1. Add a new component template `featureMenuTemplate`:
   - Modal/overlay style UI
   - List of all available navigation items with toggle switches
   - Save and Cancel buttons
   - Visual indication of enabled/disabled state
   - Warning message when trying to disable too many items

2. Add HTML structure:
   - Container div with modal styling
   - Grid layout for items (2-3 columns on desktop, 1 on mobile)
   - Each item: icon, label, toggle switch
   - Action buttons at bottom

3. Add CSS styles:
   - Modal overlay with backdrop blur
   - Smooth animations for open/close
   - Toggle switch styling
   - Disabled state visual feedback

**Verification**: Component renders correctly with all items, toggles work, styling looks good.

---

### Task 3: Implement Navigation Preference Manager
**File**: `web/js/nav-preferences.js` (new file)

1. Create `NavPreferencesManager` class:

   **Methods:**
   - `loadPreferences()`: Load from localStorage or return defaults
   - `savePreferences(preferences)`: Save to localStorage
   - `getEnabledItems()`: Return array of enabled item IDs
   - `isItemEnabled(itemId)`: Check if specific item is enabled
   - `setItemEnabled(itemId, enabled)`: Update item state
   - `canDisableItem(itemId)`: Check if disabling would leave < 2 items
   - `resetToDefaults()`: Reset all to enabled state
   - `exportPreferences()`: For backup/transfer
   - `importPreferences(data)`: For backup/transfer

2. Add validation:
   - Minimum 2 items must be enabled
   - Maximum items limited to NAV_ITEMS length
   - Validate item IDs against NAV_ITEMS

**Verification**: Unit tests pass for all methods, localStorage correctly saves/loads.

---

### Task 4: Update Navigation Rendering Logic
**File**: `web/index.html` (modify existing nav section)

1. Refactor hardcoded nav buttons:
   - Remove hardcoded HTML buttons (lines 205-252)
   - Add container div with ID `nav-buttons-container`
   - Add script to dynamically render buttons based on enabled items

2. Create `renderNavButtons()` function:
   - Read enabled items from NavPreferencesManager
   - Generate HTML for each enabled button
   - Inject into container
   - Re-initialize Lucide icons after render

3. Update `switchTab()` function:
   - Add check: if disabled item is selected, redirect to first enabled item
   - Maintain backward compatibility

**Verification**: Navigation shows only enabled items, switching works correctly.

---

### Task 5: Wire Up Feature Menu Trigger
**File**: `web/index.html` (modify Settings or add new button)

1. Add "Customize Navigation" option:
   - Option A: Add to existing Settings tab
   - Option B: Add gear icon to nav bar itself
   - Option C: Add to existing settings modal

2. Add click handler:
   - Opens feature menu component
   - Pre-fills current state from preferences
   - Handles Save/Cancel actions

3. Add keyboard shortcut (optional):
   - Cmd/Ctrl + Shift + N to open menu

**Verification**: Menu opens on trigger, current state loaded correctly.

---

### Task 6: Implement Save/Cancel Logic
**File**: `web/js/nav-preferences.js`

1. Save button handler:
   - Validate minimum 2 items enabled
   - Save preferences via NavPreferencesManager
   - Re-render navigation
   - Close modal
   - Show success feedback (toast/notification)

2. Cancel button handler:
   - Discard changes
   - Close modal
   - No side effects

3. Reset button (optional):
   - Reset all items to default enabled state
   - Show confirmation dialog

**Verification**: Save persists changes, Cancel discards, navigation updates after save.

---

### Task 7: Add Visual Feedback and Animations
**File**: `web/styles.css` and `web/js/components.js`

1. Add transition animations:
   - Fade in/out when adding/removing nav items
   - Smooth reordering of items
   - Toggle switch animations

2. Add visual states:
   - Disabled items appear grayed out in menu
   - Active tab highlighting
   - Hover effects on enabled items

3. Add empty state handling:
   - Show warning if trying to disable too many items
   - Visual shake or red highlight for invalid action

**Verification**: Animations are smooth, visual feedback is clear.

---

### Task 8: Add Migration for Existing Users
**File**: `web/js/nav-preferences.js`

1. On app load:
   - Check if `userNavPreferences` exists
   - If not, initialize with all items enabled (backward compatible)
   - Existing users keep all items by default

2. Add version field to preferences:
   - For future migration needs
   - Current version: 1

**Verification**: Existing users see all items initially, new users work correctly.

---

### Task 9: Testing and Verification
**Files**: Manual testing checklist

1. Test cases:
   - Toggle items on/off
   - Try to disable all but one item (should be prevented)
   - Save and reload page (persistence)
   - Navigate using custom nav
   - Reset to defaults
   - Access keyboard shortcut (if implemented)

2. Browser compatibility:
   - Chrome
   - Safari
   - Firefox
   - Mobile browsers

3. Edge cases:
   - localStorage disabled
   - Corrupted preferences data
   - Rapid clicking

**Verification**: All test cases pass.

---

## File Changes Summary

### New Files
1. `web/js/nav-config.js` - Navigation items configuration
2. `web/js/nav-preferences.js` - Preference management logic

### Modified Files
1. `web/index.html` - Update nav rendering, add trigger button
2. `web/js/components.js` - Add feature menu component
3. `web/styles.css` - Add styles for feature menu
4. `web/js/app.js` - May need updates for nav integration

### No Changes Needed
- Forum pages (separate nav system)
- API layer
- Database

## Rollout Plan
1. Deploy on feature branch
2. QA testing
3. User acceptance testing
4. Deploy to main branch
5. Monitor for issues

## Success Criteria
- Users can customize their navigation bar
- Preferences persist across sessions
- At least 2 items must always be enabled
- Smooth UX with proper visual feedback
- No breaking changes to existing functionality
