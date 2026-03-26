// ========================================
// auth.js - 用戶身份認證模塊 (簡潔穩定版)
// ========================================

const DebugLog = {
    send(level, message, data = null) {
        if (window.APP_CONFIG && window.APP_CONFIG.DEBUG_MODE !== true) {
            return;
        }
        console.log(`[${level.toUpperCase()}] ${message}`, data);
        // 在开发环境中记录日志，在生产环境中可选择禁用
        // 为了减少网络请求，仅在特定条件下发送到服务器
        if (window.APP_CONFIG && window.APP_CONFIG.DEBUG_MODE === true) {
            AppAPI.post('/api/debug-log', { level, message, data }, { keepalive: true }).catch(() => {});
        }
    },
    info(msg, data) {
        this.send('info', msg, data);
    },
    error(msg, data) {
        this.send('error', msg, data);
    },
    warn(msg, data) {
        this.send('warn', msg, data);
    },
};

window.DebugLog = DebugLog;

const PI_LOGIN_RECOVERY_GRACE_MS = 15000;

var _piLoginPromise = null;
var _piRefreshPromise = null;

const PiEnvironment = {
    isLocalhost() {
        return (
            window.location.hostname === 'localhost' ||
            window.location.hostname === '127.0.0.1' ||
            window.location.hostname === '::1'
        );
    },

    isSafeSdkContext() {
        return window.location.protocol === 'https:' && !this.isLocalhost();
    },

    hasPiSdk() {
        return (
            typeof window.Pi !== 'undefined' &&
            window.Pi !== null &&
            typeof window.Pi.authenticate === 'function' &&
            typeof window.Pi.init === 'function'
        );
    },

    isPiBrowser() {
        if (this.isSafeSdkContext() && this.hasPiSdk()) return true;
        const ua = navigator.userAgent || '';
        return ua.includes('PiBrowser');
    },

    getAccessToken() {
        return window.AuthManager?.currentUser?.accessToken || null;
    },

    isAuthenticated() {
        return !!this.getAccessToken();
    },

    getAuthHeaders(extraHeaders = {}) {
        const token = this.getAccessToken();
        return token ? { ...extraHeaders, Authorization: 'Bearer ' + token } : { ...extraHeaders };
    },

    shouldBlockProtectedRequests() {
        return !this.isAuthenticated();
    },
};

window.PiEnvironment = PiEnvironment;

