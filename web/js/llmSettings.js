// ========================================
// llmSettings.js - LLM Settings
// ========================================

var llmState = {
    testPassed: false,
    testPassedKey: '',
    testPassedModel: '',
    isSaving: false,
    isTesting: false,
    savedKeys: {},
    initialized: false,
};

AppStore.set('llmState', llmState);
window.llmState = llmState;

function getProviderSelect() {
    return document.getElementById('llm-provider-select');
}

function getModelSelect() {
    return document.getElementById('llm-model-select');
}

function getModelInput() {
    return document.getElementById('llm-model-input');
}

function getApiKeyInput() {
    return document.getElementById('llm-api-key-input');
}

function getTestButton() {
    return document.getElementById('test-llm-key-btn');
}

function getSaveButton() {
    return document.getElementById('save-llm-key-btn');
}

function getSelectedProvider() {
    return getProviderSelect()?.value || '';
}

function getSelectedLLMModel() {
    var provider = getSelectedProvider();
    if (provider === 'openrouter') {
        return getModelInput()?.value?.trim() || '';
    }
    return getModelSelect()?.value || '';
}

function resetLLMTestState() {
    llmState.testPassed = false;
    llmState.testPassedKey = '';
    llmState.testPassedModel = '';
    disableSaveButton();
}

async function loadSavedApiKeys() {
    const user = typeof AuthManager !== 'undefined' ? AuthManager.currentUser : null;
    const hasKnownSession = !!(user && (user.user_id || user.uid || user.pi_uid));

    if (!hasKnownSession) {
        return;
    }

    try {
        var data = await AppAPI.get('/api/user/api-keys');
        llmState.savedKeys = data.keys || {};

        var activeProvider = null;
        var entries = Object.entries(llmState.savedKeys);
        for (var i = 0; i < entries.length; i++) {
            var provider = entries[i][0];
            var info = entries[i][1];
            if (!info?.has_key) continue;

            if (info.model && typeof window.APIKeyManager?.setModelForProvider === 'function') {
                window.APIKeyManager.setModelForProvider(provider, info.model);
            }

            if (!activeProvider) {
                activeProvider = provider;
            }
        }

        var currentSelection = localStorage.getItem('user_selected_provider');
        if (
            currentSelection &&
            llmState.savedKeys[currentSelection] &&
            llmState.savedKeys[currentSelection].has_key
        ) {
            activeProvider = currentSelection;
        }

        if (activeProvider && typeof window.APIKeyManager?.setSelectedProvider === 'function') {
            window.APIKeyManager.setSelectedProvider(activeProvider);
        }

        updateBindingStatus();
        updateLLMFormState();
    } catch (error) {
        console.error('[loadSavedApiKeys] Error:', error);
    }
}
window.loadSavedApiKeys = loadSavedApiKeys;

function updateBindingStatus() {
    var statusElement = document.getElementById('llm-binding-status');
    var modelSelect = getModelSelect();
    var provider = getSelectedProvider();
    var keyInfo = llmState.savedKeys[provider];

    if (!statusElement) return;

    if (keyInfo && keyInfo.has_key) {
        statusElement.innerHTML =
            '<span class="text-green-400">已綁定金鑰：</span> <span class="text-textMuted">' +
            (keyInfo.masked_key || '') +
            '</span>';
        statusElement.classList.remove('hidden');

        if (keyInfo.model && modelSelect) {
            setTimeout(function () {
                var optionExists = Array.from(modelSelect.options).some(function (opt) {
                    return opt.value === keyInfo.model;
                });
                if (optionExists) {
                    modelSelect.value = keyInfo.model;
                    updateLLMFormState();
                }
            }, 300);
        }
        return;
    }

    statusElement.textContent = '';
    statusElement.classList.add('hidden');
}

