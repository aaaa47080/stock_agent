// ========================================
// llmSettings.js - LLM Settings 管理
// ========================================

/**
 * LLM Settings 頁面功能
 *
 * 流程：選擇 Provider/Model → 輸入 API Key → 測試連接 → 測試成功後啟用保存
 */

// 狀態管理
var llmState = {
    testPassed: false, // 測試是否通過
    testPassedKey: '', // 測試通過時的 API Key（用於保存）
    testPassedModel: '', // 測試通過時的 Model
    isSaving: false, // 是否正在保存
    isTesting: false, // 是否正在測試
    savedKeys: {}, // 已保存的 API Key 狀態 { provider: { hasKey: true, maskedKey: "sk-...abc", model: "gpt-4o" } }
    initialized: false, // 是否已初始化
};
AppStore.set('llmState', llmState);
window.llmState = llmState;

// ========================================
// 載入已保存的 API Key 狀態（全局函數，由 index.html 在 Auth 完成後調用）
// ========================================

async function loadSavedApiKeys() {
    const user = typeof AuthManager !== 'undefined' ? AuthManager.currentUser : null;
    const hasKnownSession = !!(user && (user.user_id || user.uid || user.pi_uid));
    if (!hasKnownSession) {
        console.log('[loadSavedApiKeys] No authenticated session, skipping');
        return;
    }

    try {
        var data = await AppAPI.get('/api/user/api-keys');
        llmState.savedKeys = data.keys || {};
        console.log('[loadSavedApiKeys] Loaded saved keys:', llmState.savedKeys);
        updateBindingStatus();
    } catch (error) {
        console.error('[loadSavedApiKeys] Error:', error);
    }
}
window.loadSavedApiKeys = loadSavedApiKeys;

// ========================================
// 更新綁定狀態顯示
// ========================================

function updateBindingStatus() {
    var providerSelect = document.getElementById('llm-provider-select');
    var statusElement = document.getElementById('llm-binding-status');
    var modelSelect = document.getElementById('llm-model-select');

    if (!providerSelect) return;

    var provider = providerSelect.value;
    var keyInfo = llmState.savedKeys[provider];

    // 創建或更新狀態顯示元素
    if (!statusElement) {
        var apiKeyContainer =
            document.querySelector('#llm-api-key-input')?.parentElement?.parentElement;
        if (apiKeyContainer) {
            statusElement = document.createElement('div');
            statusElement.id = 'llm-binding-status';
            statusElement.className = 'mt-2 text-xs';
            apiKeyContainer.appendChild(statusElement);
        }
    }

    if (statusElement) {
        if (keyInfo && keyInfo.has_key) {
            statusElement.innerHTML =
                '<span class="text-green-400">✓ 已綁定</span> <span class="text-textMuted">' +
                (keyInfo.masked_key || '') +
                '</span>';
            statusElement.classList.remove('hidden');

            // 如果有保存的模型，設置到 model select
            if (keyInfo.model && modelSelect) {
                // 等待模型列表載入後再設置
                setTimeout(function () {
                    var optionExists = Array.from(modelSelect.options).some(function (opt) {
                        return opt.value === keyInfo.model;
                    });
                    if (optionExists) {
                        modelSelect.value = keyInfo.model;
                    }
                }, 500);
            }
        } else {
            statusElement.innerHTML = '<span class="text-textMuted">尚未綁定</span>';
        }
    }
}

// ========================================
// 更新 API Key 輸入框狀態
// ========================================

function updateLLMKeyInput() {
    var providerSelect = document.getElementById('llm-provider-select');
    var apiKeyInput = document.getElementById('llm-api-key-input');

    if (!providerSelect) return;

    var provider = providerSelect.value;

    // 根據 provider 更新 placeholder
    if (apiKeyInput) {
        var placeholders = {
            openai: 'sk-...',
            google_gemini: 'AIza...',
            anthropic: 'sk-ant-...',
            groq: 'gsk_...',
            openrouter: 'sk-or-...',
        };
        apiKeyInput.placeholder = placeholders[provider] || 'API Key...';
        // 清空輸入框
        apiKeyInput.value = '';
    }

    // 更換 provider 時重置測試狀態
    llmState.testPassed = false;
    llmState.testPassedKey = '';
    disableSaveButton();

    // 更新綁定狀態顯示
    updateBindingStatus();
}
window.updateLLMKeyInput = updateLLMKeyInput;

// ========================================
// 啟用/禁用保存按鈕
// ========================================

function enableSaveButton() {
    var saveBtn = document.getElementById('save-llm-key-btn');
    if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}
window.enableSaveButton = enableSaveButton;

