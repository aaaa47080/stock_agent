// ========================================
// llmSettings.js - LLM API Key 設定功能
// ========================================

/**
 * 更新 LLM Key 輸入框的內容（根據選擇的 provider）
 */
function updateLLMKeyInput() {
    const providerSelect = document.getElementById('llm-provider-select');
    const input = document.getElementById('llm-api-key-input');
    const status = document.getElementById('llm-key-status');

    if (!providerSelect || !input) return;

    const provider = providerSelect.value;

    // 讀取該 provider 的 key（如果有的話）
    const existingKey = window.APIKeyManager.getKey(provider);

    if (existingKey) {
        input.value = '';
        input.placeholder = '已設置 API Key (**************)';
    } else {
        input.value = '';
        input.placeholder = provider === 'openai' ? 'sk-...' :
            provider === 'google_gemini' ? 'AIza...' :
                'sk-or-...';
    }

    // 隱藏狀態訊息
    if (status) status.classList.add('hidden');

    // 更新圖標
    lucide.createIcons();
}

/**
 * 從後端獲取模型配置
 */
async function fetchModelConfig() {
    try {
        const response = await fetch('/api/model-config');
        const data = await response.json();
        return data.model_config;
    } catch (error) {
        console.error('Failed to fetch model config from server, using fallback:', error);
        // 返回默認配置作為最終備用
        return {
            "openai": {
                "default_model": "gpt-4o-mini",
                "available_models": [
                    { "value": "gpt-4o", "display": "gpt-4o" },
                    { "value": "gpt-4o-mini", "display": "gpt-4o-mini" },
                    { "value": "gpt-4-turbo", "display": "gpt-4-turbo" }
                ]
            },
            "google_gemini": {
                "default_model": "gemini-3-flash-preview",
                "available_models": [
                    { "value": "gemini-3-flash-preview", "display": "Gemini 3 Flash Preview" }
                ]
            },
            "openrouter": {
                "default_model": "gpt-4o-mini",
                "available_models": []  // OpenRouter 有太多模型，讓用戶自行輸入
            }
        };
    }
}

/**
 * 根據選擇的 provider 更新可用模型列表
 * @param {Object|null} preloadedConfig - 可選的預先載入模型配置，傳入可避免重複 fetch
 */
async function updateAvailableModels(preloadedConfig = null) {
    const providerSelect = document.getElementById('llm-provider-select');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (!providerSelect || !modelSelect || !modelInput) return;

    const provider = providerSelect.value;

    // 根據提供商顯示不同的界面元素
    if (provider === 'openrouter') {
        // OpenRouter - 顯示輸入框
        modelSelect.style.display = 'none';
        modelInput.style.display = 'block';

        // 如果用戶已經保存了該 provider 的模型選擇，恢復它
        const savedModel = window.APIKeyManager.getModelForProvider(provider);
        if (savedModel) {
            modelInput.value = savedModel;
        }
    } else {
        // 其他提供商 - 顯示下拉選擇
        modelSelect.style.display = 'block';
        modelInput.style.display = 'none';

        // 清空當前選項
        modelSelect.innerHTML = '';

        // 使用預先載入的配置或從後端獲取
        const modelConfig = preloadedConfig || await fetchModelConfig();

        // 添加默認選項
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '請選擇模型';
        defaultOption.disabled = true;

        // 只有當沒有選中值時，才默認選中提示
        if (!modelSelect.value) {
            defaultOption.selected = true;
        }

        modelSelect.appendChild(defaultOption);

        // 添加可用模型選項
        const providerConfig = modelConfig[provider];
        if (providerConfig && providerConfig.available_models && providerConfig.available_models.length > 0) {
            providerConfig.available_models.forEach(model => {
                const optionElement = document.createElement('option');
                optionElement.value = model.value;
                optionElement.textContent = model.display;
                modelSelect.appendChild(optionElement);
            });
        }

        // 如果用戶已經保存了該 provider 的模型選擇，恢復它
        const savedModel = window.APIKeyManager.getModelForProvider(provider);
        if (savedModel) {
            modelSelect.value = savedModel;
        }
    }
}

