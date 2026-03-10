/**
 * 高級會員功能模組
 * 處理升級到高級會員的支付和狀態管理
 */

class PremiumManager {
    constructor() {
        this.premiumPrice = null; // 初始為 null，完全依賴後端
        this.initEventListeners();
    }

    /**
     * 初始化事件監聽器
     */
    initEventListeners() {
        // 監聽 DOMContentLoaded
        document.addEventListener('DOMContentLoaded', () => {
            // 嘗試從全局變數獲取（如果已經載入）
            if (window.PiPrices?.premium) {
                this.premiumPrice = window.PiPrices.premium;
            }
            this.updatePriceDisplay();
            this.initUpgradeButtons();

            // 如果價格仍未載入，嘗試手動載入
            if (this.premiumPrice === null && typeof loadPiPrices === 'function') {
                loadPiPrices();
            }
        });

        // 監聽價格更新事件 (由 forum.js 觸發)
        document.addEventListener('pi-prices-updated', () => {
            if (window.PiPrices?.premium) {
                this.premiumPrice = window.PiPrices.premium;
                this.updatePriceDisplay();
            }
        });
    }

    /**
     * 更新價格顯示
     */
    updatePriceDisplay() {
        let displayHtml;
        if (this.premiumPrice !== null) {
            displayHtml = `${this.premiumPrice} Pi`;
        } else {
            // 尝试从全局变量获取最新价格
            if (window.PiPrices?.premium) {
                this.premiumPrice = window.PiPrices.premium;
                displayHtml = `${this.premiumPrice} Pi`;
            } else {
                displayHtml = '<span class="animate-pulse">Loading...</span>';
            }
        }

        // 更新所有顯示價格的元素
        const priceElements = document.querySelectorAll('[data-price="premium"]');
        priceElements.forEach((element) => {
            element.innerHTML = displayHtml;
        });
    }

