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
                    {"value": "gpt-4o", "display": "gpt-4o"},
                    {"value": "gpt-4o-mini", "display": "gpt-4o-mini"},
                    {"value": "gpt-4-turbo", "display": "gpt-4-turbo"}
                ]
            },
            "google_gemini": {
                "default_model": "gemini-3-flash-preview",
                "available_models": [
                    {"value": "gemini-3-flash-preview", "display": "Gemini 3 Flash Preview"}
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
 */
async function updateAvailableModels() {
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

        // 從後端獲取模型配置
        const modelConfig = await fetchModelConfig();

        // 添加默認選項
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '請選擇模型';
        defaultOption.disabled = true;
        defaultOption.selected = true;
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
    const key = input.value.trim();

    // 根據提供商獲取模型名稱
    let model = '';
    if (provider === 'openrouter') {
        // OpenRouter 使用輸入框
        model = modelInput.value.trim();
    } else {
        // 其他提供商使用下拉選擇
        model = modelSelect.value;
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
        // 更新保存按鈕狀態
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

    showLLMKeyStatus('success', `✅ 模型儲存成功！${getProviderName(provider)} API Key 已保存！`);

    // 清除測試緩存
    localStorage.removeItem(`last_test_result_${provider}`);
    localStorage.removeItem(`last_test_key_${provider}`);
    localStorage.removeItem(`last_test_model_${provider}`);

    // 更新按鈕狀態
    updateSaveButtonState(provider, key, model);

    // 更新狀態指示器
    if (typeof checkApiKeyStatus === 'function') {
        checkApiKeyStatus();
    }
}

/**
 * 更新保存按鈕的狀態
 */
function updateSaveButtonState(provider, key, model) {
    const saveBtn = document.getElementById('save-llm-key-btn');
    if (!saveBtn) return;

    // 如果沒有提供有效的 provider，禁用按鈕
    if (!provider || !key) {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.remove('hover:brightness-110');
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
    } else {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
        saveBtn.classList.remove('hover:brightness-110');
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
        // 對於錯誤，額外彈出視窗提醒
        alert(message);
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
 * 页面加载时初始化
 */
window.addEventListener('DOMContentLoaded', async () => {
    // 初始化時載入已保存的 key
    const currentKey = window.APIKeyManager?.getCurrentKey();
    if (currentKey) {
        const providerSelect = document.getElementById('llm-provider-select');
        const modelSelect = document.getElementById('llm-model-select');
        const modelInput = document.getElementById('llm-model-input');

        if (providerSelect) {
            providerSelect.value = currentKey.provider;
            updateLLMKeyInput();

            // 更新可用模型列表
            await updateAvailableModels();

            // 恢復保存的模型選擇
            if (currentKey.provider) {
                const savedModel = window.APIKeyManager.getModelForProvider(currentKey.provider);
                if (savedModel) {
                    if (currentKey.provider === 'openrouter') {
                        // OpenRouter 使用輸入框
                        if (modelInput) modelInput.value = savedModel;
                    } else {
                        // 其他提供商使用下拉選擇
                        if (modelSelect) modelSelect.value = savedModel;
                    }
                }
            }
        }
    } else {
        // 如果沒有保存的 key，初始化模型列表
        await updateAvailableModels();
    }

    // 更新保存按鈕狀態
    if (currentKey) {
        const savedModel = window.APIKeyManager.getModelForProvider(currentKey.provider);
        updateSaveButtonState(currentKey.provider, currentKey.key, savedModel || '');
    } else {
        // 如果沒有保存的 key，初始化模型列表後更新按鈕狀態
        await updateAvailableModels();
        updateSaveButtonState('', '', '');
    }

    // 添加事件監聽器以在選擇改變時更新按鈕狀態
    const providerSelect = document.getElementById('llm-provider-select');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('llm-model-input');

    if (providerSelect) {
        providerSelect.addEventListener('change', function() {
            const currentKeyObj = window.APIKeyManager.getCurrentKey();
            if (currentKeyObj) {
                const savedModel = window.APIKeyManager.getModelForProvider(currentKeyObj.provider);
                updateSaveButtonState(currentKeyObj.provider, currentKeyObj.key, savedModel || '');
            } else {
                // 如果沒有保存的 key，使用當前選擇的值
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
        modelSelect.addEventListener('change', function() {
            const providerSelect = document.getElementById('llm-provider-select');
            if (providerSelect && providerSelect.value !== 'openrouter') {
                const currentKeyObj = window.APIKeyManager.getCurrentKey();
                const key = currentKeyObj ? currentKeyObj.key : (document.getElementById('llm-api-key-input') && document.getElementById('llm-api-key-input').value ? document.getElementById('llm-api-key-input').value : '').trim();
                updateSaveButtonState(providerSelect.value, key, this.value);
            }
        });
    }

    if (modelInput) {
        modelInput.addEventListener('input', function() {
            const providerSelect = document.getElementById('llm-provider-select');
            if (providerSelect && providerSelect.value === 'openrouter') {
                const currentKeyObj = window.APIKeyManager.getCurrentKey();
                const key = currentKeyObj ? currentKeyObj.key : (document.getElementById('llm-api-key-input') && document.getElementById('llm-api-key-input').value ? document.getElementById('llm-api-key-input').value : '').trim();
                updateSaveButtonState(providerSelect.value, key, this.value);
            }
        });
    }
});

// Expose functions globally
window.updateLLMKeyInput = updateLLMKeyInput;
window.toggleLLMKeyVisibility = toggleLLMKeyVisibility;
window.saveLLMKey = saveLLMKey;
window.testLLMKey = testLLMKey;
