// ========================================
// app.js - 核心應用邏輯與全局變量
// ========================================

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

// markdown-it 可能不存在於所有頁面
// 安全修復: 關閉 HTML 功能以防止 XSS 攻擊
const md = window.markdownit
    ? window.markdownit({ html: false, linkify: true, breaks: true })
    : null;
window.md = md;
AppStore.set('isAnalyzing', false);
window.isAnalyzing = false; // backward compat
let marketRefreshInterval = null;

// ========================================
// 安全工具函數
// ========================================

/**
 * 轉義 HTML 特殊字符，防止 XSS 攻擊
 * 注意：security-utils.js 另有 SecurityUtils.escapeHTML（使用 DOM textContent）。
 * 此版本額外轉義單引號（&#039;），適合用在 HTML attribute 值中，兩者不衝突。
 * 全域程式碼（chat.js、forum.js 等）均使用此簡短名稱 escapeHtml。
 * @param {string} str - 要轉義的字符串
 * @returns {string} 轉義後的字符串
 */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

// ========================================
// 自定義對話框系統 (替代原生 alert/confirm)
// ========================================

/**
 * 處理返回主程式的過渡效果
 * @param {Event} e - 事件對象
 * @param {string} targetTab - 可選的目標 tab（如 'friends', 'chat' 等）
 */
function handleBackToApp(e, targetTab = '') {
    if (e) e.preventDefault();

    // 添加淡出效果（統一使用 0.2s）
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.2s ease-out';

    // 構建目標 URL
    let targetUrl = '/static/index.html';
    if (targetTab) {
        targetUrl += '#' + targetTab;
    }

    setTimeout(() => {
        window.location.href = targetUrl;
    }, 200);
}

// 暴露到全局
window.handleBackToApp = handleBackToApp;

/**
 * 通用的平滑導航函數
 * @param {string} url - 目標 URL
 * @param {number} delay - 過渡延遲（毫秒）
 */
function smoothNavigate(url, delay = 200) {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.2s ease-out';
    setTimeout(() => {
        window.location.href = url;
    }, delay);
}
window.smoothNavigate = smoothNavigate;

/**
 * 初始化頁面淡入效果
 */
function initPageTransition() {
    // 頁面載入時的淡入效果
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.2s ease-in';
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });

    // 為所有返回主應用的連結添加平滑過渡
    document
        .querySelectorAll('a[href="/static/index.html"], a[href^="/static/index.html#"]')
        .forEach((link) => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                smoothNavigate(link.href);
            });
        });

    // 為所有論壇內部連結添加平滑過渡
    document.querySelectorAll('a[href^="/static/forum/"]').forEach((link) => {
        // 排除當前頁面的連結
        if (link.href === window.location.href) return;

        link.addEventListener('click', (e) => {
            e.preventDefault();
            smoothNavigate(link.href);
        });
    });
}

// 在 DOM 載入後初始化頁面過渡
document.addEventListener('DOMContentLoaded', () => {
    // 只在論壇頁面執行（非主應用）
    const page = document.body.dataset.page;
    if (page && page !== 'main') {
        initPageTransition();
    }
});

window.initPageTransition = initPageTransition;

/**
 * 顯示確認對話框 (替代 confirm)
 */
