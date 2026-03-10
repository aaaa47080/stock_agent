// ========================================
// app.js - 核心應用邏輯與全局變量
// ========================================

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

// markdown-it 可能不存在於所有頁面
// 安全修復: 關閉 HTML 功能以防止 XSS 攻擊
const md = window.markdownit ? window.markdownit({ html: false, linkify: true, breaks: true }) : null;
window.md = md;
window.isAnalyzing = false;
let marketRefreshInterval = null;

// ========================================
// 安全工具函數
// ========================================

/**
 * 轉義 HTML 特殊字符，防止 XSS 攻擊
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
 * 顯示 Toast 通知
 * @param {string} message - 訊息內容
 * @param {string} type - 類型: 'success', 'error', 'warning', 'info'
 * @param {number} duration - 顯示時間(ms)，默認 3000
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: 'check-circle',
        error: 'x-circle',
        warning: 'alert-triangle',
        info: 'info'
    };

    const colors = {
        success: 'bg-success/20 border-success/30 text-success',
        error: 'bg-danger/20 border-danger/30 text-danger',
        warning: 'bg-primary/20 border-primary/30 text-primary',
        info: 'bg-accent/20 border-accent/30 text-accent'
    };

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-2xl border backdrop-blur-xl shadow-xl ${colors[type]} animate-fade-in-up max-w-sm`;
    toast.innerHTML = `
        <i data-lucide="${icons[type]}" class="w-5 h-5 flex-shrink-0 mt-0.5"></i>
        <p class="text-sm leading-relaxed whitespace-pre-line">${message}</p>
        <button onclick="this.parentElement.remove()" class="ml-auto flex-shrink-0 opacity-60 hover:opacity-100 transition">
            <i data-lucide="x" class="w-4 h-4"></i>
        </button>
    `;

    container.appendChild(toast);
    lucide.createIcons();

    // 自動移除
    if (duration > 0) {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

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
    document.querySelectorAll('a[href="/static/index.html"], a[href^="/static/index.html#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            smoothNavigate(link.href);
        });
    });

    // 為所有論壇內部連結添加平滑過渡
    document.querySelectorAll('a[href^="/static/forum/"]').forEach(link => {
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
            cancelText = '取消'
        } = options;

        // 設置圖標和顏色
        const iconConfig = {
            danger: { icon: 'alert-triangle', bg: 'bg-danger/20', color: 'text-danger' },
            warning: { icon: 'alert-circle', bg: 'bg-primary/20', color: 'text-primary' },
            info: { icon: 'info', bg: 'bg-accent/20', color: 'text-accent' },
            success: { icon: 'check-circle', bg: 'bg-success/20', color: 'text-success' }
        };

        const config = iconConfig[type] || iconConfig.warning;

        if (iconEl) {
            iconEl.className = `w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${config.bg}`;
            iconEl.innerHTML = `<i data-lucide="${config.icon}" class="w-8 h-8 ${config.color}"></i>`;
        }

        if (titleEl) titleEl.textContent = title;
        if (messageEl) messageEl.textContent = message;
        if (confirmBtn) confirmBtn.textContent = confirmText;
        if (cancelBtn) cancelBtn.textContent = cancelText;

        // 根據類型設置確認按鈕樣式
        if (confirmBtn) {
            if (type === 'danger') {
                confirmBtn.className = 'flex-1 py-3 bg-danger hover:brightness-110 text-white font-bold rounded-2xl transition shadow-lg';
            } else {
                confirmBtn.className = 'flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg';
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

        const {
            title = '提示',
            message = '',
            type = 'info',
            confirmText = '確定'
        } = options;

        // 設置圖標和顏色
        const iconConfig = {
            danger: { icon: 'x-circle', bg: 'bg-danger/20', color: 'text-danger' },
            warning: { icon: 'alert-triangle', bg: 'bg-primary/20', color: 'text-primary' },
            info: { icon: 'info', bg: 'bg-accent/20', color: 'text-accent' },
            success: { icon: 'check-circle', bg: 'bg-success/20', color: 'text-success' }
        };

        const config = iconConfig[type] || iconConfig.info;

        iconEl.className = `w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${config.bg}`;
        iconEl.innerHTML = `<i data-lucide="${config.icon}" class="w-8 h-8 ${config.color}"></i>`;

        titleEl.textContent = title;
        messageEl.textContent = message;

        // 只顯示一個按鈕
        buttonsEl.innerHTML = `
            <button id="confirm-modal-ok" class="flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg">
                ${confirmText}
            </button>
        `;

        lucide.createIcons();
        modal.classList.remove('hidden');

        document.getElementById('confirm-modal-ok').onclick = () => {
            // 恢復兩個按鈕的結構
            buttonsEl.innerHTML = `
                <button id="confirm-modal-cancel" class="flex-1 py-3 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5">
                    取消
                </button>
                <button id="confirm-modal-confirm" class="flex-1 py-3 bg-danger hover:brightness-110 text-white font-bold rounded-2xl transition shadow-lg">
                    確認
                </button>
            `;
            modal.classList.add('hidden');
            resolve();
        };
    });
}

// 全局導出
window.showToast = showToast;
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

    // Check OKX Key
    const hasOkxKey = window.OKXKeyManager?.hasCredentials();

    // 1. Update Top Bar Indicator (LLM Status)
    if (indicator && statusText && statusDot) {
        if (hasLlmKey) {
            const providerName = currentKey.provider === 'openai' ? 'OpenAI' :
                currentKey.provider === 'google_gemini' ? 'Gemini' :
                    currentKey.provider === 'openrouter' ? 'OpenRouter' : currentKey.provider;

            statusDot.className = 'w-2 h-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse';
            statusText.textContent = `AI Online: ${providerName}`;
            statusText.className = 'text-emerald-400 font-mono tracking-tight';
            statusText.onclick = null;
        } else {
            statusDot.className = 'w-2 h-2 bg-rose-500 rounded-full animate-pulse';
            statusText.textContent = 'SYSTEM OFFLINE (NO KEY)';
            statusText.className = 'text-rose-400 font-mono tracking-tight cursor-pointer hover:underline';
            statusText.onclick = () => { if (typeof openSettings === 'function') openSettings(); };
        }
    }

    // 2. Control Chat Tab Overlay (LLM Key)
    const llmOverlay = document.getElementById('no-llm-key-warning');
    if (window.DEBUG_MODE) console.log('[App] llmOverlay element:', !!llmOverlay, 'hasLlmKey:', hasLlmKey);
    if (llmOverlay) {
        if (hasLlmKey) {
            llmOverlay.classList.add('hidden');
            if (window.DEBUG_MODE) console.log('[App] Hiding LLM overlay (has key)');
        } else {
            llmOverlay.classList.remove('hidden');
            if (window.DEBUG_MODE) console.log('[App] Showing LLM overlay (no key)');
        }
    }

    // 3. Control Assets Tab Overlay (OKX Key)
    const okxOverlay = document.getElementById('no-okx-key-overlay');
    if (okxOverlay) {
        if (hasOkxKey) {
            okxOverlay.classList.add('hidden');
        } else {
            okxOverlay.classList.remove('hidden');
        }
    }

    // 4. Update Chat Input State
    updateChatUIState(hasLlmKey);
}

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
            ? (window.I18n?.t('chat.placeholderReady') || 'Send a command to AI Agent...') 
            : (window.I18n?.t('chat.systemLocked') || 'System Locked - Please Configure API Key');
        userInput.classList.toggle('opacity-50', !hasApiKey);
        userInput.classList.toggle('cursor-not-allowed', !hasApiKey);
    }

    if (sendBtn) {
        sendBtn.disabled = !hasApiKey;
        sendBtn.classList.toggle('opacity-50', !hasApiKey);
        sendBtn.classList.toggle('cursor-not-allowed', !hasApiKey);
    }
}

// 暴露到全局供 index.html 控制初始化順序
window.initializeUIStatus = function () {
    if (window.DEBUG_MODE) console.log('[App] initializeUIStatus called');
    if (window.DEBUG_MODE) console.log('[App] APIKeyManager exists:', !!window.APIKeyManager);
    // Note: getCurrentKey() is async, so we can't check it synchronously in debug log

    // 只在初始化時檢查一次
    checkApiKeyStatus();
    // 移除定期輪詢 - API Key 設定後狀態就確定了
    // 狀態變更時應該主動調用 checkApiKeyStatus() 而非輪詢
};

// 頁面加載時不再自動執行，由 index.html 統一調度
// window.addEventListener('DOMContentLoaded', () => { ... });


// --- Global Filter Logic Variables ---
window.allMarketSymbols = [];
window.globalSelectedSymbols = []; // Unified selection
window.selectedNewsSources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']; // ✅ 固定使用所有新聞來源
window.currentFilterExchange = 'okx';

// API Key Validity Cache
let validKeys = {
    openai: false,
    google_gemini: false,
    openrouter: false
};

function updateProviderOptions() {
    // Simple implementation to visually indicate valid keys in the dropdown
    const select = document.getElementById('llm-provider-select');
    if (!select) return;

    Array.from(select.options).forEach(opt => {
        const provider = opt.value;
        if (validKeys[provider]) {
            if (!opt.text.includes('✅')) {
                opt.text = `${opt.text} ✅`;
            }
        }
    });
}

// Watchlist & Chart Variables
let currentUserId = 'guest';

// Pulse Data Cache (使用 window 物件避免重複聲明)
if (typeof window.currentPulseData === 'undefined') {
    window.currentPulseData = {};
}

// Trade Proposal

// Analysis Abort Controller
window.currentAnalysisController = null;

// Pi Network Initialization
const Pi = window.Pi;

// ========================================
// Tab Switching (called from HTML after basic UI update)
// ========================================
// Note: The main switchTab() function is now defined inline in index.html
// This function handles additional logic like intervals and API calls

function onTabSwitch(tab) {
    // Abort pending analysis if leaving chat tab
    if (tab !== 'chat' && window.currentAnalysisController) {
        window.currentAnalysisController.abort();
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
    if (window.pulseInterval) {
        clearInterval(window.pulseInterval);
        window.pulseInterval = null;
    }
    if (window.assetsInterval) {
        clearInterval(window.assetsInterval);
        window.assetsInterval = null;
    }

    // Set up new intervals based on tab
    if (tab === 'crypto' || tab === 'market') {
        marketRefreshInterval = setInterval(() => {
            if (typeof refreshScreener === 'function') refreshScreener(false);
        }, 60000);
    }

    if (tab === 'crypto' || tab === 'pulse') {
        window.pulseInterval = setInterval(() => {
            if (typeof checkMarketPulse === 'function') checkMarketPulse(false);
        }, 30000);
    }

    if (tab === 'assets') {
        // ✅ 效能優化：assets 刷新間隔從 10s 延長為 30s，減少不必要的 API 請求
        window.assetsInterval = setInterval(() => {
            if (typeof refreshAssets === 'function') refreshAssets();
        }, 30000);
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
window.cleanupIntervals = function() {
    // Clear market refresh interval
    if (marketRefreshInterval) {
        clearInterval(marketRefreshInterval);
        marketRefreshInterval = null;
    }
    // Clear pulse interval
    if (window.pulseInterval) {
        clearInterval(window.pulseInterval);
        window.pulseInterval = null;
    }
    // Clear assets interval
    if (window.assetsInterval) {
        clearInterval(window.assetsInterval);
        window.assetsInterval = null;
    }
};

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    window.cleanupIntervals();
});

// ========================================
// Utility Functions
// ========================================
function updateUserId(uid) { currentUserId = uid || 'guest'; }

/**
 * 顯示全局錯誤提示 (Unified Error Display)
 * @param {string} title - 錯誤標題
 * @param {string} message - 錯誤詳情
 * @param {boolean} isQuotaError - 是否為配額/額度不足錯誤
 */
