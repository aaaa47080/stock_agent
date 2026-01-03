// ========================================
// llmSettings.js - LLM API Key 設定功能
// ========================================

/**
 * 更新 LLM Key 輸入框的內容（根據選擇的 provider）
 */
function updateLLMKeyInput() {
    const provider = document.getElementById('llm-provider-select').value;
    const input = document.getElementById('llm-api-key-input');
    const status = document.getElementById('llm-key-status');

    // 讀取該 provider 的 key（如果有的話）
    const existingKey = window.APIKeyManager.getKey(provider);

    if (existingKey) {
        input.value = existingKey;
        input.placeholder = '已設置 API Key';
    } else {
        input.value = '';
        input.placeholder = provider === 'openai' ? 'sk-...' :
                           provider === 'google_gemini' ? 'AIza...' :
                           'sk-or-...';
    }

    // 隱藏狀態訊息
    status.classList.add('hidden');

    // 更新圖標
    lucide.createIcons();
}

/**
 * 切換 API Key 顯示/隱藏
 */
function toggleLLMKeyVisibility() {
    const input = document.getElementById('llm-api-key-input');
    const icon = document.getElementById('llm-key-eye-icon');

    if (input.type === 'password') {
        input.type = 'text';
        icon.setAttribute('data-lucide', 'eye-off');
    } else {
        input.type = 'password';
        icon.setAttribute('data-lucide', 'eye');
    }

    lucide.createIcons();
}

/**
 * 保存 LLM API Key
 */
function saveLLMKey() {
    const provider = document.getElementById('llm-provider-select').value;
    const key = document.getElementById('llm-api-key-input').value.trim();
    const status = document.getElementById('llm-key-status');

    // 格式驗證
    const validation = window.APIKeyManager.validateKeyFormat(provider, key);

    if (!validation.valid) {
        showLLMKeyStatus('error', validation.message);
        return;
    }

    // 保存到 localStorage
    window.APIKeyManager.setKey(provider, key);
    window.APIKeyManager.setSelectedProvider(provider);

    showLLMKeyStatus('success', `✅ ${getProviderName(provider)} API Key 已保存！`);

    // 更新狀態指示器
    if (typeof checkApiKeyStatus === 'function') {
        checkApiKeyStatus();
    }
}

/**
 * 測試 LLM API Key
 */
async function testLLMKey() {
    const provider = document.getElementById('llm-provider-select').value;
    const key = document.getElementById('llm-api-key-input').value.trim();
    const status = document.getElementById('llm-key-status');

    if (!key) {
        showLLMKeyStatus('error', '請先輸入 API Key');
        return;
    }

    // 格式驗證
    const validation = window.APIKeyManager.validateKeyFormat(provider, key);
    if (!validation.valid) {
        showLLMKeyStatus('error', validation.message);
        return;
    }

    showLLMKeyStatus('loading', '🔄 正在測試連接...');

    try {
        const response = await fetch('/api/settings/validate-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: provider,
                api_key: key
            })
        });

        const result = await response.json();

        if (result.valid) {
            showLLMKeyStatus('success', `✅ ${result.message}`);
            // 自動保存
            window.APIKeyManager.setKey(provider, key);
            window.APIKeyManager.setSelectedProvider(provider);

            // 更新狀態指示器
            if (typeof checkApiKeyStatus === 'function') {
                checkApiKeyStatus();
            }
        } else {
            showLLMKeyStatus('error', `❌ ${result.message}`);
        }
    } catch (error) {
        console.error('Failed to test API key:', error);
        showLLMKeyStatus('error', '❌ 測試失敗，請檢查網絡連接');
    }
}

/**
 * 顯示狀態訊息
 * @param {string} type - 'success', 'error', 'loading'
 * @param {string} message
 */
function showLLMKeyStatus(type, message) {
    const status = document.getElementById('llm-key-status');
    const textEl = status.querySelector('p');

    status.classList.remove('hidden', 'bg-green-900/20', 'bg-red-900/20', 'bg-blue-900/20', 'border-green-500/30', 'border-red-500/30', 'border-blue-500/30');

    if (type === 'success') {
        status.classList.add('bg-green-900/20', 'border', 'border-green-500/30');
        textEl.className = 'text-sm text-green-400';
    } else if (type === 'error') {
        status.classList.add('bg-red-900/20', 'border', 'border-red-500/30');
        textEl.className = 'text-sm text-red-400';
    } else if (type === 'loading') {
        status.classList.add('bg-blue-900/20', 'border', 'border-blue-500/30');
        textEl.className = 'text-sm text-blue-400';
    }

    textEl.textContent = message;
}

/**
 * 獲取 Provider 的中文名稱
 */
function getProviderName(provider) {
    const names = {
        'openai': 'OpenAI',
        'google_gemini': 'Google Gemini',
        'openrouter': 'OpenRouter'
    };
    return names[provider] || provider;
}

/**
 * 頁面加載時初始化
 */
window.addEventListener('DOMContentLoaded', () => {
    // 初始化時載入已保存的 key
    const currentKey = window.APIKeyManager?.getCurrentKey();
    if (currentKey) {
        const select = document.getElementById('llm-provider-select');
        if (select) {
            select.value = currentKey.provider;
            updateLLMKeyInput();
        }
    }
});
