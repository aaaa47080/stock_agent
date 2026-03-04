// ========================================
// OKX API Key Manager (BYOK Mode)
// Bring Your Own Keys - 前端安全管理
// ========================================
//
// ⚠️ 安全警告 / SECURITY WARNING ⚠️
// =====================================
// 本模組使用 Base64 編碼存儲 OKX API 憑證，這不是真正的加密！
// Base64 編碼可以被輕易解碼（使用 atob() 函數）。
//
// 風險：
// - 任何能存取瀏覽器 localStorage 的人都可以取得您的 API 憑證
// - XSS 攻擊可以竊取完整的 OKX 交易權限
// - 惡意瀏覽器擴展可以讀取這些憑證
//
// 建議：
// - 只在您信任的設備上使用此功能
// - 為您的 OKX API Key 設置 IP 白名單限制
// - 定期輪換 API Key
// - 使用只讀權限的 API Key（如果不需要交易功能）
//
// 未來改進：應該使用後端代理來處理 OKX API 請求
// ========================================

class OKXKeyManager {
    constructor() {
        this.STORAGE_KEY = 'okx_api_credentials';
    }

    /**
     * 保存 OKX API 金鑰到 localStorage
     * ⚠️ 警告：Base64 編碼不是加密，憑證可被輕易解碼
     * @param {Object} credentials - {api_key, secret_key, passphrase}
     */
    saveCredentials(credentials) {
        if (!credentials.api_key || !credentials.secret_key || !credentials.passphrase) {
            throw new Error('所有 OKX API 憑證欄位都是必填的');
        }

        // ⚠️ 安全警告：Base64 不是加密！
        // 這只是混淆，任何人都可以使用 atob() 解碼
        // 強烈建議為 API Key 設置 IP 白名單和權限限制
        const encoded = btoa(JSON.stringify(credentials));
        localStorage.setItem(this.STORAGE_KEY, encoded);

        console.warn('[OKXKeyManager] ⚠️ 憑證已存儲（Base64 編碼，非加密）。請確保您的 API Key 已設置適當的權限限制。');
    }

    /**
     * 從 localStorage 讀取 OKX API 金鑰
     * @returns {Object|null} - {api_key, secret_key, passphrase} 或 null
     */
    getCredentials() {
        const encoded = localStorage.getItem(this.STORAGE_KEY);
        if (!encoded) {
            return null;
        }

        try {
            // 注意：Base64 可以被任何人解碼
            const decoded = atob(encoded);
            return JSON.parse(decoded);
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
        return !!this.getCredentials();
    }

    /**
     * 清除已保存的 OKX API 金鑰
     */
    clearCredentials() {
        localStorage.removeItem(this.STORAGE_KEY);
        console.log('[OKXKeyManager] OKX 憑證已清除');
    }

    /**
     * 獲取 API 請求頭（包含憑證）
     * @returns {Object} - 包含 OKX 憑證的 headers
     */
    getAuthHeaders() {
        const credentials = this.getCredentials();
        if (!credentials) {
            return {};
        }

        return {
            'X-OKX-API-KEY': credentials.api_key,
            'X-OKX-SECRET-KEY': credentials.secret_key,
            'X-OKX-PASSPHRASE': credentials.passphrase
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
                    ...this._createTempAuthHeaders(credentials)
                }
            });

            const result = await response.json();
            return {
                valid: result.success === true,
                message: result.message || (result.success ? '驗證成功' : '驗證失敗')
            };
        } catch (e) {
            console.error('[OKXKeyManager] 驗證失敗', e);
            return {
                valid: false,
                message: '無法連接到服務器: ' + e.message
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
            'X-OKX-PASSPHRASE': credentials.passphrase
        };
    }

    /**
     * 獲取憑證狀態顯示信息
     * @returns {Object} - {hasKey: boolean, maskedKey: string}
     */
    getStatus() {
        const credentials = this.getCredentials();
        if (!credentials) {
            return {
                hasKey: false,
                maskedKey: ''
            };
        }

        // 顯示前 4 位和後 4 位，中間用 * 遮蔽
        const maskKey = (key) => {
            if (!key || key.length < 8) return '****';
            return key.substring(0, 4) + '****' + key.substring(key.length - 4);
        };

        return {
            hasKey: true,
            maskedKey: maskKey(credentials.api_key)
        };
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
        statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 border border-success/20';
        notConnected.classList.add('hidden');
        connected.classList.remove('hidden');
    } else {
        // 未連接狀態
        statusBadge.innerHTML = `
            <span class="w-2 h-2 rounded-full bg-textMuted"></span>
            <span class="text-textMuted">Not Connected</span>
        `;
        statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10';
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
        cancelText: '取消'
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

console.log('[OKXKeyManager] OKX API 金鑰管理器已初始化（BYOK 模式）');
