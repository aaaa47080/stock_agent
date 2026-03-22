/**
 * Shared Utility Functions
 *
 * Single source of truth for common helpers used across all modules.
 * This file MUST be loaded before any other JS file in index.html.
 */
const AppUtils = {
    /**
     * Escape HTML special characters to prevent XSS.
     * Safe for use in both text content and HTML attribute values.
     * @param {string} str
     * @returns {string}
     */
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    /**
     * Sanitize a URL to prevent javascript:/data:/vbscript: injection.
     * @param {string} url
     * @returns {string}
     */
    sanitizeUrl(url) {
        if (!url) return '#';
        var trimmed = String(url).trim();
        if (
            trimmed.startsWith('javascript:') ||
            trimmed.startsWith('data:') ||
            trimmed.startsWith('vbscript:')
        ) {
            return '#';
        }
        return trimmed;
    },

    /**
     * i18n translation helper — wraps the verbose inline fallback pattern.
     * Returns the translated string or falls back to the key itself.
     * @param {string} key - i18next key
     * @param {object} [options] - i18next interpolation options
     * @returns {string}
     */
    t(key, options) {
        if (window.I18n && typeof window.I18n.t === 'function') {
            return window.I18n.t(key, options);
        }
        return key;
    },

    /**
     * Refresh Lucide icons within a specific container (scoped).
     * Falls back to global scan if no container is provided.
     * @param {HTMLElement} [container] - scope to specific element
     */
    refreshIcons(container) {
        if (!window.lucide || typeof window.lucide.createIcons !== 'function') return;
        if (container) {
            window.lucide.createIcons({ nodes: [container] });
        } else {
            window.lucide.createIcons();
        }
    },
};

window.AppUtils = AppUtils;
window.escapeHtml = AppUtils.escapeHtml;
window.sanitizeUrl = AppUtils.sanitizeUrl;
window._t = AppUtils.t;
window.t = AppUtils.t;
export { AppUtils };
