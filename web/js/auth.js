// ========================================
// auth.js - 用戶身份認證模塊 (簡潔穩定版)
// ========================================

const DebugLog = {
    send(level, message, data = null) {
        console.log(`[${level.toUpperCase()}] ${message}`, data);
        // 在开发环境中记录日志，在生产环境中可选择禁用
        // 为了减少网络请求，仅在特定条件下发送到服务器
        if (window.APP_CONFIG && window.APP_CONFIG.DEBUG_MODE === true) {
            fetch('/api/debug/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level, message, data }),
                keepalive: true
            }).catch(() => { });
        }
    },
    info(msg, data) { this.send('info', msg, data); },
    error(msg, data) { this.send('error', msg, data); },
    warn(msg, data) { this.send('warn', msg, data); }
};

window.DebugLog = DebugLog;

const AuthManager = {
    currentUser: null,
    piInitialized: false,
    _refreshTimer: null,

    // Token 過期時間（7 天，與後端 ACCESS_TOKEN_EXPIRE_MINUTES 一致）
    TOKEN_EXPIRY_MS: 7 * 24 * 60 * 60 * 1000,

    // 在過期前多久開始刷新（1 天）
    REFRESH_BEFORE_EXPIRY_MS: 24 * 60 * 60 * 1000,

    /**
     * 檢查 token 是否過期
     * @returns {boolean} true = 已過期, false = 未過期
     */
    isTokenExpired() {
        if (!this.currentUser) return true;

        const expiry = this.currentUser.accessTokenExpiry;
        if (!expiry) {
            // 沒有過期時間，假設已過期（舊格式 token）
            return true;
        }

        return Date.now() > expiry;
    },

    /**
     * 檢查 token 是否即將過期（1 小時內）
     * @returns {boolean} true = 即將過期
     */
    isTokenExpiringSoon() {
        if (!this.currentUser) return true;

        const expiry = this.currentUser.accessTokenExpiry;
        if (!expiry) return true;

        const oneHour = 60 * 60 * 1000;
        return (expiry - Date.now()) < oneHour;
    },

    /**
     * 檢查 token 是否需要刷新（過期前 1 天內）
     * @returns {boolean} true = 需要刷新
     */
    needsRefresh() {
        if (!this.currentUser) return false;

        const expiry = this.currentUser.accessTokenExpiry;
        if (!expiry) return false;

        const timeUntilExpiry = expiry - Date.now();
        // 在過期前 REFRESH_BEFORE_EXPIRY_MS 毫秒內需要刷新
        return timeUntilExpiry > 0 && timeUntilExpiry < this.REFRESH_BEFORE_EXPIRY_MS;
    },

    /**
     * 清除過期的 token 並導向登入
     */
    clearExpiredToken() {
        DebugLog.warn('Token 已過期，清除並導向登入');
        this.currentUser = null;
        localStorage.removeItem('pi_user');
        this._updateUI(false);

        // 顯示提示
        if (typeof showToast === 'function') {
            showToast('登入已過期，請重新登入', 'warning');
        }

        // 重整頁面以顯示登入 modal
        window.location.reload();
    },

    /**
     * 啟動 token 自動刷新定時器
     * 每小時檢查一次，如果 token 快過期則自動刷新
     */
    startTokenRefreshTimer() {
        // 清除舊的定時器
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
        }

        // 每小時檢查一次
        this._refreshTimer = setInterval(async () => {
            if (!this.currentUser) return;

            DebugLog.info('Token refresh check', {
                needsRefresh: this.needsRefresh(),
                isExpired: this.isTokenExpired(),
                timeUntilExpiry: this.currentUser.accessTokenExpiry
                    ? Math.round((this.currentUser.accessTokenExpiry - Date.now()) / 1000 / 60) + ' minutes'
                    : 'unknown'
            });

            if (this.isTokenExpired()) {
                // Token 已過期，嘗試自動刷新
                DebugLog.info('Token 已過期，嘗試自動刷新');
                await this.silentRefresh();
            } else if (this.needsRefresh()) {
                // Token 快過期，提前刷新
                DebugLog.info('Token 快過期，提前刷新');
                await this.silentRefresh();
            }
        }, 60 * 60 * 1000); // 每小時檢查一次

        DebugLog.info('Token refresh timer started');
    },

    /**
     * 靜默刷新 token（使用 Pi SDK 重新認證）
     * @returns {Promise<{success: boolean, error?: string}>}
     */
    async silentRefresh() {
        // 只有 Pi 用戶才能靜默刷新
        if (!this.currentUser?.pi_uid) {
            DebugLog.warn('非 Pi 用戶，無法靜默刷新');
            return { success: false, error: 'Not a Pi user' };
        }

        // 檢查是否在 Pi Browser 環境
        if (!this.isPiBrowser()) {
            DebugLog.warn('非 Pi Browser 環境，無法靜默刷新');
            return { success: false, error: 'Not in Pi Browser' };
        }

        try {
            DebugLog.info('開始靜默刷新 token...');

            // 確保 Pi SDK 已初始化
            if (!this.piInitialized) {
                this.initPiSDK();
            }

            // 重新調用 Pi SDK 認證
            const auth = await Pi.authenticate(['username', 'payments', 'wallet_address'], (payment) => {
                DebugLog.warn('刷新時發現未完成的支付', payment);
            });

            DebugLog.info('Pi SDK 重新認證成功', { username: auth.user.username });

            // 同步到後端獲取新的 JWT
            const res = await fetch('/api/user/pi-sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pi_uid: auth.user.uid,
                    username: auth.user.username,
                    access_token: auth.accessToken
                })
            });

            if (!res.ok) {
                const result = await res.json();
                throw new Error(result.detail || 'Sync failed');
            }

            const syncResult = await res.json();

            // 更新本地用戶資料
            this.currentUser = {
                ...this.currentUser,
                accessToken: syncResult.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
                piAccessToken: auth.accessToken
            };

            localStorage.setItem('pi_user', JSON.stringify(this.currentUser));

            DebugLog.info('Token 靜默刷新成功', {
                newExpiry: new Date(this.currentUser.accessTokenExpiry).toISOString()
            });

            return { success: true };
        } catch (error) {
            DebugLog.error('靜默刷新失敗', { error: error.message });
            return { success: false, error: error.message };
        }
    },

    /**
     * 停止 token 自動刷新定時器
     */
    stopTokenRefreshTimer() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
            this._refreshTimer = null;
            DebugLog.info('Token refresh timer stopped');
        }
    },

    initPiSDK() {
        if (this.piInitialized) {
            DebugLog.info('initPiSDK: 已初始化，跳過');
            return true;
        }
        if (window.Pi) {
            try {
                // Official Guide: Initialize SDK early. Use sandbox: true for development.
                Pi.init({ version: "2.0", sandbox: false });
                this.piInitialized = true;
                DebugLog.info('Pi SDK 初始化成功 (Sandbox Mode)');
                return true;
            } catch (e) {
                DebugLog.error('Pi SDK 初始化失敗', { error: e.message, stack: e.stack });
                return false;
            }
        }
        DebugLog.warn('initPiSDK: window.Pi 不存在');
        return false;
    },

    isPiBrowser() {
        // 同步檢測：Pi SDK 必須存在且有必要方法
        const hasPiSDK = typeof window.Pi !== 'undefined' &&
            window.Pi !== null &&
            typeof window.Pi.authenticate === 'function' &&
            typeof window.Pi.init === 'function';

        DebugLog.info('isPiBrowser 同步檢測', {
            userAgent: navigator.userAgent,
            hasPiSDK: hasPiSDK,
            hasAuthMethod: typeof window.Pi?.authenticate === 'function',
            hasInitMethod: typeof window.Pi?.init === 'function',
            result: hasPiSDK
        });
        return hasPiSDK;
    },

    // 異步快速檢測 Pi Browser 環境是否有效
    // 注意：nativeFeaturesList 在某些 Pi Browser 版本中可能不可用，
    // 但只要 Pi SDK 存在（有 authenticate 和 init 方法），就應該允許用戶嘗試登入
    async verifyPiBrowserEnvironment() {
        if (!this.isPiBrowser()) {
            return { valid: false, reason: 'Pi SDK 不存在' };
        }

        // Pi SDK 存在，嘗試初始化
        try {
            this.initPiSDK();
        } catch (e) {
            DebugLog.warn('Pi SDK 初始化失敗', { error: e.message });
        }

        // 嘗試使用 nativeFeaturesList 做額外驗證（可選）
        // 如果可用就使用，不可用也沒關係，因為 Pi SDK 已經存在
        if (typeof window.Pi.nativeFeaturesList === 'function') {
            try {
                const QUICK_TIMEOUT = 1500;
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('TIMEOUT')), QUICK_TIMEOUT);
                });

                const features = await Promise.race([Pi.nativeFeaturesList(), timeoutPromise]);
                DebugLog.info('Pi Browser 環境驗證成功 (nativeFeaturesList)', { features });
                return { valid: true, features };
            } catch (error) {
                // nativeFeaturesList 失敗不應阻止登入，因為 Pi SDK 已存在
                DebugLog.warn('nativeFeaturesList 驗證失敗，但 Pi SDK 存在，允許繼續', { error: error.message });
            }
        } else {
            DebugLog.info('nativeFeaturesList 不可用，但 Pi SDK 存在，允許繼續');
        }

        // Pi SDK 存在，允許用戶嘗試登入
        // 真正的認證會由 Pi.authenticate() 處理
        return { valid: true, reason: 'Pi SDK 已載入' };
    },

    isLoggedIn() {
        return !!this.currentUser;
    },

    async loginAsMockUser() {
        console.log("⚠️ [Dev Mode] Manually triggering Mock Login.");
        showToast('開發模式：使用測試帳號登入...', 'info');

        await new Promise(r => setTimeout(r, 500)); // 模擬延遲

        try {
            // 使用新的 Dev Login Endpoint
            const res = await fetch('/api/user/dev-login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await res.json();

            if (!res.ok) {
                showToast(result.detail || 'Test Mode disabled', 'error');
                return { success: false, error: result.detail };
            }

            this.currentUser = {
                uid: result.user.uid,
                user_id: result.user.uid,
                username: result.user.username,
                accessToken: result.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
                authMethod: result.user.authMethod
            };

            localStorage.setItem('pi_user', JSON.stringify(this.currentUser));
            this._updateUI(true);

            if (typeof initChat === 'function') initChat();
            return { success: true, user: this.currentUser };

        } catch (e) {
            console.error("Mock login error:", e);
            showToast('模擬登入失敗', 'error');
            return { success: false, error: e.message };
        }
    },

    async authenticateWithPi() {
        DebugLog.info('authenticateWithPi 開始', {
            piInitialized: this.piInitialized,
            hasPiSDK: !!window.Pi
        });

        try {
            if (!this.piInitialized) {
                DebugLog.info('初始化 Pi SDK...');
                this.initPiSDK();
            }

            DebugLog.info('呼叫 Pi.authenticate...');

            // 呼叫 Pi SDK 認證 (包含 payments 權限) - 60 秒超時（用戶需要時間確認授權視窗）
            const AUTH_TIMEOUT = 60000;

            const authPromise = Pi.authenticate(['username', 'payments', 'wallet_address'], (payment) => {
                DebugLog.warn('發現未完成的支付', payment);
                fetch('/api/user/payment/complete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paymentId: payment.identifier, txid: payment.transaction.txid })
                });
            });

            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => {
                    DebugLog.error('Pi.authenticate 超時', { timeout: AUTH_TIMEOUT });
                    reject(new Error('Pi 認證超時，請確認 Pi Browser 是否有彈出授權視窗'));
                }, AUTH_TIMEOUT);
            });

            const auth = await Promise.race([authPromise, timeoutPromise]);

            DebugLog.info('Pi 認證成功', { username: auth.user.username, uid: auth.user.uid });

            // 同步到後端
            const res = await fetch('/api/user/pi-sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pi_uid: auth.user.uid,
                    username: auth.user.username,
                    access_token: auth.accessToken
                })
            });

            const syncResult = await res.json();
            if (!res.ok) {
                const detail = syncResult.detail;
                const msg = Array.isArray(detail)
                    ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
                    : (typeof detail === 'string' ? detail : 'Sync failed');
                throw new Error(msg);
            }

            this.currentUser = {
                uid: syncResult.user.user_id,
                user_id: syncResult.user.user_id,
                username: syncResult.user.username,
                accessToken: syncResult.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
                authMethod: syncResult.user.auth_method,
                role: syncResult.user.role || 'user',
                membership_tier: syncResult.user.membership_tier || 'free',
                pi_uid: auth.user.uid,
                pi_username: auth.user.username,
                piAccessToken: auth.accessToken
            };

            localStorage.setItem('pi_user', JSON.stringify(this.currentUser));

            // 啟動 token 自動刷新定時器
            this.startTokenRefreshTimer();
            // Note: _updateUI is NOT called here because handlePiLogin() will
            // call window.location.reload() immediately after. The reload will
            // trigger init() which calls _updateUI(true) naturally.
            // Calling _updateUI(true) here would flash the app behind the
            // login modal before the reload, causing the "two screens" effect.

            DebugLog.info('Pi 登入流程完成', { user: this.currentUser });
            return { success: true, user: this.currentUser };
        } catch (error) {
            DebugLog.error('authenticateWithPi 失敗', {
                error: error.message,
                stack: error.stack,
                piExists: !!window.Pi
            });
            return { success: false, error: error.message };
        }
    },

    async init() {
        // 檢查 URL 參數是否要求強制登出
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('logout') === '1' || urlParams.get('force_logout') === '1') {
            DebugLog.info('URL 參數觸發強制登出');
            localStorage.removeItem('pi_user');
            window.history.replaceState({}, '', window.location.pathname);
            window.location.reload();
            return false;
        }

        // 優先從 localStorage 載入用戶（同步，確保立即可用）
        const savedUser = localStorage.getItem('pi_user');
        if (savedUser) {
            try {
                this.currentUser = JSON.parse(savedUser);

                // 檢查 token 是否過期
                if (this.isTokenExpired()) {
                    DebugLog.warn('Token 已過期，清除並導向登入');
                    this.clearExpiredToken();
                    return false;
                }

                this._updateUI(true);
            } catch (e) {
                localStorage.removeItem('pi_user');
            }
        } else {
            this._updateUI(false);
        }

        // 檢查測試模式（async，但不影響已登入用戶）
        try {
            const configRes = await fetch('/api/config');
            const config = await configRes.json();

            // Show/hide dev-user-switcher based on test_mode
            const switcher = document.getElementById('dev-user-switcher');
            if (switcher) {
                if (config.test_mode) {
                    switcher.classList.remove('hidden');
                } else {
                    switcher.classList.add('hidden');
                }
            }

            if (config.test_mode && !this.currentUser) {
                console.log('🧪 [Test Mode] 自動登入測試用戶（透過 dev-login endpoint）');
                const result = await this.loginAsMockUser();
                if (!result.success) {
                    console.warn('🧪 [Test Mode] 自動登入失敗:', result.error);
                }
            }
        } catch (e) {
            console.warn('Failed to check test mode:', e);
        }

        // Ensure Pi SDK is initialized on startup
        this.initPiSDK();

        // 啟動 token 自動刷新定時器（僅對已登入的 Pi 用戶）
        if (this.currentUser?.pi_uid) {
            this.startTokenRefreshTimer();

            // 如果 token 快過期，立即嘗試刷新
            if (this.needsRefresh()) {
                DebugLog.info('Token 快過期，啟動時立即刷新');
                this.silentRefresh().catch(e => {
                    DebugLog.warn('啟動時刷新失敗，將在定時器中重試', { error: e.message });
                });
            }
        }

        return !!this.currentUser;
    },

    _updateUI(isLoggedIn) {
        const username = this.currentUser?.username || 'Guest';
        const uid = this.currentUser?.uid || this.currentUser?.user_id || '--';
        const authMethod = this.currentUser?.authMethod || 'guest';

        // 控制 auth-only 和 guest-only 元素的顯示
        document.querySelectorAll('.auth-only').forEach(el => {
            if (isLoggedIn) {
                el.classList.remove('hidden');
            } else {
                el.classList.add('hidden');
            }
        });
        document.querySelectorAll('.guest-only').forEach(el => {
            if (isLoggedIn) {
                el.classList.add('hidden');
            } else {
                el.classList.remove('hidden');
            }
        });

        // 更新所有可能存在的使用者名稱欄位
        ['sidebar-user-name', 'forum-user-name', 'profile-username', 'nav-username'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = username;
        });

        // 更新所有有 user-display-name class 的元素
        document.querySelectorAll('.user-display-name').forEach(el => {
            el.textContent = username;
        });

        // 更新 UID 顯示
        const uidEl = document.getElementById('profile-uid');
        if (uidEl) {
            uidEl.textContent = isLoggedIn ? `UID: ${uid}` : 'UID: --';
        }

        // 更新登入方式顯示
        const methodEl = document.getElementById('profile-method');
        if (methodEl) {
            const methodText = authMethod === 'pi_network' ? 'PI WALLET' :
                authMethod === 'password' ? 'PASSWORD' : 'GUEST';
            methodEl.textContent = methodText;
        }

        // 更新頭像
        ['sidebar-user-avatar', 'forum-user-avatar', 'profile-avatar', 'nav-avatar'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                if (isLoggedIn) {
                    el.textContent = username[0].toUpperCase();
                    el.classList.add('bg-gradient-to-br', 'from-primary', 'to-accent', 'text-background');
                } else {
                    el.innerHTML = '<i data-lucide="user" class="w-4 h-4"></i>';
                    el.classList.remove('bg-gradient-to-br', 'from-primary', 'to-accent', 'text-background');
                }
            }
        });

        // 控制登入 Modal 顯示
        const modal = document.getElementById('login-modal');
        if (modal) {
            if (isLoggedIn) modal.classList.add('hidden');
            else modal.classList.remove('hidden');
        }

        // 更新會員狀態顯示
        if (isLoggedIn && typeof loadPremiumStatus === 'function') {
            loadPremiumStatus();
        }

        // 登入後重新初始化通知服務（取得真實通知 + 連接 WebSocket）
        if (isLoggedIn && window.NotificationService) {
            window.NotificationService.init();
        }

        // 重新渲染導覽列（根據 role 顯示/隱藏 admin tab）
        if (typeof renderNavButtons === 'function') renderNavButtons();
        if (window.GlobalNav && typeof GlobalNav.renderNavButtons === 'function') GlobalNav.renderNavButtons();

        if (window.lucide) lucide.createIcons();
    },

    logout() {
        this.stopTokenRefreshTimer();
        this.currentUser = null;
        localStorage.removeItem('pi_user');
        this._updateUI(false);
        window.location.reload();
    }
};