/**
 * 切換 API Key 顯示/隱藏
 */
function toggleLLMKeyVisibility() {
    const input = document.getElementById('llm-api-key-input');
    const icon = document.getElementById('llm-key-eye-icon');

    if (!input || !icon) return;

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
    const providerSelect = document.getElementById('llm-provider-select');
    const input = document.getElementById('llm-api-key-input');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (!providerSelect || !input) return;

    const provider = providerSelect.value;
    const inputKey = input.value.trim();

    // 根據提供商獲取模型名稱
    let model = '';
    if (provider === 'openrouter') {
        model = modelInput.value.trim();
    } else {
        model = modelSelect.value;
    }

    // 檢查已保存的 Key
    const existingKey = window.APIKeyManager.getKey(provider);
    const isKeyUnchanged = existingKey && (inputKey === '' || inputKey === existingKey);

    if (isKeyUnchanged) {
        // ✅ 情況 A: Key 已保存且沒有更改，只是換模型 → 直接保存模型
        if (!model) {
            showLLMKeyStatus('error', '❌ 請選擇一個模型');
            return;
        }

        window.APIKeyManager.setModelForProvider(provider, model);
        window.APIKeyManager.setSelectedProvider(provider);

        showLLMKeyStatus('success', `✅ 模型已切換為 ${model}`);

        // 更新 LLM 狀態 UI
        if (typeof updateLLMStatusUI === 'function') {
            updateLLMStatusUI();
        }
        return;
    }

    // ✅ 情況 B: Key 是新的或已更改 → 需要先 TEST
    const key = inputKey;

    if (!key) {
        showLLMKeyStatus('error', '❌ 請輸入 API Key');
        return;
    }

    // 檢查是否已經測試成功
    const lastTestResult = localStorage.getItem(`last_test_result_${provider}`);
    const lastTestKey = localStorage.getItem(`last_test_key_${provider}`);
    const lastTestModel = localStorage.getItem(`last_test_model_${provider}`);

    // 檢查是否測試過，且測試的 key 和模型與當前輸入一致
    if (!lastTestResult || lastTestResult !== 'success' ||
        lastTestKey !== key ||
        lastTestModel !== model) {
        showLLMKeyStatus('error', '❌ 請先測試 API Key 並確保測試成功後再保存！');
        updateSaveButtonState(provider, key, model);
        return;
    }

    // 格式驗證
    const validation = window.APIKeyManager.validateKeyFormat(provider, key);

    if (!validation.valid) {
        showLLMKeyStatus('error', validation.message);
        return;
    }

    // 保存到 localStorage
    window.APIKeyManager.setKey(provider, key);
    window.APIKeyManager.setSelectedProvider(provider);

    // 保存用戶選擇的模型
    if (model) {
        window.APIKeyManager.setModelForProvider(provider, model);
    }

    showLLMKeyStatus('success', `✅ ${getProviderName(provider)} API Key 已保存！`);

    // 清除測試緩存
    localStorage.removeItem(`last_test_result_${provider}`);
    localStorage.removeItem(`last_test_key_${provider}`);
    localStorage.removeItem(`last_test_model_${provider}`);

    // 更新 Provider 下拉選單狀態（添加 ✅）
    if (typeof updateProviderDropdownStatus === 'function') {
        updateProviderDropdownStatus();
    }

    // 更新按鈕狀態
    updateSaveButtonState(provider, key, model);

    // 更新狀態指示器
    if (typeof checkApiKeyStatus === 'function') {
        checkApiKeyStatus();
    }

    // 更新 LLM 狀態 UI
    if (typeof updateLLMStatusUI === 'function') {
        updateLLMStatusUI();
    }

}

/**
 * 更新保存按鈕的狀態
 */
