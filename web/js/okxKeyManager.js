// ========================================
// OKX API Key Manager (BYOK Mode)
// Bring Your Own Keys - 前端安全管理
// ========================================
//
// 🔐 安全改進 / SECURITY IMPROVEMENT
// =====================================
// 本模組使用 Web Crypto API (AES-GCM) 進行真正的加密存儲。
// 加密密鑰從用戶會話令牌派生，只有在登入狀態下才能解密。
//
// 仍然存在的風險：
// - 在用戶登入期間，XSS 攻擊仍可能獲取解密後的憑證
// - 惡意瀏覽器擴展仍可能在運行時讀取憑證
//
// 建議：
// - 為您的 OKX API Key 設置 IP 白名單限制
// - 定期輪換 API Key
// - 使用只讀權限的 API Key（如果不需要交易功能）
//
// 最佳方案：使用後端代理來處理 OKX API 請求
// ========================================

class OKXKeyManager {
    constructor() {
        this.STORAGE_KEY = 'okx_api_credentials';
    }

    /**
     * 從用戶會話獲取加密密鑰
     * @returns {Promise<CryptoKey|null>}
     */
    async _getEncryptionKey() {
        try {
            // 從 AuthManager 獲取用戶令牌作為密鑰源
            const user = window.AuthManager?.currentUser;
            if (!user || !user.accessToken) {
                console.warn('[OKXKeyManager] 未登入，無法獲取加密密鑰');
                return null;
            }

            // 使用 PBKDF2 從令牌派生密鑰
            const encoder = new TextEncoder();
            const keyMaterial = await crypto.subtle.importKey(
                'raw',
                encoder.encode(user.accessToken),
                'PBKDF2',
                false,
                ['deriveKey']
            );

            // 派生 AES-GCM 密鑰
            const salt = encoder.encode('okx-key-encryption-salt');
            const key = await crypto.subtle.deriveKey(
                {
                    name: 'PBKDF2',
                    salt: salt,
                    iterations: 100000,
                    hash: 'SHA-256',
                },
                keyMaterial,
                { name: 'AES-GCM', length: 256 },
                false,
                ['encrypt', 'decrypt']
            );

            return key;
        } catch (e) {
            console.error('[OKXKeyManager] 獲取加密密鑰失敗', e);
            return null;
        }
    }

    /**
     * 加密數據
     * @param {string} data - 要加密的數據
     * @returns {Promise<string|null>} - Base64 編碼的加密數據
     */
    async _encrypt(data) {
        try {
            const key = await this._getEncryptionKey();
            if (!key) return null;

            const encoder = new TextEncoder();
            const iv = crypto.getRandomValues(new Uint8Array(12));
            const encrypted = await crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: iv },
                key,
                encoder.encode(data)
            );

            // 合併 IV 和加密數據
            const combined = new Uint8Array(iv.length + encrypted.byteLength);
            combined.set(iv);
            combined.set(new Uint8Array(encrypted), iv.length);

