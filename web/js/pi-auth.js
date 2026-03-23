// ========================================
// pi-auth.js - Pi Network SDK 初始化與認證
// ========================================

AppStore.set('piLoginInProgress', false);
window._piLoginInProgress = false;

window.safePiLogin = async function () {
    if (AppStore.get('piLoginInProgress')) {
        console.log('登入已在進行中，忽略重複點擊');
        return;
    }

    const btn = document.getElementById('pi-login-btn');
    const originalText = btn ? btn.innerHTML : '';
    const LOGIN_WATCHDOG_MS = 70000;
    let watchdogId = null;

    try {
        AppStore.set('piLoginInProgress', true);
        window._piLoginInProgress = true;

        if (btn) {
            btn.disabled = true;
            btn.innerHTML =
                '<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> 連接中...';
            btn.classList.add('opacity-70', 'cursor-not-allowed');
        }

        const runLogin = () => {
            const watchdogPromise = new Promise((_, reject) => {
                watchdogId = setTimeout(() => reject(new Error('Pi 登入逾時，請重試')), LOGIN_WATCHDOG_MS);
            });
            return Promise.race([handlePiLogin(), watchdogPromise]);
        };

        if (typeof handlePiLogin === 'function') {
            return await runLogin();
        }
        await new Promise((r) => setTimeout(r, 500));
        if (typeof handlePiLogin === 'function') {
            return await runLogin();
        }
    } catch (error) {
        console.error('[Pi Login] safePiLogin failed:', error);
        if (typeof showToast === 'function') {
            showToast(error?.message || 'Pi 登入失敗，請稍後重試', 'error');
        }
    } finally {
        if (watchdogId) clearTimeout(watchdogId);
        AppStore.set('piLoginInProgress', false);
        window._piLoginInProgress = false;
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
            btn.classList.remove('opacity-70', 'cursor-not-allowed');
        }
    }
};

// ========================================
// Login Modal 顯示邏輯
// ========================================

function _showLoginButton() {
    const show = () => {
        const loginBtn = document.getElementById('pi-login-btn');
        const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
        if (loginBtn) loginBtn.style.display = 'flex';
        if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'none';
        const modal = document.getElementById('login-modal');
        if (modal) modal.classList.remove('hidden');
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(show, 0), { once: true });
    } else {
        show();
    }
}
window._showLoginButton = _showLoginButton;

function showPiLoginLoadingModal() {
    const modal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('pi-login-btn');
    const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
    if (loginBtn) loginBtn.style.display = 'none';
    if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'none';
    if (modal) modal.classList.remove('hidden');
}

// 不再使用 gate 鎖定機制。
// Pi SDK 只在 Pi Browser 裡運作，非 Pi Browser 用戶 Pi.authenticate() 自然會報錯。
// 保留空的函數簽名避免其他 JS 呼叫時出錯（向後相容）。
window.lockPiBrowserGate = function () {};
window.unlockPiBrowserGate = function () {};
window.applyPiBrowserGateUI = function () {};
window.isPiBrowserGateLocked = function () { return false; };

// 等待 Pi SDK 載入後顯示 Connect Wallet 按鈕
(function () {
    let attempts = 0;
    const maxAttempts = 50;
    const check = () => {
        const detected =
            typeof window.Pi !== 'undefined' &&
            window.Pi !== null &&
            typeof window.Pi.authenticate === 'function';
        if (detected) {
            _showLoginButton();
            return;
        }
        attempts++;
        if (attempts < maxAttempts) {
            setTimeout(check, 100);
        } else {
            _showLoginButton();
        }
    };
    check();
})();

// ========================================
// 測試模式登入
// ========================================

fetch('/api/config')
    .then((r) => r.json())
    .then((cfg) => {
        if (cfg.test_mode) {
            const devArea = document.getElementById('dev-login-area');
            if (devArea) devArea.style.display = 'block';
            const subtitle = document.querySelector(
                '#login-modal p[data-i18n="login.welcomeSubtitle"]'
            );
            if (subtitle) subtitle.textContent = 'Connect your wallet to continue, or use Dev Login in test mode';
        }
    })
export {};