function disableSaveButton() {
    var saveBtn = document.getElementById('save-llm-key-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
}
window.disableSaveButton = disableSaveButton;

function setSaveButtonLoading(loading) {
    var saveBtn = document.getElementById('save-llm-key-btn');
    if (saveBtn) {
        if (loading) {
            saveBtn.disabled = true;
            saveBtn.innerHTML =
                '<span class="inline-flex items-center"><svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>儲存中...</span>';
        } else {
            saveBtn.innerHTML = 'Save AI Configuration';
        }
    }
}

// ========================================
// 測試 LLM Key
// ========================================

async function testLLMKey() {
    if (llmState.isTesting) {
        console.log('Test already in progress');
        return;
    }

    var providerSelect = document.getElementById('llm-provider-select');
    var modelSelect = document.getElementById('llm-model-select');
    var modelInput = document.getElementById('llm-model-input');
    var apiKeyInput = document.getElementById('llm-api-key-input');
    var testBtn = document.getElementById('test-llm-key-btn');

    var provider = providerSelect ? providerSelect.value : '';
    var model = '';
    var apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';

    // OpenRouter 從輸入框獲取
    if (provider === 'openrouter' && modelInput) {
        model = modelInput.value.trim();
    } else if (modelSelect) {
        model = modelSelect.value;
    }

    // 驗證
    if (!provider) {
        llmShowToast('請選擇 Provider', 'error');
        return;
    }

    if (!model) {
        llmShowToast('請選擇或輸入 Model', 'error');
        return;
    }

    if (!apiKey) {
        llmShowToast('請輸入 API Key 進行測試', 'error');
        return;
    }

    llmState.isTesting = true;

    // 顯示測試中狀態
    if (testBtn) {
        testBtn.disabled = true;
        testBtn.innerHTML =
            '<span class="inline-flex items-center"><svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>測試中...</span>';
    }

    llmShowToast('正在測試連接...', 'info');

    try {
        var data = await AppAPI.post('/api/settings/validate-key', {
            provider: provider,
            model: model,
            api_key: apiKey,
        });

        if (data.valid) {
            llmShowToast('✅ ' + (data.message || 'API Key 測試成功！'), 'success');
            // 測試通過，啟用保存按鈕
            llmState.testPassed = true;
            llmState.testPassedKey = apiKey;
            llmState.testPassedModel = model;
            enableSaveButton();
        } else {
            // 正確處理錯誤消息
            var errorMsg = '測試失敗';
            if (typeof data.message === 'string') {
                errorMsg = data.message;
            } else if (typeof data.error === 'string') {
                errorMsg = data.error;
            } else if (data.detail && typeof data.detail === 'string') {
                errorMsg = data.detail;
            }
            llmShowToast(errorMsg, 'error');
            llmState.testPassed = false;
            llmState.testPassedKey = '';
            disableSaveButton();
        }
    } catch (error) {
        console.error('Test LLM key error:', error);
        llmShowToast('測試失敗，請稍後重試', 'error');
        llmState.testPassed = false;
        llmState.testPassedKey = '';
        disableSaveButton();
    } finally {
        llmState.isTesting = false;
        // 恢復測試按鈕
        if (testBtn) {
            testBtn.disabled = false;
            testBtn.textContent = 'TEST';
        }
    }
}
window.testLLMKey = testLLMKey;

// ========================================
// 保存 LLM Key
// ========================================

async function saveLLMKey() {
    // 防止重複點擊
    if (llmState.isSaving) {
        console.log('Save already in progress');
        return;
    }

    // 必須先測試通過
    if (!llmState.testPassed) {
        llmShowToast('請先測試 API Key', 'error');
        return;
    }

    var providerSelect = document.getElementById('llm-provider-select');
    var apiKeyInput = document.getElementById('llm-api-key-input');

    var provider = providerSelect ? providerSelect.value : '';
    var apiKey = llmState.testPassedKey; // 使用測試通過的 API Key
    var model = llmState.testPassedModel; // 使用測試通過的 Model

    if (!provider || !model || !apiKey) {
        llmShowToast('資料不完整，請重新測試', 'error');
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
            llmShowToast('✅ 設置已保存', 'success');
            // 清空 API Key 輸入框（安全考量）
            if (apiKeyInput) {
                apiKeyInput.value = '';
            }
            // 重置測試狀態
            llmState.testPassed = false;
            llmState.testPassedKey = '';
            llmState.testPassedModel = '';
            disableSaveButton();

            // ✅ 修復：從後端重新載入狀態，而不是手動設置本地狀態
            // 這確保 UI 顯示的狀態與後端實際保存的狀態一致
            await loadSavedApiKeys();

            // 更新全局狀態
            if (typeof window.setKeyValidity === 'function') {
                window.setKeyValidity(provider, true);
            }
            // 緻加：設置選中的 provider（關鍵！）
            if (typeof window.APIKeyManager?.setSelectedProvider === 'function') {
                window.APIKeyManager.setSelectedProvider(provider);
            }
            // 保存模型到 localStorage（解決重啟後模型不顯示問題）
            if (model && typeof window.APIKeyManager?.setModelForProvider === 'function') {
                window.APIKeyManager.setModelForProvider(provider, model);
            }
            if (window.APIKeyManager) {
                window.APIKeyManager._maskedKeysCache = null;
            }
            // ✅ 通知 chat.js 清除 userKey 快取
            window.dispatchEvent(new Event('apiKeyUpdated'));
            if (typeof checkApiKeyStatus === 'function') {
                await checkApiKeyStatus();
            }
            if (typeof window.updateLLMStatusUI === 'function') {
                await window.updateLLMStatusUI();
            }
        } else {
            // 正確處理錯誤消息
            var errorMsg = '保存失敗';
            if (data.detail) {
                if (typeof data.detail === 'string') {
                    errorMsg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    errorMsg = data.detail
                        .map(function (e) {
                            return e.msg || String(e);
                        })
                        .join(', ');
                } else {
                    errorMsg = JSON.stringify(data.detail);
                }
            } else if (data.error) {
                errorMsg = typeof data.error === 'string' ? data.error : JSON.stringify(data.error);
            }
            llmShowToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Save LLM key error:', error);
        llmShowToast('保存失敗，請稍後重試', 'error');
    } finally {
        llmState.isSaving = false;
        setSaveButtonLoading(false);
    }
}
window.saveLLMKey = saveLLMKey;

// ========================================
// 輔助函數
// ========================================

function llmShowToast(message, type) {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
        return;
    }

    console.warn('showToast is unavailable:', message, type);
}