            return btoa(String.fromCharCode(...combined));
        } catch (e) {
            console.error('[OKXKeyManager] 加密失敗', e);
            return null;
        }
    }

    /**
     * 解密數據
     * @param {string} encryptedData - Base64 編碼的加密數據
     * @returns {Promise<string|null>} - 解密後的數據
     */
    async _decrypt(encryptedData) {
        try {
            const key = await this._getEncryptionKey();
            if (!key) return null;

            const combined = Uint8Array.from(atob(encryptedData), (c) => c.charCodeAt(0));
            const iv = combined.slice(0, 12);
            const data = combined.slice(12);

            const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv }, key, data);

            return new TextDecoder().decode(decrypted);
        } catch (e) {
            console.error('[OKXKeyManager] 解密失敗', e);
            return null;
        }
    }

    /**
     * 保存 OKX API 金鑰到 localStorage（加密存儲）
     * @param {Object} credentials - {api_key, secret_key, passphrase}
     */
    async saveCredentials(credentials) {
        if (!credentials.api_key || !credentials.secret_key || !credentials.passphrase) {
            throw new Error('所有 OKX API 憑證欄位都是必填的');
        }

        const encrypted = await this._encrypt(JSON.stringify(credentials));
        if (!encrypted) {
            throw new Error('無法加密憑證，請確保已登入');
        }

        localStorage.setItem(this.STORAGE_KEY, encrypted);
        console.log('[OKXKeyManager] 🔐 憑證已安全加密存儲');
    }

    /**
     * 從 localStorage 讀取 OKX API 金鑰（自動解密）
     * @returns {Promise<Object|null>} - {api_key, secret_key, passphrase} 或 null
     */
    async getCredentials() {
        const encrypted = localStorage.getItem(this.STORAGE_KEY);
        if (!encrypted) {
            return null;
        }

        try {
            const decrypted = await this._decrypt(encrypted);
            if (!decrypted) {
                console.warn('[OKXKeyManager] 無法解密憑證，可能需要重新登入');
                return null;
            }
            return JSON.parse(decrypted);
        } catch (e) {
            console.error('[OKXKeyManager] 讀取憑證失敗', e);
            return null;
        }
    }

    /**
     * 檢查是否已設置 OKX API 金鑰
     * @returns {boolean}
     */
    hasCredentials() {
        return !!localStorage.getItem(this.STORAGE_KEY);
    }

    /**
     * 清除已保存的 OKX API 金鑰
     */
    clearCredentials() {
        localStorage.removeItem(this.STORAGE_KEY);
        if (window.DEBUG_MODE) console.log('[OKXKeyManager] OKX 憑證已清除');
    }

    /**
     * 獲取 API 請求頭（包含憑證）- 異步版本
     * @returns {Promise<Object>} - 包含 OKX 憑證的 headers
     */
    async getAuthHeaders() {
        const credentials = await this.getCredentials();
        if (!credentials) {
            return {};
        }

        return {
            'X-OKX-API-KEY': credentials.api_key,
            'X-OKX-SECRET-KEY': credentials.secret_key,
            'X-OKX-PASSPHRASE': credentials.passphrase,
        };
    }

    /**
     * 驗證憑證是否有效（通過後端測試連接）
     * @param {Object} credentials - {api_key, secret_key, passphrase}
     * @returns {Promise<{valid: boolean, message: string}>}
     */
    async validateCredentials(credentials) {
        try {
            const response = await fetch('/api/okx/test-connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this._createTempAuthHeaders(credentials),
                },
            });

            const result = await response.json();
            return {
                valid: result.success === true,
                message: result.message || (result.success ? '驗證成功' : '驗證失敗'),
            };
        } catch (e) {
            console.error('[OKXKeyManager] 驗證失敗', e);
            return {
                valid: false,
                message: '無法連接到服務器: ' + e.message,
            };
        }
    }

    /**
     * 創建臨時認證頭（用於驗證時）
     * @private
     */
    _createTempAuthHeaders(credentials) {
        return {
            'X-OKX-API-KEY': credentials.api_key,
            'X-OKX-SECRET-KEY': credentials.secret_key,
            'X-OKX-PASSPHRASE': credentials.passphrase,
        };
    }

    /**
     * 獲取憑證狀態顯示信息 - 異步版本
     * @returns {Promise<Object>} - {hasKey: boolean, maskedKey: string}
     */
    async getStatus() {
        if (!this.hasCredentials()) {
            return {
                hasKey: false,
                maskedKey: '',
            };
        }

        try {
            const credentials = await this.getCredentials();
            if (!credentials) {
                return {
                    hasKey: false,
                    maskedKey: '',
                };
            }

            // 顯示前 4 位和後 4 位，中間用 * 遮蔽
            const maskKey = (key) => {
                if (!key || key.length < 8) return '****';
                return key.substring(0, 4) + '****' + key.substring(key.length - 4);
            };

            return {
                hasKey: true,
                maskedKey: maskKey(credentials.api_key),
            };
        } catch (e) {
            console.error('[OKXKeyManager] 獲取狀態失敗', e);
            return {
                hasKey: false,
                maskedKey: '',
            };
        }
    }
}

// 創建全局實例
window.OKXKeyManager = new OKXKeyManager();

/**
 * 更新 Settings 頁面的 OKX 連接狀態 UI
 */
function updateOKXStatusUI() {
    const okxKeyManager = window.OKXKeyManager;
    const statusBadge = document.getElementById('okx-status-badge');
    const notConnected = document.getElementById('okx-not-connected');
    const connected = document.getElementById('okx-connected');

    if (!statusBadge || !notConnected || !connected) return;

    if (okxKeyManager && okxKeyManager.hasCredentials()) {
        // 已連接狀態
        statusBadge.innerHTML = `
            <span class="w-2 h-2 rounded-full bg-success animate-pulse"></span>
            <span class="text-success">Connected</span>
        `;
        statusBadge.className =
            'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 border border-success/20';
        notConnected.classList.add('hidden');
        connected.classList.remove('hidden');
    } else {
        // 未連接狀態
        statusBadge.innerHTML = `
            <span class="w-2 h-2 rounded-full bg-textMuted"></span>
            <span class="text-textMuted">Not Connected</span>
        `;
        statusBadge.className =
            'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10';
        notConnected.classList.remove('hidden');
        connected.classList.add('hidden');
    }

    lucide.createIcons();
}

/**
 * 斷開 OKX 連接
 */
async function disconnectOKX() {
    const confirmed = await showConfirm({
        title: '斷開連接',
        message: '確定要斷開 OKX 連接嗎？\n\n您的 API 金鑰將從瀏覽器中移除。',
        type: 'danger',
        confirmText: '斷開',
        cancelText: '取消',
    });

    if (!confirmed) return;

    const okxKeyManager = window.OKXKeyManager;
    if (okxKeyManager) {
        okxKeyManager.clearCredentials();
    }

    // 更新 UI
    updateOKXStatusUI();

    // 如果在 Assets 頁面，也更新那邊的 UI
    if (typeof refreshAssets === 'function') {
        refreshAssets();
    }

    showToast('OKX 連接已斷開', 'success');
}

// 頁面載入時更新狀態
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(updateOKXStatusUI, 100);
});

if (window.DEBUG_MODE) console.log('[OKXKeyManager] OKX API 金鑰管理器已初始化（BYOK 模式）');