function showConfirm(options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const iconEl = document.getElementById('confirm-modal-icon');
        const titleEl = document.getElementById('confirm-modal-title');
        const messageEl = document.getElementById('confirm-modal-message');
        const confirmBtn = document.getElementById('confirm-modal-confirm');
        const cancelBtn = document.getElementById('confirm-modal-cancel');
        const content = modal ? modal.querySelector('div') : null;

        if (!modal) {
            resolve(window.confirm(options.message || '確定嗎？'));
            return;
        }

        const {
            title = '確認操作',
            message = '確定要執行此操作嗎？',
            type = 'warning',
            confirmText = '確認',
            cancelText = '取消',
        } = options;

        // 設置圖標和顏色
        const iconConfig = {
            danger: { icon: 'alert-triangle', bg: 'bg-danger/20', color: 'text-danger' },
            warning: { icon: 'alert-circle', bg: 'bg-primary/20', color: 'text-primary' },
            info: { icon: 'info', bg: 'bg-accent/20', color: 'text-accent' },
            success: { icon: 'check-circle', bg: 'bg-success/20', color: 'text-success' },
        };

        const config = iconConfig[type] || iconConfig.warning;

        const ALLOWED_ICON_NAMES = new Set([
            'alert-triangle',
            'alert-circle',
            'info',
            'check-circle',
            'x-circle',
        ]);
        const safeIcon = ALLOWED_ICON_NAMES.has(config.icon) ? config.icon : 'info';

        if (iconEl) {
            iconEl.className = `w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${config.bg}`;
            iconEl.innerHTML = `<i data-lucide="${safeIcon}" class="w-8 h-8 ${config.color}"></i>`;
        }

        if (titleEl) titleEl.textContent = title;
        if (messageEl) messageEl.textContent = message;
        if (confirmBtn) confirmBtn.textContent = confirmText;
        if (cancelBtn) cancelBtn.textContent = cancelText;

        // 根據類型設置確認按鈕樣式
        if (confirmBtn) {
            if (type === 'danger') {
                confirmBtn.className =
                    'flex-1 py-3 bg-danger hover:brightness-110 text-white font-bold rounded-2xl transition shadow-lg';
            } else {
                confirmBtn.className =
                    'flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg';
            }
        }

        if (window.lucide) lucide.createIcons();

        // 觸發動畫
        if (content) {
            content.classList.remove('modal-content-active');
            void content.offsetWidth; // 強制重繪
            content.classList.add('modal-content-active');
        }

        modal.classList.remove('hidden');

        // 清除舊的事件監聽器並添加新的
        const newConfirmBtn = confirmBtn.cloneNode(true);
        const newCancelBtn = cancelBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

        newConfirmBtn.onclick = () => {
            modal.classList.add('hidden');
            resolve(true);
        };

        newCancelBtn.onclick = () => {
            modal.classList.add('hidden');
            resolve(false);
        };
    });
}

/**
 * 顯示 Alert 對話框 (替代 alert，只有確認按鈕)
 * @param {Object} options - 配置選項
 * @returns {Promise<void>}
 */
function showAlert(options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const iconEl = document.getElementById('confirm-modal-icon');
        const titleEl = document.getElementById('confirm-modal-title');
        const messageEl = document.getElementById('confirm-modal-message');
        const buttonsEl = document.getElementById('confirm-modal-buttons');

        if (!modal) {
            window.alert(options.message || '提示');
            resolve();
            return;
        }

        const { title = '提示', message = '', type = 'info', confirmText = '確定' } = options;

        // 設置圖標和顏色
        const iconConfig = {
            danger: { icon: 'x-circle', bg: 'bg-danger/20', color: 'text-danger' },
            warning: { icon: 'alert-triangle', bg: 'bg-primary/20', color: 'text-primary' },
            info: { icon: 'info', bg: 'bg-accent/20', color: 'text-accent' },
            success: { icon: 'check-circle', bg: 'bg-success/20', color: 'text-success' },
        };

        const config = iconConfig[type] || iconConfig.info;

        const ALLOWED_ICON_NAMES = new Set([
            'alert-triangle',
            'alert-circle',
            'info',
            'check-circle',
            'x-circle',
        ]);
        const safeIcon = ALLOWED_ICON_NAMES.has(config.icon) ? config.icon : 'info';

        iconEl.className = `w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${config.bg}`;
        iconEl.innerHTML = `<i data-lucide="${safeIcon}" class="w-8 h-8 ${config.color}"></i>`;

        titleEl.textContent = title;
        messageEl.textContent = message;

        // 只顯示一個按鈕
        const safeConfirmText = String(confirmText || '確定');
        buttonsEl.innerHTML = `
            <button id="confirm-modal-ok" class="flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg">
                ${escapeHtml(safeConfirmText)}
            </button>
        `;

        lucide.createIcons();
        modal.classList.remove('hidden');

        document.getElementById('confirm-modal-ok').onclick = () => {
            // 恢復兩個按鈕的結構
            buttonsEl.innerHTML = `
                <button id="confirm-modal-cancel" class="flex-1 py-3 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5">
                    ${window.i18next?.t('common.cancel') || '取消'}
                </button>
                <button id="confirm-modal-confirm" class="flex-1 py-3 bg-danger hover:brightness-110 text-white font-bold rounded-2xl transition shadow-lg">
                    ${window.i18next?.t('common.confirm') || '確認'}
                </button>
            `;
            modal.classList.add('hidden');
            resolve();
        };
    });
}