function updateSaveButtonState(provider, key, model) {
    const saveBtn = document.getElementById('save-llm-key-btn');
    if (!saveBtn) return;

    // 檢查已保存的 Key
    const existingKey = window.APIKeyManager.getKey(provider);
    const isKeyUnchanged = existingKey && (key === '' || key === existingKey);

    // ✅ 情況 A: Key 已保存且沒有更改 → 只要有選擇模型就可以保存
    if (isKeyUnchanged && model) {
        saveBtn.disabled = false;
        saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.add('hover:brightness-110');
        saveBtn.textContent = 'Save Model';
        return;
    }

    // ✅ 情況 B: 新 Key → 需要先測試
    if (!key) {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.remove('hover:brightness-110');
        saveBtn.textContent = 'Save AI Configuration';
        return;
    }

    const lastTestResult = localStorage.getItem(`last_test_result_${provider}`);
    const lastTestKey = localStorage.getItem(`last_test_key_${provider}`);
    const lastTestModel = localStorage.getItem(`last_test_model_${provider}`);

    // 檢查是否測試成功且 key 和 model 與測試時一致
    if (lastTestResult === 'success' && lastTestKey === key && lastTestModel === model) {
        saveBtn.disabled = false;
        saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.add('hover:brightness-110');
        saveBtn.textContent = 'Save AI Configuration';
    } else {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.remove('hover:brightness-110');
        saveBtn.textContent = 'Save AI Configuration';
    }
}

/**
 * 測試 LLM API Key
 */
async function testLLMKey() {
    const providerSelect = document.getElementById('llm-provider-select');
    const input = document.getElementById('llm-api-key-input');
    const modelSelect = document.getElementById('llm-model-select');

    if (!providerSelect || !input) return;

    const provider = providerSelect.value;
    const key = input.value.trim();

    // 根據提供商獲取模型名稱
    let selectedModel = '';
    if (provider === 'openrouter') {
        // OpenRouter 使用輸入框
        selectedModel = document.getElementById('llm-model-input').value.trim();
    } else {
        // 其他提供商使用下拉選擇
        selectedModel = document.getElementById('llm-model-select').value;
    }

    if (!key) {
        showLLMKeyStatus('error', '請先輸入 API Key');
        return;
    }

    // 檢查是否選擇了模型
    if (!selectedModel) {
        showLLMKeyStatus('error', '請先選擇模型');
        return;
    }

    // 格式驗證
    const validation = window.APIKeyManager.validateKeyFormat(provider, key);
    if (!validation.valid) {
        showLLMKeyStatus('error', validation.message);
        return;
    }

    showLLMKeyStatus('loading', '🔄 正在測試 API Key 與模型...');

    try {
        const response = await fetch('/api/settings/validate-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: provider,
                api_key: key,
                model: selectedModel  // Include the selected model for testing
            })
        });

        const result = await response.json();

        if (result.valid) {
            showLLMKeyStatus('success', `✅ ${result.message}`);

            // ✅ Auto-save key after successful test (fixes: features showing "no API key" after test)
            window.APIKeyManager.setKey(provider, key);
            window.APIKeyManager.setSelectedProvider(provider);
            if (selectedModel) {
                window.APIKeyManager.setModelForProvider(provider, selectedModel);
            }

            // 保存測試結果到 localStorage，以便 saveLLMKey 檢查
            localStorage.setItem(`last_test_result_${provider}`, 'success');
            localStorage.setItem(`last_test_key_${provider}`, key);
            localStorage.setItem(`last_test_model_${provider}`, selectedModel);

            // 更新保存按鈕狀態
            updateSaveButtonState(provider, key, selectedModel);

            // 通知 app.js 更新選單狀態
            if (window.setKeyValidity) {
                window.setKeyValidity(provider, true);
            }

            // 更新狀態指示器
            if (typeof checkApiKeyStatus === 'function') {
                checkApiKeyStatus();
            }

            // 更新 LLM 狀態 UI 和 Provider 下拉選單
            if (typeof updateLLMStatusUI === 'function') {
                updateLLMStatusUI();
            }
            updateProviderDropdownStatus();

            // 顯示測試結果 Modal
            if (result.reply) {
                const modal = document.getElementById('api-test-modal');
                const responseText = document.getElementById('api-test-response');
                if (modal && responseText) {
                    responseText.textContent = result.reply;
                    modal.classList.remove('hidden');
                }
            }

        } else {
            // 清除之前的測試結果
            localStorage.removeItem(`last_test_result_${provider}`);
            localStorage.removeItem(`last_test_key_${provider}`);
            localStorage.removeItem(`last_test_model_${provider}`);

            // 更新保存按鈕狀態
            updateSaveButtonState(provider, key, selectedModel);

            showLLMKeyStatus('error', `❌ ${result.message}`);
        }
    } catch (error) {
        console.error('Failed to test API key:', error);
        // 顯示更具體的錯誤信息
        let errorMessage = '❌ 測試失敗，請檢查網絡連接';
        if (error.message) {
            errorMessage += ` (${error.message})`;
        }
        showLLMKeyStatus('error', errorMessage);
    }
}