// 工具函式
function isPiBrowser() {
    // 嚴格檢測：Pi SDK 必須存在且有必要方法
    const hasPiSDK = typeof window.Pi !== 'undefined' &&
        window.Pi !== null &&
        typeof window.Pi.authenticate === 'function' &&
        typeof window.Pi.init === 'function';
    return hasPiSDK;
}

function canMakePiPayment() {
    if (!AuthManager.currentUser) return false;
    // 有 pi_uid 表示已綁定錢包或用 Pi 登入
    if (AuthManager.currentUser.pi_uid) return true;
    // 沒有綁定但在開發環境中模擬
    if (!isPiBrowser()) return true;
    return false;
}

// 獲取錢包狀態（從後端 API）- 含超時機制
async function getWalletStatus() {
    const uid = AuthManager.currentUser?.uid || AuthManager.currentUser?.user_id;
    if (!uid) {
        return { has_wallet: false, auth_method: 'guest' };
    }

    const TIMEOUT_MS = 10000; // 10 秒超時

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

        const token = AuthManager.currentUser?.accessToken;
        const res = await fetch(`/api/user/wallet-status/${uid}`, {
            signal: controller.signal,
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
            console.error('Wallet status API error:', res.status);
            return { has_wallet: false, auth_method: 'unknown' };
        }
        const data = await res.json();
        return {
            has_wallet: data.has_wallet || false,
            pi_uid: data.pi_uid || null,
            pi_username: data.pi_username || null,
            auth_method: data.auth_method || 'password'
        };
    } catch (e) {
        if (e.name === 'AbortError') {
            console.error('getWalletStatus timeout after', TIMEOUT_MS, 'ms');
        } else {
            console.error('getWalletStatus error:', e);
        }
        return { has_wallet: false, auth_method: 'unknown' };
    }
}