// 全局導出
window.showConfirm = showConfirm;
window.showAlert = showAlert;

// ========================================
// API Key Status Check
// ========================================
async function checkApiKeyStatus() {
    if (window.DEBUG_MODE) console.log('[App] checkApiKeyStatus called');

    const indicator = document.getElementById('api-status-indicator');
    const statusText = document.getElementById('api-status-text');
    const statusDot = indicator ? indicator.querySelector('span') : null;

    // Check LLM Key (async) - 添加錯誤處理
    let currentKey = null;
    let hasLlmKey = false;
    try {
        if (window.APIKeyManager && typeof window.APIKeyManager.getCurrentKey === 'function') {
            currentKey = await window.APIKeyManager.getCurrentKey();
            hasLlmKey = !!currentKey;
        }
    } catch (e) {
        console.warn('[App] Error checking API key:', e);
        hasLlmKey = false;
    }
    if (window.DEBUG_MODE) console.log('[App] hasLlmKey:', hasLlmKey);

    // 1. Update Top Bar Indicator (LLM Status)
    if (indicator && statusText && statusDot) {
        if (hasLlmKey) {
            const providerName =
                currentKey.provider === 'openai'
                    ? 'OpenAI'
                    : currentKey.provider === 'google_gemini'
                      ? 'Gemini'
                      : currentKey.provider === 'openrouter'
                        ? 'OpenRouter'
                        : currentKey.provider;

            statusDot.className =
                'w-2 h-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse';
            statusText.textContent = `AI Online: ${providerName}`;
            statusText.className = 'text-emerald-400 font-mono tracking-tight';
            statusText.onclick = null;
        } else {
            statusDot.className = 'w-2 h-2 bg-rose-500 rounded-full animate-pulse';
            statusText.textContent = 'SYSTEM OFFLINE (NO KEY)';
            statusText.className =
                'text-rose-400 font-mono tracking-tight cursor-pointer hover:underline';
            statusText.onclick = () => {
                if (typeof openSettings === 'function') openSettings();
            };
        }
    }

    // 2. Control Chat Tab Overlay (LLM Key)
    const llmOverlay = document.getElementById('no-llm-key-warning');
    if (window.DEBUG_MODE)
        console.log('[App] llmOverlay element:', !!llmOverlay, 'hasLlmKey:', hasLlmKey);
    if (llmOverlay) {
        if (hasLlmKey) {
            llmOverlay.classList.add('hidden');
            if (window.DEBUG_MODE) console.log('[App] Hiding LLM overlay (has key)');
        } else {
            llmOverlay.classList.remove('hidden');
            if (window.DEBUG_MODE) console.log('[App] Showing LLM overlay (no key)');
        }
    }

    // 3. Update Chat Input State
    updateChatUIState(hasLlmKey);
}
window.checkApiKeyStatus = checkApiKeyStatus;

