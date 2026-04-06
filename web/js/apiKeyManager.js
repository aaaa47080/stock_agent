// ========================================
// apiKeyManager.js - 用戶 API Key 管理
// ========================================

/**
 * API Key 管理器 - 負責存儲和管理用戶的 LLM API Keys
 *
 * 🔐 安全架構 (v3):
 * - API Keys 加密儲存在後端資料庫
 * - 前端只保留 provider / 遮蔽資訊，不再取回完整後端金鑰
 * - 由後端在需要時代表使用者讀取解密後的 Key
 * - 支援離線模式降級到 localStorage
 */
const APIKeyManager = {
    // Storage keys (用於離線模式和 UI 顯示)
    STORAGE_KEYS: {
        SELECTED_PROVIDER: 'user_selected_provider',
        OFFLINE_MODE: 'api_key_offline_mode',
    },

    // 支援的 providers
    PROVIDERS: ['openai', 'google_gemini', 'anthropic', 'groq', 'openrouter'],

    // 內部緩存（遮蔽版本）
    _maskedKeysCache: null,
    _lastFetchTime: 0,
    CACHE_TTL: 30000, // 30 秒

    /**
     * 檢查是否應該使用後端儲存
     * @returns {boolean}
     */
    _shouldUseBackend() {
        const user = window.AuthManager?.currentUser;
        return !!(user && (user.user_id || user.uid));
    },

    /**
     * 獲取 API 基礎 URL
     * @returns {string}
     * @deprecated Use AppAPI directly without prepending base URL.
     *             AppAPI handles routing; other modules use bare paths like '/api/user/api-keys'.
     */
    _getApiBase() {
        return '';
    },



    /**
     * 設置 API Key（儲存到後端）
     * @param {string} provider - 'openai', 'google_gemini', etc.
     * @param {string} key - API key
     * @param {string} model - 可選的模型選擇
     */
    async setKey(provider, key, model = null) {
        if (!key || key.trim() === '') {
            return await this.removeKey(provider);
        }

        if (this._shouldUseBackend()) {
            try {
                // AppAPI.post() returns parsed JSON on success, throws on error
                await AppAPI.post('/api/user/api-keys', {
                    provider: provider,
                    api_key: key.trim(),
                    model: model,
                });

                this._maskedKeysCache = null;

                if (window.DEBUG_MODE) {
                    console.log(`🔐 ${provider} API Key saved to backend (encrypted)`);
                }

                return { success: true };
            } catch (e) {
                // Silently fall back — don't spam console on expected failures
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.warn('[APIKeyManager] Backend save failed, using localStorage:', e.message);
                return await this._setKeyLocalStorage(provider, key, model);
            }
        } else {
            // 未登入，使用 localStorage
            return await this._setKeyLocalStorage(provider, key, model);
        }
    },

    /**
     * localStorage 降級方案
     */
    async _setKeyLocalStorage(provider, key, model) {
        const encrypted = await this._encrypt(key.trim());
        localStorage.setItem(`user_${provider}_api_key`, encrypted);
        if (model) {
            localStorage.setItem(`user_${provider}_selected_model`, model);
        }
        localStorage.setItem(this.STORAGE_KEYS.OFFLINE_MODE, 'true');
        window.APP_CONFIG?.DEBUG_MODE &&
            console.log(`🔐 ${provider} API Key saved to localStorage (offline mode)`);
        return { success: true, offline: true };
    },

    async _getKeyLocalStorage(provider) {
        const stored = localStorage.getItem(`user_${provider}_api_key`);
        if (!stored || stored.trim() === '') return null;

        const decrypted = await this._decrypt(stored, `user_${provider}_api_key`);
        return decrypted && decrypted.trim() !== '' ? decrypted.trim() : null;
    },

    async _migrateLegacyLocalKeyIfNeeded(provider) {
        const localKey = localStorage.getItem(`user_${provider}_api_key`);
        if (!localKey || !localKey.startsWith('enc:')) return;

        const decrypted = await this._decrypt(localKey, `user_${provider}_api_key`);
        if (!decrypted) return;

        window.APP_CONFIG?.DEBUG_MODE &&
            console.log(`[APIKeyManager] 遷移 ${provider} key 到後端...`);
        await this.setKey(provider, decrypted);
        localStorage.removeItem(`user_${provider}_api_key`);
    },

    /**
     * 獲取所有 API Key 的遮蔽版本（用於 UI 顯示）
     * @returns {Promise<Object>}
     */
    async getAllKeysMasked() {
        // 使用緩存
        const now = Date.now();
        if (this._maskedKeysCache && now - this._lastFetchTime < this.CACHE_TTL) {
            return this._maskedKeysCache;
        }

        if (this._shouldUseBackend()) {
            try {
                for (const provider of this.PROVIDERS) {
                    await this._migrateLegacyLocalKeyIfNeeded(provider);
                }
                // AppAPI.get() returns parsed JSON directly on success, throws on error
                const data = await AppAPI.get('/api/user/api-keys');
                this._maskedKeysCache = data.keys;
                this._lastFetchTime = now;
                return data.keys;
            } catch (e) {
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.warn('[APIKeyManager] Failed to fetch masked keys:', e.message);
            }
        }

        // 降級：從 localStorage 構建遮蔽版本
        const result = {};
        for (const provider of this.PROVIDERS) {
            const key = await this._getKeyLocalStorage(provider);
            result[provider] = {
                has_key: !!key,
                masked_key: key ? this._maskKey(key) : null,
                model: localStorage.getItem(`user_${provider}_selected_model`),
                updated_at: null,
            };
        }
        return result;
    },

    /**
     * 移除 API Key
     * @param {string} provider
     */
    async removeKey(provider) {
        if (this._shouldUseBackend()) {
            try {
                // AppAPI.delete() returns parsed JSON on success, throws on error
                await AppAPI.delete(`/api/user/api-keys/${provider}`);

                this._maskedKeysCache = null;
                if (window.DEBUG_MODE) {
                    console.log(`🗑️ ${provider} API Key removed from backend`);
                }
                return { success: true };
            } catch (e) {
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.warn('[APIKeyManager] Backend delete failed:', e.message);
            }
        }

        // 降級或後端失敗，清除 localStorage
        localStorage.removeItem(`user_${provider}_api_key`);
        localStorage.removeItem(`user_${provider}_selected_model`);
        this._maskedKeysCache = null;
        return { success: true };
    },

    /**
     * 檢查是否有任何 API Key
     * @returns {Promise<boolean>}
     */
    async hasAnyKey() {
        const keys = await this.getAllKeysMasked();
        return Object.values(keys).some((k) => k.has_key);
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
     * 獲取當前有效的 provider。
     * 已登入時只回傳 provider，不再把完整後端 key 帶回前端。
     */
    async getCurrentProvider() {
        let provider = this.getSelectedProvider();

        if (this._shouldUseBackend()) {
            const keys = await this.getAllKeysMasked();
            if (provider && keys[provider]?.has_key) {
                return provider;
            }
            for (const p of this.PROVIDERS) {
                if (keys[p]?.has_key) {
                    this.setSelectedProvider(p);
                    return p;
                }
            }
            return null;
        }

        if (provider) {
            const key = await this._getKeyLocalStorage(provider);
            if (key) return provider;
        }

        for (const p of this.PROVIDERS) {
            const key = await this._getKeyLocalStorage(p);
            if (key) {
                this.setSelectedProvider(p);
                return p;
            }
        }

        return null;
    },

    /**
     * 設置用戶選擇的模型
     * @param {string} provider
     * @param {string} model
     */
    async setModelForProvider(provider, model) {
        if (!provider || !model) return;

        // 先保存到 localStorage（快速）
        localStorage.setItem(`user_${provider}_selected_model`, model.trim());

        // 然後同步到後端
        if (this._shouldUseBackend()) {
            try {
                await AppAPI.post('/api/user/api-keys/model', {
                    provider: provider,
                    model: model.trim(),
                });
            } catch (e) {
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.warn('[APIKeyManager] Failed to save model to backend:', e.message);
            }
        }

        window.APP_CONFIG?.DEBUG_MODE &&
            console.log(`✅ ${provider} selected model saved: ${model}`);
    },

    /**
     * 獲取用戶選擇的模型
     * @param {string} provider
     * @returns {string|null}
     */
    getModelForProvider(provider) {
        if (!provider) return null;
        const model = localStorage.getItem(`user_${provider}_selected_model`);
        return model && model.trim() !== '' ? model.trim() : null;
    },

    /**
     * 清除所有 keys
     */
    async clearAll() {
        for (const provider of this.PROVIDERS) {
            await this.removeKey(provider);
        }
        localStorage.removeItem(this.STORAGE_KEYS.SELECTED_PROVIDER);
        this._maskedKeysCache = null;
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
        } else if (provider === 'anthropic') {
            if (!trimmedKey.startsWith('sk-ant-')) {
                return { valid: false, message: 'Anthropic Key 應該以 sk-ant- 開頭' };
            }
        }

        return { valid: true, message: 'OK' };
    },

    /**
     * 遮蔽 API Key 用於顯示
     * @param {string} key
     * @returns {string}
     */
    _maskKey(key) {
        if (!key || key.length < 8) return '****';
        const prefixLen = Math.min(4, Math.floor(key.length / 4));
        const suffixLen = Math.min(4, Math.floor(key.length / 4));
        return `${key.slice(0, prefixLen)}****...****${key.slice(-suffixLen)}`;
    },

    // ========================================
    // 加密功能（用於 localStorage 降級方案）
    // ========================================

    ENCRYPTION_VERSION: 'v2',

    async _getEncryptionKey() {
        try {
            const user = window.AuthManager?.currentUser;
            if (!user) return null;

            const stableId = user.user_id || user.uid || user.pi_uid;
            if (!stableId) return null;

            const encoder = new TextEncoder();
            const keyMaterial = await crypto.subtle.importKey(
                'raw',
                encoder.encode(stableId),
                'PBKDF2',
                false,
                ['deriveKey']
            );

            return await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: encoder.encode('llm-key-encryption-salt-v2'),
                    iterations: 100000,
                    hash: 'SHA-256',
                },
                keyMaterial,
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt', 'decrypt']
            );
        } catch (e) {
            return null;
        }
    },

    async _encrypt(data) {
        try {
            const key = await this._getEncryptionKey();
            if (!key) return data;

            const encoder = new TextEncoder();
            const iv = crypto.getRandomValues(new Uint8Array(12));
            const encrypted = await crypto.subtle.encrypt(
                { name: 'AES-GCM', iv },
                key,
                encoder.encode(data)
            );

            const combined = new Uint8Array(iv.length + encrypted.byteLength);
            combined.set(iv);
            combined.set(new Uint8Array(encrypted), iv.length);

            return 'enc:' + this.ENCRYPTION_VERSION + ':' + btoa(String.fromCharCode(...combined));
        } catch (e) {
            return data;
        }
    },

    async _decrypt(encryptedData, storageKey = null) {
        if (!encryptedData.startsWith('enc:')) return encryptedData;

        let version = 'v1';
        let data = encryptedData.slice(4);

        if (data.startsWith('v2:')) {
            version = 'v2';
            data = data.slice(3);
        }

        try {
            const key = version === 'v2' ? await this._getEncryptionKey() : null;
            if (!key) return null;

            const combined = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
            const iv = combined.slice(0, 12);
            const encrypted = combined.slice(12);

            const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, encrypted);
            return new TextDecoder().decode(decrypted);
        } catch (e) {
            return null;
        }
    },
};

