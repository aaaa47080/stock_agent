// ========================================
// pi-auth.js - Pi Network SDK 初始化與認證
// ========================================

/**
 * 初始化 Pi 登入防重複點擊機制
 */
window._piLoginInProgress = false;
window.__forceGuestLandingTab = false;
window.__piBrowserGateLocked = false;
window.__piBrowserGateReason = '';

function isSafePiSdkContext() {
    return window.PiEnvironment
        ? window.PiEnvironment.isSafeSdkContext()
        : window.location.protocol === 'https:';
}

function hasPiBrowserUserAgent() {
    const ua = (navigator.userAgent || '').toLowerCase();
    return ua.includes('pibrowser') || ua.includes('pi browser') || ua.includes('minepi');
}

function showPiBrowserRequiredModal() {
    const modal = document.getElementById('login-modal');
    const loginBtn = document.getElementById('pi-login-btn');
    const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
    if (loginBtn) loginBtn.style.display = 'none';
    if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'block';
    if (modal) modal.classList.remove('hidden');
}

function enableGuestLandingGate() {
    window.__forceGuestLandingTab = true;
}

function lockPiBrowserGate(reason = 'unknown') {
    window.__piBrowserGateLocked = true;
    window.__piBrowserGateReason = reason;
    enableGuestLandingGate();
    showPiBrowserRequiredModal();
}

function unlockPiBrowserGate() {
    window.__piBrowserGateLocked = false;
    window.__piBrowserGateReason = '';
    window.__forceGuestLandingTab = false;
}

function applyPiBrowserGateUI() {
    if (window.__piBrowserGateLocked) {
        showPiBrowserRequiredModal();
    }
}

window.lockPiBrowserGate = lockPiBrowserGate;
window.unlockPiBrowserGate = unlockPiBrowserGate;
window.applyPiBrowserGateUI = applyPiBrowserGateUI;
window.isPiBrowserGateLocked = function () {
    return window.__piBrowserGateLocked === true;
};

/**
 * 安全的 Pi 登入函數（含防重複點擊機制）
 */
window.safePiLogin = async function () {
    // 防止重複點擊
    if (window._piLoginInProgress) {
        console.log('登入已在進行中，忽略重複點擊');
        return;
    }

    const btn = document.getElementById('pi-login-btn');
    const originalText = btn ? btn.innerHTML : '';

    try {
        window._piLoginInProgress = true;

        // 更新按鈕狀態為 Loading
        if (btn) {
            btn.disabled = true;
            btn.innerHTML =
                '<svg class="animate-spin w-5 h-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg> 連接中...';
            btn.classList.add('opacity-70', 'cursor-not-allowed');
        }

        if (typeof handlePiLogin === 'function') {
            return await handlePiLogin();
        }
        // 如果 JS 尚未載入完成，等待後重試
        await new Promise((r) => setTimeout(r, 500));
        if (typeof handlePiLogin === 'function') {
            return await handlePiLogin();
        }
    } finally {
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
        // 完全沒有登入紀錄 → 直接顯示 modal
        enableGuestLandingGate();
        document.addEventListener('DOMContentLoaded', function () {
            showPiBrowserRequiredModal();
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
            enableGuestLandingGate();
            document.addEventListener('DOMContentLoaded', function () {
                showPiBrowserRequiredModal();
            });
            return;
        }
        // Token 有效 → 還需要檢測 Pi 環境
        // 如果不在 Pi Browser 中，仍需顯示提示（除非是測試模式）
        document.addEventListener('DOMContentLoaded', function () {
            // 明確不在 Pi Browser 相容上下文時，立即顯示 gate，
            // 避免頁面先還原到其他 tab 再被拉回登入提示。
            if (!isSafePiSdkContext()) {
                lockPiBrowserGate('unsafe_context_with_saved_token');
                return;
            }

            // 先檢查是否為測試模式
            var testModeCheck = fetch('/api/config')
                .then((r) => r.json())
                .catch(function () {
                    return { test_mode: false };
                });

            var attempts = 0;
            var maxAttempts = 30; // 最多等 3 秒
            var checkPiSDK = function () {
                var hasPiSDK =
                    typeof window.Pi !== 'undefined' &&
                    window.Pi !== null &&
                    typeof window.Pi.authenticate === 'function';
                if (hasPiSDK) {
                    // Pi SDK 存在，保持 modal hidden，讓 auth.js 正常處理
                    console.log('✅ Token valid + Pi SDK detected, normal flow');
                    return;
                }
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkPiSDK, 100);
                } else {
                    // Pi SDK 不存在 → 非 Pi 環境
                    // 檢查是否為測試模式，測試模式下不強制顯示 modal
                    testModeCheck.then(function (cfg) {
                        if (cfg && cfg.test_mode) {
                            console.log('✅ Test mode: skipping Pi Browser check');
                            return;
                        }
                        // 非測試模式，顯示 login modal 提示用戶
                        console.warn('⚠️ Token valid but NOT in Pi Browser, showing login modal');
                        lockPiBrowserGate('saved_token_without_sdk');
                    });
                }
            };
            checkPiSDK();
        });
    } catch (e) {
        localStorage.removeItem('pi_user');
        enableGuestLandingGate();
        document.addEventListener('DOMContentLoaded', function () {
            showPiBrowserRequiredModal();
        });
    }
})();