// ========================================
// 更新聊天 UI 狀態（根據 API key 是否存在）
// ========================================
async function updateChatUIState(hasApiKey) {
    if (hasApiKey === undefined) {
        hasApiKey = !!(await window.APIKeyManager?.getCurrentKey());
    }

    // 1. 建議按鈕區域
    const suggestionsArea = document.getElementById('suggestions-area');
    if (suggestionsArea) {
        suggestionsArea.classList.toggle('hidden', !hasApiKey);
    }

    // 2. API Key 未設置警告覆蓋層
    const noLlmKeyWarning = document.getElementById('no-llm-key-warning');
    if (noLlmKeyWarning) {
        // 沒有 API key 時顯示覆蓋層
        noLlmKeyWarning.classList.toggle('hidden', hasApiKey);
    }

    // 3. 舊的 API Key 警告 (保留相容性)
    const apiKeyWarning = document.getElementById('api-key-warning');
    if (apiKeyWarning) {
        apiKeyWarning.classList.toggle('hidden', hasApiKey);
    }

    // 4. 輸入框和發送按鈕
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    if (userInput) {
        userInput.disabled = !hasApiKey;
        userInput.placeholder = hasApiKey
            ? window.I18n?.t('chat.placeholderReady') || 'Send a command to AI Agent...'
            : window.I18n?.t('chat.systemLocked') || 'System Locked - Please Configure API Key';
        userInput.classList.toggle('opacity-50', !hasApiKey);
        userInput.classList.toggle('cursor-not-allowed', !hasApiKey);
    }

    if (sendBtn) {
        sendBtn.disabled = !hasApiKey;
        sendBtn.classList.toggle('opacity-50', !hasApiKey);
        sendBtn.classList.toggle('cursor-not-allowed', !hasApiKey);
    }
}
window.updateChatUIState = updateChatUIState;

// 暴露到全局供 index.html 控制初始化順序
function initializeUIStatus() {
    if (window.DEBUG_MODE) console.log('[App] initializeUIStatus called');
    if (window.DEBUG_MODE) console.log('[App] APIKeyManager exists:', !!window.APIKeyManager);
    // Note: getCurrentKey() is async, so we can't check it synchronously in debug log

    // 只在初始化時檢查一次
    checkApiKeyStatus();
    // 移除定期輪詢 - API Key 設定後狀態就確定了
    // 狀態變更時應該主動調用 checkApiKeyStatus() 而非輪詢
}
window.initializeUIStatus = initializeUIStatus;

// 頁面加載時不再自動執行，由 index.html 統一調度
// window.addEventListener('DOMContentLoaded', () => { ... });

// --- Global Filter Logic Variables ---
AppStore.set('allMarketSymbols', []);
window.allMarketSymbols = [];
AppStore.set('globalSelectedSymbols', []);
window.globalSelectedSymbols = []; // Unified selection
AppStore.set('selectedNewsSources', ['google', 'cryptocompare', 'cryptopanic', 'newsapi']);
window.selectedNewsSources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']; // ✅ 固定使用所有新聞來源
AppStore.set('currentFilterExchange', 'okx');
window.currentFilterExchange = 'okx';

// API Key Validity Cache
let validKeys = {
    openai: false,
    google_gemini: false,
    openrouter: false,
};

function updateProviderOptions() {
    // Simple implementation to visually indicate valid keys in the dropdown
    const select = document.getElementById('llm-provider-select');
    if (!select) return;

    Array.from(select.options).forEach((opt) => {
        const provider = opt.value;
        if (validKeys[provider]) {
            if (!opt.text.includes('✅')) {
                opt.text = `${opt.text} ✅`;
            }
        }
    });
}
window.updateProviderOptions = updateProviderOptions;

// Watchlist & Chart Variables
let currentUserId = null;

// Pulse Data Cache (使用 window 物件避免重複聲明)
if (typeof window.currentPulseData === 'undefined') {
    AppStore.set('currentPulseData', {});
    window.currentPulseData = {};
}

// Trade Proposal