// 綁定 Pi 錢包（含快速環境檢測）
async function linkPiWallet() {
    const TIMEOUT_MS = 3000; // 3秒超時（快速反饋）

    if (!AuthManager.currentUser) {
        if (typeof showToast === 'function') showToast('請先登入', 'warning');
        return { success: false, error: '請先登入' };
    }

    // 第一步：同步檢測 Pi SDK 是否存在
    if (!isPiBrowser()) {
        const msg = '請在 Pi Browser 中開啟此頁面以綁定錢包';
        if (typeof showAlert === 'function') {
            await showAlert({ title: '提示', message: msg, type: 'warning' });
        } else {
            alert(msg);
        }
        return { success: false, error: msg };
    }

    // 第二步：快速驗證 Pi Browser 環境是否有效
    const envCheck = await AuthManager.verifyPiBrowserEnvironment();
    if (!envCheck.valid) {
        if (typeof showAlert === 'function') {
            await showAlert({
                title: 'Pi Browser 環境異常',
                message: '無法連接到 Pi Network。\n\n請確認已登入 Pi 帳號且網路連線正常。',
                type: 'warning'
            });
        } else if (typeof showToast === 'function') {
            showToast('Pi Browser 環境異常', 'warning');
        }
        return { success: false, error: 'Pi Browser 環境異常' };
    }

    // 顯示連接中提示
    if (typeof showToast === 'function') showToast('正在連接 Pi 錢包...', 'info', 0);

    try {
        AuthManager.initPiSDK();

        // 使用 Promise.race 實現超時
        const authPromise = Pi.authenticate(['username', 'payments', 'wallet_address'], (payment) => {
            console.warn('Incomplete payment found during wallet link:', payment);
        });

        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('TIMEOUT')), TIMEOUT_MS);
        });

        const auth = await Promise.race([authPromise, timeoutPromise]);

        // 移除連接中提示（如果有持續的 toast）
        const toastContainer = document.getElementById('toast-container');
        if (toastContainer) toastContainer.innerHTML = '';

        console.log('Pi Auth for wallet link:', auth.user.username);

        // 呼叫後端 API 綁定錢包
        const uid = AuthManager.currentUser.uid || AuthManager.currentUser.user_id;
        const res = await fetch('/api/user/link-wallet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: uid,
                pi_uid: auth.user.uid,
                pi_username: auth.user.username,
                access_token: auth.accessToken
            })
        });

        const result = await res.json();

        if (!res.ok) {
            throw new Error(result.detail || '綁定失敗');
        }

        // 更新本地用戶資料
        AuthManager.currentUser.pi_uid = auth.user.uid;
        AuthManager.currentUser.pi_username = auth.user.username;
        localStorage.setItem('pi_user', JSON.stringify(AuthManager.currentUser));

        if (typeof showToast === 'function') showToast('Pi 錢包綁定成功！', 'success');

        return { success: true, pi_uid: auth.user.uid, pi_username: auth.user.username };

    } catch (error) {
        // 移除連接中提示
        const toastContainer = document.getElementById('toast-container');
        if (toastContainer) toastContainer.innerHTML = '';

        if (error.message === 'TIMEOUT') {
            // 超時：顯示重試對話框
            const retry = typeof showConfirm === 'function' ? await showConfirm({
                title: '連接超時',
                message: '無法連接到 Pi 錢包，請確認您正在使用 Pi Browser。\n\n是否重試？',
                type: 'warning',
                confirmText: '重試',
                cancelText: '取消'
            }) : confirm('連接超時，是否重試？');

            if (retry) {
                return linkPiWallet(); // 遞迴重試
            }
            return { success: false, error: '連接超時' };
        }

        console.error('linkPiWallet error:', error);
        if (typeof showToast === 'function') showToast('綁定失敗: ' + error.message, 'error');
        return { success: false, error: error.message };
    }
}

