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

        // Settings Profile Elements
        const profileCard = document.getElementById('settings-profile-card');
        const profileAvatar = document.getElementById('profile-avatar');
        const profileUsername = document.getElementById('profile-username');
        const profileUid = document.getElementById('profile-uid');
        const profileMethod = document.getElementById('profile-method');

        // Sidebar User Elements
        const sidebarUserName = document.getElementById('sidebar-user-name');
        const sidebarUserAvatar = document.getElementById('sidebar-user-avatar');

        if (isLoggedIn && this.currentUser) {
            if (loginBtn) loginBtn.classList.add('hidden');
            if (logoutBtn) logoutBtn.classList.remove('hidden');
            if (userInfo) {
                userInfo.textContent = this.currentUser.username || 'User';
                userInfo.classList.remove('hidden');
            }
            if (loginOverlay) loginOverlay.classList.add('hidden');

            // Update Profile Card in Settings
            if (profileCard) {
                profileCard.classList.remove('hidden');
                if(profileUsername) profileUsername.textContent = this.currentUser.username || 'User';
                if(profileUid) profileUid.textContent = `UID: ${this.currentUser.uid}`;
                if(profileAvatar) profileAvatar.textContent = (this.currentUser.username || 'U')[0].toUpperCase();
                if(profileMethod) profileMethod.textContent = (this.currentUser.authMethod || 'UNKNOWN').replace('_', ' ').toUpperCase();
            }

            // Update Sidebar User Info
            if (sidebarUserName) sidebarUserName.textContent = this.currentUser.username || 'User';
            if (sidebarUserAvatar) {
                sidebarUserAvatar.textContent = (this.currentUser.username || 'U')[0].toUpperCase();
                sidebarUserAvatar.classList.remove('bg-surfaceHighlight');
                sidebarUserAvatar.classList.add('bg-gradient-to-br', 'from-primary', 'to-accent', 'text-background');
            }

        } else {
            if (loginBtn) loginBtn.classList.remove('hidden');
            if (logoutBtn) logoutBtn.classList.add('hidden');
            if (userInfo) userInfo.classList.add('hidden');
            if (loginOverlay) loginOverlay.classList.remove('hidden');

            // Hide Profile Card
            if (profileCard) profileCard.classList.add('hidden');

            // Reset Sidebar User Info
            if (sidebarUserName) sidebarUserName.textContent = 'Guest';
            if (sidebarUserAvatar) {
                sidebarUserAvatar.innerHTML = '<i data-lucide="user" class="w-4 h-4"></i>';
                sidebarUserAvatar.classList.add('bg-surfaceHighlight');
                sidebarUserAvatar.classList.remove('bg-gradient-to-br', 'from-primary', 'to-accent', 'text-background');
                if (window.lucide) window.lucide.createIcons();
            }
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

function toggleAuthMode(mode) {
    const loginForm = document.getElementById('form-login');
    const registerForm = document.getElementById('form-register');
    const loginTab = document.getElementById('tab-login');
    const registerTab = document.getElementById('tab-register');

    if (mode === 'login') {
        loginForm.classList.remove('hidden');
        registerForm.classList.add('hidden');
        loginTab.classList.remove('text-textMuted', 'hover:text-secondary');
        loginTab.classList.add('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        registerTab.classList.add('text-textMuted', 'hover:text-secondary');
        registerTab.classList.remove('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
    } else {
        loginForm.classList.add('hidden');
        registerForm.classList.remove('hidden');
        registerTab.classList.remove('text-textMuted', 'hover:text-secondary');
        registerTab.classList.add('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
        loginTab.classList.add('text-textMuted', 'hover:text-secondary');
        loginTab.classList.remove('bg-surfaceHighlight', 'text-secondary', 'shadow-sm');
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
            showToast('Pi Network 認證成功', 'success');
        } else {
            showToast('Pi Network 認證失敗: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('handlePiLogin error:', error);
        showToast('錯誤: ' + error.message, 'error');
    }
}

async function handleCredentialLogin() {
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const username = usernameInput?.value.trim();
    const password = passwordInput?.value;

    if (!username || !password) {
        showToast('請輸入用戶名和密碼', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/user/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            AuthManager.currentUser = {
                uid: data.user.uid,
                username: data.user.username,
                authMethod: 'password',
                loginTime: Date.now()
            };
            localStorage.setItem('pi_user', JSON.stringify(AuthManager.currentUser));
            AuthManager._updateGlobalUserId();
            AuthManager._updateUI(true);

            // 認證成功後初始化聊天
            if (typeof initChat === 'function') {
                await initChat();
            }

            hideLoginModal();
            showToast('登入成功', 'success');
        } else {
            showToast(data.detail || '登入失敗', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showToast('登入發生錯誤', 'error');
    }
}

async function handleRegister() {
    const username = document.getElementById('reg-username')?.value.trim();
    const email = document.getElementById('reg-email')?.value.trim();
    const password = document.getElementById('reg-password')?.value;
    const confirmPassword = document.getElementById('reg-confirm-password')?.value;

    if (!username || !password) {
        showToast('請填寫用戶名和密碼', 'warning');
        return;
    }

    // 用戶名長度驗證（至少 6 個字元）
    if (username.length < 6) {
        showToast('用戶名至少需要 6 個字元', 'warning');
        return;
    }

    // 密碼長度驗證（8-15 個字元）
    if (password.length < 8 || password.length > 15) {
        showToast('密碼需要 8-15 個字元', 'warning');
        return;
    }

    // Email 必填檢查
    if (!email) {
        showToast('請填寫 Email（用於密碼找回）', 'warning');
        return;
    }

    // Email 格式驗證
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showToast('請輸入有效的 Email 地址', 'warning');
        return;
    }

    // 再次檢查用戶名是否可用 (選擇性，確保安全)
    const checkResponse = await fetch(`/api/user/check/${username}`);
    const checkData = await checkResponse.json();
    if (!checkData.available) {
        showToast('該用戶名已被使用，請更換', 'warning');
        return;
    }

    if (password !== confirmPassword) {
        showToast('兩次密碼輸入不一致', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/user/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password, email })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('註冊成功，請登入', 'success');
            toggleAuthMode('login');
            // 自動填入用戶名
            document.getElementById('login-username').value = username;
        } else {
            showToast(data.detail || '註冊失敗', 'error');
        }
    } catch (error) {
        console.error('Register error:', error);
        showToast('註冊發生錯誤', 'error');
    }
}

async function checkUsernameAvailability() {
    const input = document.getElementById('reg-username');
    const msgElement = document.getElementById('reg-username-msg');
    const username = input?.value.trim();

    if (!username) {
        if(msgElement) {
            msgElement.textContent = '';
            msgElement.className = 'text-xs mt-1 min-h-[1.25rem] transition-colors duration-300';
        }
        input?.classList.remove('border-success/50', 'border-danger/50');
        input?.classList.add('border-white/5');
        return;
    }

    // 用戶名長度驗證
    if (username.length < 6) {
        if(msgElement) {
            msgElement.textContent = '用戶名至少需要 6 個字元';
            msgElement.className = 'text-xs mt-1 min-h-[1.25rem] text-danger font-bold transition-colors duration-300';
        }
        input?.classList.remove('border-white/5', 'border-success/50');
        input?.classList.add('border-danger/50');
        return;
    }

    try {
        const response = await fetch(`/api/user/check/${username}`);
        const data = await response.json();

        if (response.ok && data.available) {
            if(msgElement) {
                msgElement.textContent = '此用戶名可用';
                msgElement.className = 'text-xs mt-1 min-h-[1.25rem] text-success font-bold transition-colors duration-300';
            }
            input.classList.remove('border-white/5', 'border-danger/50');
            input.classList.add('border-success/50');
        } else {
             if(msgElement) {
                msgElement.textContent = data.message || '此用戶名已被註冊';
                msgElement.className = 'text-xs mt-1 min-h-[1.25rem] text-danger font-bold transition-colors duration-300';
            }
            input.classList.remove('border-white/5', 'border-success/50');
            input.classList.add('border-danger/50');
        }
    } catch (error) {
        console.error('Check username error:', error);
    }
}

async function checkEmailAvailability() {
    const input = document.getElementById('reg-email');
    const msgElement = document.getElementById('reg-email-msg');
    const email = input?.value.trim();

    if (!email) {
        if (msgElement) {
            msgElement.textContent = 'Required for password recovery';
            msgElement.className = 'text-xs text-textMuted/60 mt-1';
        }
        input?.classList.remove('border-success/50', 'border-danger/50');
        input?.classList.add('border-white/5');
        return;
    }

    // Email 格式驗證
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        if (msgElement) {
            msgElement.textContent = '請輸入有效的 Email 格式';
            msgElement.className = 'text-xs mt-1 text-danger font-bold';
        }
        input?.classList.remove('border-white/5', 'border-success/50');
        input?.classList.add('border-danger/50');
        return;
    }

    try {
        const response = await fetch(`/api/user/check-email/${encodeURIComponent(email)}`);
        const data = await response.json();

        if (response.ok && data.available) {
            if (msgElement) {
                msgElement.textContent = 'Email 可用';
                msgElement.className = 'text-xs mt-1 text-success font-bold';
            }
            input?.classList.remove('border-white/5', 'border-danger/50');
            input?.classList.add('border-success/50');
        } else {
            if (msgElement) {
                msgElement.textContent = data.message || '此 Email 已被註冊';
                msgElement.className = 'text-xs mt-1 text-danger font-bold';
            }
            input?.classList.remove('border-white/5', 'border-success/50');
            input?.classList.add('border-danger/50');
        }
    } catch (error) {
        console.error('Check email error:', error);
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
// 忘記密碼相關函數
// ========================================

// 當前重置 Token（從 URL 獲取）
let currentResetToken = null;

function showForgotPasswordModal() {
    hideLoginModal();
    const modal = document.getElementById('forgot-password-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('forgot-email')?.focus();
        if (window.lucide) window.lucide.createIcons();
    }
}

function hideForgotPasswordModal() {
    const modal = document.getElementById('forgot-password-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    showLoginModal();
}

async function handleForgotPassword() {
    const emailInput = document.getElementById('forgot-email');
    const submitBtn = document.getElementById('forgot-submit-btn');
    const email = emailInput?.value.trim();

    if (!email) {
        showToast('Please enter your email address', 'warning');
        return;
    }

    // Email 格式驗證
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showToast('Please enter a valid email address', 'warning');
        return;
    }

    // 禁用按鈕避免重複提交
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';
    }

    try {
        const response = await fetch('/api/user/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (response.ok) {
            showToast('If the email exists, a reset link has been sent.', 'success');
            hideForgotPasswordModal();
            // 清空輸入框
            if (emailInput) emailInput.value = '';
        } else {
            showToast(data.detail || 'Failed to send reset email', 'error');
        }
    } catch (error) {
        console.error('Forgot password error:', error);
        showToast('An error occurred. Please try again.', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Send Reset Link';
        }
    }
}

function showResetPasswordModal(token) {
    currentResetToken = token;
    hideLoginModal();
    const modal = document.getElementById('reset-password-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('reset-new-password')?.focus();
        if (window.lucide) window.lucide.createIcons();
    }
}

function hideResetPasswordModal() {
    const modal = document.getElementById('reset-password-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    currentResetToken = null;
    // 清除 URL 中的 token 參數
    const url = new URL(window.location);
    url.searchParams.delete('reset_token');
    window.history.replaceState({}, '', url);
    showLoginModal();
}

async function handleResetPassword() {
    const newPassword = document.getElementById('reset-new-password')?.value;
    const confirmPassword = document.getElementById('reset-confirm-password')?.value;
    const submitBtn = document.getElementById('reset-submit-btn');

    if (!newPassword || !confirmPassword) {
        showToast('Please fill in all fields', 'warning');
        return;
    }

    if (newPassword.length < 6) {
        showToast('Password must be at least 6 characters', 'warning');
        return;
    }

    if (newPassword !== confirmPassword) {
        showToast('Passwords do not match', 'warning');
        return;
    }

    if (!currentResetToken) {
        showToast('Invalid reset token. Please request a new reset link.', 'error');
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Resetting...';
    }

    try {
        const response = await fetch('/api/user/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token: currentResetToken,
                new_password: newPassword
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('Password reset successfully! Please login.', 'success');
            hideResetPasswordModal();
            // 清空輸入框
            document.getElementById('reset-new-password').value = '';
            document.getElementById('reset-confirm-password').value = '';
        } else {
            showToast(data.detail || 'Failed to reset password', 'error');
        }
    } catch (error) {
        console.error('Reset password error:', error);
        showToast('An error occurred. Please try again.', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Reset Password';
        }
    }
}

async function checkResetTokenFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const resetToken = urlParams.get('reset_token');

    if (resetToken) {
        // 驗證 Token 是否有效
        try {
            const response = await fetch(`/api/user/verify-reset-token/${resetToken}`);
            const data = await response.json();

            if (data.valid) {
                showResetPasswordModal(resetToken);
            } else {
                showToast('Invalid or expired reset link. Please request a new one.', 'error');
                // 清除 URL 參數
                const url = new URL(window.location);
                url.searchParams.delete('reset_token');
                window.history.replaceState({}, '', url);
            }
        } catch (error) {
            console.error('Token verification error:', error);
            showToast('Failed to verify reset token.', 'error');
        }
    }
}

// ========================================
// 初始化
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    // 檢查是否有已保存的登入狀態
    const isLoggedIn = AuthManager.init();

    // 檢查 URL 是否有重置密碼的 Token
    checkResetTokenFromUrl();

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
window.handleCredentialLogin = handleCredentialLogin;
window.handleRegister = handleRegister;
window.checkUsernameAvailability = checkUsernameAvailability;
window.checkEmailAvailability = checkEmailAvailability;
window.toggleAuthMode = toggleAuthMode;
window.handleLogout = handleLogout;
window.showForgotPasswordModal = showForgotPasswordModal;
window.hideForgotPasswordModal = hideForgotPasswordModal;
window.handleForgotPassword = handleForgotPassword;
window.showResetPasswordModal = showResetPasswordModal;
window.hideResetPasswordModal = hideResetPasswordModal;
window.handleResetPassword = handleResetPassword;