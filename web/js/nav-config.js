/**
 * Navigation Configuration Module
 * Defines all available navigation items and default states
 */

const NAV_ITEMS = [
    { id: 'chat', icon: 'message-circle', label: 'Chat', defaultEnabled: true },
    { id: 'market', icon: 'bar-chart-2', label: 'Market', defaultEnabled: true },
    { id: 'pulse', icon: 'activity', label: 'Pulse', defaultEnabled: true },
    { id: 'wallet', icon: 'credit-card', label: 'Wallet', defaultEnabled: true },
    { id: 'assets', icon: 'wallet', label: 'Assets', defaultEnabled: true },
    { id: 'friends', icon: 'users', label: 'Friends', defaultEnabled: true },
    { id: 'forum', icon: 'messages-square', label: 'Forum', defaultEnabled: true },
    { id: 'safety', icon: 'shield-alert', label: 'Safety', defaultEnabled: true },
    { id: 'settings', icon: 'settings-2', label: 'Settings', defaultEnabled: true, locked: true }
];

/**
 * Navigation Preferences Manager
 * Handles user's navigation customization preferences
 */
const NavPreferences = {
    STORAGE_KEY: 'userNavPreferences',
    PREFERENCES_VERSION: 2,
    MIN_ENABLED_ITEMS: 2,

    /**
     * Get all enabled navigation items
     * @returns {Array} Array of enabled NAV_ITEMS
     */
    getEnabledItems() {
        const preferences = this.loadPreferences();
        return NAV_ITEMS.filter(item => preferences.enabledItems.includes(item.id));
    },

    /**
     * Check if a specific item is enabled
     * @param {string} itemId - The item ID to check
     * @returns {boolean}
     */
    isItemEnabled(itemId) {
        const preferences = this.loadPreferences();
        return preferences.enabledItems.includes(itemId);
    },

    /**
     * Enable or disable a navigation item
     * @param {string} itemId - The item ID to update
     * @param {boolean} enabled - Whether to enable or disable
     * @returns {boolean} Success status
     */
    setItemEnabled(itemId, enabled) {
        const preferences = this.loadPreferences();
        const itemExists = NAV_ITEMS.some(item => item.id === itemId);

        if (!itemExists) {
            console.warn(`Navigation item '${itemId}' does not exist`);
            return false;
        }

        if (enabled) {
            if (!preferences.enabledItems.includes(itemId)) {
                preferences.enabledItems.push(itemId);
            }
        } else {
            if (!this.canDisableItem(itemId)) {
                console.warn(`Cannot disable '${itemId}': minimum ${this.MIN_ENABLED_ITEMS} items must be enabled`);
                return false;
            }
            preferences.enabledItems = preferences.enabledItems.filter(id => id !== itemId);
        }

        this.savePreferences(preferences);
        return true;
    },

    /**
     * Check if an item can be disabled (ensures minimum items)
     * @param {string} itemId - The item to check
     * @returns {boolean}
     */
    canDisableItem(itemId) {
        // Locked items can never be disabled
        const item = NAV_ITEMS.find(i => i.id === itemId);
        if (item && item.locked) return false;

        const preferences = this.loadPreferences();
        const currentlyEnabled = preferences.enabledItems.filter(id => id !== itemId);
        return currentlyEnabled.length >= this.MIN_ENABLED_ITEMS;
    },

    /**
     * Reset all items to default enabled state
     */
    resetToDefaults() {
        const defaultPreferences = {
            version: this.PREFERENCES_VERSION,
            enabledItems: NAV_ITEMS.filter(item => item.defaultEnabled).map(item => item.id)
        };
        this.savePreferences(defaultPreferences);
    },

    /**
     * Validate preferences object
     * @param {Object} preferences - Preferences to validate
     * @returns {Object} { valid: boolean, errors: Array }
     */
    validate(preferences) {
        const errors = [];

        if (!preferences.version || typeof preferences.version !== 'number') {
            errors.push('Invalid or missing version');
        }

        if (!Array.isArray(preferences.enabledItems)) {
            errors.push('enabledItems must be an array');
        } else {
            if (preferences.enabledItems.length < this.MIN_ENABLED_ITEMS) {
                errors.push(`At least ${this.MIN_ENABLED_ITEMS} items must be enabled`);
            }

            const validIds = NAV_ITEMS.map(item => item.id);
            const invalidIds = preferences.enabledItems.filter(id => !validIds.includes(id));
            if (invalidIds.length > 0) {
                errors.push(`Invalid item IDs: ${invalidIds.join(', ')}`);
            }
        }

        return {
            valid: errors.length === 0,
            errors
        };
    },

    /**
     * Load preferences from localStorage
     * @returns {Object} Preferences object
     */
    loadPreferences() {
        try {
            const stored = localStorage.getItem(this.STORAGE_KEY);
            if (stored) {
                const preferences = JSON.parse(stored);

                // Validate loaded preferences
                const validation = this.validate(preferences);
                if (!validation.valid) {
                    console.warn('Invalid preferences loaded, resetting to defaults:', validation.errors);
                    return this._getDefaultPreferences();
                }

                let changed = false;

                // Version migration: add new default items when version bumps
                if (!preferences.version || preferences.version < this.PREFERENCES_VERSION) {
                    NAV_ITEMS.filter(i => i.defaultEnabled).forEach(item => {
                        if (!preferences.enabledItems.includes(item.id)) {
                            preferences.enabledItems.push(item.id);
                            changed = true;
                        }
                    });
                    preferences.version = this.PREFERENCES_VERSION;
                    changed = true;
                }

                // Ensure locked items are always included
                NAV_ITEMS.filter(i => i.locked).forEach(item => {
                    if (!preferences.enabledItems.includes(item.id)) {
                        preferences.enabledItems.push(item.id);
                        changed = true;
                    }
                });

                if (changed) {
                    this.savePreferences(preferences);
                }

                return preferences;
            }
        } catch (error) {
            console.error('Error loading navigation preferences:', error);
        }

        return this._getDefaultPreferences();
    },

    /**
     * Save preferences to localStorage
     * @param {Object} preferences - Preferences to save
     * @returns {boolean} Success status
     */
    savePreferences(preferences) {
        const validation = this.validate(preferences);
        if (!validation.valid) {
            console.error('Invalid preferences:', validation.errors);
            return false;
        }

        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(preferences));
            return true;
        } catch (error) {
            console.error('Error saving navigation preferences:', error);
            return false;
        }
    },

    /**
     * Export preferences for backup/transfer
     * @returns {string} JSON string of preferences
     */
    exportPreferences() {
        const preferences = this.loadPreferences();
        return JSON.stringify(preferences, null, 2);
    },

    /**
     * Import preferences from JSON string
     * @param {string} jsonString - JSON string to import
     * @returns {boolean} Success status
     */
    importPreferences(jsonString) {
        try {
            const preferences = JSON.parse(jsonString);
            const validation = this.validate(preferences);

            if (!validation.valid) {
                console.error('Invalid preferences to import:', validation.errors);
                return false;
            }

            this.savePreferences(preferences);
            return true;
        } catch (error) {
            console.error('Error importing navigation preferences:', error);
            return false;
        }
    },

    /**
     * Get default preferences
     * @returns {Object} Default preferences object
     * @private
     */
    _getDefaultPreferences() {
        return {
            version: this.PREFERENCES_VERSION,
            enabledItems: NAV_ITEMS.filter(item => item.defaultEnabled).map(item => item.id)
        };
    }
};

// Make available on window for cross-script access
window.NAV_ITEMS = NAV_ITEMS;
window.NavPreferences = NavPreferences;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NAV_ITEMS, NavPreferences };
}
