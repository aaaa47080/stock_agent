// ========================================
// pi-auth.js - Pi Network SDK 初始化與認證
// ========================================

/**
 * 初始化 Pi 登入防重複點擊機制
 */
AppStore.set('piLoginInProgress', false);
window._piLoginInProgress = false;
AppStore.set('forceGuestLandingTab', false);
window.__forceGuestLandingTab = false;
AppStore.set('piBrowserGateLocked', false);
window.__piBrowserGateLocked = false;
AppStore.set('piBrowserGateReason', '');
window.__piBrowserGateReason = '';

function isSafePiSdkContext() {
    if (window.PiEnvironment) return window.PiEnvironment.isSafeSdkContext();
    // Fallback: match auth.js PiEnvironment.isSafeSdkContext() logic exactly
    const isLocalhost =
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === '::1';
    return window.location.protocol === 'https:' && !isLocalhost;
}

function showPiBrowserRequiredModal() {
    const modal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('pi-login-btn');
    const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
    if (loginBtn) loginBtn.style.display = 'none';
    if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'block';
    if (modal) modal.classList.remove('hidden');
}

function showPiLoginLoadingModal() {
    const modal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('pi-login-btn');
    const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
    if (loginBtn) loginBtn.style.display = 'none';
    if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'none';
    if (modal) modal.classList.remove('hidden');
}

function enableGuestLandingGate() {
    AppStore.set('forceGuestLandingTab', true);
    window.__forceGuestLandingTab = true;
}

function lockPiBrowserGate(reason = 'unknown') {
    AppStore.set('piBrowserGateLocked', true);
    window.__piBrowserGateLocked = true;
    AppStore.set('piBrowserGateReason', reason);
    window.__piBrowserGateReason = reason;
    enableGuestLandingGate();
    showPiBrowserRequiredModal();
}

function unlockPiBrowserGate() {
    AppStore.set('piBrowserGateLocked', false);
    window.__piBrowserGateLocked = false;
    AppStore.set('piBrowserGateReason', '');
    window.__piBrowserGateReason = '';
    AppStore.set('forceGuestLandingTab', false);
    window.__forceGuestLandingTab = false;
}

function applyPiBrowserGateUI() {
    if (AppStore.get('piBrowserGateLocked')) {
        showPiBrowserRequiredModal();
    }
}

window.lockPiBrowserGate = lockPiBrowserGate;
window.unlockPiBrowserGate = unlockPiBrowserGate;
window.applyPiBrowserGateUI = applyPiBrowserGateUI;
window.isPiBrowserGateLocked = function () {
    return AppStore.get('piBrowserGateLocked') === true;
};

/**
 * 安全的 Pi 登入函數（含防重複點擊機制）
 */