    /**
     * 初始化升級按鈕
     */
    initUpgradeButtons() {
        // 查找所有升級按鈕並添加事件監聽器
        const upgradeButtons = document.querySelectorAll('.upgrade-premium-btn');
        upgradeButtons.forEach((button) => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleUpgradeClick();
            });
        });
    }

    /**
     * 處理升級按鈕點擊
     */
    async handleUpgradeClick() {
        try {
            // 確保價格已載入
            if (this.premiumPrice === null) {
                // 再次嘗試從全局讀取
                if (window.PiPrices?.premium) {
                    this.premiumPrice = window.PiPrices.premium;
                } else {
                    // 使用智能重試策略載入價格
                    if (typeof loadPiPrices === 'function') {
                        showToast('正在獲取最新價格...', 'info', 2000);

                        try {
                            // 主動觸發載入
                            await loadPiPrices();

                            // 使用指數退避重試（最多 3 次）
                            let retries = 0;
                            while (!window.PiPrices?.premium && retries < 3) {
                                await new Promise((resolve) =>
                                    setTimeout(resolve, 500 * Math.pow(2, retries))
                                );
                                retries++;
                            }

                            // 檢查是否成功載入
                            if (window.PiPrices?.premium) {
                                this.premiumPrice = window.PiPrices.premium;
                            } else {
                                // 無法載入價格，顯示錯誤
                                showToast('無法取得價格配置，請重新整理頁面', 'error');
                                console.error('[Premium] 無法從後端獲取價格，請確認 API 連線');
                                return;
                            }
                        } catch (error) {
                            console.error('[Premium] 載入價格時發生錯誤:', error);
                            showToast('價格載入失敗，請重新整理頁面', 'error');
                            return;
                        }
                    } else {
                        // 如果沒有 loadPiPrices 函數，顯示錯誤
                        showToast('系統錯誤：價格載入模組未初始化', 'error');
                        console.error('[Premium] loadPiPrices 函數不存在');
                        return;
                    }

                    // 更新顯示
                    this.updatePriceDisplay();
                }
            }

            // 檢查用戶是否已登入
            if (!window.AuthManager || !window.AuthManager.currentUser) {
                showToast('請先登入', 'warning');
                return;
            }

            // 檢查是否已在 Pi Browser 中
            const isPi = typeof isPiBrowser === 'function' ? isPiBrowser() : false;

            if (!isPi) {
                showToast('請在 Pi Browser 中進行升級', 'warning');
                return;
            }

            // 確認升級
            const confirmed = await this.showUpgradeConfirmation();
            if (!confirmed) return;

            // 開始升級流程
            await this.startUpgradeProcess();
        } catch (error) {
            console.error('[Premium] 升級錯誤:', error);
            showToast('升級過程中發生錯誤: ' + error.message, 'error');
        }
    }

    /**
     * 顯示升級確認對話框
     */
    async showUpgradeConfirmation() {
        return new Promise((resolve) => {
            // 檢查是否有現有的確認對話框
            const existingModal = document.getElementById('confirm-modal');
            if (existingModal) {
                // 設置對話框內容
                document.getElementById('confirm-modal-title').textContent = '確認升級';
                document.getElementById('confirm-modal-message').innerHTML = `
                    確認升級到高級會員？<br>
                    <strong>${this.premiumPrice} Pi</strong> 將從您的錢包扣除。<br>
                    <small class="text-textMuted/60">高級會員享有無限發文、無限回覆等特權。</small>
                `;

                // 設置圖標
                const iconEl = document.getElementById('confirm-modal-icon');
                iconEl.className =
                    'w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 bg-success/20';
                iconEl.innerHTML = '<i data-lucide="star" class="w-8 h-8 text-success"></i>';

                // 設置按鈕
                const cancelBtn = document.getElementById('confirm-modal-cancel');
                const confirmBtn = document.getElementById('confirm-modal-confirm');

                cancelBtn.textContent = '取消';
                confirmBtn.textContent = `支付 ${this.premiumPrice} Pi`;
                confirmBtn.className =
                    'flex-1 py-3 bg-success hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg';

                // 設置事件處理器
                const handleCancel = () => {
                    existingModal.classList.add('hidden');
                    resolve(false);
                };

                const handleConfirm = async () => {
                    existingModal.classList.add('hidden');
                    resolve(true);

                    // 移除事件監聽器
                    cancelBtn.removeEventListener('click', handleCancel);
                    confirmBtn.removeEventListener('click', handleConfirm);
                };

                // 添加事件監聽器
                cancelBtn.removeEventListener('click', handleCancel);
                confirmBtn.removeEventListener('click', handleConfirm);
                cancelBtn.addEventListener('click', handleCancel);
                confirmBtn.addEventListener('click', handleConfirm);

                // 顯示對話框
                existingModal.classList.remove('hidden');

                // 更新 Lucide 圖標
                if (window.lucide) {
                    lucide.createIcons();
                }
            } else {
                // 如果沒有預設對話框，使用瀏覽器確認
                const result = confirm(
                    `確認升級到高級會員？${this.premiumPrice} Pi 將從您的錢包扣除。`
                );
                resolve(result);
            }
        });
    }

    /**
     * 開始升級流程
     */
    async startUpgradeProcess() {
        let loadingToastId = null;

        try {
            // 顯示處理中提示
            loadingToastId = showToast('正在處理升級...', 'info', 0); // 持續顯示

            // 1. 認證 Pi 支付權限
            await this.authenticateForPayment();

            // 2. 執行 Pi 支付
            const txHash = await this.executePiPayment();

            if (!txHash) {
                // 清除加載提示
                if (loadingToastId) {
                    const toastContainer = document.getElementById('toast-container');
                    if (toastContainer) toastContainer.innerHTML = '';
                }
                showToast('支付失敗或已取消', 'error');
                return;
            }

            // 3. 請求後端升級會員
            const upgradeResult = await this.requestUpgrade(txHash);

            if (upgradeResult.success) {
                // 清除之前的提示
                if (loadingToastId) {
                    const toastContainer = document.getElementById('toast-container');
                    if (toastContainer) toastContainer.innerHTML = '';
                }

                showToast('🎉 恭喜！您已成為高級會員！', 'success', 5000);

                // 更新用戶界面
                this.updateUserInterface();

                // 重新載入頁面以反映新的會員狀態
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                // 清除加載提示
                if (loadingToastId) {
                    const toastContainer = document.getElementById('toast-container');
                    if (toastContainer) toastContainer.innerHTML = '';
                }
                showToast('升級失敗: ' + upgradeResult.message, 'error');
            }
        } catch (error) {
            console.error('[Premium] 升級流程錯誤:', error);
            // 清除加載提示
            if (loadingToastId) {
                const toastContainer = document.getElementById('toast-container');
                if (toastContainer) toastContainer.innerHTML = '';
            }
            showToast('升級失敗: ' + error.message, 'error');
        }
    }

    /**
     * 認證 Pi 支付權限
     */
    async authenticateForPayment() {
        if (!window.Pi) {
            throw new Error('Pi SDK 未載入');
        }

        try {
            // 快速環境驗證
            if (
                window.AuthManager &&
                typeof window.AuthManager.verifyPiBrowserEnvironment === 'function'
            ) {
                const envCheck = await window.AuthManager.verifyPiBrowserEnvironment();
                if (!envCheck.valid) {
                    throw new Error('Pi Browser 環境異常，請確認已登入 Pi 帳號');
                }
            }

            // 認證 payments scope
            await window.Pi.authenticate(['payments'], (incompletePayment) => {
                console.warn('[Premium] 發現未完成的支付', incompletePayment);
                // 處理未完成的支付
                this.handleIncompletePayment(incompletePayment);
            });

            console.log('[Premium] payments scope 認證成功');
        } catch (authErr) {
            console.error('[Premium] payments scope 認證失敗', authErr);
            throw new Error('支付權限不足，請重新登入 Pi 帳號');
        }
    }

    /**
     * 處理未完成的支付
     */
    async handleIncompletePayment(payment) {
        console.warn('[Premium] 處理未完成支付:', payment);
        try {
            // 呼叫後端 API 完成或取消此支付
            await fetch('/api/user/payment/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(window.AuthManager?.currentUser?.accessToken
                        ? { Authorization: `Bearer ${window.AuthManager.currentUser.accessToken}` }
                        : {}),
                },
                body: JSON.stringify({
                    paymentId: payment.identifier,
                    txid: payment.transaction?.txid || null,
                }),
            });
        } catch (e) {
            console.error('[Premium] 處理未完成支付失敗:', e);
        }
    }

    /**
     * 執行 Pi 支付
     */
    async executePiPayment() {
        return new Promise((resolve, reject) => {
            let paymentComplete = false;
            let paymentError = null;
            let txHash = null;

            console.log(`[Premium] 開始支付 ${this.premiumPrice} Pi`);

            try {
                window.Pi.createPayment(
                    {
                        amount: this.premiumPrice,
                        memo: `升級高級會員 (${this.premiumPrice} Pi)`,
                        metadata: {
                            type: 'premium_upgrade',
                            user_id:
                                window.AuthManager.currentUser?.user_id ||
                                window.AuthManager.currentUser?.uid,
                            upgrade_type: 'premium',
                        },
                    },
                    {
                        // 步驟 1: 支付已創建，等待後端批准
                        onReadyForServerApproval: async (paymentId) => {
                            console.log('[Premium] 支付待批准:', paymentId);
                            try {
                                const response = await fetch('/api/user/payment/approve', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        ...(window.AuthManager?.currentUser?.accessToken
                                            ? {
                                                  Authorization: `Bearer ${window.AuthManager.currentUser.accessToken}`,
                                              }
                                            : {}),
                                    },
                                    body: JSON.stringify({ paymentId }),
                                });

                                if (!response.ok) {
                                    const errorData = await response.json();
                                    console.error('[Premium] 批准請求失敗:', errorData);
                                    throw new Error(errorData.detail || '批准請求失敗');
                                }

                                console.log('[Premium] 支付批准成功:', paymentId);
                            } catch (error) {
                                console.error('[Premium] 批准支付時發生錯誤:', error);
                            }
                        },

                        // 步驟 2: 區塊鏈交易完成，等待後端確認完成
                        onReadyForServerCompletion: async (paymentId, txid) => {
                            console.log('[Premium] 支付待完成:', paymentId, txid);

                            // 立即保存 txid 到 localStorage 以防萬一
                            try {
                                localStorage.setItem(
                                    'pending_premium_upgrade',
                                    JSON.stringify({
                                        paymentId,
                                        txid,
                                        timestamp: Date.now(),
                                    })
                                );
                            } catch (e) {
                                console.warn('[Premium] 無法保存到 localStorage:', e);
                            }

                            // 重試機制：最多 3 次
                            let retryCount = 0;
                            const maxRetries = 3;
                            let lastError = null;

                            while (retryCount < maxRetries) {
                                try {
                                    console.log(
                                        `[Premium] 嘗試完成請求 (${retryCount + 1}/${maxRetries})...`
                                    );

                                    const response = await fetch('/api/user/payment/complete', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                            ...(window.AuthManager?.currentUser?.accessToken
                                                ? {
                                                      Authorization: `Bearer ${window.AuthManager.currentUser.accessToken}`,
                                                  }
                                                : {}),
                                        },
                                        body: JSON.stringify({ paymentId, txid }),
                                    });

                                    if (response.ok) {
                                        // 成功！清除 localStorage
                                        try {
                                            localStorage.removeItem('pending_premium_upgrade');
                                        } catch (e) {}

                                        txHash = txid;
                                        paymentComplete = true;
                                        console.log('[Premium] 支付完成:', { paymentId, txid });

                                        // 清除加載提示
                                        const toastContainer =
                                            document.getElementById('toast-container');
                                        if (toastContainer) toastContainer.innerHTML = '';

                                        resolve(txid);
                                        return; // 成功退出
                                    } else {
                                        const errorData = await response.json();
                                        lastError = new Error(errorData.detail || '完成請求失敗');
                                        console.warn(
                                            `[Premium] 完成請求失敗 (嘗試 ${retryCount + 1}):`,
                                            errorData
                                        );
                                    }
                                } catch (error) {
                                    lastError = error;
                                    console.warn(
                                        `[Premium] 網絡錯誤 (嘗試 ${retryCount + 1}):`,
                                        error
                                    );
                                }

                                retryCount++;
                                if (retryCount < maxRetries) {
                                    // 指數退避：等待 1s, 2s, 4s
                                    await new Promise((r) =>
                                        setTimeout(r, 1000 * Math.pow(2, retryCount - 1))
                                    );
                                }
                            }

                            // 所有重試都失敗，顯示錯誤並保持 txid
                            console.error('[Premium] 完成支付所有重試均失敗:', lastError);
                            console.error('[Premium] 交易已完成但後端確認失敗，txid:', txid);

                            // 清除加載提示
                            const toastContainer = document.getElementById('toast-container');
                            if (toastContainer) toastContainer.innerHTML = '';

                            // 不拒絕 Promise，而是設置一個標記並繼續
                            txHash = txid;
                            paymentComplete = true; // 支付確實完成了

                            // 提示用戶聯繫客服
                            showToast(
                                '⚠️ 支付已完成，但系統確認失敗。請聯繫客服並提供交易 ID。',
                                'warning',
                                10000
                            );

                            resolve(txid); // 繼續流程，讓用戶可以使用 txid 重試升級
                        },

                        // 用戶取消支付
                        onCancel: (paymentId) => {
                            console.log('[Premium] 支付已取消:', paymentId);
                            paymentError = 'CANCELLED';

                            // 清除加載提示
                            const toastContainer = document.getElementById('toast-container');
                            if (toastContainer) toastContainer.innerHTML = '';

                            reject(new Error('用戶取消支付'));
                        },

                        // 發生錯誤
                        onError: (error, payment) => {
                            console.error('[Premium] 支付錯誤:', error, payment);
                            paymentError = error;

                            // 清除加載提示
                            const toastContainer = document.getElementById('toast-container');
                            if (toastContainer) toastContainer.innerHTML = '';

                            reject(error);
                        },
                    }
                );

                // 等待支付完成（最多 120 秒）
                const startTime = Date.now();
                const checkInterval = setInterval(async () => {
                    if (paymentComplete || paymentError) {
                        clearInterval(checkInterval);
                        return;
                    }

                    if (Date.now() - startTime >= 120000) {
                        // 2分鐘超時
                        clearInterval(checkInterval);

                        // 清除加載提示
                        const toastContainer = document.getElementById('toast-container');
                        if (toastContainer) toastContainer.innerHTML = '';

                        reject(new Error('支付超時'));
                    }
                }, 500);
            } catch (error) {
                console.error('[Premium] 創建支付時發生錯誤:', error);

                // 清除加載提示
                const toastContainer = document.getElementById('toast-container');
                if (toastContainer) toastContainer.innerHTML = '';

                reject(error);
            }
        });
    }

    /**
     * 請求後端升級會員
     */
    async requestUpgrade(txHash) {
        const userId =
            window.AuthManager.currentUser?.user_id || window.AuthManager.currentUser?.uid;

        if (!userId) {
            throw new Error('無法獲取用戶ID');
        }

        const response = await fetch('/api/premium/upgrade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(window.AuthManager?.currentUser?.accessToken
                    ? { Authorization: `Bearer ${window.AuthManager.currentUser.accessToken}` }
                    : {}),
            },
            body: JSON.stringify({
                user_id: userId,
                months: 1, // 默認1個月，可以根據需要調整
                tx_hash: txHash,
            }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || '升級請求失敗');
        }

        return result;
    }

    /**
     * 更新用戶界面以反映新的會員狀態
     */
    updateUserInterface() {
        // 更新會員狀態顯示
        const membershipBadges = document.querySelectorAll('.membership-badge');
        membershipBadges.forEach((badge) => {
            badge.innerHTML = `
                <i data-lucide="star" class="w-3 h-3"></i>
                高級會員
            `;
            badge.className =
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-gradient-to-r from-yellow-500 to-orange-500 text-white';
        });

        // 更新用戶頭像（如果適用）
        const avatarElements = document.querySelectorAll('.premium-avatar');
        avatarElements.forEach((avatar) => {
            avatar.classList.add(
                'ring-2',
                'ring-yellow-500',
                'ring-offset-2',
                'ring-offset-background'
            );
        });

        // 更新功能限制提示（如果適用）
        const premiumFeatures = document.querySelectorAll('.premium-feature');
        premiumFeatures.forEach((feature) => {
            feature.classList.remove('hidden');
        });

        // 更新 Lucide 圖標
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    /**
     * 檢查用戶當前的會員狀態
     */
    async checkMembershipStatus(userId) {
        try {
            const response = await fetch(`/api/premium/status/${userId}`);
            const result = await response.json();

            if (response.ok && result.success) {
                return result.membership;
            }

            return { tier: 'free', is_pro: false, expires_at: null };
        } catch (error) {
            console.error('[Premium] 獲取會員狀態失敗:', error);
            return { tier: 'free', is_pro: false, expires_at: null };
        }
    }
}

// 初始化 PremiumManager
window.PremiumManager = new PremiumManager();

// 暴露全局函數
window.upgradeToPremium = () => window.PremiumManager.handleUpgradeClick();
window.checkMembershipStatus = (userId) => window.PremiumManager.checkMembershipStatus(userId);

console.log('[Premium] 高級會員模組已載入');