// 載入 Settings 頁面的錢包狀態
async function loadSettingsWalletStatus() {
    const statusBadge = document.getElementById('settings-wallet-status-badge');
    const notLinkedSection = document.getElementById('wallet-not-linked');
    const linkedSection = document.getElementById('wallet-linked');
    const usernameEl = document.getElementById('settings-wallet-username');
    const walletIcon = document.getElementById('settings-wallet-icon');

    // 如果元素不存在（Settings 頁面未載入），直接返回
    if (!statusBadge) return;

    try {
        const status = await getWalletStatus();

        if (status.has_wallet || status.auth_method === 'pi_network') {
            // 已綁定或 Pi 登入
            statusBadge.innerHTML = `
                <i data-lucide="check-circle" class="w-3 h-3"></i>
                已連接
            `;
            statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 text-success';

            if (walletIcon) {
                walletIcon.innerHTML = '<i data-lucide="wallet" class="w-5 h-5 text-success"></i>';
                walletIcon.className = 'w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center';
            }

            if (notLinkedSection) notLinkedSection.classList.add('hidden');
            if (linkedSection) linkedSection.classList.remove('hidden');
            if (usernameEl && status.pi_username) {
                usernameEl.textContent = `@${status.pi_username}`;
            }
        } else {
            // 未綁定
            statusBadge.innerHTML = `
                <i data-lucide="link-2-off" class="w-3 h-3"></i>
                未綁定
            `;
            statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';

            if (walletIcon) {
                walletIcon.innerHTML = '<i data-lucide="wallet" class="w-5 h-5 text-primary"></i>';
                walletIcon.className = 'w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center';
            }

            if (notLinkedSection) notLinkedSection.classList.remove('hidden');
            if (linkedSection) linkedSection.classList.add('hidden');
        }

        if (window.lucide) lucide.createIcons();
    } catch (e) {
        console.error('loadSettingsWalletStatus error:', e);
        if (statusBadge) {
            statusBadge.innerHTML = `
                <i data-lucide="alert-circle" class="w-3 h-3"></i>
                載入失敗
            `;
            statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-danger/10 text-danger';
        }
    }
}