const AuthManager = {
    currentUser: null,
    piInitialized: false,
    _refreshTimer: null,

    // Token 過期時間（7 天，與後端 ACCESS_TOKEN_EXPIRE_MINUTES 一致）
    TOKEN_EXPIRY_MS: 7 * 24 * 60 * 60 * 1000,

    // 在過期前多久開始刷新（1 天）
    REFRESH_BEFORE_EXPIRY_MS: 24 * 60 * 60 * 1000,

    isPasswordSession(user) {
        const method = user?.authMethod || user?.auth_method;
        return method === 'password';
    },

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
        return expiry - Date.now() < oneHour;
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

    _saveUserSession() {
        if (!this.currentUser) return;
        const safe = { ...this.currentUser };
        delete safe.accessToken;
        delete safe.piAccessToken;
        localStorage.setItem('pi_user', JSON.stringify(safe));
    },

    restoreSessionFromStorage() {
        if (this.currentUser) {
            return true;
        }

        const savedUser = localStorage.getItem('pi_user');
        if (!savedUser) {
            return false;
        }

        try {
            const parsedUser = JSON.parse(savedUser);
            if (!parsedUser || (!parsedUser.user_id && !parsedUser.uid)) {
                localStorage.removeItem('pi_user');
                return false;
            }

            this.currentUser = parsedUser;
            this._updateUI(true);
            DebugLog.info('已從 localStorage 恢復登入狀態');
            return true;
        } catch (error) {
            DebugLog.warn('恢復登入狀態失敗，清除損壞快取', { error: error.message });
            localStorage.removeItem('pi_user');
            return false;
        }
    },

    /**
     * 清除過期的 token 並導向登入
     */
    clearExpiredToken() {
        if (this.shouldDeferExpiredSessionCleanup()) {
            DebugLog.warn('Skip expired token cleanup during Pi login transition');
            return false;
        }
        DebugLog.warn('Token 已過期，清除並導向登入');
        this.currentUser = null;
        localStorage.removeItem('pi_user');
        this._updateUI(false);

        AppAPI.post('/api/user/logout').catch(() => {});

        // 顯示提示
        if (typeof showToast === 'function') {
            showToast(
                window.i18next?.t('auth.loginExpired') || '登入已過期，請重新登入',
                'warning'
            );
        }

        // 重整頁面以顯示登入 modal
        window.location.reload();
        return true;
    },

    getRecentLoginSuccessAt() {
        const raw = sessionStorage.getItem('pi_login_success_at');
        const value = raw ? Number(raw) : 0;
        return Number.isFinite(value) ? value : 0;
    },

    markRecentLoginSuccess() {
        sessionStorage.setItem('pi_login_success_at', String(Date.now()));
    },

    shouldDeferExpiredSessionCleanup() {
        const loginInProgress =
            (typeof AppStore !== 'undefined' && AppStore.get('piLoginInProgress')) ||
            window._piLoginInProgress === true;
        if (loginInProgress) {
            return true;
        }

        const lastSuccessAt = this.getRecentLoginSuccessAt();
        return lastSuccessAt > 0 && Date.now() - lastSuccessAt < PI_LOGIN_RECOVERY_GRACE_MS;
    },

    /**
     * 啟動 token 自動刷新定時器
     * 每 10 分鐘檢查一次，如果 token 快過期則自動刷新
     */
    startTokenRefreshTimer() {
        // 清除舊的定時器
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
        }

        // 每 30 分鐘檢查一次（平衡用戶體驗和及時刷新）
        this._refreshTimer = setInterval(
            async () => {
                if (!this.currentUser) return;

                DebugLog.info('Token refresh check', {
                    needsRefresh: this.needsRefresh(),
                    isExpired: this.isTokenExpired(),
                    timeUntilExpiry: this.currentUser.accessTokenExpiry
                        ? Math.round(
                              (this.currentUser.accessTokenExpiry - Date.now()) / 1000 / 60
                          ) + ' minutes'
                        : 'unknown',
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
            },
            30 * 60 * 1000
        ); // 每 30 分鐘檢查一次

        // 監聽頁面可見性變化（用戶回到頁面時檢查）
        this._visibilityHandler = async () => {
            if (document.visibilityState === 'visible' && this.currentUser) {
                if (this.shouldDeferExpiredSessionCleanup()) {
                    DebugLog.info('頁面可見但登入交接中，跳過 token 檢查');
                    return;
                }
                DebugLog.info('頁面重新可見，檢查 token 狀態');
                if (this.isTokenExpired() || this.needsRefresh()) {
                    // On app resume, prefer backend refresh and avoid Pi SDK prompts/blank pages.
                    await this.backendTokenRefresh();
                }
            }
        };

        document.addEventListener('visibilitychange', this._visibilityHandler);

        this._pageShowHandler = () => {
            if (!this.currentUser) {
                this.restoreSessionFromStorage();
            }
        };
        window.addEventListener('pageshow', this._pageShowHandler);

        DebugLog.info('Token refresh timer started (30 min interval + visibility check)');
    },

    /**
     * 靜默刷新 token（使用 Pi SDK 重新認證）
     * @returns {Promise<{success: boolean, error?: string}>}
     */
    async silentRefresh() {
        if (!this.currentUser?.pi_uid) {
            DebugLog.warn('非 Pi 用戶，無法靜默刷新');
            return { success: false, error: 'Not a Pi user' };
        }

        if (_piRefreshPromise) {
            DebugLog.info('silentRefresh: 刷新已在進行中，跳過');
            return _piRefreshPromise;
        }

        if (!PiEnvironment.isPiBrowser()) {
            DebugLog.warn('非 Pi Browser 環境，嘗試使用後端刷新');
            return await this.backendTokenRefresh();
        }

        _piRefreshPromise = this._doSilentRefresh().finally(() => { _piRefreshPromise = null; });
        return _piRefreshPromise;
    },

    async _doSilentRefresh() {
        try {
            DebugLog.info('開始靜默刷新 token...');

            await this.initPiSDKAsync();

            const auth = await Pi.authenticate(
                ['username', 'payments', 'wallet_address'],
                (payment) => {
                    DebugLog.warn('刷新時發現未完成的支付', payment);
                }
            );

            DebugLog.info('Pi SDK 重新認證成功', { username: auth.user.username });

            const syncResult = await AppAPI.post('/api/user/pi-sync', {
                pi_uid: auth.user.uid,
                username: auth.user.username,
                access_token: auth.accessToken,
                wallet_address: auth.user.wallet_address || null,
            });

            this.currentUser = {
                ...this.currentUser,
                accessToken: syncResult.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
                piAccessToken: auth.accessToken,
            };

            this._saveUserSession();

            DebugLog.info('Token 靜默刷新成功', {
                newExpiry: new Date(this.currentUser.accessTokenExpiry).toISOString(),
            });

            return { success: true };
        } catch (error) {
            DebugLog.error('靜默刷新失敗，嘗試後端刷新', { error: error.message });
            return await this.backendTokenRefresh();
        }
    },

    /**
     * 使用後端刷新 token（備用方案，不需要 Pi SDK）
     * @returns {Promise<{success: boolean, error?: string}>}
     */
    async backendTokenRefresh() {
        if (!this.currentUser?.accessToken) {
            return { success: false, error: 'No token to refresh' };
        }

        try {
            DebugLog.info('嘗試後端 token 刷新...');

            const result = await AppAPI.post('/api/user/refresh-token');

            // 更新本地用戶資料
            this.currentUser = {
                ...this.currentUser,
                accessToken: result.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
            };

            this._saveUserSession();
            this.markRecentLoginSuccess();

            DebugLog.info('後端 token 刷新成功', {
                newExpiry: new Date(this.currentUser.accessTokenExpiry).toISOString(),
            });

            return { success: true };
        } catch (error) {
            DebugLog.error('後端刷新也失敗', { error: error.message });
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
        if (this._visibilityHandler) {
            document.removeEventListener('visibilitychange', this._visibilityHandler);
            this._visibilityHandler = null;
        }
        if (this._pageShowHandler) {
            window.removeEventListener('pageshow', this._pageShowHandler);
            this._pageShowHandler = null;
        }
    },

    /**
     * 異步初始化 Pi SDK
     * @returns {Promise<boolean>}
     */
    async initPiSDKAsync() {
        if (!PiEnvironment.isPiBrowser()) {
            DebugLog.info('initPiSDKAsync: skipping outside secure Pi context');
            return false;
        }
        if (this.piInitialized) {
            DebugLog.info('initPiSDKAsync: 已初始化，跳過');
            return true;
        }
        if (window.Pi) {
            try {
                // Official Guide: Initialize SDK early
                const sandbox = window.__APP_PI_SANDBOX === true;
                await Pi.init({ version: '2.0', sandbox: sandbox });
                this.piInitialized = true;
                DebugLog.info('Pi SDK async init success', { sandbox });
                return true;
            } catch (e) {
                DebugLog.error('Pi SDK 異步初始化失敗', { error: e.message, stack: e.stack });
                return false;
            }
        }
        DebugLog.warn('initPiSDKAsync: window.Pi 不存在');
        return false;
    },

    initPiSDK() {
        if (!PiEnvironment.isPiBrowser()) {
            DebugLog.info('initPiSDK: skipping outside secure Pi context');
            return false;
        }
        if (this.piInitialized) {
            DebugLog.info('initPiSDK: already initialized, skipping');
            return true;
        }
        if (window.Pi) {
            try {
                const sandbox = window.__APP_PI_SANDBOX === true;
                Pi.init({ version: '2.0', sandbox: sandbox });
                this.piInitialized = true;
                DebugLog.info('Pi SDK initialized', { sandbox });
                return true;
            } catch (e) {
                DebugLog.error('Pi SDK init failed', { error: e.message, stack: e.stack });
                return false;
            }
        }
        DebugLog.warn('initPiSDK: window.Pi is not available');
        return false;
    },

    // 異步快速檢測 Pi Browser 環境是否有效
    // 注意：nativeFeaturesList 在某些 Pi Browser 版本中可能不可用，
    // 但只要 Pi SDK 存在（有 authenticate 和 init 方法），就應該允許用戶嘗試登入
    isLoggedIn() {
        return !!this.currentUser;
    },

    async loginAsMockUser() {
        window.APP_CONFIG?.DEBUG_MODE &&
            console.log('⚠️ [Dev Mode] Manually triggering Mock Login.');
        showToast('開發模式：使用測試帳號登入...', 'info');

        await new Promise((r) => setTimeout(r, 500)); // 模擬延遲

        try {
            // 使用新的 Dev Login Endpoint
            const result = await AppAPI.post('/api/user/dev-login');

            this.currentUser = {
                uid: result.user.uid,
                user_id: result.user.uid,
                username: result.user.username,
                accessToken: result.access_token,
                accessTokenExpiry: Date.now() + this.TOKEN_EXPIRY_MS,
                authMethod: result.user.authMethod,
            };

            this._saveUserSession();
            this._updateUI(true);

            if (typeof initChat === 'function') initChat();
            return { success: true, user: this.currentUser };
        } catch (e) {
            console.error('Mock login error:', e);
            showToast('模擬登入失敗', 'error');
            return { success: false, error: e.message };
        }
    },

    async authenticateWithPi() {
        if (_piLoginPromise) {
            DebugLog.info('Pi login 已在進行中，等待結果');
            return _piLoginPromise;
        }

        _piLoginPromise = this._doPiAuth().finally(() => { _piLoginPromise = null; });
        return _piLoginPromise;
    },

    async _doPiAuth() {
        DebugLog.info('authenticateWithPi 開始', {
            piInitialized: this.piInitialized,
            hasPiSDK: !!window.Pi,
        });

        try {
            if (!this.piInitialized) {
                DebugLog.info('初始化 Pi SDK...');
                this.initPiSDK();
            }

            DebugLog.info('呼叫 Pi.authenticate...');

            // Pi SDK auth - request scopes matching official Pi demo app
            // Ref: https://github.com/pi-apps/demo/blob/main/FLOWS.md
            const AUTH_TIMEOUT = 60000;

            const authPromise = Pi.authenticate(
                ['username', 'payments', 'wallet_address', 'roles', 'in_app_notifications'],
                (payment) => {
                    DebugLog.warn('發現未完成的支付', payment);
                    AppAPI.post('/api/user/payment/complete', {
                        paymentId: payment.identifier,
                        txid: payment.transaction.txid,
                    }).catch(() => {});
                }
            );

            const timeoutPromise = new Promise((_, reject) => {
                const timeoutId = setTimeout(() => {
                    DebugLog.error('Pi.authenticate 超時', { timeout: AUTH_TIMEOUT });
                    reject(new Error('Pi 認證超時，請確認 Pi Browser 是否有彈出授權視窗'));
                }, AUTH_TIMEOUT);
                authPromise.finally(() => clearTimeout(timeoutId));
            });

            const auth = await Promise.race([authPromise, timeoutPromise]);

            DebugLog.info('Pi 認證成功', { username: auth.user.username, uid: auth.user.uid });

            // 同步到後端；若 Pi API 可提供 wallet_address，後端會優先採用驗證結果。
            const syncResult = await AppAPI.post('/api/user/pi-sync', {
                    pi_uid: auth.user.uid,
                    username: auth.user.username,
                    access_token: auth.accessToken,
                    wallet_address: auth.user.wallet_address || null,
                });

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
                pi_wallet_address: auth.user.wallet_address || null,
                has_wallet: syncResult.user.has_wallet || false,
                piAccessToken: auth.accessToken,
            };

            this._saveUserSession();

            // 啟動 token 自動刷新定時器
            this.markRecentLoginSuccess();
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
                piExists: !!window.Pi,
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
        if (this.restoreSessionFromStorage()) {
            // 檢查 token 是否過期
            if (this.isTokenExpired()) {
                DebugLog.warn('Token 已過期，清除並導向登入');
                this.clearExpiredToken();
                return false;
            }
        } else {
            this._updateUI(false);
        }

        // 檢查測試模式（async，但不影響已登入用戶）
        try {
            const config = await AppAPI.get('/api/config');

            window.__APP_TEST_MODE = !!config.test_mode;
            window.__APP_PI_SANDBOX = !!config.pi_sandbox;

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
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('🧪 [Test Mode] 自動登入測試用戶（透過 dev-login endpoint）');
                const result = await this.loginAsMockUser();
                if (!result.success) {
                    console.warn('🧪 [Test Mode] 自動登入失敗:', result.error);
                }
            }
        } catch (e) {
            console.warn('Failed to check test mode:', e);
        }

        // Only initialize Pi SDK in a secure Pi-compatible context.
        if (isPiBrowser()) {
            this.initPiSDK();
        }

        // 啟動 token 自動刷新定時器（僅對已登入的 Pi 用戶）
        if (this.currentUser?.pi_uid) {
            this.startTokenRefreshTimer();

            // 如果 token 快過期，立即嘗試刷新
            if (this.needsRefresh()) {
                DebugLog.info('Token 快過期，啟動時立即刷新');
                this.silentRefresh().catch((e) => {
                    DebugLog.warn('啟動時刷新失敗，將在定時器中重試', { error: e.message });
                });
            }
        }

        if (this.currentUser) {
            window.dispatchEvent(new Event('auth:ready'));
        }

        return !!this.currentUser;
    },

    _updateUI(isLoggedIn) {
        const username =
            this.currentUser?.username ||
            this.currentUser?.pi_username ||
            this.currentUser?.displayName ||
            'Login Required';
        const uid =
            this.currentUser?.uid || this.currentUser?.user_id || this.currentUser?.pi_uid || '--';
        const authMethod =
            this.currentUser?.authMethod ||
            this.currentUser?.auth_method ||
            (this.currentUser?.pi_uid ? 'pi_network' : 'guest');

        // 控制 auth-only 和 guest-only 元素的顯示
        document.querySelectorAll('.auth-only').forEach((el) => {
            if (isLoggedIn) {
                el.classList.remove('hidden');
            } else {
                el.classList.add('hidden');
            }
        });
        document.querySelectorAll('.guest-only').forEach((el) => {
            el.classList.add('hidden');
        });

        // 更新所有可能存在的使用者名稱欄位
        ['sidebar-user-name', 'forum-user-name', 'profile-username', 'nav-username'].forEach(
            (id) => {
                const el = document.getElementById(id);
                if (el) el.textContent = username;
            }
        );

        // 更新所有有 user-display-name class 的元素
        document.querySelectorAll('.user-display-name').forEach((el) => {
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
            const methodText =
                authMethod === 'pi_network'
                    ? 'PI WALLET'
                    : authMethod === 'password'
                      ? 'PASSWORD'
                      : 'LOCKED';
            methodEl.textContent = methodText;
        }

        // 更新頭像
        ['sidebar-user-avatar', 'forum-user-avatar', 'profile-avatar', 'nav-avatar'].forEach(
            (id) => {
                const el = document.getElementById(id);
                if (el) {
                    if (isLoggedIn) {
                        el.textContent = username[0].toUpperCase();
                        el.classList.add(
                            'bg-gradient-to-br',
                            'from-primary',
                            'to-accent',
                            'text-background'
                        );
                    } else {
                        el.innerHTML = '<i data-lucide="user" class="w-4 h-4"></i>';
                        el.classList.remove(
                            'bg-gradient-to-br',
                            'from-primary',
                            'to-accent',
                            'text-background'
                        );
                    }
                }
            }
        );

        // 控制登入 Modal 顯示
        const modal = document.getElementById('login-modal');
        if (modal) {
            if (isLoggedIn) {
                modal.classList.add('hidden');
            } else {
                modal.classList.remove('hidden');
                if (typeof window._showLoginButton === 'function') {
                    window._showLoginButton();
                }
            }
        }

        // 更新會員狀態顯示
        if (isLoggedIn && typeof loadPremiumStatus === 'function') {
            loadPremiumStatus();
        }

        if (typeof window.refreshAnalysisModeSelector === 'function') {
            window.refreshAnalysisModeSelector();
        }

        // 登入後觸發 auth:ready 事件，由 NotificationService 監聽並初始化
        if (isLoggedIn) {
            window.dispatchEvent(new Event('auth:ready'));
        }

        // 重新渲染導覽列（根據 role 顯示/隱藏 admin tab）
        if (typeof renderNavButtons === 'function') renderNavButtons();
        if (window.GlobalNav && typeof GlobalNav.renderNavButtons === 'function')
            GlobalNav.renderNavButtons();

        AppUtils.refreshIcons();
    },

    logout() {
        this.stopTokenRefreshTimer();
        this.currentUser = null;
        localStorage.removeItem('pi_user');
        AppAPI.post('/api/user/logout').finally(() => {
            this._updateUI(false);
            window.location.reload();
        });
    },
};

// 工具函式
function isPiBrowser() {
    return PiEnvironment.isPiBrowser();
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

    try {
        const data = await AppAPI.get('/api/user/wallet-status');
        return {
            has_wallet: data.has_wallet || false,
            pi_uid: data.pi_uid || null,
            pi_username: data.pi_username || null,
            auth_method: data.auth_method || 'password',
        };
    } catch (e) {
        console.error('getWalletStatus error:', e);
        return { has_wallet: false, auth_method: 'unknown' };
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

        if (status.has_wallet) {
            // 已綁定或 Pi 登入
            statusBadge.innerHTML = `
                <i data-lucide="check-circle" class="w-3 h-3"></i>
                已連接
            `;
            statusBadge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 text-success';

            if (walletIcon) {
                walletIcon.innerHTML = '<i data-lucide="wallet" class="w-5 h-5 text-success"></i>';
                walletIcon.className =
                    'w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center';
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
            statusBadge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';

            if (walletIcon) {
                walletIcon.innerHTML = '<i data-lucide="wallet" class="w-5 h-5 text-primary"></i>';
                walletIcon.className =
                    'w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center';
            }

            if (notLinkedSection) notLinkedSection.classList.remove('hidden');
            if (linkedSection) linkedSection.classList.add('hidden');
        }

        AppUtils.refreshIcons();
    } catch (e) {
        console.error('loadSettingsWalletStatus error:', e);
        if (statusBadge) {
            statusBadge.innerHTML = `
                <i data-lucide="alert-circle" class="w-3 h-3"></i>
                載入失敗
            `;
            statusBadge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-danger/10 text-danger';
        }
    }
}

// 套用 premium badge UI（抽出共用邏輯）
function _applyPremiumBadgeUI(statusBadge, upgradeBtn, isPro, expiresAt) {
    const sidebarBadge = document.getElementById('sidebar-premium-badge');
    if (isPro) {
        const expiryText = expiresAt
            ? ` · ${new Date(expiresAt).toLocaleDateString('zh-TW')} 到期`
            : '';
        statusBadge.innerHTML = `
            <i data-lucide="star" class="w-3 h-3 text-yellow-400"></i>
            <span class="font-bold text-yellow-400">${window.i18next?.t('auth.premiumMember') || 'Premium 會員'}${expiryText}</span>
        `;
        statusBadge.className =
            'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-400 border border-yellow-500/30 shadow-sm shadow-yellow-500/10';
        if (sidebarBadge) sidebarBadge.classList.remove('hidden');
        if (upgradeBtn) {
            upgradeBtn.disabled = true;
            upgradeBtn.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4"></i> ${window.i18next?.t('auth.alreadyPremium') || '已是 Premium 會員'}`;
            upgradeBtn.className =
                'w-full py-3.5 bg-gradient-to-r from-green-500 to-emerald-500 text-background font-bold rounded-xl transition flex items-center justify-center gap-2 cursor-default';
        }
    } else {
        statusBadge.innerHTML = `
            <i data-lucide="user" class="w-3 h-3"></i>
            <span class="font-bold text-textMuted">${window.i18next?.t('auth.freeMember') || '免費會員'}</span>
        `;
        statusBadge.className =
            'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';
        if (sidebarBadge) sidebarBadge.classList.add('hidden');
    }
    AppUtils.refreshIcons();
}

// 載入 Premium 會員狀態（即時顯示快取值，後台更新精確到期日）
async function loadPremiumStatus() {
    const statusBadge = document.getElementById('premium-status-badge');
    const upgradeBtn = document.querySelector('.upgrade-premium-btn');

    if (!statusBadge) return;

    if (!AuthManager.currentUser) {
        const sidebarBadge = document.getElementById('sidebar-premium-badge');
        if (sidebarBadge) sidebarBadge.classList.add('hidden');
        statusBadge.innerHTML = `<i data-lucide="x-circle" class="w-3 h-3"></i> ${window.i18next?.t('login.loginRequired') || '未登入'}`;
        statusBadge.className =
            'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted';
        if (upgradeBtn) upgradeBtn.disabled = true;
        AppUtils.refreshIcons();
        return;
    }

    // ── 即時顯示：從 currentUser 快取直接讀取，無需等待 API ──
    const cachedTier = AuthManager.currentUser.membership_tier || 'free';
    _applyPremiumBadgeUI(statusBadge, upgradeBtn, cachedTier === 'premium');

    // ── 後台更新：呼叫 API 取得精確到期日 ──
    try {
        const result = await AppAPI.get('/api/premium/status');
        const membership = result.membership;
        // Re-apply with accurate expiry date from API
        _applyPremiumBadgeUI(statusBadge, upgradeBtn, membership.is_premium, membership.expires_at);
    } catch (e) {
        // Cached display already shown — silently ignore API errors
        console.warn('loadPremiumStatus API error (cached display retained):', e);
    }
}

// 處理 Premium 會員升級按鈕
async function handleUpgradeToPremium() {
    if (typeof upgradeToPremium === 'function') {
        await upgradeToPremium();
        // 升級後重新載入狀態
        setTimeout(loadPremiumStatus, 2000);
    } else {
        showToast('Premium 會員功能尚未載入', 'error');
    }
}

// 暴露全域
window.AuthManager = AuthManager;

async function handlePiLogin() {
    DebugLog.info('handlePiLogin 被呼叫');

    // 第一步：同步檢測 Pi SDK 是否存在
    if (!isPiBrowser()) {
        DebugLog.warn('非 Pi Browser 環境，無法登入');
        const msg = '請在 Pi Browser 中開啟此頁面才能登入';
        if (typeof showAlert === 'function') {
            await showAlert({
                title: '需要 Pi Browser',
                message:
                    '此應用需要使用 Pi Browser 才能登入。\n\n請複製此網址到 Pi Browser 中開啟。',
                type: 'warning',
            });
        } else if (typeof showToast === 'function') {
            showToast(msg, 'warning');
        } else {
            alert(msg);
        }
        return;
    }

    // 第二步：環境有效，直接進行認證
    try {
        AuthManager.initPiSDK();
    } catch (e) {
        DebugLog.warn('Pi SDK 初始化失敗', { error: e.message });
    }

    DebugLog.info('Pi Browser 環境驗證通過，開始認證...');
    try {
        const res = await AuthManager.authenticateWithPi();
        DebugLog.info('Pi 登入結果', res);
        if (res.success) {
            // ✅ 優化：不再 reload 整頁，改成直接更新 UI，消除空白畫面
            const btn = document.getElementById('pi-login-btn');
            if (btn) {
                btn.innerHTML =
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> 登入成功，載入中...';
                btn.classList.remove('opacity-70');
                btn.classList.add('bg-green-600');
            }

            // 隱藏 login modal
            const modal = document.getElementById('login-modal');
            if (modal) modal.classList.add('hidden');
            AppStore.set('forceGuestLandingTab', false);
            window.__forceGuestLandingTab = false;
            // 更新認證 UI 狀態
            if (typeof AuthManager._updateUI === 'function') {
                AuthManager._updateUI(true);
            }

            let hasAnyApiKey = false;
            try {
                if (window.APIKeyManager?.hasAnyKey) {
                    hasAnyApiKey = await window.APIKeyManager.hasAnyKey();
                }
            } catch (apiKeyError) {
                DebugLog.warn('登入後檢查 API Key 狀態失敗', { error: apiKeyError.message });
            }

            if (!hasAnyApiKey && typeof switchTab === 'function') {
                await switchTab('settings');
            }

            if (typeof showToast === 'function') {
                showToast(
                    hasAnyApiKey
                        ? '✅ 登入成功！歡迎回來'
                        : '✅ 登入成功！請先設定 API 金鑰以使用 AI 分析',
                    'success'
                );
            }

            // 後台同步狀態（不阻塞 UI，也不覆蓋使用者當前分頁）
            if (typeof window.loadSavedApiKeys === 'function') {
                Promise.resolve(window.loadSavedApiKeys()).catch(() => {});
            }
            if (typeof checkApiKeyStatus === 'function') {
                Promise.resolve(checkApiKeyStatus()).catch(() => {});
            }
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
window.handlePiLogin = handlePiLogin;
// Note: window.safePiLogin is defined in pi-auth.js (loaded before this file)
// with watchdog, loading UI, and SDK readiness polling.

function handleLogout() {
    AuthManager.logout();
}
window.handleLogout = handleLogout;

function initializeAuth() {
    AuthManager.init();
}
window.initializeAuth = initializeAuth;
window.isPiBrowser = isPiBrowser;
window.canMakePiPayment = canMakePiPayment;
window.getWalletStatus = getWalletStatus;
window.loadSettingsWalletStatus = loadSettingsWalletStatus;
window.loadPremiumStatus = loadPremiumStatus;
window.handleUpgradeToPremium = handleUpgradeToPremium;

// ========================================
// Dev Mode: Switch User (Test Mode Only)
// ========================================
async function handleDevSwitchUser(userId) {
    window.APP_CONFIG?.DEBUG_MODE && console.log(`[Dev] Switching to user: ${userId}`);

    try {
        // 使用 dev-login endpoint 並指定用戶 ID
        const result = await AppAPI.post('/api/user/dev-login', { user_id: userId });

        // 更新 AuthManager
        AuthManager.currentUser = {
            uid: result.user.uid,
            user_id: result.user.uid,
            username: result.user.username,
            accessToken: result.access_token,
            accessTokenExpiry: Date.now() + AuthManager.TOKEN_EXPIRY_MS,
            authMethod: result.user.authMethod,
        };

        AuthManager._saveUserSession();

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

export {
    DebugLog,
    PiEnvironment,
    AuthManager,
    handlePiLogin,
    handleLogout,
    initializeAuth,
    isPiBrowser,
    canMakePiPayment,
    getWalletStatus,
    loadSettingsWalletStatus,
    loadPremiumStatus,
    handleUpgradeToPremium,
    handleDevSwitchUser,
    _applyPremiumBadgeUI,
};
