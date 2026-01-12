// ========================================
// auth.js - 用戶身份認證模塊
// 支持 Pi Network 和測試模式
// ========================================

const AuthManager = {
    // 當前用戶資料
    currentUser: null,

    // Pi SDK 是否已初始化
    piInitialized: false,

    // 測試帳號（開發用）
    TEST_CREDENTIALS: {
        publicKey: 'test_uuid',
        password: 'test_uuid'
    },

    /**
     * 初始化 Pi SDK
     * 必須在調用其他 Pi 方法之前執行
     */
    initPiSDK() {
        console.log('initPiSDK called, already initialized:', this.piInitialized);
        if (this.piInitialized) return true;

        console.log('window.Pi:', window.Pi);
        if (window.Pi) {
            try {
                Pi.init({
                    version: "2.0",
                    sandbox: true  // true = 測試環境, false = 正式環境
                });
                this.piInitialized = true;
                console.log('Pi SDK initialized successfully');
                return true;
            } catch (e) {
                console.error('Pi.init error:', e);
                return false;
            }
        }
        console.log('window.Pi not found');
        return false;
    },

    /**
     * 初始化認證狀態
     * 檢查是否有已保存的 session
     */
    init() {
        // 嘗試初始化 Pi SDK
        this.initPiSDK();
        const savedUser = localStorage.getItem('pi_user');
        if (savedUser) {
            try {
                this.currentUser = JSON.parse(savedUser);
                this._updateGlobalUserId();
                this._updateUI(true);
                return true;
            } catch (e) {
                localStorage.removeItem('pi_user');
            }
        }
        this._updateUI(false);
        return false;
    },

    /**
     * Pi Network 認證
     * 使用 Pi SDK 進行真實認證
     */
    async authenticateWithPi() {
        console.log('authenticateWithPi called');
        try {
            if (!window.Pi) {
                throw new Error('Pi SDK not loaded. Please open in Pi Browser.');
            }

            // 確保 Pi SDK 已初始化
            if (!this.piInitialized) {
                console.log('Initializing Pi SDK before auth...');
                this.initPiSDK();
            }

            console.log('Calling Pi.authenticate...');
            const auth = await Pi.authenticate(
                ['username', 'payments'],
                this._onIncompletePayment
            );
            console.log('Pi.authenticate returned:', auth);

            this.currentUser = {
                uid: auth.user.uid,
                username: auth.user.username,
                accessToken: auth.accessToken,
                authMethod: 'pi_network',
                loginTime: Date.now()
            };

            localStorage.setItem('pi_user', JSON.stringify(this.currentUser));
            this._updateGlobalUserId();
            this._updateUI(true);

            // 認證成功後初始化聊天
            if (typeof initChat === 'function') {
                await initChat();
            }

            return { success: true, user: this.currentUser };
        } catch (error) {
            console.error('Pi authentication failed:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * 測試模式認證
     * 用於開發環境，使用 publicKey + password
     */
    async authenticateWithCredentials(publicKey, password) {
        // 驗證測試帳號
        if (publicKey === this.TEST_CREDENTIALS.publicKey &&
            password === this.TEST_CREDENTIALS.password) {

            this.currentUser = {
                uid: publicKey,
                username: 'Test User',
                authMethod: 'test_credentials',
                loginTime: Date.now()
            };

            localStorage.setItem('pi_user', JSON.stringify(this.currentUser));
            this._updateGlobalUserId();
            this._updateUI(true);

            // 認證成功後初始化聊天
            if (typeof initChat === 'function') {
                await initChat();
            }

            return { success: true, user: this.currentUser };
        }

        return { success: false, error: 'Invalid credentials' };
    },

    /**
     * 登出
     */
    logout() {
        this.currentUser = null;
        localStorage.removeItem('pi_user');
        window.currentUserId = 'guest';
        this._updateUI(false);

        // 重置聊天初始化狀態
        if (typeof resetChatInit === 'function') {
            resetChatInit();
        }

        // 清空聊天畫面
        const container = document.getElementById('chat-messages');
        if (container) {
            container.innerHTML = '';
        }
        const sessionList = document.getElementById('chat-session-list');
        if (sessionList) {
            sessionList.innerHTML = '<div class="text-center text-xs text-textMuted/40 py-4">Please login first</div>';
        }
    },

    /**
     * 檢查是否已登入
     */
    isLoggedIn() {
        return this.currentUser !== null;
    },

    /**
     * 獲取當前用戶 ID
     */
    getUserId() {
        return this.currentUser?.uid || 'guest';
    },

    /**
     * 更新全局 userId
     */
    _updateGlobalUserId() {
        if (this.currentUser) {
            window.currentUserId = this.currentUser.uid;
            if (typeof updateUserId === 'function') {
                updateUserId(this.currentUser.uid);
            }
        }
    },

    /**
     * 更新 UI 狀態
     */
    _updateUI(isLoggedIn) {
        const loginBtn = document.getElementById('auth-login-btn');
        const logoutBtn = document.getElementById('auth-logout-btn');
        const userInfo = document.getElementById('auth-user-info');
        const loginOverlay = document.getElementById('login-overlay');

        if (isLoggedIn && this.currentUser) {
            if (loginBtn) loginBtn.classList.add('hidden');
            if (logoutBtn) logoutBtn.classList.remove('hidden');
            if (userInfo) {
                userInfo.textContent = this.currentUser.username || 'User';
                userInfo.classList.remove('hidden');
            }
            if (loginOverlay) loginOverlay.classList.add('hidden');
        } else {
            if (loginBtn) loginBtn.classList.remove('hidden');
            if (logoutBtn) logoutBtn.classList.add('hidden');
            if (userInfo) userInfo.classList.add('hidden');
            if (loginOverlay) loginOverlay.classList.remove('hidden');
        }
    },

    /**
     * Pi Network 未完成支付回調
     */
    _onIncompletePayment(payment) {
        console.log('Incomplete payment found:', payment);
        // 處理未完成的支付
    }
};

// ========================================
// 登入對話框相關函數
// ========================================

function showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

async function handlePiLogin() {
    console.log('handlePiLogin called');
    console.log('window.Pi exists:', !!window.Pi);
    console.log('piInitialized:', AuthManager.piInitialized);

    try {
        const result = await AuthManager.authenticateWithPi();
        console.log('Auth result:', result);
        if (result.success) {
            hideLoginModal();
            // 可以顯示成功提示
        } else {
            alert('Pi Network 認證失敗: ' + result.error);
        }
    } catch (error) {
        console.error('handlePiLogin error:', error);
        alert('錯誤: ' + error.message);
    }
}

async function handleTestLogin() {
    const publicKey = document.getElementById('login-public-key')?.value;
    const password = document.getElementById('login-password')?.value;

    if (!publicKey || !password) {
        alert('請輸入公鑰和密碼');
        return;
    }

    const result = await AuthManager.authenticateWithCredentials(publicKey, password);
    if (result.success) {
        hideLoginModal();
    } else {
        alert('認證失敗: ' + result.error);
    }
}

async function handleLogout() {
    const confirmed = await showConfirmDialog({
        title: '登出',
        message: '確定要登出嗎？',
        confirmText: '登出',
        cancelText: '取消',
        type: 'warning'
    });

    if (confirmed) {
        AuthManager.logout();
    }
}

// ========================================
// 初始化
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    // 檢查是否有已保存的登入狀態
    const isLoggedIn = AuthManager.init();

    // 如果沒有登入，顯示登入提示
    if (!isLoggedIn) {
        // 可以自動顯示登入對話框
        // showLoginModal();
    }
});

// 暴露到全局
window.AuthManager = AuthManager;
window.showLoginModal = showLoginModal;
window.hideLoginModal = hideLoginModal;
window.handlePiLogin = handlePiLogin;
window.handleTestLogin = handleTestLogin;
window.handleLogout = handleLogout;