// Analysis Abort Controller
AppStore.set('currentAnalysisController', null);
window.currentAnalysisController = null;

// Pi Network Initialization
const Pi = window.Pi;

// ========================================
// Tab Switching (called from HTML after basic UI update)
// ========================================
// Note: The main switchTab() function is now defined inline in index.html
// This function handles additional logic like intervals and API calls

// 記錄上一個 tab，防止相同 tab 重複觸發 setInterval
let _lastOnTabSwitchTab = null;

function onTabSwitch(tab) {
    // ✅ 防止相同 tab 重複創建 interval（快速點擊或初始化時的雙重呼叫）
    if (tab === _lastOnTabSwitchTab) return;
    _lastOnTabSwitchTab = tab;

    // Abort pending analysis if leaving chat tab
    if (tab !== 'chat' && AppStore.get('currentAnalysisController')) {
        AppStore.get('currentAnalysisController').abort();
        AppStore.set('currentAnalysisController', null);
        window.currentAnalysisController = null;
        isAnalyzing = false;

        const input = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        if (input && sendBtn) {
            input.disabled = false;
            sendBtn.disabled = false;
            input.classList.remove('opacity-50');
            sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    // Clear all intervals
    if (marketRefreshInterval) {
        clearInterval(marketRefreshInterval);
        marketRefreshInterval = null;
    }
    if (AppStore.get('pulseInterval')) {
        clearInterval(AppStore.get('pulseInterval'));
        AppStore.set('pulseInterval', null);
        window.pulseInterval = null;
    }
    if (AppStore.get('assetsInterval')) {
        clearInterval(AppStore.get('assetsInterval'));
        AppStore.set('assetsInterval', null);
        window.assetsInterval = null;
    }

    // Set up new intervals based on tab
    if (tab === 'crypto' || tab === 'market') {
        marketRefreshInterval = setInterval(() => {
            if (typeof refreshScreener === 'function') refreshScreener(false);
        }, 60000);
    }

    if (tab === 'crypto' || tab === 'pulse') {
        AppStore.set('pulseInterval', setInterval(() => {
            if (typeof checkMarketPulse === 'function') checkMarketPulse(false);
        }, 30000));
        window.pulseInterval = AppStore.get('pulseInterval');
    }

    // Friends Tab
    if (tab === 'friends') {
        // Force inject component if not already done (though switchTab usually handles this)
        const initFriends = () => {
            if (typeof loadFriendsTabData === 'function') loadFriendsTabData();
        };

        if (window.Components && !window.Components.isInjected('friends')) {
            window.Components.inject('friends').then(initFriends);
        } else {
            initFriends();
        }

        // 移除自動輪詢 - Friends 更新應該透過 WebSocket 或用戶手動刷新
        // 不需要每 5 秒重新載入整個列表，這會造成閃爍和不必要的 API 請求
    }
}

// Make it globally accessible
window.onTabSwitch = onTabSwitch;

// ========================================
// Memory Leak Fix: Cleanup on page unload
// ========================================
function cleanupIntervals() {
    // Clear market refresh interval
    if (marketRefreshInterval) {
        clearInterval(marketRefreshInterval);
        marketRefreshInterval = null;
    }
    // Clear pulse interval
    if (AppStore.get('pulseInterval')) {
        clearInterval(AppStore.get('pulseInterval'));
        AppStore.set('pulseInterval', null);
    }
    // Clear assets interval
    if (AppStore.get('assetsInterval')) {
        clearInterval(AppStore.get('assetsInterval'));
        AppStore.set('assetsInterval', null);
    }
}
window.cleanupIntervals = cleanupIntervals;

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    window.cleanupIntervals();
});

// ========================================
// Utility Functions
// ========================================
function updateUserId(uid) {
    currentUserId = uid || null;
}

/**
 * 顯示全局錯誤提示 (Unified Error Display)
 * @param {string} title - 錯誤標題
 * @param {string} message - 錯誤詳情
 * @param {boolean} isQuotaError - 是否為配額/額度不足錯誤
 */
