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

    if (!statusText || !statusDot) return;

    // 檢查用戶是否有設置 API key（從 localStorage）
    const currentKey = window.APIKeyManager?.getCurrentKey();

    if (currentKey) {
        // 用戶已設置 API key
        const providerName = currentKey.provider === 'openai' ? 'OpenAI' :
                            currentKey.provider === 'google_gemini' ? 'Gemini' :
                            currentKey.provider === 'openrouter' ? 'OpenRouter' : currentKey.provider;

        statusDot.className = 'w-2 h-2 bg-green-500 rounded-full animate-pulse';
        statusText.textContent = `AI Ready (${providerName})`;
        statusText.className = 'text-green-400';
        statusText.onclick = null; // 移除點擊事件
    } else {
        // 用戶未設置 API key
        statusDot.className = 'w-2 h-2 bg-red-500 rounded-full animate-pulse';
        statusText.textContent = '請設置 API Key';
        statusText.className = 'text-red-400 cursor-pointer hover:underline';

        // 點擊狀態文字可以開啟設定
        statusText.onclick = () => {
            if (typeof openSettings === 'function') {
                openSettings();
            }
        };
    }

    // ⭐ 同時更新聊天 UI 狀態
    updateChatUIState();
}

// ========================================
// 更新聊天 UI 狀態（根據 API key 是否存在）
// ========================================
function updateChatUIState() {
    const currentKey = window.APIKeyManager?.getCurrentKey();
    const hasApiKey = !!currentKey;

    // 1. 建議按鈕區域
    const suggestionsArea = document.getElementById('suggestions-area');
    if (suggestionsArea) {
        suggestionsArea.classList.toggle('hidden', !hasApiKey);
    }

    // 2. API Key 未設置警告
    const apiKeyWarning = document.getElementById('api-key-warning');
    if (apiKeyWarning) {
        apiKeyWarning.classList.toggle('hidden', hasApiKey);
    }

    // 3. 輸入框和發送按鈕
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    if (userInput) {
        userInput.disabled = !hasApiKey;
        userInput.placeholder = hasApiKey ? '請輸入您的問題...' : '請先設置 API Key 才能使用';
        userInput.classList.toggle('opacity-50', !hasApiKey);
    }

    if (sendBtn) {
        sendBtn.disabled = !hasApiKey;
        sendBtn.classList.toggle('opacity-50', !hasApiKey);
        sendBtn.classList.toggle('cursor-not-allowed', !hasApiKey);
    }

    // 4. 分析選項按鈕
    const optionsBtn = document.querySelector('[onclick="toggleOptions()"]');
    if (optionsBtn) {
        optionsBtn.disabled = !hasApiKey;
        optionsBtn.classList.toggle('opacity-50', !hasApiKey);
        optionsBtn.classList.toggle('cursor-not-allowed', !hasApiKey);
    }

    // 5. 重新渲染 Lucide 圖標
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

// 頁面加載時檢查 API key 狀態
window.addEventListener('DOMContentLoaded', () => {
    checkApiKeyStatus();
    // 每10秒更新一次狀態（檢測用戶是否輸入了 key）
    setInterval(checkApiKeyStatus, 10000);
});


// --- Global Filter Logic Variables ---
let allMarketSymbols = [];
let globalSelectedSymbols = []; // Unified selection
let selectedNewsSources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']; // ✅ 固定使用所有新聞來源（不需要用戶選擇）
let currentFilterExchange = 'okx';
let isFirstLoad = true;

// Watchlist & Chart Variables
let currentUserId = 'guest';
let chart = null;
let candleSeries = null;

// Pulse Data Cache
let currentPulseData = {};

// Trade Proposal
let currentProposal = null;

// Analysis Abort Controller
window.currentAnalysisController = null;

// Pi Network Initialization
const Pi = window.Pi;

// ========================================
// Tab Switching
// ========================================
function switchTab(tab) {
    // 如果是 settings，不隱藏當前頁面，而是打開 Modal
    if (tab === 'settings') {
        openSettings();
        return;
    }

    // 隱藏所有頁籤（移除了 watchlist）
    ['chat', 'market', 'pulse', 'assets'].forEach(t => {
        const el = document.getElementById(t + '-tab');
        if (el) el.classList.add('hidden');
    });

    const targetTab = document.getElementById(tab + '-tab');
    if (targetTab) targetTab.classList.remove('hidden');

    // Update nav icon colors
    document.querySelectorAll('nav button').forEach(btn => btn.classList.replace('text-blue-500', 'text-slate-400'));
    // Highlight active (Optional logic here)
    // TODO: Need a better way to map button to tab since we don't have IDs on buttons in original HTML
    // For now, simple color reset is fine.

    // Abort pending analysis if leaving chat tab
    if (tab !== 'chat' && window.currentAnalysisController) {
        window.currentAnalysisController.abort();
        window.currentAnalysisController = null;
        isAnalyzing = false; // Reset analyzing state
        
        // Reset Chat UI if needed (optional, but good for UX)
        const input = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        if (input && sendBtn) {
            input.disabled = false;
            sendBtn.disabled = false;
            input.classList.remove('opacity-50');
            sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    if (marketRefreshInterval) {
        clearInterval(marketRefreshInterval);
        marketRefreshInterval = null;
    }
    if (window.pulseInterval) {
        clearInterval(window.pulseInterval);
        window.pulseInterval = null;
    }

    if (tab === 'market') {
        refreshScreener(true);
        marketRefreshInterval = setInterval(() => {
            refreshScreener(false);
        }, 1000);
    }

    if (tab === 'pulse') {
        checkMarketPulse(true);
        window.pulseInterval = setInterval(() => {
            checkMarketPulse(false);
        }, 30000);
    }

    if (window.assetsInterval) {
        clearInterval(window.assetsInterval);
        window.assetsInterval = null;
    }

    if (tab === 'watchlist') refreshWatchlist();

    if (tab === 'assets') {
        refreshAssets();
        window.assetsInterval = setInterval(refreshAssets, 10000);
    }

    lucide.createIcons();
}

// ========================================
// Utility Functions
// ========================================
function updateUserId(uid) { currentUserId = uid || 'guest'; }

function quickAsk(text) {
    document.getElementById('user-input').value = text;
    sendMessage();
}

// ========================================
// Pi Network Authentication
// ========================================
if (Pi) {
    Pi.init({ version: "2.0", sandbox: true });
    Pi.authenticate(['username'], (payment) => {}).then(auth => {
        const userEl = document.getElementById('pi-user');
        userEl.innerHTML = `<span class="text-blue-400 font-medium">@${auth.user.username}</span>`;
        userEl.classList.remove('hidden');
        const settingsUserEl = document.getElementById('settings-user');
        if (settingsUserEl) settingsUserEl.innerText = "@" + auth.user.username;
        updateUserId(auth.user.uid || auth.user.username);
    }).catch(err => console.error(err));
}

// ========================================
// Settings Logic
// ========================================

// Local state for committee models and keys
let tempBullModels = [];
let tempBearModels = [];
let validKeys = {
    openai: false,
    google_gemini: false,
    openrouter: false
};

const keyInputMap = {
    openai: 'set-openai-key',
    google_gemini: 'set-google-key',
    openrouter: 'set-openrouter-key'
};

async function verifyKey(provider) {
    const inputId = keyInputMap[provider];
    const key = document.getElementById(inputId).value.trim();
    const statusEl = document.getElementById(`status-${provider}`);
    
    if (!key) {
        // 如果是已保存的狀態（後端有 Key 但前端顯示為空），視為不需要重新驗證
        // 但如果用戶想測試，必須輸入。這裡簡化：如果有 placeholder 暗示已設定，允許後端測試？
        // 安全起見，這裡要求用戶必須輸入 Key 才能進行「主動驗證」
        alert("請輸入 API Key 以進行驗證");
        return;
    }

    statusEl.innerHTML = '<div class="spinner w-3 h-3 border-2 border-slate-500 border-t-blue-500 rounded-full inline-block"></div> 驗證中...';
    
    try {
        const res = await fetch('/api/settings/validate-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: key })
        });
        const result = await res.json();
        
        if (result.valid) {
            statusEl.innerHTML = '<i data-lucide="check-circle" class="w-3 h-3 text-green-500 inline"></i> <span class="text-green-500">有效</span>';
            validKeys[provider] = true;
        } else {
            statusEl.innerHTML = '<i data-lucide="x-circle" class="w-3 h-3 text-red-500 inline"></i> <span class="text-red-500">無效</span>';
            validKeys[provider] = false;
            alert(result.message);
        }
    } catch (e) {
        statusEl.innerHTML = '<span class="text-red-500">錯誤</span>';
        console.error(e);
    }
    
    lucide.createIcons();
    updateProviderOptions();
}

function resetKeyStatus(provider) {
    validKeys[provider] = false;
    const statusEl = document.getElementById(`status-${provider}`);
    statusEl.innerHTML = '<i data-lucide="circle-dashed" class="w-3 h-3 text-slate-500 inline"></i> 未驗證';
    lucide.createIcons();
    updateProviderOptions();
}

function updateProviderOptions() {
    const select = document.getElementById('set-model-provider');
    const options = select.options;
    
    for (let i = 0; i < options.length; i++) {
        const provider = options[i].value;
        if (validKeys[provider]) {
            options[i].disabled = false;
            options[i].text = options[i].text.replace(' (需驗證)', '');
        } else {
            options[i].disabled = true;
            if (!options[i].text.includes('(需驗證)')) {
                options[i].text += ' (需驗證)';
            }
        }
    }
    
    // 如果當前選中的被禁用了，嘗試切換到第一個可用的
    if (select.selectedOptions.length > 0 && select.selectedOptions[0].disabled) {
        for (let i = 0; i < options.length; i++) {
            if (!options[i].disabled) {
                select.selectedIndex = i;
                break;
            }
        }
    }
}

async function openSettings() {
    const modal = document.getElementById('settings-modal');
    if (!modal) return; // Safety check
    modal.classList.remove('hidden');

    // Load current config
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        const settings = data.current_settings || {};

        // Update Valid Keys state based on backend existence
        // 注意：這只是表示「已設定」，嚴格來說應該要驗證，但為了 UX，我們假設已設定的是有效的
        // 用戶如果修改了 Key，會觸發 resetKeyStatus
        
        const setStatus = (provider, hasKey) => {
            const el = document.getElementById(`status-${provider}`);
            if (hasKey) {
                validKeys[provider] = true;
                el.innerHTML = '<i data-lucide="check-circle" class="w-3 h-3 text-green-500 inline"></i> <span class="text-green-500">已設定</span>';
            } else {
                validKeys[provider] = false;
                el.innerHTML = '<i data-lucide="circle-dashed" class="w-3 h-3 text-slate-500 inline"></i> 未設定';
            }
        };

        setStatus('openai', settings.has_openai_key);
        setStatus('google_gemini', settings.has_google_key);
        setStatus('openrouter', settings.has_openrouter_key);
        
        lucide.createIcons();
        updateProviderOptions();

        document.getElementById('set-committee-mode').checked = settings.enable_committee;
        
        if (settings.primary_model_provider) {
             document.getElementById('set-model-provider').value = settings.primary_model_provider;
        }
        if (settings.primary_model_name) {
            document.getElementById('set-model-name').value = settings.primary_model_name;
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
    document.getElementById('settings-modal').classList.add('hidden');

    // ⭐ 關閉設定後立即更新 UI 狀態
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


async function saveSettings() {
    const btn = document.getElementById('btn-save-settings');
    
    // --- 強制驗證邏輯 (Gatekeeper) ---
    // 檢查是否有任何已輸入但未通過驗證的 Key
    const providerNames = {
        openai: 'OpenAI',
        google_gemini: 'Google Gemini',
        openrouter: 'OpenRouter'
    };

    for (const [provider, inputId] of Object.entries(keyInputMap)) {
        const inputVal = document.getElementById(inputId).value.trim();
        // 如果用戶輸入了內容，但狀態是無效/未驗證，則阻止保存
        if (inputVal && !validKeys[provider]) {
            alert(`⛔ 無法保存：\n\n您輸入了 ${providerNames[provider]} API Key 但尚未通過驗證。\n\n請點擊輸入框旁的「驗證」按鈕，確認 Key 有效後再保存。`);
            return; // 中止保存流程
        }
    }

    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner w-4 h-4 border-2 border-white/30 border-t-white rounded-full inline-block"></div> 保存中...';
    btn.disabled = true;

    // ✅ 處理 OKX API Key (BYOK 模式 - 保存到前端)
    const okxKey = document.getElementById('set-okx-key').value.trim();
    const okxSecret = document.getElementById('set-okx-secret').value.trim();
    const okxPass = document.getElementById('set-okx-pass').value.trim();

    if (okxKey || okxSecret || okxPass) {
        // 如果用戶填寫了任何 OKX 欄位，則驗證並保存到前端
        if (!okxKey || !okxSecret || !okxPass) {
            alert('⚠️ OKX API 金鑰必須填寫完整（API Key, Secret Key, Passphrase）');
            btn.innerHTML = originalText;
            btn.disabled = false;
            return;
        }

        // 驗證 OKX Key
        btn.innerHTML = '<div class="spinner w-4 h-4 border-2 border-white/30 border-t-white rounded-full inline-block"></div> 驗證 OKX Key...';
        const okxKeyManager = window.OKXKeyManager;
        const validation = await okxKeyManager.validateCredentials({
            api_key: okxKey,
            secret_key: okxSecret,
            passphrase: okxPass
        });

        if (!validation.valid) {
            alert('❌ OKX API 金鑰驗證失敗: ' + validation.message);
            btn.innerHTML = originalText;
            btn.disabled = false;
            return;
        }

        // 保存到前端
        okxKeyManager.saveCredentials({
            api_key: okxKey,
            secret_key: okxSecret,
            passphrase: okxPass
        });
        console.log('[Settings] OKX API 金鑰已保存到本地瀏覽器（BYOK 模式）');
    }

    // ⚠️ 不再將 OKX Key 發送到後端（安全改進）
    const payload = {
        openai_api_key: document.getElementById('set-openai-key').value || null,
        google_api_key: document.getElementById('set-google-key').value || null,
        openrouter_api_key: document.getElementById('set-openrouter-key').value || null,

        enable_committee: document.getElementById('set-committee-mode').checked,
        primary_model_provider: document.getElementById('set-model-provider').value,
        primary_model_name: document.getElementById('set-model-name').value,

        bull_committee_models: tempBullModels,
        bear_committee_models: tempBearModels
    };

    try {
        btn.innerHTML = '<div class="spinner w-4 h-4 border-2 border-white/30 border-t-white rounded-full inline-block"></div> 保存中...';

        const res = await fetch('/api/settings/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            const message = okxKey ? '✅ 設置已保存！\n\n📌 OKX API 金鑰已保存到本地瀏覽器（BYOK 模式）\n⚠️ 無痕視窗不會保存您的金鑰' : result.message;
            alert(message);
            closeSettings();
            // Clear sensitive inputs
            document.getElementById('set-openai-key').value = '';
            document.getElementById('set-google-key').value = '';
            document.getElementById('set-openrouter-key').value = '';
            document.getElementById('set-okx-key').value = '';
            document.getElementById('set-okx-secret').value = '';
            document.getElementById('set-okx-pass').value = '';
        } else {
            alert('保存失敗: ' + (result.detail || '未知錯誤'));
        }
    } catch (e) {
        alert('保存時發生錯誤: ' + e);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}