window.showError = function (title, message, isQuotaError = false) {
    // Check if modal exists, if not create it
    let modal = document.getElementById('global-error-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'global-error-modal';
        modal.className = 'fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm hidden';
        modal.innerHTML = `
            <div class="bg-surface border border-red-500/30 rounded-3xl w-[90%] max-w-md p-6 shadow-2xl transform transition-all scale-95 opacity-0" id="global-error-content">
                <div class="flex items-center gap-3 mb-4 text-red-400">
                    <i data-lucide="alert-triangle" class="w-8 h-8"></i>
                    <h3 class="text-xl font-bold font-serif" id="global-error-title">Error</h3>
                </div>
                <div class="text-secondary/90 text-sm leading-relaxed mb-6" id="global-error-message"></div>
                
                <div id="quota-error-actions" class="hidden mb-4 bg-red-500/10 p-3 rounded-xl border border-red-500/20">
                    <p class="text-xs text-red-300 mb-2">💡 建議解決方案:</p>
                    <ul class="text-xs text-textMuted list-disc pl-4 space-y-1">
                        <li>檢查 API Key 是否正確設定</li>
                        <li>確認您的 Google/OpenAI 帳戶餘額是否充足</li>
                        <li>嘗試切換其他 AI 提供商 (如 OpenRouter)</li>
                    </ul>
                    <button onclick="openSettings(); closeErrorModal()" class="mt-3 w-full py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg text-sm font-medium transition border border-red-500/30">
                        前往設定檢查金鑰
                    </button>
                </div>

                <div class="flex justify-end">
                    <button onclick="closeErrorModal()" class="px-5 py-2 bg-surfaceHighlight hover:bg-white/10 text-white rounded-xl transition border border-white/10">
                        關閉
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
    msgEl.innerText = message || "發生未知錯誤";

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
};

window.closeErrorModal = function () {
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

// ... existing code ...

async function openSettings() {
    // Switch to settings tab
    if (typeof switchTab === 'function') {
        switchTab('settings');
    }

    // Ensure component is injected
    if (window.Components && typeof window.Components.inject === 'function') {
        await window.Components.inject('settings');
    }

    // Load current config — fetch both endpoints in parallel
    try {
        const [configRes, modelConfigRes] = await Promise.all([
            fetch('/api/config'),
            fetch('/api/model-config')
        ]);
        const data = await configRes.json();
        const modelConfigData = await modelConfigRes.json();
        const settings = data.current_settings || {};
        const preloadedModelConfig = modelConfigData.model_config || null;

        // Update Valid Keys state based on backend existence
        const setStatus = (provider, hasKey) => {
            validKeys[provider] = hasKey;
        };

        setStatus('openai', settings.has_openai_key);
        setStatus('google_gemini', settings.has_google_key);
        setStatus('openrouter', settings.has_openrouter_key);

        // Update Provider Select Options based on validity
        updateProviderOptions();

        if (settings.primary_model_provider) {
            const providerSelect = document.getElementById('llm-provider-select');
            if (providerSelect) {
                providerSelect.value = settings.primary_model_provider;
                // 觸發更新，傳入預載的 modelConfig 避免重複 fetch
                if (typeof updateLLMKeyInput === 'function') updateLLMKeyInput();
                if (typeof window.updateAvailableModels === 'function') await window.updateAvailableModels(preloadedModelConfig);
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

        // Load premium membership status (no artificial delay needed)
        if (typeof loadPremiumStatus === 'function') {
            loadPremiumStatus();
        }

    } catch (e) {
        console.error("Failed to load settings", e);
    }
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

// ========================================
// LLM Model Selection
// ========================================

/**
 * 更新可用模型列表
 * @param {Object|null} preloadedConfig - 預載的模型配置（可選）
 */
window.updateAvailableModels = async function(preloadedConfig = null) {
    const providerSelect = document.getElementById('llm-provider-select');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (!providerSelect || !modelSelect) {
        console.warn('[updateAvailableModels] Required elements not found');
        return;
    }

    const provider = providerSelect.value;
    console.log('[updateAvailableModels] Provider:', provider);

    // 獲取模型配置
    let modelConfig = preloadedConfig;

    if (!modelConfig) {
        try {
            const response = await fetch('/api/model-config');
            if (response.ok) {
                const data = await response.json();
                modelConfig = data.model_config;
            }
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

    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.display || model.value;
        modelSelect.appendChild(option);
    });

    // 設置當前選擇的模型（優先使用已保存的，其次使用 default_model，最後使用第一個）
    const savedModel = window.APIKeyManager?.getModelForProvider?.(provider);
    if (savedModel && models.some(m => m.value === savedModel)) {
        modelSelect.value = savedModel;
    } else if (modelConfig?.[provider]?.default_model) {
        modelSelect.value = modelConfig[provider].default_model;
    } else if (models.length > 0) {
        modelSelect.value = models[0].value;
    }

    console.log('[updateAvailableModels] Loaded', models.length, 'models for', provider);
}

// Allow external modules (like llmSettings.js) to update key validity
window.setKeyValidity = function (provider, isValid) {
    if (validKeys.hasOwnProperty(provider)) {
        validKeys[provider] = isValid;
        updateProviderOptions();
    }
};

// ========================================
// Draggable Navigation Logic (Optimized)
// ========================================
let navCollapsed = false;

function toggleNavCollapse() {
    const navButtons = document.getElementById('nav-buttons');
    const toggleIcon = document.getElementById('nav-toggle-icon');
    const nav = document.getElementById('draggable-nav');

    if (!navButtons || !toggleIcon) return;

    navCollapsed = !navCollapsed;

    if (navCollapsed) {
        // 收縮
        navButtons.style.width = '0';
        navButtons.style.opacity = '0';
        navButtons.style.pointerEvents = 'none';
        toggleIcon.style.transform = 'rotate(180deg)';
        nav.style.borderRadius = '9999px';
    } else {
        // 展開
        navButtons.style.width = '';
        navButtons.style.opacity = '1';
        navButtons.style.pointerEvents = 'auto';
        toggleIcon.style.transform = 'rotate(0deg)';
        nav.style.borderRadius = '9999px';
    }

    // 保存狀態
    localStorage.setItem('navCollapsed', navCollapsed);
}

// 初始化收縮狀態
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('navCollapsed');
    if (saved === 'true') {
        navCollapsed = false; // 先設為 false，讓 toggle 變成 true
        toggleNavCollapse();
    }
});

// Draggable Logic (Optimized with requestAnimationFrame)
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('global-nav-container');
    const nav = document.getElementById('draggable-nav');
    if (!container || !nav) return;

    // State Variables
    let isDragging = false;
    let currentX = 0, currentY = 0; // Current Translation
    let initialX, initialY; // Touch/Mouse Start Position
    let xOffset = 0, yOffset = 0; // Saved Offset
    let animationFrameId = null;

    // Load saved position (with bounds clamp to avoid loading an off-screen position)
    const savedPos = localStorage.getItem('navPosition');
    if (savedPos) {
        try {
            const { x, y } = JSON.parse(savedPos);
            const viewW = window.innerWidth;
            const viewH = window.innerHeight;
            const navHeight = nav.getBoundingClientRect().height || 65;
            // Clamp on load: allow upward drag only within bottom 55% of screen
            const maxUp = -(viewH * 0.55 - navHeight);
            const maxDown = 80;
            xOffset = Math.max(-(viewW / 2) + 80, Math.min((viewW / 2) - 80, x));
            yOffset = Math.max(maxUp, Math.min(maxDown, y));
            setTranslate(xOffset, yOffset, container);
        } catch (e) {
            localStorage.removeItem('navPosition');
        }
    }

    const dragHandle = nav.querySelector('.drag-handle');
    if (!dragHandle) return;

    // Mobile Optimization: Prevent default touch actions (scrolling) on handle
    dragHandle.style.touchAction = 'none';

    // Event Listeners
    dragHandle.addEventListener('mousedown', dragStart);
    dragHandle.addEventListener('touchstart', dragStart, { passive: false });

    document.addEventListener('mouseup', dragEnd);
    document.addEventListener('touchend', dragEnd);

    document.addEventListener('mousemove', drag);
    document.addEventListener('touchmove', drag, { passive: false });

    function dragStart(e) {
        if (e.target.closest('button:not(.drag-handle)')) return;

        if (e.type === 'touchstart') {
            initialX = e.touches[0].clientX - xOffset;
            initialY = e.touches[0].clientY - yOffset;
        } else {
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;
        }

        isDragging = true;

        // Performance: specific optimization classes
        container.style.willChange = 'transform';
        container.style.transition = 'none'; // Disable transition on container if any
        nav.style.transition = 'none'; // Disable hover transitions etc on nav

        dragHandle.style.cursor = 'grabbing';
    }

    function dragEnd(e) {
        if (!isDragging) return;

        initialX = currentX;
        initialY = currentY;

        isDragging = false;
        cancelAnimationFrame(animationFrameId);

        // Snap to bounds logic
        const navRect = nav.getBoundingClientRect();
        const navWidth = navRect.width;
        const navHeight = navRect.height;
        const viewW = window.innerWidth;
        const viewH = window.innerHeight;
        const padding = 10;

        // Boundaries (Note: container is strictly centered horizontally by default via CSS)
        // offsetX represents deviation from that center.
        const minX = -(viewW / 2) + (navWidth / 2) + padding;
        const maxX = (viewW / 2) - (navWidth / 2) - padding;

        // Vertical boundaries
        // Initial bottom is 24px (approx 96px from bottom).
        // initialTop = viewH - 96 - navHeight;
        // Let's rely on computed rect for safer bounds
        // Reset transition for smooth snap
        container.style.transition = 'transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)';

        // Clamp offsets
        // Recalculate based on current state to ensure robustness
        // Since we are moving with transform translate, currentX is the translation value.

        let targetX = currentX;
        let targetY = currentY;

        // Clamp X
        if (targetX < minX) targetX = minX;
        if (targetX > maxX) targetX = maxX;

        // Clamp Y (Simplify: just keep it on screen)
        // Top boundary (negative Y moves up)
        // Bottom is fixed at 24px.
        // Transforming Y negative moves UP.
        // Max UP = viewH - margin
        // Max DOWN = margin (since it starts at bottom)

        // Let's use simple logic: keep center on screen
        const safeMarginY = viewH / 2 - navHeight; // Rough estimate
        // Actually, just clamp to keep rect visible
        // We know initial position (0,0) is bottom-center.

        // Constrain Y to be reasonable (e.g., +/- screen height)
        // Ideally we would calculate exact pixels but rough clamp works for "keep on screen"
        const maxUp = -(viewH - 150);
        const maxDown = 80;

        if (targetY < maxUp) targetY = maxUp;
        if (targetY > maxDown) targetY = maxDown;

        // Commit final position
        xOffset = targetX;
        yOffset = targetY; // Actually we should use targetY but let's trust the clamp

        setTranslate(targetX, targetY, container);

        // Cleanup
        setTimeout(() => {
            container.style.willChange = 'auto';
            container.style.transition = '';
            nav.style.transition = 'all 0.3s ease'; // Restore nav transition
        }, 300);

        dragHandle.style.cursor = 'grab';

        // Save
        localStorage.setItem('navPosition', JSON.stringify({ x: targetX, y: targetY }));
    }

    function drag(e) {
        if (!isDragging) return;

        e.preventDefault(); // Important for touch

        let clientX, clientY;
        if (e.type === 'touchmove') {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }

        currentX = clientX - initialX;
        currentY = clientY - initialY;

        // Debounce via rAF
        if (!animationFrameId) {
            animationFrameId = requestAnimationFrame(() => {
                setTranslate(currentX, currentY, container);
                animationFrameId = null;
            });
        }
    }

    function setTranslate(xPos, yPos, el) {
        // Use stacked transforms for better compatibility than calc() inside translate3d
        // translateX(-50%) centers it, then translate3d moves it by offset
        el.style.transform = `translateX(-50%) translate3d(${xPos}px, ${yPos}px, 0)`;
    }

    // Fix resize reset
    window.addEventListener('resize', () => {
        if (!isDragging) {
            // Reset to center x if window resizes drastically? 
            // Or just clamp. For now, keep simple.
        }
    });
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

        primary_model_provider: document.getElementById('llm-provider-select') ? document.getElementById('llm-provider-select').value : '',
        primary_model_name: (function () {
            const select = document.getElementById('llm-model-select');
            const input = document.getElementById('llm-model-input');
            const provider = document.getElementById('llm-provider-select') ? document.getElementById('llm-provider-select').value : '';
            if (provider === 'openrouter') return input ? input.value : '';
            return select ? select.value : '';
        })(),
    };

    let success = false;

    try {
        const res = await fetch('/api/settings/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            success = true;
            if (payload.primary_model_provider) {
                window.APIKeyManager.setSelectedProvider(payload.primary_model_provider);
            }

            // 2. 儲存成功：維持灰色狀態半秒後直接關閉
            setTimeout(() => {
                closeSettings();
                checkApiKeyStatus();

                // 3. 在畫面切換後才恢復按鈕狀態
                setTimeout(() => {
                    btn.disabled = false;
                    btn.classList.remove('opacity-50', 'cursor-not-allowed');
                }, 500);
            }, 500);

        } else {
            showToast('保存設定失敗: ' + (result.detail || '未知錯誤'), 'error');
        }
    } catch (e) {
        showToast('保存設定時發生錯誤: ' + e, 'error');
    }

    // 只有在失敗時才立即恢復按鈕
    if (!success) {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}