// Settings 頁面的綁定錢包按鈕處理
async function handleSettingsLinkWallet() {
    const result = await linkPiWallet();
    if (result.success) {
        loadSettingsWalletStatus();
    }
}

// 處理綁定錢包按鈕
async function handleLinkWallet() {
    const result = await linkPiWallet();
    if (result.success) {
        // 重新載入狀態
        if (typeof loadSettingsWalletStatus === 'function') loadSettingsWalletStatus();
        if (typeof ForumApp !== 'undefined' && ForumApp.loadWalletStatus) ForumApp.loadWalletStatus();
    }
}

// 套用 premium badge UI（抽出共用邏輯）
function _applyPremiumBadgeUI(statusBadge, upgradeBtn, isPro, expiresAt) {
    const sidebarBadge = document.getElementById('sidebar-premium-badge');
    if (isPro) {
        const expiryText = expiresAt ? ` · ${new Date(expiresAt).toLocaleDateString('zh-TW')} 到期` : '';
        statusBadge.innerHTML = `
            <i data-lucide="star" class="w-3 h-3 text-yellow-400"></i>
            <span class="font-bold text-yellow-400">高級會員${expiryText}</span>
        `;
        statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-400 border border-yellow-500/30 shadow-sm shadow-yellow-500/10';
        if (sidebarBadge) sidebarBadge.classList.remove('hidden');
        if (upgradeBtn) {
            upgradeBtn.disabled = true;
            upgradeBtn.innerHTML = '<i data-lucide="check-circle" class="w-4 h-4"></i> 已是高級會員';
            upgradeBtn.className = 'w-full py-3.5 bg-gradient-to-r from-green-500 to-emerald-500 text-background font-bold rounded-xl transition flex items-center justify-center gap-2 cursor-default';
        }
    } else {
        statusBadge.innerHTML = `
            <i data-lucide="user" class="w-3 h-3"></i>
            <span class="font-bold text-textMuted">免費會員</span>
        `;
        statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';
        if (sidebarBadge) sidebarBadge.classList.add('hidden');
    }
    if (window.lucide) lucide.createIcons();
}

