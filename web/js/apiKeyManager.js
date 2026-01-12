// ========================================
// apiKeyManager.js - 用戶 API Key 管理
// ========================================

/**
 * API Key 管理器 - 負責存儲和管理用戶的 LLM API Keys
 * 使用 localStorage 進行本地存儲（僅存在用戶瀏覽器）
 */
const APIKeyManager = {
    // Storage keys
    STORAGE_KEYS: {
        OPENAI: 'user_openai_api_key',
        GOOGLE: 'user_google_api_key',
        OPENROUTER: 'user_openrouter_api_key',
        SELECTED_PROVIDER: 'user_selected_provider'
    },

    /**
     * 設置 API Key
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @param {string} key - API key
     */
    setKey(provider, key) {
        if (!key || key.trim() === '') {
            this.removeKey(provider);
            return;
        }

        const storageKey = this._getStorageKey(provider);
        if (storageKey) {
            localStorage.setItem(storageKey, key.trim());
            console.log(`✅ ${provider} API Key saved to localStorage`);
        }
    },

    /**
     * 獲取 API Key
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @returns {string|null}
     */
    getKey(provider) {
        const storageKey = this._getStorageKey(provider);
        if (!storageKey) return null;

        const key = localStorage.getItem(storageKey);
        return key && key.trim() !== '' ? key.trim() : null;
    },

    /**
     * 移除 API Key
     * @param {string} provider
     */
    removeKey(provider) {
        const storageKey = this._getStorageKey(provider);
        if (storageKey) {
            localStorage.removeItem(storageKey);
            console.log(`🗑️ ${provider} API Key removed`);
        }
    },

    /**
     * 檢查是否有任何 API Key
     * @returns {boolean}
     */
    hasAnyKey() {
        return this.getKey('openai') ||
               this.getKey('google_gemini') ||
               this.getKey('openrouter');
    },

    /**
     * 獲取當前選擇的 provider
     * @returns {string|null}
     */
    getSelectedProvider() {
        return localStorage.getItem(this.STORAGE_KEYS.SELECTED_PROVIDER) || null;
    },

    /**
     * 設置選擇的 provider
     * @param {string} provider
     */
    setSelectedProvider(provider) {
        localStorage.setItem(this.STORAGE_KEYS.SELECTED_PROVIDER, provider);
    },

    /**
     * 獲取當前有效的 API Key（根據選擇的 provider）
     * @returns {{provider: string, key: string}|null}
     */
    getCurrentKey() {
        // 優先使用用戶選擇的 provider
        let provider = this.getSelectedProvider();

        if (provider) {
            const key = this.getKey(provider);
            if (key) {
                return { provider, key };
            }
        }

        // 如果沒有選擇或該 provider 沒有 key，自動選擇第一個有 key 的
        const providers = ['openai', 'google_gemini', 'openrouter'];
        for (const p of providers) {
            const key = this.getKey(p);
            if (key) {
                this.setSelectedProvider(p); // 自動設置
                return { provider: p, key };
            }
        }

        return null;
    },

    /**
     * 獲取所有已設置的 keys
     * @returns {Object}
     */
    getAllKeys() {
        return {
            openai: this.getKey('openai'),
            google_gemini: this.getKey('google_gemini'),
            openrouter: this.getKey('openrouter')
        };
    },

    /**
     * 清除所有 keys
     */
    clearAll() {
        Object.values(this.STORAGE_KEYS).forEach(key => {
            localStorage.removeItem(key);
        });
        console.log('🗑️ All API Keys cleared');
    },

    /**
     * 驗證 API Key 格式
     * @param {string} provider
     * @param {string} key
     * @returns {{valid: boolean, message: string}}
     */
    validateKeyFormat(provider, key) {
        if (!key || key.trim() === '') {
            return { valid: false, message: 'API Key 不能為空' };
        }

        const trimmedKey = key.trim();

        // 基本格式驗證
        if (provider === 'openai') {
            if (!trimmedKey.startsWith('sk-')) {
                return { valid: false, message: 'OpenAI Key 應該以 sk- 開頭' };
            }
            if (trimmedKey.length < 40) {
                return { valid: false, message: 'OpenAI Key 長度不足' };
            }
        } else if (provider === 'google_gemini') {
            if (trimmedKey.length < 30) {
                return { valid: false, message: 'Google API Key 長度不足' };
            }
        } else if (provider === 'openrouter') {
            if (!trimmedKey.startsWith('sk-or-')) {
                return { valid: false, message: 'OpenRouter Key 應該以 sk-or- 開頭' };
            }
        }

        return { valid: true, message: 'OK' };
    },

    /**
     * 獲取對應的 localStorage key
     * @private
     */
    _getStorageKey(provider) {
        const map = {
            'openai': this.STORAGE_KEYS.OPENAI,
            'google_gemini': this.STORAGE_KEYS.GOOGLE,
            'openrouter': this.STORAGE_KEYS.OPENROUTER
        };
        return map[provider] || null;
    },

    /**
     * 設置用戶選擇的模型（按提供商）
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @param {string} model - 模型名稱
     */
    setModelForProvider(provider, model) {
        if (!provider || !model) return;

        const storageKey = `user_${provider}_selected_model`;
        localStorage.setItem(storageKey, model.trim());
        console.log(`✅ ${provider} selected model saved: ${model}`);
    },

    /**
     * 獲取用戶選擇的模型（按提供商）
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @returns {string|null}
     */
    getModelForProvider(provider) {
        if (!provider) return null;

        const storageKey = `user_${provider}_selected_model`;
        const model = localStorage.getItem(storageKey);
        return model && model.trim() !== '' ? model.trim() : null;
    }
};

// Export to global scope
window.APIKeyManager = APIKeyManager;
