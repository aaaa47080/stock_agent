// ========================================
// core.js - Components system core methods
// Auto-generated from components.js split (lines 1460-1521)
// ========================================

// Initialize Components object if not already created by tab files
window.Components = window.Components || {};

// Track injected components
window.Components._injected = {};

/**
 * 同步注入組件並確保 DOM 更新完成
 * @param {string} id - 分頁 ID (如 'market', 'pulse', 'settings')
 * @returns {Promise<boolean>}
 */
window.Components.inject = async function (id) {
    const container = document.getElementById(id + '-tab');
    if (!container || !this[id]) {
        console.error(
            `[Components] inject failed: container = ${!!container}, template = ${!!this[id]} `
        );
        return false;
    }

    // 如果已經注入過，直接返回
    if (this._injected[id]) {
        console.log(`[Components] ${id} already injected, skipping`);
        return true;
    }

    console.log(`[Components] Injecting ${id}...`);

    // 直接設置 innerHTML
    container.innerHTML = this[id];
    this._injected[id] = true;

    // ✅ 效能優化：用 requestAnimationFrame 取代 setTimeout(50ms)，等 DOM paint 完成即可
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

    // 初始化 Lucide 圖標
    AppUtils.refreshIcons();

    // 更新 i18n 翻譯（動態注入的 data-i18n 元素需要重新翻譯）
    if (window.I18n && typeof window.I18n.updatePageContent === 'function') {
        window.I18n.updatePageContent();
    }

    console.log(`[Components] ${id} injected successfully`);
    return true;
};

/**
 * 檢查組件是否已注入
 */
window.Components.isInjected = function (id) {
    return !!this._injected[id];
};

/**
 * 強制重新注入
 */
window.Components.forceInject = async function (id) {
    this._injected[id] = false;
    return this.inject(id);
};

// 標記組件系統已就緒
window.ComponentsReady = true;

// Side-effect module — Components is on window for backward compatibility.
export {};