window.safePiLogin = async function () {
    // 防止重複點擊
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

        // 更新按鈕狀態為 Loading
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
        // 如果 JS 尚未載入完成，等待後重試
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
        // 恢復按鈕狀態
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

/**
 * 為未登入用戶顯示 login modal
 * 檢查本地存儲的 token 是否有效，決定是否顯示登入介面
 */
(function () {
    var saved = localStorage.getItem('pi_user');
    if (!saved) {
        // 沒有登入紀錄時先顯示中性登入 modal，避免在 Pi Browser 中先誤顯示
        // 「非 Pi Browser」提示。
        document.addEventListener('DOMContentLoaded', function () {
            if (!isSafePiSdkContext()) {
                enableGuestLandingGate();
                showPiBrowserRequiredModal();
                return;
            }
            showPiLoginLoadingModal();
        });
        return;
    }
    // 有登入紀錄 → 先驗證 token 是否過期
    try {
        var user = JSON.parse(saved);
        var expiry = user.accessTokenExpiry;
        if (!expiry || Date.now() > expiry) {
            // Token 已過期，清除並顯示 modal
            localStorage.removeItem('pi_user');
            document.addEventListener('DOMContentLoaded', function () {
                if (!isSafePiSdkContext()) {
                    enableGuestLandingGate();
                    showPiBrowserRequiredModal();
                    return;
                }
                showPiLoginLoadingModal();
            });
            return;
        }
        // Token 有效：不要因為前端 SDK 載入延遲就把已登入會話判成 guest。
        document.addEventListener('DOMContentLoaded', function () {
            if (!isSafePiSdkContext()) {
                lockPiBrowserGate('unsafe_context_with_saved_token');
            }
        });
    } catch (e) {
        localStorage.removeItem('pi_user');
        document.addEventListener('DOMContentLoaded', function () {
            if (!isSafePiSdkContext()) {
                enableGuestLandingGate();
                showPiBrowserRequiredModal();
                return;
            }
            showPiLoginLoadingModal();
        });
    }
})();

// ========================================
// Pi SDK 初始化（在 login modal 內）
// ========================================

/**
 * 顯示登入按鈕並確保 modal 可見。
 * 必須在 DOMContentLoaded 後才能操作 DOM — 使用 readyState 確保安全。
 * 使用 setTimeout(0) 確保在同一輪 DOMContentLoaded 的其他 handler 完成後才執行，
 * 避免被 showPiLoginLoadingModal() 覆蓋。
 */
function _showLoginButton() {
    const show = () => {
        unlockPiBrowserGate();
        const modal = document.getElementById('login-modal');
        const loginBtn = document.getElementById('pi-login-btn');
        const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
        if (modal) modal.classList.remove('hidden');
        if (loginBtn) loginBtn.style.display = 'flex';
        if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'none';
        console.log('✅ Connect Wallet button shown');
    };
    if (document.readyState === 'loading') {
        // DOM 尚未就緒：等 DOMContentLoaded 再用 setTimeout(0) 後執行，
        // 確保晚於同輪其他 DOMContentLoaded handlers（如 showPiLoginLoadingModal）
        document.addEventListener('DOMContentLoaded', () => setTimeout(show, 0), { once: true });
    } else {
        // DOM 已就緒（含 interactive/complete）：直接執行
        show();
    }
}
window._showLoginButton = _showLoginButton;

/**
 * 偵測 Pi Browser 並顯示按鈕。
 * Pi.init() 及 Pi.authenticate() 在用戶點擊時才執行（由 auth.js 處理）。
 * 等待策略：最多輪詢 2 秒（20×100ms），超時則顯示「非 Pi Browser」提示。
 */
(function () {
    if (!isSafePiSdkContext()) {
        console.log('ℹ️ Non-Pi-Browser context — showing Pi Browser required message');
        lockPiBrowserGate('unsafe_context_auto_init');
        return;
    }

    // HTTPS 環境：Pi SDK script 已注入，等待最多 2 秒
    let attempts = 0;
    const maxAttempts = 20;
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
            console.warn('⚠️ Pi SDK not detected after 2s — showing Pi Browser required message');
            lockPiBrowserGate('pi_sdk_timeout');
        }
    };
    check();
})();

// ========================================
// 測試模式登入
// ========================================

/**
 * 檢測測試模式並顯示測試登入按鈕
 */
fetch('/api/config')
    .then((r) => r.json())
    .then((cfg) => {
        if (cfg.test_mode) {
            // 顯示測試模式登入區域
            const devArea = document.getElementById('dev-login-area');
            if (devArea) devArea.style.display = 'block';

            // 隱藏 Pi 錢包區域（測試模式不需要 Pi Browser）

            // 更新副標題文字
            const subtitle = document.querySelector(
                '#login-modal p[data-i18n="login.welcomeSubtitle"]'
            );
            if (subtitle) subtitle.textContent = 'Connect your wallet to continue, or use Dev Login in test mode';
        }
    })
// Side-effect module — no named exports needed.
// All functions are assigned to window for backward compatibility.
export {};