// 載入高級會員狀態（即時顯示快取值，後台更新精確到期日）
async function loadPremiumStatus() {
    const statusBadge = document.getElementById('premium-status-badge');
    const upgradeBtn = document.querySelector('.upgrade-premium-btn');

    if (!statusBadge) return;

    if (!AuthManager.currentUser) {
        const sidebarBadge = document.getElementById('sidebar-premium-badge');
        if (sidebarBadge) sidebarBadge.classList.add('hidden');
        statusBadge.innerHTML = `<i data-lucide="x-circle" class="w-3 h-3"></i> 未登入`;
        statusBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';
        if (upgradeBtn) upgradeBtn.disabled = true;
        if (window.lucide) lucide.createIcons();
        return;
    }

    // ── 即時顯示：從 currentUser 快取直接讀取，無需等待 API ──
    const cachedTier = AuthManager.currentUser.membership_tier || 'free';
    _applyPremiumBadgeUI(statusBadge, upgradeBtn, cachedTier === 'premium');

    // ── 後台更新：呼叫 API 取得精確到期日 ──
    try {
        const userId = AuthManager.currentUser.uid || AuthManager.currentUser.user_id;
        const response = await fetch(`/api/premium/status/${userId}`, {
            headers: { 'Authorization': `Bearer ${AuthManager.currentUser.accessToken}` }
        });
        if (!response.ok) return; // 保留快取顯示，不覆蓋

        const result = await response.json();
        const membership = result.membership;
        // Re-apply with accurate expiry date from API
        _applyPremiumBadgeUI(statusBadge, upgradeBtn, membership.is_pro, membership.expires_at);
    } catch (e) {
        // Cached display already shown — silently ignore API errors
        console.warn('loadPremiumStatus API error (cached display retained):', e);
    }
}