// ========================================
// Pi SDK 初始化（在 login modal 內）
// ========================================

/**
 * 初始化 Pi SDK 並檢測 Pi Browser 環境
 * 在 login modal 內執行，確保 Pi SDK 正確載入
 */
(function () {
    // 第一階段：確認 Pi SDK 已載入（最多等 3 秒）
    // 第二階段：用 nativeFeaturesList 驗證是否真正在 Pi Browser（最多再等 1.5 秒）
    // nativeFeaturesList 是 Pi Browser 專屬 native bridge，普通瀏覽器不具備
    (async function () {
        if (!isSafePiSdkContext()) {
            console.log('ℹ️ Skipping Pi SDK auto-init outside Pi Browser compatible context');
            lockPiBrowserGate('unsafe_context_auto_init');
            return;
        }

        // 階段一：等待 Pi SDK script 載入
        let attempts = 0;
        const maxAttempts = 30;
        const hasPiSDK = await new Promise((resolve) => {
            const check = () => {
                const detected =
                    typeof window.Pi !== 'undefined' &&
                    window.Pi !== null &&
                    typeof window.Pi.authenticate === 'function' &&
                    typeof window.Pi.init === 'function';
                if (detected) {
                    resolve(true);
                    return;
                }
                attempts++;
                if (attempts < maxAttempts) setTimeout(check, 100);
                else resolve(false);
            };
            check();
        });

        if (!hasPiSDK) {
            console.warn('⚠️ Pi SDK not detected after 3 seconds.');
            lockPiBrowserGate('sdk_not_detected');
            return; // 保持預設「請使用 Pi Browser」提示
        }

        if (window.__piBrowserGateLocked) {
            console.warn(
                '⚠️ Pi Browser gate already locked, skip exposing login button:',
                window.__piBrowserGateReason
            );
            return;
        }

        // 階段二：嘗試使用 nativeFeaturesList 做額外驗證（可選）
        // 若 UA 與 native bridge 都無法證明是 Pi Browser，維持 gate 鎖定
        const hasPiUA = hasPiBrowserUserAgent();
        let nativeVerified = false;

        try {
            await Pi.init({ version: '2.0', sandbox: false });
        } catch (initError) {
            console.warn('⚠️ Pi SDK init failed:', initError.message);
            lockPiBrowserGate('pi_init_failed');
            return;
        }

        if (typeof window.Pi.nativeFeaturesList === 'function') {
            // 有 nativeFeaturesList，做額外驗證
            try {
                const features = await Promise.race([
                    Pi.nativeFeaturesList(),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('TIMEOUT')), 1500)
                    ),
                ]);
                nativeVerified = true;
                console.log('✅ Pi Browser verified (nativeFeaturesList), features:', features);
            } catch (e) {
                console.warn(
                    '⚠️ nativeFeaturesList failed:',
                    e.message
                );
            }
        } else {
            console.log('ℹ️ nativeFeaturesList unavailable');
        }

        if (!hasPiUA && !nativeVerified) {
            console.warn(
                '⚠️ Pi SDK detected but UA/native verification failed. Keep Pi Browser gate locked.'
            );
            lockPiBrowserGate('ua_native_verification_failed');
            return;
        }

        // Pi SDK 存在，顯示登入按鈕讓用戶嘗試
        // 真正的認證會由 Pi.authenticate() 處理
        unlockPiBrowserGate();
        console.log('✅ Pi SDK loaded - showing login button');
        const loginBtn = document.getElementById('pi-login-btn');
        const notPiBrowserMsg = document.getElementById('not-pi-browser-msg');
        if (loginBtn) loginBtn.style.display = 'flex';
        if (notPiBrowserMsg) notPiBrowserMsg.style.display = 'none';
    })();
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
            const piArea = document.getElementById('pi-login-area');
            if (piArea) piArea.style.display = 'none';

            // 更新副標題文字
            const subtitle = document.querySelector(
                '#login-modal p[data-i18n="login.welcomeSubtitle"]'
            );
            if (subtitle) subtitle.textContent = 'Test mode enabled - click below to login';
        }
    })
    .catch(() => {});
