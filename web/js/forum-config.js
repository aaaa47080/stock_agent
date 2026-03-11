// ========================================
// forum.js - 論壇功能核心邏輯
// ========================================

// ============================================
// Pi 支付價格配置（從後端動態獲取）
// ============================================
window.PiPrices = {
    create_post: null, // 完全依賴後端配置
    tip: null,
    premium: null,
    loaded: false,
};

// ============================================
// 論壇限制配置（從後端動態獲取）
// ============================================
window.ForumLimits = {
    daily_post_free: null,
    daily_post_premium: null,
    daily_comment_free: null,
    daily_comment_premium: null,
    loaded: false,
};

// 從後端載入價格配置
async function loadPiPrices() {
    if (window.PiPrices.loading) return; // Prevent concurrent requests
    window.PiPrices.loading = true;

    try {
        const res = await fetch('/api/config/prices');
        if (res.ok) {
            const data = await res.json();
            window.PiPrices = { ...data.prices, loaded: true, loading: false };
            console.log('[Forum] Pi 價格配置已載入:', window.PiPrices);
            // 更新頁面上的價格顯示
            updatePriceDisplays();
            // 通知其他模組價格已更新
            document.dispatchEvent(new Event('pi-prices-updated'));
        } else {
            window.PiPrices.loading = false;
        }
    } catch (e) {
        console.error('[Forum] 載入價格配置失敗:', e);
        window.PiPrices.loading = false;
    }
}

function updatePriceDisplays() {
    // 更新所有帶有 data-price 屬性的元素
    if (!window.PiPrices || !window.PiPrices.loaded) {
        console.log('[Forum] 價格尚未載入，跳過更新');
        return;
    }

    const priceElements = document.querySelectorAll('[data-price]');
    priceElements.forEach((el) => {
        const priceKey = el.getAttribute('data-price');
        const price = window.PiPrices[priceKey];

        if (price !== undefined && price !== null) {
            el.textContent = `${price} Pi`;
        }
    });

    console.log('[Forum] 價格顯示已更新:', window.PiPrices);
}

// 從後端載入論壇限制配置
async function loadForumLimits() {
    if (window.ForumLimits.loading) return;
    window.ForumLimits.loading = true;

    try {
        const res = await fetch('/api/config/limits');
        if (res.ok) {
            const data = await res.json();
            window.ForumLimits = { ...data.limits, loaded: true, loading: false };
            console.log('[Forum] 論壇限制配置已載入:', window.ForumLimits);
            // 通知其他模組限制已更新
            document.dispatchEvent(new Event('forum-limits-updated'));
        } else {
            window.ForumLimits.loading = false;
        }
    } catch (e) {
        console.error('[Forum] 載入論壇限制配置失敗:', e);
        window.ForumLimits.loading = false;
    }
}

// 取得價格的輔助函數（確保有值）
function getPrice(key) {
    if (window.PiPrices?.loaded && window.PiPrices[key] !== null) {
        return window.PiPrices[key];
    }
    console.warn(`[Forum] 價格 ${key} 尚未載入，請確認 API 連線`);
    return null;
}

// 取得限制的輔助函數（確保有值）
function getLimit(key) {
    if (window.ForumLimits?.loaded && window.ForumLimits[key] !== undefined) {
        return window.ForumLimits[key];
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