function showError(title, message, isQuotaError = false) {
    // Check if modal exists, if not create it
    let modal = document.getElementById('global-error-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'global-error-modal';
        modal.className =
            'fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm hidden';
        modal.innerHTML = `
            <div class="bg-surface border border-red-500/30 rounded-3xl w-[90%] max-w-md p-6 shadow-2xl transform transition-all scale-95 opacity-0" id="global-error-content">
                <div class="flex items-center gap-3 mb-4 text-red-400">
                    <i data-lucide="alert-triangle" class="w-8 h-8"></i>
                    <h3 class="text-xl font-bold font-serif" id="global-error-title">Error</h3>
                </div>
                <div class="text-secondary/90 text-sm leading-relaxed mb-6" id="global-error-message"></div>
                
                <div id="quota-error-actions" class="hidden mb-4 bg-red-500/10 p-3 rounded-xl border border-red-500/20">
                    <p class="text-xs text-red-300 mb-2">${window.i18next?.t('error.suggestedFixes') || '💡 建議解決方案:'}</p>
                    <ul class="text-xs text-textMuted list-disc pl-4 space-y-1">
                        <li>${window.i18next?.t('error.checkApiKey') || '檢查 API Key 是否正確設定'}</li>
                        <li>${window.i18next?.t('error.checkBalance') || '確認您的 Google/OpenAI 帳戶餘額是否充足'}</li>
                        <li>${window.i18next?.t('error.tryOtherProvider') || '嘗試切換其他 AI 提供商 (如 OpenRouter)'}</li>
                    </ul>
                    <button onclick="openSettings(); closeErrorModal()" class="mt-3 w-full py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg text-sm font-medium transition border border-red-500/30">
                        ${window.i18next?.t('error.goToCheckKey') || '前往設定檢查金鑰'}
                    </button>
                </div>

                <div class="flex justify-end">
                    <button onclick="closeErrorModal()" class="px-5 py-2 bg-surfaceHighlight hover:bg-white/10 text-white rounded-xl transition border border-white/10">
                        ${window.i18next?.t('error.close') || '關閉'}
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        lucide.createIcons();
    }

    const titleEl = document.getElementById('global-error-title');
    const msgEl = document.getElementById('global-error-message');
    const quotaActions = document.getElementById('quota-error-actions');

    titleEl.innerText = title;
    msgEl.innerText = message || window.i18next?.t('error.unknownError') || '發生未知錯誤';

    if (isQuotaError) {
        quotaActions.classList.remove('hidden');
    } else {
        quotaActions.classList.add('hidden');
    }

    modal.classList.remove('hidden');
    // Animation
    setTimeout(() => {
        const content = document.getElementById('global-error-content');
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
}
window.showError = showError;

function closeErrorModal() {
    const modal = document.getElementById('global-error-modal');
    const content = document.getElementById('global-error-content');
    if (modal && content) {
        content.classList.remove('scale-100', 'opacity-100');
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => {
            modal.classList.add('hidden');
        }, 300);
    }
};

function quickAsk(text) {
    const input = document.getElementById('user-input');
    if (input) {
        input.value = text;
        sendMessage();
    }
}
window.quickAsk = quickAsk;

const SETTINGS_CONFIG_CACHE_TTL_MS = 60000;

async function hydrateSettingsFromBackend(force = false) {
    if (!AppStore.has('settingsConfigCache')) {
        const cache = { ts: 0, payload: null };
        AppStore.set('settingsConfigCache', cache);
        window.__settingsConfigCache = cache;
    }

    const cache = AppStore.get('settingsConfigCache');
    const now = Date.now();
    if (!force && cache.payload && now - cache.ts < SETTINGS_CONFIG_CACHE_TTL_MS) {
        return cache.payload;
    }

    const [configData, modelConfigData] = await Promise.all([
        AppAPI.get('/api/config'),
        AppAPI.get('/api/model-config'),
    ]);
    const settings = configData.current_settings || {};
    const preloadedModelConfig = modelConfigData.model_config || null;

    validKeys.openai = !!settings.has_openai_key;
    validKeys.google_gemini = !!settings.has_google_key;
    validKeys.openrouter = !!settings.has_openrouter_key;
    updateProviderOptions();

    if (settings.primary_model_provider) {
        const providerSelect = document.getElementById('llm-provider-select');
        if (providerSelect) {
            providerSelect.value = settings.primary_model_provider;
            if (typeof updateLLMKeyInput === 'function') updateLLMKeyInput();
            if (typeof window.updateAvailableModels === 'function') {
                await window.updateAvailableModels(preloadedModelConfig);
            }
        }
    }

    if (settings.primary_model_name) {
        const modelSelect = document.getElementById('llm-model-select');
        const modelInput = document.getElementById('llm-model-input');
        if (modelSelect && settings.primary_model_provider !== 'openrouter') {
            modelSelect.value = settings.primary_model_name;
        } else if (modelInput) {
            modelInput.value = settings.primary_model_name;
        }
    }

    cache.payload = { settings, preloadedModelConfig };
    cache.ts = Date.now();
    return cache.payload;
}
window.hydrateSettingsFromBackend = hydrateSettingsFromBackend;

async function openSettings() {
    if (typeof switchTab === 'function') {
        await switchTab('settings');
    }

    if (typeof window.loadSavedApiKeys === 'function') {
        Promise.resolve(window.loadSavedApiKeys()).catch((e) =>
            console.warn('loadSavedApiKeys in settings failed:', e)
        );
    }

    Promise.resolve(hydrateSettingsFromBackend()).catch((e) =>
        console.error('Failed to hydrate settings', e)
    );
}

function closeSettings() {
    // Just switch back to default chat tab or previous tab
    // For simplicity, go to Chat
    switchTab('chat');

    // Force UI status update
    if (typeof checkApiKeyStatus === 'function') {
        checkApiKeyStatus();
    }
}
window.closeSettings = closeSettings;

// ========================================
// LLM Model Selection
// ========================================

/**
 * 更新可用模型列表
 * @param {Object|null} preloadedConfig - 預載的模型配置（可選）
 */
async function updateAvailableModels(preloadedConfig = null) {
    const providerSelect = document.getElementById('llm-provider-select');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (!providerSelect || !modelSelect) {
        console.warn('[updateAvailableModels] Required elements not found');
        return;
    }

    const provider = providerSelect.value;
    window.APP_CONFIG?.DEBUG_MODE && console.log('[updateAvailableModels] Provider:', provider);

    // 獲取模型配置
    let modelConfig = preloadedConfig;

    if (!modelConfig) {
        try {
            const data = await AppAPI.get('/api/model-config');
        } catch (e) {
            console.error('[updateAvailableModels] Failed to fetch model config:', e);
        }
    }

    // OpenRouter 使用文字輸入框
    if (provider === 'openrouter') {
        modelSelect.style.display = 'none';
        if (modelInput) {
            modelInput.style.display = 'block';
            modelInput.placeholder = 'e.g., openai/gpt-4o, anthropic/claude-3.5-sonnet';
        }
        return;
    }

    // 其他 provider 使用下拉選單
    modelSelect.style.display = 'block';
    if (modelInput) {
        modelInput.style.display = 'none';
    }

    // 填充模型選項
    const models = modelConfig?.[provider]?.available_models || [];

    // 清空現有選項（不添加 placeholder）
    modelSelect.innerHTML = '';

    if (models.length === 0) {
        console.warn('[updateAvailableModels] No models found for provider:', provider);
        // 添加一個提示選項
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No models available';
        option.disabled = true;
        modelSelect.appendChild(option);
        return;
    }

    models.forEach((model) => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.display || model.value;
        modelSelect.appendChild(option);
    });

    // 設置當前選擇的模型（優先使用已保存的，其次使用 default_model，最後使用第一個）
    const savedModel = window.APIKeyManager?.getModelForProvider?.(provider);
    if (savedModel && models.some((m) => m.value === savedModel)) {
        modelSelect.value = savedModel;
    } else if (modelConfig?.[provider]?.default_model) {
        modelSelect.value = modelConfig[provider].default_model;
    } else if (models.length > 0) {
        modelSelect.value = models[0].value;
    }

    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('[updateAvailableModels] Loaded', models.length, 'models for', provider);
}
window.updateAvailableModels = updateAvailableModels;

// Allow external modules (like llmSettings.js) to update key validity
function setKeyValidity(provider, isValid) {
    if (validKeys.hasOwnProperty(provider)) {
        validKeys[provider] = isValid;
        updateProviderOptions();
    }
}
window.setKeyValidity = setKeyValidity;

// ========================================
// Navigation Logic - 委託給 global-nav.js (GlobalNav)
// 原有 234 行重複的拖拽/收縮邏輯已移除，統一由 GlobalNav 管理
// ========================================

// 向後相容：index.html 的按鈕仍呼叫此名稱
function toggleNavCollapse() {
    if (window.GlobalNav) window.GlobalNav.toggleCollapse();
}
window.toggleNavCollapse = toggleNavCollapse;

// 初始化主應用的導航拖拽與狀態恢復
document.addEventListener('DOMContentLoaded', () => {
    if (window.GlobalNav) {
        window.GlobalNav.initDraggable();
        window.GlobalNav.restoreNavState();
    }
});

async function saveSettings() {
    const btn = document.getElementById('btn-save-settings');
    if (!btn) return;

    // 1. 僅停用並變灰，不改變文字內容 (不閃爍)
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');

    // ⚠️ Prepare Backend Payload
    const payload = {
        openai_api_key: null,
        google_api_key: null,
        openrouter_api_key: null,

        primary_model_provider: document.getElementById('llm-provider-select')
            ? document.getElementById('llm-provider-select').value
            : '',
        primary_model_name: (function () {
            const select = document.getElementById('llm-model-select');
            const input = document.getElementById('llm-model-input');
            const provider = document.getElementById('llm-provider-select')
                ? document.getElementById('llm-provider-select').value
                : '';
            if (provider === 'openrouter') return input ? input.value : '';
            return select ? select.value : '';
        })(),
    };

    try {
        const result = await AppAPI.post('/api/settings/update', payload);

        if (result.success) {
            if (payload.primary_model_provider) {
                window.APIKeyManager.setSelectedProvider(payload.primary_model_provider);
            }

            AppStore.set('settingsConfigCache', null);
            window.__settingsConfigCache = null;
            if (typeof checkApiKeyStatus === 'function') {
                await checkApiKeyStatus();
            }
            if (typeof showToast === 'function') {
                window.showToast('設定已儲存', 'success');
            }
        } else {
            window.showToast('保存設定失敗: ' + (result.detail || '未知錯誤'), 'error');
        }
    } catch (e) {
        window.showToast('保存設定時發生錯誤: ' + e, 'error');
    }

    btn.disabled = false;
    btn.classList.remove('opacity-50', 'cursor-not-allowed');
}
window.saveSettings = saveSettings;

export {
    md,
    escapeHtml,
    handleBackToApp,
    smoothNavigate,
    initPageTransition,
    showConfirm,
    showAlert,
    checkApiKeyStatus,
    updateChatUIState,
    initializeUIStatus,
    updateProviderOptions,
    onTabSwitch,
    cleanupIntervals,
    showError,
    closeErrorModal,
    quickAsk,
    hydrateSettingsFromBackend,
    openSettings,
    closeSettings,
    updateAvailableModels,
    setKeyValidity,
    toggleNavCollapse,
    saveSettings,
};
