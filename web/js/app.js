// ========================================
// app.js - 核心應用邏輯與全局變量
// ========================================

// Initialize Lucide icons
lucide.createIcons();
const md = window.markdownit({ html: true, linkify: true });
let isAnalyzing = false;
let marketRefreshInterval = null;

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

    // 2. API Key 未設置警告 (Old element, kept for compatibility if exists)
    const apiKeyWarning = document.getElementById('api-key-warning');
    if (apiKeyWarning) {
        apiKeyWarning.classList.toggle('hidden', hasApiKey);
    }

    // 3. 輸入框和發送按鈕
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

// Committee Variables
let tempBullModels = [];
let tempBearModels = [];

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
             const providerSelect = document.getElementById('set-model-provider');
             if (providerSelect) providerSelect.value = settings.primary_model_provider;
        }
        if (settings.primary_model_name) {
            const nameInput = document.getElementById('set-model-name');
            if (nameInput) nameInput.value = settings.primary_model_name;
        }

        // Initialize committee lists
        tempBullModels = settings.bull_committee_models || [];
        tempBearModels = settings.bear_committee_models || [];
        
        toggleCommitteePanel(); // Show/Hide based on checkbox
        renderCommitteeLists();

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

function toggleCommitteePanel() {
    const isEnabled = document.getElementById('set-committee-mode').checked;
    const panel = document.getElementById('committee-management-panel');
    const singleConfig = document.getElementById('single-model-config');
    
    if (isEnabled) {
        panel.classList.remove('hidden');
        // Optional: Maybe dim single config or label it differently
    } else {
        panel.classList.add('hidden');
    }
}

function renderCommitteeLists() {
    const renderList = (models, elementId, type) => {
        const ul = document.getElementById(elementId);
        ul.innerHTML = '';
        if (models.length === 0) {
            ul.innerHTML = '<li class="text-slate-500 italic">尚無成員，請添加</li>';
            return;
        }
        models.forEach((m, idx) => {
            const li = document.createElement('li');
            li.className = 'flex justify-between items-center bg-slate-800 rounded px-2 py-1 border border-slate-700';
            li.innerHTML = `
                <span class="truncate" title="${m.model} (${m.provider})">
                    <span class="text-blue-400 font-bold">[${m.provider === 'google_gemini' ? 'Gemini' : (m.provider === 'openai' ? 'OpenAI' : 'OpenRouter')}]</span> 
                    ${m.model}
                </span>
                <button onclick="removeCommitteeModel('${type}', ${idx})" class="text-slate-500 hover:text-red-400">
                    <i data-lucide="trash-2" class="w-3 h-3"></i>
                </button>
            `;
            ul.appendChild(li);
        });
    };

    renderList(tempBullModels, 'bull-committee-list', 'bull');
    renderList(tempBearModels, 'bear-committee-list', 'bear');
    lucide.createIcons();
}

function addCurrentModelToCommittee(targetType) {
    const provider = document.getElementById('set-model-provider').value;
    const model = document.getElementById('set-model-name').value;

    if (!model) {
        alert("請先輸入或選擇模型名稱");
        return;
    }

    const newModel = { provider, model };

    const addTo = (list) => {
        const exists = list.some(m => m.provider === provider && m.model === model);
        if (!exists) list.push(newModel);
    };

    if (targetType === 'bull') {
        addTo(tempBullModels);
    } else if (targetType === 'bear') {
        addTo(tempBearModels);
    } else {
        // Fallback: add to both if called without type (backward compatibility)
        addTo(tempBullModels);
        addTo(tempBearModels);
    }

    renderCommitteeLists();
}

// Expose to global scope for onclick events
window.removeCommitteeModel = function(type, index) {
    if (type === 'bull') {
        tempBullModels.splice(index, 1);
    } else {
        tempBearModels.splice(index, 1);
    }
    renderCommitteeLists();
};
window.addCurrentModelToCommittee = addCurrentModelToCommittee;
window.toggleCommitteePanel = toggleCommitteePanel;

// Allow external modules (like llmSettings.js) to update key validity
window.setKeyValidity = function(provider, isValid) {
    if (validKeys.hasOwnProperty(provider)) {
        validKeys[provider] = isValid;
        updateProviderOptions();
    }
};

async function saveSettings() {
    const btn = document.getElementById('btn-save-settings');
    if (!btn) {
        console.error('Save settings button not found');
        return;
    }
    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block"></div> Saving...';
    btn.disabled = true;

    // ✅ Handle OKX Key (BYOK) - Only if modal inputs are populated (which are separate now)
    // Actually, OKX configuration is now handled via the modal directly, so we don't need to do it here
    // unless we want to support saving from the modal's inputs if they were open.
    // For now, assume OKX is handled by the modal's own save button.

    // ⚠️ Prepare Backend Payload
    const payload = {
        // We don't send API keys here anymore as we encourage BYOK or .env
        // But if we wanted to support server-side keys, we'd need inputs for them.
        // For now, just send nulls to indicate "don't change" or handle logic in backend
        openai_api_key: null,
        google_api_key: null,
        openrouter_api_key: null,

        enable_committee: document.getElementById('set-committee-mode') ? document.getElementById('set-committee-mode').checked : false,
        primary_model_provider: document.getElementById('llm-provider-select') ? document.getElementById('llm-provider-select').value : '',
        primary_model_name: document.getElementById('set-model-name') ? document.getElementById('set-model-name').value : '',

        bull_committee_models: tempBullModels,
        bear_committee_models: tempBearModels
    };

    try {
        const res = await fetch('/api/settings/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            // Update local provider selection
            if (payload.primary_model_provider) {
                window.APIKeyManager.setSelectedProvider(payload.primary_model_provider);
            }

            alert('✅ Settings saved successfully!\nCommittee configuration has been updated.');
            closeSettings();
            
            // Force UI update
            checkApiKeyStatus();
        } else {
            alert('Failed to save settings: ' + (result.detail || 'Unknown error'));
        }
    } catch (e) {
        alert('Error saving settings: ' + e);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}