// Export to global scope
window.APIKeyManager = APIKeyManager;

/**
 * 更新 Settings 頁面的 LLM 連接狀態 UI
 */
async function updateLLMStatusUI() {
    const statusBadge = document.getElementById('llm-status-badge');
    if (!statusBadge) return;

    try {
        const keys = await APIKeyManager.getAllKeysMasked();
        const hasAny = Object.values(keys).some((k) => k.has_key);

        if (hasAny) {
            // 找到有 key 的 provider
            let activeProvider = null;
            for (const [provider, info] of Object.entries(keys)) {
                if (info.has_key) {
                    activeProvider = provider;
                    break;
                }
            }

            const providerNames = {
                openai: 'OpenAI',
                google_gemini: 'Gemini',
                anthropic: 'Anthropic',
                groq: 'Groq',
                openrouter: 'OpenRouter',
            };
            const providerName = providerNames[activeProvider] || activeProvider;

            statusBadge.innerHTML = `
                <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
                <span class="text-success">${providerName}</span>
            `;
            statusBadge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 border border-success/20';
        } else {
            statusBadge.innerHTML = `
                <span class="w-2 h-2 rounded-full bg-textMuted"></span>
                <span class="text-textMuted">Not Connected</span>
            `;
            statusBadge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10';
        }
    } catch (e) {
        console.error('[updateLLMStatusUI] Error:', e);
    }
}

// 暴露到全域供其他模組使用
window.updateLLMStatusUI = updateLLMStatusUI;

// 頁面載入時更新狀態
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(updateLLMStatusUI, 100);
});

// 登入成功後自動刷新 Key 狀態（Pi 登入 & 頁面重載恢復登入）
['pi-auth-success', 'auth:ready'].forEach((event) => {
    window.addEventListener(event, () => {
        APIKeyManager._maskedKeysCache = null;
        APIKeyManager._lastFetchTime = 0;
        setTimeout(updateLLMStatusUI, 400);
    });
});

export {
    APIKeyManager,
    updateLLMStatusUI,
};
