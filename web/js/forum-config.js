// ========================================
// forum.js - 論壇功能核心邏輯
// ========================================

// ============================================
// Pi 支付價格配置（從後端動態獲取）
// ============================================
const _defaultPiPrices = {
    create_post: null, // 完全依賴後端配置
    tip: null,
    premium: null,
    loaded: false,
};
// AppStore is optional (not loaded on all pages); always keep window.PiPrices in sync
window.PiPrices = _defaultPiPrices;
if (typeof AppStore !== 'undefined') AppStore.set('PiPrices', _defaultPiPrices);

// ============================================
// 論壇限制配置（從後端動態獲取）
// ============================================
const _defaultForumLimits = {
    daily_post_free: null,
    daily_post_premium: null,
    daily_comment_free: null,
    daily_comment_premium: null,
    loaded: false,
};
window.ForumLimits = _defaultForumLimits;
if (typeof AppStore !== 'undefined') AppStore.set('ForumLimits', _defaultForumLimits);

// 從後端載入價格配置
async function loadPiPrices() {
    if (window.PiPrices.loading) return; // Prevent concurrent requests
    window.PiPrices = { ...window.PiPrices, loading: true };
    if (typeof AppStore !== 'undefined') AppStore.set('PiPrices', window.PiPrices);

    try {
        const data = await AppAPI.get('/api/config/prices');
        const updated = { ...data.prices, loaded: true, loading: false };
        window.PiPrices = updated;
        if (typeof AppStore !== 'undefined') AppStore.set('PiPrices', updated);
        console.log('[Forum] Pi 價格配置已載入:', updated);
        // 更新頁面上的價格顯示
        updatePriceDisplays();
        // 通知其他模組價格已更新
        document.dispatchEvent(new Event('pi-prices-updated'));
    } catch (e) {
        console.error('[Forum] 載入價格配置失敗:', e);
        window.PiPrices = { ...window.PiPrices, loading: false };
        if (typeof AppStore !== 'undefined') AppStore.set('PiPrices', window.PiPrices);
    }
}

function updatePriceDisplays() {
    // 更新所有帶有 data-price 屬性的元素
    const prices = window.PiPrices;
    if (!prices || !prices.loaded) {
        console.log('[Forum] 價格尚未載入，跳過更新');
        return;
    }

    const priceElements = document.querySelectorAll('[data-price]');
    priceElements.forEach((el) => {
        const priceKey = el.getAttribute('data-price');
        const price = prices[priceKey];

        if (price !== undefined && price !== null) {
            el.textContent = `${price} Pi`;
        }
    });

    console.log('[Forum] 價格顯示已更新:', prices);
}

// 從後端載入論壇限制配置
async function loadForumLimits() {
    if (window.ForumLimits.loading) return;
    window.ForumLimits = { ...window.ForumLimits, loading: true };
    if (typeof AppStore !== 'undefined') AppStore.set('ForumLimits', window.ForumLimits);

    try {
        const data = await AppAPI.get('/api/config/limits');
        const updated = { ...data.limits, loaded: true, loading: false };
        window.ForumLimits = updated;
        if (typeof AppStore !== 'undefined') AppStore.set('ForumLimits', updated);
        console.log('[Forum] 論壇限制配置已載入:', updated);
        // 通知其他模組限制已更新
        document.dispatchEvent(new Event('forum-limits-updated'));
    } catch (e) {
        console.error('[Forum] 載入論壇限制配置失敗:', e);
        window.ForumLimits = { ...window.ForumLimits, loading: false };
        if (typeof AppStore !== 'undefined') AppStore.set('ForumLimits', window.ForumLimits);
    }
}

// 取得價格的輔助函數（確保有值）
function getPrice(key) {
    const prices = window.PiPrices;
    if (prices?.loaded && prices[key] !== null) {
        return prices[key];
    }
    console.warn(`[Forum] 價格 ${key} 尚未載入，請確認 API 連線`);
    return null;
}

// 取得限制的輔助函數（確保有值）
function getLimit(key) {
    const limits = window.ForumLimits;
    if (limits?.loaded && limits[key] !== undefined) {
        return limits[key];
    }
    console.warn(`[Forum] 限制 ${key} 尚未載入，請確認 API 連線`);
    return null;
}

// Helper to format date
function formatTWDate(dateStr, full = false) {
    if (!dateStr) return '';
    try {
        // Server stores UTC — append 'Z' if no timezone info so JS parses as UTC
        let normalized = dateStr;
        if (
            typeof dateStr === 'string' &&
            !dateStr.endsWith('Z') &&
            !dateStr.includes('+') &&
            !/\d{2}:\d{2}:\d{2}-/.test(dateStr)
        ) {
            normalized = dateStr.replace(' ', 'T') + 'Z';
        }
        const date = new Date(normalized);
        const now = new Date();
        const diff = now - date;

        // Less than 24 hours
        if (diff < 86400000 && !full) {
            if (diff < 3600000) return Math.max(1, Math.floor(diff / 60000)) + 'm ago';
            return Math.floor(diff / 3600000) + 'h ago';
        }

        // Format: MM/DD or YYYY/MM/DD HH:mm
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');

        if (full) return `${year}/${month}/${day} ${hours}:${minutes}`;
        return `${month}/${day}`;
    } catch (e) {
        return dateStr;
    }
}

export { loadPiPrices, loadForumLimits, getPrice, getLimit, formatTWDate };