// 處理高級會員升級按鈕
async function handleUpgradeToPremium() {
    if (typeof upgradeToPremium === 'function') {
        await upgradeToPremium();
        // 升級後重新載入狀態
        setTimeout(loadPremiumStatus, 2000);
    } else {
        showToast('高級會員功能尚未載入', 'error');
    }
}

// ========================================
// 密碼登入與註冊 - REMOVED (Strict Pi Network Policy)
// ========================================

async function handleCredentialLogin() {
    showToast('Login with Password is deprecated. Please use Pi Network.', 'warning');
}

async function handleRegister() {
    showToast('Registration is disabled. Please use Pi Network.', 'warning');
}

// 註冊邏輯已移除

// 切換登入/註冊表單
function toggleAuthMode(mode) {
    const loginForm = document.getElementById('form-login');
    const registerForm = document.getElementById('form-register');
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');

    if (mode === 'login') {
        loginForm?.classList.remove('hidden');
        registerForm?.classList.add('hidden');
        tabLogin?.classList.add('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        tabLogin?.classList.remove('text-textMuted');
        tabRegister?.classList.remove('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        tabRegister?.classList.add('text-textMuted');
    } else {
        loginForm?.classList.add('hidden');
        registerForm?.classList.remove('hidden');
        tabRegister?.classList.add('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        tabRegister?.classList.remove('text-textMuted');
        tabLogin?.classList.remove('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        tabLogin?.classList.add('text-textMuted');
    }
}

// 檢查用戶名是否可用
async function checkUsernameAvailability() {
    const input = document.getElementById('reg-username');
    const msg = document.getElementById('reg-username-msg');
    const username = input?.value?.trim();

    if (!username || username.length < 6) {
        if (msg) {
            msg.textContent = '至少需要 6 個字元';
            msg.className = 'text-xs mt-1 text-textMuted/60';
        }
        return;
    }

    try {
        const res = await fetch(`/api/user/check/${username}`);
        const result = await res.json();

        if (msg) {
            if (result.available) {
                msg.textContent = '✓ 用戶名可用';
                msg.className = 'text-xs mt-1 text-success';
            } else {
                msg.textContent = '✗ 用戶名已被使用';
                msg.className = 'text-xs mt-1 text-danger';
            }
        }
    } catch (e) {
        console.error('Check username error:', e);
    }
}

// 檢查 Email 是否可用
async function checkEmailAvailability() {
    const input = document.getElementById('reg-email');
    const msg = document.getElementById('reg-email-msg');
    const email = input?.value?.trim();

    if (!email || !email.includes('@')) {
        if (msg) {
            msg.textContent = '用於密碼重置';
            msg.className = 'text-xs mt-1 text-textMuted/60';
        }
        return;
    }

    try {
        const res = await fetch(`/api/user/check-email/${encodeURIComponent(email)}`);
        const result = await res.json();

        if (msg) {
            if (result.available) {
                msg.textContent = '✓ Email 可用';
                msg.className = 'text-xs mt-1 text-success';
            } else {
                msg.textContent = '✗ Email 已被註冊';
                msg.className = 'text-xs mt-1 text-danger';
            }
        }
    } catch (e) {
        console.error('Check email error:', e);
    }
}

// 忘記密碼
function showForgotPasswordModal() {
    document.getElementById('forgot-password-modal')?.classList.remove('hidden');
}

function hideForgotPasswordModal() {
    document.getElementById('forgot-password-modal')?.classList.add('hidden');
}

async function handleForgotPassword() {
    const email = document.getElementById('forgot-email')?.value?.trim();
    const btn = document.getElementById('forgot-submit-btn');

    if (!email) {
        showToast('請輸入 Email', 'warning');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = '發送中...';
    }

    try {
        const res = await fetch('/api/user/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        const result = await res.json();

        if (res.ok) {
            showToast('如果 Email 存在，重置連結已發送', 'success');
            hideForgotPasswordModal();
        } else {
            showToast(result.detail || '發送失敗', 'error');
        }
    } catch (e) {
        showToast('發送時發生錯誤', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Send Reset Link';
        }
    }
}

// 暴露全域
window.AuthManager = AuthManager;

// ============================================================
// EMAIL LOGIN DISABLED - Pi SDK Exclusive Authentication
// 官方要求：只允許 Pi SDK 登入，不允許其他登入方式
// 如需恢復，取消以下註解即可
// ============================================================
// window.handleCredentialLogin = handleCredentialLogin;
// window.handleRegister = handleRegister;
// window.toggleAuthMode = toggleAuthMode;
// window.checkUsernameAvailability = checkUsernameAvailability;
// window.checkEmailAvailability = checkEmailAvailability;
// window.showForgotPasswordModal = showForgotPasswordModal;
// window.hideForgotPasswordModal = hideForgotPasswordModal;
// window.handleForgotPassword = handleForgotPassword;
window.handlePiLogin = async () => {
    DebugLog.info('handlePiLogin 被呼叫');

    // 第一步：同步檢測 Pi SDK 是否存在
    if (!isPiBrowser()) {
        DebugLog.warn('非 Pi Browser 環境，無法登入');
        const msg = '請在 Pi Browser 中開啟此頁面才能登入';
        if (typeof showAlert === 'function') {
            await showAlert({
                title: '需要 Pi Browser',
                message: '此應用需要使用 Pi Browser 才能登入。\n\n請複製此網址到 Pi Browser 中開啟。',
                type: 'warning'
            });
        } else if (typeof showToast === 'function') {
            showToast(msg, 'warning');
        } else {
            alert(msg);
        }
        return;
    }

    // 第二步：快速驗證是否真的在 Pi Browser 環境（最多 1.5 秒）
    // 避免非 Pi Browser 環境等待 60 秒後才顯示失敗
    DebugLog.info('驗證 Pi Browser 環境...');
    const envCheck = await AuthManager.verifyPiBrowserEnvironment();
    if (!envCheck.valid) {
        DebugLog.warn('Pi Browser 環境驗證失敗', { reason: envCheck.reason });
        if (typeof showAlert === 'function') {
            await showAlert({
                title: '需要 Pi Browser',
                message: '此應用需要使用 Pi Browser 才能登入。\n\n請複製此網址到 Pi Browser 中開啟。',
                type: 'warning'
            });
        } else if (typeof showToast === 'function') {
            showToast('請在 Pi Browser 中開啟此頁面才能登入', 'warning');
        } else {
            alert('請在 Pi Browser 中開啟此頁面才能登入');
        }
        return;
    }

    // 第三步：環境有效，進行認證
    DebugLog.info('Pi Browser 環境驗證通過，開始認證...');
    try {
        const res = await AuthManager.authenticateWithPi();
        DebugLog.info('Pi 登入結果', res);
        if (res.success) {
            // Show success state on the login modal before reload
            // This prevents the login modal from being hidden and briefly
            // flashing the app content before the page reloads.
            const btn = document.getElementById('pi-login-btn');
            if (btn) {
                btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> 登入成功，載入中...';
                btn.classList.remove('opacity-70');
                btn.classList.add('bg-green-600');
            }
            window.location.reload();
        } else {
            if (typeof showToast === 'function') {
                showToast('登入失敗: ' + res.error, 'error');
            } else {
                alert('登入失敗: ' + res.error);
            }
        }
    } catch (e) {
        DebugLog.error('handlePiLogin 異常', { error: e.message, stack: e.stack });
        if (typeof showToast === 'function') {
            showToast('登入異常: ' + e.message, 'error');
        } else {
            alert('登入異常: ' + e.message);
        }
    }
};
window.handleLogout = () => AuthManager.logout();
window.initializeAuth = () => AuthManager.init();
window.isPiBrowser = isPiBrowser;
window.canMakePiPayment = canMakePiPayment;
window.getWalletStatus = getWalletStatus;
window.linkPiWallet = linkPiWallet;
window.loadSettingsWalletStatus = loadSettingsWalletStatus;
window.handleLinkWallet = handleLinkWallet;
window.handleSettingsLinkWallet = handleSettingsLinkWallet;
window.loadPremiumStatus = loadPremiumStatus;
window.handleUpgradeToPremium = handleUpgradeToPremium;

// ========================================
// Dev Mode: Switch User (Test Mode Only)
// ========================================
window.handleDevSwitchUser = async function (userId) {
    console.log(`[Dev] Switching to user: ${userId}`);

    try {
        // 使用 dev-login endpoint 並指定用戶 ID
        const res = await fetch('/api/user/dev-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });

        const result = await res.json();

        if (!res.ok) {
            if (typeof showToast === 'function') {
                showToast(result.detail || 'Switch failed', 'error');
            }
            return;
        }

        // 更新 AuthManager
        AuthManager.currentUser = {
            uid: result.user.uid,
            user_id: result.user.uid,
            username: result.user.username,
            accessToken: result.access_token,
            accessTokenExpiry: Date.now() + AuthManager.TOKEN_EXPIRY_MS,
            authMethod: result.user.authMethod
        };

        localStorage.setItem('pi_user', JSON.stringify(AuthManager.currentUser));

        if (typeof showToast === 'function') {
            showToast(`切換到 ${result.user.username}`, 'success');
        }

        // 重新載入頁面以更新所有狀態
        setTimeout(() => window.location.reload(), 500);

    } catch (e) {
        console.error('Dev switch user error:', e);
        if (typeof showToast === 'function') {
            showToast('切換用戶失敗', 'error');
        }
    }
};