/**
 * 顯示狀態訊息
 * @param {string} type - 'success', 'error', 'loading'
 * @param {string} message
 */
function showLLMKeyStatus(type, message) {
    const status = document.getElementById('llm-key-status');
    if (!status) return;

    status.classList.remove('hidden', 'bg-green-900/20', 'bg-red-900/20', 'bg-blue-900/20', 'border-green-500/30', 'border-red-500/30', 'border-blue-500/30', 'border');

    if (type === 'success') {
        status.classList.add('bg-green-900/20', 'border', 'border-green-500/30', 'text-green-400');
    } else if (type === 'error') {
        status.classList.add('bg-red-900/20', 'border', 'border-red-500/30', 'text-red-400');
        // 對於錯誤，使用 Toast 提醒
        showToast(message.replace(/^❌\s*/, ''), 'error');
    } else if (type === 'loading') {
        status.classList.add('bg-blue-900/20', 'border', 'border-blue-500/30', 'text-blue-400');
    }

    status.textContent = message;
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
 * 更新 Provider 下拉選單的顯示狀態（添加 ✅）
 */
function updateProviderDropdownStatus() {
    const providerSelect = document.getElementById('llm-provider-select');
    if (!providerSelect) return;

    const providers = [
        { value: 'openai', label: 'OpenAI' },
        { value: 'google_gemini', label: 'Google Gemini' },
        { value: 'openrouter', label: 'OpenRouter' }
    ];

    // 保存當前選擇的值
    const currentValue = providerSelect.value;

    // 清空並重建選項
    providerSelect.innerHTML = '';

    providers.forEach(p => {
        const key = window.APIKeyManager.getKey(p.value);
        const option = document.createElement('option');
        option.value = p.value;
        // 如果有 key，在名稱後顯示 ✅
        option.textContent = key ? `${p.label} ✅` : p.label;
        providerSelect.appendChild(option);
    });

    // 恢復選擇
    providerSelect.value = currentValue;
}

/**
 * 页面加载时初始化
 */
window.addEventListener('DOMContentLoaded', () => {
    // 使用獨立的初始化函數處理異步邏輯，確保錯誤不會靜默失敗
    initializeLLMSettings().catch(error => {
        console.error('LLM Settings initialization failed:', error);
        showLLMKeyStatus('error', '初始化失敗，請重新整理頁面');
    });
});

/**
 * 異步初始化 LLM 設定
 */
async function initializeLLMSettings() {
    // 1. 初始化 Provider 下拉選單狀態 (顯示 ✅)
    updateProviderDropdownStatus();

    // 2. 初始化選中狀態和模型
    // 優先使用當前 active 的 provider，如果沒有則使用第一個有的 key
    let currentProvider = window.APIKeyManager?.getSelectedProvider();

    // 如果沒有選中的，嘗試找第一個有 Key 的
    if (!currentProvider) {
        const keys = window.APIKeyManager?.getAllKeys() || {};
        const providersWithKeys = Object.keys(keys).filter(k => keys[k]);
        if (providersWithKeys.length > 0) {
            currentProvider = providersWithKeys[0];
        } else {
            currentProvider = 'openai'; // Default fallback
        }
    }

    const providerSelect = document.getElementById('llm-provider-select');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (currentProvider && providerSelect) {
        providerSelect.value = currentProvider;

        // 恢復保存的模型選擇
        const savedModel = window.APIKeyManager.getModelForProvider(currentProvider);
        if (savedModel) {
            // 我們會在 updateAvailableModels 中設置 value，但這裡先存個引用
            providerSelect.dataset.savedModel = savedModel;
        }
    }

    // 3. 無論是否有 currentKey，都要更新當前選中 Provider 的輸入框狀態
    // 這樣即使默認選中 OpenAI 且有 Key，也會正確顯示 placeholder
    updateLLMKeyInput();

    // 4. 更新可用模型列表（包含錯誤處理）
    try {
        await updateAvailableModels();
    } catch (error) {
        console.error('Failed to update available models:', error);
        // 繼續初始化流程，即使模型列表更新失敗
    }

    // 5. 再次確保模型被選中 (因為 updateAvailableModels 會重置選項)
    if (providerSelect && providerSelect.dataset.savedModel) {
        if (providerSelect.value === 'openrouter') {
            if (modelInput) modelInput.value = providerSelect.dataset.savedModel;
        } else {
            if (modelSelect) modelSelect.value = providerSelect.dataset.savedModel;
        }
    }

    // 6. 更新保存按鈕狀態
    if (providerSelect) {
        const provider = providerSelect.value;
        const keyInput = document.getElementById('llm-api-key-input');
        const key = keyInput ? keyInput.value.trim() : '';

        let model = '';
        if (provider === 'openrouter') {
            model = modelInput ? modelInput.value.trim() : '';
        } else {
            model = modelSelect ? modelSelect.value : '';
        }

        updateSaveButtonState(provider, key, model);
    }

    // 添加事件監聽器以在選擇改變時更新按鈕狀態
    if (providerSelect) {
        providerSelect.addEventListener('change', async function () {
            updateLLMKeyInput(); // 確保切換時更新 placeholder

            // 切換 provider 時更新可用模型列表
            try {
                await updateAvailableModels();
            } catch (error) {
                console.error('Failed to update models on provider change:', error);
            }

            // 如果切換到的 provider 已有保存的 key
            const existingKey = window.APIKeyManager.getKey(this.value);

            if (existingKey) {
                const savedModel = window.APIKeyManager.getModelForProvider(this.value);
                updateSaveButtonState(this.value, '', savedModel || '');
            } else {
                // 如果沒有保存的 key，使用當前輸入框的值
                const keyInput = document.getElementById('llm-api-key-input');
                if (keyInput) {
                    const key = keyInput.value.trim();
                    let model = '';
                    if (this.value === 'openrouter') {
                        model = modelInput ? modelInput.value.trim() : '';
                    } else {
                        model = modelSelect ? modelSelect.value : '';
                    }
                    updateSaveButtonState(this.value, key, model);
                }
            }
        });
    }

    if (modelSelect) {
        modelSelect.addEventListener('change', function () {
            const providerSelect = document.getElementById('llm-provider-select');
            if (providerSelect && providerSelect.value !== 'openrouter') {
                const keyInput = document.getElementById('llm-api-key-input');
                const key = keyInput ? keyInput.value.trim() : '';
                updateSaveButtonState(providerSelect.value, key, this.value);
            }
        });
    }

    if (modelInput) {
        modelInput.addEventListener('input', function () {
            const providerSelect = document.getElementById('llm-provider-select');
            if (providerSelect && providerSelect.value === 'openrouter') {
                const keyInput = document.getElementById('llm-api-key-input');
                const key = keyInput ? keyInput.value.trim() : '';
                updateSaveButtonState(providerSelect.value, key, this.value);
            }
        });
    }
}

// Expose functions globally
window.updateLLMKeyInput = updateLLMKeyInput;
window.toggleLLMKeyVisibility = toggleLLMKeyVisibility;
window.saveLLMKey = saveLLMKey;
window.testLLMKey = testLLMKey;
window.updateAvailableModels = updateAvailableModels;
