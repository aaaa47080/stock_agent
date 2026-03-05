// ========================================
// apiKeyManager.js - 用戶 API Key 管理
// ========================================

/**
 * API Key 管理器 - 負責存儲和管理用戶的 LLM API Keys
 * 🔐 使用 Web Crypto API (AES-GCM) 加密存儲
 * 加密密鑰從用戶會話令牌派生，只有在登入狀態下才能解密
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
     * 從用戶會話獲取加密密鑰
     * @returns {Promise<CryptoKey|null>}
     */
    async _getEncryptionKey() {
        try {
            const user = window.AuthManager?.currentUser;
            if (!user || !user.accessToken) {
                return null;
            }

            const encoder = new TextEncoder();
            const keyMaterial = await crypto.subtle.importKey(
                'raw',
                encoder.encode(user.accessToken),
                'PBKDF2',
                false,
                ['deriveKey']
            );

            const salt = encoder.encode('llm-key-encryption-salt');
            const key = await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: salt,
                    iterations: 100000,
                    hash: 'SHA-256'
                },
                keyMaterial,
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt', 'decrypt']
            );

            return key;
        } catch (e) {
            console.error('[APIKeyManager] 獲取加密密鑰失敗', e);
            return null;
        }
    },

    /**
     * 加密數據
     * @param {string} data - 要加密的數據
     * @returns {Promise<string|null>}
     */
    async _encrypt(data) {
        try {
            const key = await this._getEncryptionKey();
            if (!key) return data; // 未登入時不加密，返回原始數據

            const encoder = new TextEncoder();
            const iv = crypto.getRandomValues(new Uint8Array(12));
            const encrypted = await crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: iv },
                key,
                encoder.encode(data)
            );

            const combined = new Uint8Array(iv.length + encrypted.byteLength);
            combined.set(iv);
            combined.set(new Uint8Array(encrypted), iv.length);

            return 'enc:' + btoa(String.fromCharCode(...combined));
        } catch (e) {
            console.error('[APIKeyManager] 加密失敗', e);
            return data;
        }
    },

    /**
     * 解密數據
     * @param {string} encryptedData - 加密的數據
     * @returns {Promise<string>}
     */
    async _decrypt(encryptedData) {
        // 如果不是加密格式，直接返回
        if (!encryptedData.startsWith('enc:')) {
            return encryptedData;
        }

        try {
            const key = await this._getEncryptionKey();
            if (!key) return null;

            const data = encryptedData.slice(4); // 移除 'enc:' 前綴
            const combined = Uint8Array.from(atob(data), c => c.charCodeAt(0));
            const iv = combined.slice(0, 12);
            const encrypted = combined.slice(12);

            const decrypted = await crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: iv },
                key,
                encrypted
            );

            return new TextDecoder().decode(decrypted);
        } catch (e) {
            console.error('[APIKeyManager] 解密失敗', e);
            return null;
        }
    },

    /**
     * 設置 API Key（加密存儲）
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @param {string} key - API key
     */
    async setKey(provider, key) {
        if (!key || key.trim() === '') {
            this.removeKey(provider);
            return;
        }

        const storageKey = this._getStorageKey(provider);
        if (storageKey) {
            const encrypted = await this._encrypt(key.trim());
            localStorage.setItem(storageKey, encrypted);
            if (window.DEBUG_MODE) console.log(`🔐 ${provider} API Key saved (encrypted)`);
        }
    },

    /**
     * 獲取 API Key（自動解密）
     * @param {string} provider - 'openai', 'google_gemini', 'openrouter'
     * @returns {Promise<string|null>}
     */
    async getKey(provider) {
        const storageKey = this._getStorageKey(provider);
        if (!storageKey) return null;

        const stored = localStorage.getItem(storageKey);
        if (!stored || stored.trim() === '') return null;

        const decrypted = await this._decrypt(stored);
        return decrypted && decrypted.trim() !== '' ? decrypted.trim() : null;
    },

    /**
     * 移除 API Key
     * @param {string} provider
     */
    removeKey(provider) {
        const storageKey = this._getStorageKey(provider);
        if (storageKey) {
            localStorage.removeItem(storageKey);
            if (window.DEBUG_MODE) console.log(`🗑️ ${provider} API Key removed`);
        }
    },

    /**
     * 檢查是否有任何 API Key
     * @returns {boolean}
     */
    hasAnyKey() {
        return !!(localStorage.getItem(this.STORAGE_KEYS.OPENAI) ||
                  localStorage.getItem(this.STORAGE_KEYS.GOOGLE) ||
                  localStorage.getItem(this.STORAGE_KEYS.OPENROUTER));
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
     * 獲取當前有效的 API Key（根據選擇的 provider）- 異步版本
     * @returns {Promise<{provider: string, key: string}|null>}
     */
    async getCurrentKey() {
        let provider = this.getSelectedProvider();

        if (provider) {
            const key = await this.getKey(provider);
            if (key) {
                return { provider, key };
            }
        }

        const providers = ['openai', 'google_gemini', 'openrouter'];
        for (const p of providers) {
            const key = await this.getKey(p);
            if (key) {
                this.setSelectedProvider(p);
                return { provider: p, key };
            }
        }

        return null;
    },

    /**
     * 獲取所有已設置的 keys - 異步版本
     * @returns {Promise<Object>}
     */
    async getAllKeys() {
        return {
            openai: await this.getKey('openai'),
            google_gemini: await this.getKey('google_gemini'),
            openrouter: await this.getKey('openrouter')
        };
    },

    /**
     * 清除所有 keys
     */
    clearAll() {
        Object.values(this.STORAGE_KEYS).forEach(key => {
            localStorage.removeItem(key);
        });
        if (window.DEBUG_MODE) console.log('🗑️ All API Keys cleared');
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

/**
 * 更新 Settings 頁面的 LLM 連接狀態 UI（異步版本）
 */
async function updateLLMStatusUI() {
    const statusBadge = document.getElementById('llm-status-badge');
    if (!statusBadge) return;

    try {
        const currentKey = await APIKeyManager.getCurrentKey();

        if (currentKey && currentKey.key) {
            const providerNames = {
                'openai': 'OpenAI',
                'google_gemini': 'Gemini',
                'openrouter': 'OpenRouter'
            };
            const providerName = providerNames[currentKey.provider] || currentKey.provider;

            statusBadge.innerHTML = `
                <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                <span class="text-success">${providerName}</span>
            `;
            statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 border border-success/20';
        } else {
            statusBadge.innerHTML = `
                <span class="w-2 h-2 rounded-full bg-textMuted"></span>
                <span class="text-textMuted">Not Connected</span>
            `;
            statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10';
        }
    } catch (e) {
        console.error('[updateLLMStatusUI] Error:', e);
    }
}

// 頁面載入時更新狀態
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(updateLLMStatusUI, 100);
});