function updateLLMFormState() {
    var provider = getSelectedProvider();
    var model = getSelectedLLMModel();
    var hasModel = !!model;
    var apiKeyInput = getApiKeyInput();
    var testBtn = getTestButton();
    var keyStatus = document.getElementById('llm-key-status');
    var modelHint = document.getElementById('llm-model-hint');

    if (apiKeyInput) {
        apiKeyInput.disabled = !hasModel;
        if (hasModel) {
            var placeholders = {
                openai: 'sk-...',
                google_gemini: 'AIza...',
                anthropic: 'sk-ant-...',
                groq: 'gsk_...',
                openrouter: 'sk-or-...',
            };
            apiKeyInput.placeholder = placeholders[provider] || 'API Key...';
        } else {
            apiKeyInput.placeholder =
                provider === 'openrouter'
                    ? '請先輸入模型名稱...'
                    : '請先選擇模型...';
        }
    }

    if (testBtn) {
        testBtn.disabled = !hasModel || llmState.isTesting;
    }

    if (modelHint) {
        modelHint.textContent =
            provider === 'openrouter'
                ? '請先輸入完整的 OpenRouter 模型 ID，再測試 API 金鑰。'
                : '先選定目標模型，連線測試才會使用正確的模型設定。';
    }

    if (keyStatus) {
        if (!hasModel) {
            keyStatus.textContent = '請先選擇供應商與模型，再輸入 API 金鑰。';
        } else if (llmState.testPassed) {
            keyStatus.textContent = '連線測試已通過，現在可以直接儲存設定。';
        } else {
            keyStatus.textContent = '輸入 API 金鑰後，請先完成連線測試再儲存。';
        }
        keyStatus.classList.remove('hidden');
    }
}
window.updateLLMFormState = updateLLMFormState;

function updateLLMKeyInput() {
    var apiKeyInput = getApiKeyInput();

    if (apiKeyInput) {
        apiKeyInput.value = '';
    }

    resetLLMTestState();
    updateBindingStatus();
    updateLLMFormState();
}
window.updateLLMKeyInput = updateLLMKeyInput;

function enableSaveButton() {
    var saveBtn = getSaveButton();
    if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}
window.enableSaveButton = enableSaveButton;

function disableSaveButton() {
    var saveBtn = getSaveButton();
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
}
window.disableSaveButton = disableSaveButton;

function setSaveButtonLoading(loading) {
    var saveBtn = getSaveButton();
    if (!saveBtn) return;

    if (loading) {
        saveBtn.disabled = true;
        saveBtn.innerHTML =
            '<span class="inline-flex items-center"><svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Saving...</span>';
    } else {
        saveBtn.innerHTML = 'Save AI Configuration';
    }

    updateLLMFormState();
}

async function testLLMKey() {
    if (llmState.isTesting) {
        return;
    }

    var provider = getSelectedProvider();
    var model = getSelectedLLMModel();
    var apiKey = getApiKeyInput()?.value?.trim() || '';
    var testBtn = getTestButton();

    if (!provider) {
        llmShowToast('請先選擇供應商。', 'error');
        return;
    }

    if (!model) {
        llmShowToast('請先選擇或輸入模型。', 'error');
        updateLLMFormState();
        return;
    }

    if (!apiKey) {
        llmShowToast('請先輸入 API 金鑰再進行測試。', 'error');
        return;
    }

    llmState.isTesting = true;
    updateLLMFormState();

    if (testBtn) {
        testBtn.disabled = true;
        testBtn.innerHTML =
            '<span class="inline-flex items-center"><svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Testing...</span>';
    }

    llmShowToast('正在測試連線...', 'info');

    try {
        var data = await AppAPI.post('/api/settings/validate-key', {
            provider: provider,
            model: model,
            api_key: apiKey,
        });

        if (data.valid) {
            llmState.testPassed = true;
            llmState.testPassedKey = apiKey;
            llmState.testPassedModel = model;
            enableSaveButton();
            llmShowToast(data.message || 'API 金鑰有效。', 'success');
        } else {
            resetLLMTestState();
            llmShowToast(
                data.message || data.error || data.detail || '連線測試失敗。',
                'error'
            );
        }
    } catch (error) {
        console.error('Test LLM key error:', error);
        resetLLMTestState();
        llmShowToast('連線測試失敗，請稍後再試。', 'error');
    } finally {
        llmState.isTesting = false;
        if (testBtn) {
            testBtn.textContent = 'TEST';
        }
        updateLLMFormState();
    }
}
window.testLLMKey = testLLMKey;

