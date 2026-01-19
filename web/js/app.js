// ========================================
// app.js - 核心應用邏輯與全局變量
// ========================================

// Initialize Lucide icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}

// markdown-it 可能不存在於所有頁面
const md = window.markdownit ? window.markdownit({ html: true, linkify: true }) : null;
let isAnalyzing = false;
let marketRefreshInterval = null;

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
 */
function handleBackToApp(e) {
    if (e) e.preventDefault();
    
    // 添加淡出效果
    document.body.style.opacity = '0';
    document.body.style.transform = 'scale(0.99)';
    document.body.style.transition = 'all 0.3s ease-in-out';
    
    setTimeout(() => {
        window.location.href = '/static/index.html';
    }, 250);
}

// 暴露到全局
window.handleBackToApp = handleBackToApp;

/**
 * 顯示確認對話框 (替代 confirm)
 */
function showConfirm(options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const content = modal ? modal.querySelector('div') : null;
        
        // ... (中間邏輯保持不變)

        if (content) {
            content.classList.remove('modal-content-active');
            void content.offsetWidth; // 強制重繪
            content.classList.add('modal-content-active');
        }

        modal.classList.remove('hidden');
        // ...
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
function checkApiKeyStatus() {
    const indicator = document.getElementById('api-status-indicator');
    const statusText = document.getElementById('api-status-text');
    const statusDot = indicator ? indicator.querySelector('span') : null;

    // Check LLM Key
    const currentKey = window.APIKeyManager?.getCurrentKey();
    const hasLlmKey = !!currentKey;

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
    if (llmOverlay) {
        if (hasLlmKey) {
            llmOverlay.classList.add('hidden');
        } else {
            llmOverlay.classList.remove('hidden');
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
function updateChatUIState(hasApiKey) {
    if (hasApiKey === undefined) {
         hasApiKey = !!window.APIKeyManager?.getCurrentKey();
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
        userInput.placeholder = hasApiKey ? 'Send a command to AI Agent...' : 'System Locked - Please Configure API Key';
        userInput.classList.toggle('opacity-50', !hasApiKey);
        userInput.classList.toggle('cursor-not-allowed', !hasApiKey);
    }

    if (sendBtn) {
        sendBtn.disabled = !hasApiKey;
        sendBtn.classList.toggle('opacity-50', !hasApiKey);
        sendBtn.classList.toggle('cursor-not-allowed', !hasApiKey);
    }
}

// 頁面加載時檢查 API key 狀態
window.addEventListener('DOMContentLoaded', () => {
    checkApiKeyStatus();
    // 立即觸發數據預加載，讓用戶切換分頁時「進去就有東西看」
    refreshScreener(false);
    // 每10秒檢查一次 API 狀態
    setInterval(checkApiKeyStatus, 10000);
});


// --- Global Filter Logic Variables ---
window.allMarketSymbols = [];
window.globalSelectedSymbols = []; // Unified selection
window.selectedNewsSources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']; // ✅ 固定使用所有新聞來源
window.currentFilterExchange = 'okx';
let isFirstLoad = true;

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

// Pulse Data Cache
let currentPulseData = {};

// Trade Proposal
let currentProposal = null;

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
    if (tab === 'market') {
        marketRefreshInterval = setInterval(() => {
            refreshScreener(false);
        }, 60000);
    }

    if (tab === 'pulse') {
        window.pulseInterval = setInterval(() => {
            checkMarketPulse(false);
        }, 30000);
    }

    if (tab === 'assets') {
        window.assetsInterval = setInterval(refreshAssets, 10000);
    }
}

// Make it globally accessible
window.onTabSwitch = onTabSwitch;

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
window.showError = function(title, message, isQuotaError = false) {
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

window.closeErrorModal = function() {
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

    // Load current config
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        const settings = data.current_settings || {};

        // Update Valid Keys state based on backend existence
        const setStatus = (provider, hasKey) => {
            // Note: We don't have visual indicators for "Server has key" in the new simplified UI yet,
            // but we maintain the validKeys state for logic.
            validKeys[provider] = hasKey;
        };

        setStatus('openai', settings.has_openai_key);
        setStatus('google_gemini', settings.has_google_key);
        setStatus('openrouter', settings.has_openrouter_key);
        
        // Update Provider Select Options based on validity
        updateProviderOptions();

        const committeeMode = document.getElementById('set-committee-mode');
        if (committeeMode) committeeMode.checked = settings.enable_committee;
        
        if (settings.primary_model_provider) {
             const providerSelect = document.getElementById('llm-provider-select');
             if (providerSelect) {
                 providerSelect.value = settings.primary_model_provider;
                 // 觸發更新
                 if (typeof updateLLMKeyInput === 'function') updateLLMKeyInput();
                 if (typeof updateAvailableModels === 'function') await updateAvailableModels();
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

        // Initialize committee lists using CommitteeManager
        if (window.CommitteeManager) {
            window.CommitteeManager.loadConfig({
                bull: settings.bull_committee_models || [],
                bear: settings.bear_committee_models || []
            });
            window.CommitteeManager.togglePanel(settings.enable_committee);
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

// Allow external modules (like llmSettings.js) to update key validity
window.setKeyValidity = function(provider, isValid) {
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

// Draggable Logic
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('global-nav-container');
    const nav = document.getElementById('draggable-nav');
    if (!container || !nav) return;

    let isDragging = false;
    let hasMoved = false;
    let startX, startY;
    let offsetX = 0, offsetY = 0;

    // 從 localStorage 恢復位置
    const savedPos = localStorage.getItem('navPosition');
    if (savedPos) {
        const { x, y } = JSON.parse(savedPos);
        offsetX = x;
        offsetY = y;
        updatePosition();
    }

    const dragHandle = nav.querySelector('.drag-handle');
    if (!dragHandle) return;

    // Mouse events
    dragHandle.addEventListener('mousedown', onStart);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onEnd);

    // Touch events
    dragHandle.addEventListener('touchstart', onStart, { passive: false });
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onEnd);

    function onStart(e) {
        if (e.target.closest('button:not(.drag-handle)')) return;

        isDragging = true;
        hasMoved = false;

        const point = e.touches ? e.touches[0] : e;
        startX = point.clientX - offsetX;
        startY = point.clientY - offsetY;

        nav.style.transition = 'none';
        dragHandle.style.cursor = 'grabbing';
    }

    function onMove(e) {
        if (!isDragging) return;
        e.preventDefault();

        const point = e.touches ? e.touches[0] : e;
        const newX = point.clientX - startX;
        const newY = point.clientY - startY;

        // 檢測是否真的移動了
        if (Math.abs(newX - offsetX) > 3 || Math.abs(newY - offsetY) > 3) {
            hasMoved = true;
        }

        offsetX = newX;
        offsetY = newY;

        updatePosition();
    }

    function onEnd() {
        if (!isDragging) return;
        isDragging = false;

        nav.style.transition = 'all 0.3s ease';
        dragHandle.style.cursor = 'grab';

        // 邊界檢測與吸附
        const navRect = nav.getBoundingClientRect();
        const navWidth = navRect.width;
        const navHeight = navRect.height;
        const viewW = window.innerWidth;
        const viewH = window.innerHeight;
        const padding = 10;

        // 計算導航欄可移動的範圍
        // 初始位置是 left: 50%, transform: translateX(-50%)，所以中心點在屏幕中央
        // offsetX/offsetY 是相對於初始中心位置的偏移

        // 水平邊界：導航欄不能超出屏幕左右
        const minX = -(viewW / 2) + (navWidth / 2) + padding;
        const maxX = (viewW / 2) - (navWidth / 2) - padding;

        // 垂直邊界：導航欄不能超出屏幕上下
        // 初始位置是 bottom: 24 (約 96px)，所以初始 top 約為 viewH - 96 - navHeight
        const initialTop = viewH - 96 - navHeight;
        const minY = -initialTop + padding;
        const maxY = viewH - initialTop - navHeight - padding;

        // 限制在邊界內
        offsetX = Math.max(minX, Math.min(maxX, offsetX));
        offsetY = Math.max(minY, Math.min(maxY, offsetY));

        updatePosition();

        // 保存位置
        localStorage.setItem('navPosition', JSON.stringify({ x: offsetX, y: offsetY }));
    }

    function updatePosition() {
        container.style.transform = `translate(calc(-50% + ${offsetX}px), ${offsetY}px)`;
    }

    // 窗口大小改變時重新檢測邊界
    window.addEventListener('resize', () => {
        if (!isDragging) {
            onEnd();
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
    const committeeConfig = window.CommitteeManager ? window.CommitteeManager.getConfig() : { bull: [], bear: [] };
    
    const payload = {
        openai_api_key: null,
        google_api_key: null,
        openrouter_api_key: null,

        enable_committee: document.getElementById('set-committee-mode') ? document.getElementById('set-committee-mode').checked : false,
        primary_model_provider: document.getElementById('llm-provider-select') ? document.getElementById('llm-provider-select').value : '',
        primary_model_name: document.getElementById('set-model-name') ? document.getElementById('set-model-name').value : '',

        bull_committee_models: committeeConfig.bull,
        bear_committee_models: committeeConfig.bear
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