// ========================================
// 初始化（只綁定事件，不調用 API）
// ========================================

document.addEventListener('DOMContentLoaded', function () {
    // 頁面載入時初始化 UI
    updateLLMKeyInput();

    // 保存按鈕預設禁用
    disableSaveButton();

    // 注意：不在此處調用 loadSavedApiKeys()，因為 AuthManager 可能還沒初始化
    // loadSavedApiKeys() 會由 index.html 在 initializeAuth() 完成後調用

    // 綁定 provider select 變更事件
    var providerSelect = document.getElementById('llm-provider-select');
    if (providerSelect) {
        providerSelect.addEventListener('change', function () {
            updateLLMKeyInput();
            if (typeof window.updateAvailableModels === 'function') {
                window.updateAvailableModels();
            }
        });
    }

    // 綁定 API Key 輸入變更事件（重置測試狀態）
    var apiKeyInput = document.getElementById('llm-api-key-input');
    if (apiKeyInput) {
        apiKeyInput.addEventListener('input', function () {
            llmState.testPassed = false;
            llmState.testPassedKey = '';
            disableSaveButton();
        });
    }

    // 綁定 model select 變更事件（重置測試狀態）
    var modelSelect = document.getElementById('llm-model-select');
    if (modelSelect) {
        modelSelect.addEventListener('change', function () {
            llmState.testPassed = false;
            llmState.testPassedKey = '';
            disableSaveButton();
        });
    }

    // 綁定 model input 變更事件（OpenRouter）
    var modelInput = document.getElementById('llm-model-input');
    if (modelInput) {
        modelInput.addEventListener('input', function () {
            llmState.testPassed = false;
            llmState.testPassedKey = '';
            disableSaveButton();
        });
    }

    llmState.initialized = true;
    console.log('LLM Settings 初始化完成（等待 Auth 完成後載入綁定狀態）');
});

window.addEventListener('auth:ready', () => {
    loadSavedApiKeys().catch((error) =>
        console.error('[loadSavedApiKeys] auth:ready reload failed:', error)
    );
});

window.addEventListener('auth:initialized', (event) => {
    if (!event?.detail?.isLoggedIn) {
        return;
    }

    loadSavedApiKeys().catch((error) =>
        console.error('[loadSavedApiKeys] auth:initialized reload failed:', error)
    );
});

export {
    llmState,
    loadSavedApiKeys,
    updateBindingStatus,
    updateLLMKeyInput,
    enableSaveButton,
    disableSaveButton,
    setSaveButtonLoading,
    testLLMKey,
    saveLLMKey,
    llmShowToast,
};