async function saveLLMKey() {
    if (llmState.isSaving) {
        return;
    }

    if (!llmState.testPassed) {
        llmShowToast('請先完成 API 金鑰測試再儲存。', 'error');
        return;
    }

    var provider = getSelectedProvider();
    var apiKey = llmState.testPassedKey;
    var model = llmState.testPassedModel;
    var apiKeyInput = getApiKeyInput();

    if (!provider || !model || !apiKey) {
        llmShowToast('供應商、模型與 API 金鑰缺一不可。', 'error');
        return;
    }

    llmState.isSaving = true;
    setSaveButtonLoading(true);

    try {
        var data = await AppAPI.post('/api/user/api-keys', {
            provider: provider,
            model: model,
            api_key: apiKey,
        });

        if (data.success || data.ok) {
            if (apiKeyInput) {
                apiKeyInput.value = '';
            }

            resetLLMTestState();
            await loadSavedApiKeys();

            if (typeof window.setKeyValidity === 'function') {
                window.setKeyValidity(provider, true);
            }
            if (typeof window.APIKeyManager?.setSelectedProvider === 'function') {
                window.APIKeyManager.setSelectedProvider(provider);
            }
            if (typeof window.APIKeyManager?.setModelForProvider === 'function') {
                window.APIKeyManager.setModelForProvider(provider, model);
            }
            if (window.APIKeyManager) {
                window.APIKeyManager._maskedKeysCache = null;
            }

            window.dispatchEvent(new Event('apiKeyUpdated'));
            if (typeof checkApiKeyStatus === 'function') {
                await checkApiKeyStatus();
            }
            if (typeof window.updateLLMStatusUI === 'function') {
                await window.updateLLMStatusUI();
            }

            llmShowToast('AI 設定已儲存。', 'success');
        } else {
            llmShowToast(
                data.detail || data.error || 'AI 設定儲存失敗。',
                'error'
            );
        }
    } catch (error) {
        console.error('Save LLM key error:', error);
        llmShowToast('AI 設定儲存失敗，請稍後再試。', 'error');
    } finally {
        llmState.isSaving = false;
        setSaveButtonLoading(false);
        updateLLMFormState();
    }
}
window.saveLLMKey = saveLLMKey;

function llmShowToast(message, type) {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
        return;
    }

    console.warn('showToast is unavailable:', message, type);
}

function bindLLMSettingsEvents() {
    if (document.body?.dataset.llmSettingsBound === 'true') {
        return;
    }

    document.body.dataset.llmSettingsBound = 'true';

    document.addEventListener('change', function (event) {
        var target = event.target;
        if (!target || !target.id) return;

        if (target.id === 'llm-provider-select') {
            updateLLMKeyInput();
            if (typeof window.updateAvailableModels === 'function') {
                window.updateAvailableModels();
            }
            return;
        }

        if (target.id === 'llm-model-select') {
            resetLLMTestState();
            updateLLMFormState();
        }
    });

    document.addEventListener('input', function (event) {
        var target = event.target;
        if (!target || !target.id) return;

        if (
            target.id === 'llm-api-key-input' ||
            target.id === 'llm-model-input'
        ) {
            resetLLMTestState();
            updateLLMFormState();
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    updateLLMKeyInput();
    disableSaveButton();
    bindLLMSettingsEvents();
    llmState.initialized = true;
    updateLLMFormState();
});

window.addEventListener('auth:ready', function () {
    loadSavedApiKeys().catch(function (error) {
        console.error('[loadSavedApiKeys] auth:ready reload failed:', error);
    });
});

window.addEventListener('auth:initialized', function (event) {
    if (!event?.detail?.isLoggedIn) {
        return;
    }

    loadSavedApiKeys().catch(function (error) {
        console.error('[loadSavedApiKeys] auth:initialized reload failed:', error);
    });
});

export {
    llmState,
    loadSavedApiKeys,
    updateBindingStatus,
    updateLLMFormState,
    updateLLMKeyInput,
    enableSaveButton,
    disableSaveButton,
    setSaveButtonLoading,
    testLLMKey,
    saveLLMKey,
    llmShowToast,
};
