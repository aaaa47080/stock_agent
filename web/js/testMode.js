// ========================================
// testMode.js - 測試模式功能
// ========================================

/**
 * 初始化測試模式 UI
 */
async function initTestMode() {
    const tierSwitcher = document.getElementById('test-tier-switcher');
    if (window.PiEnvironment?.shouldBlockProtectedRequests()) {
        if (tierSwitcher) {
            tierSwitcher.classList.add('hidden');
        }
        return;
    }

    // 檢查是否在測試模式
    try {
        const res = await fetch('/api/test-mode/current-tier', {
            headers: window.PiEnvironment?.getAuthHeaders() || {},
        });
        if (!res.ok) {
            // 非 403 錯誤，可能是真正的 API 錯誤
            if (res.status !== 403) {
                console.warn('[testMode] Failed to check test mode status');
            }
            return;
        }

        const data = await res.json();
        if (data.is_test_mode) {
            // 顯示等級切換器
            if (tierSwitcher) {
                tierSwitcher.classList.remove('hidden');
                updateTierButtons(data.tier);
            }
        }
    } catch (err) {
        // 非測試模式或 API 不可用，隱藏切換器
        if (tierSwitcher) {
            tierSwitcher.classList.add('hidden');
        }
    }
}

/**
 * 切換測試帳號等級
 */
async function handleSwitchTestTier(tier) {
    const btn = document.querySelector(`.test-tier-btn[data-tier="${tier}"]`);
    if (!btn) return;

    // 顯示 loading 狀態
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader" class="w-3 h-3 animate-spin"></i>';
    btn.disabled = true;

    try {
        const res = await fetch('/api/test-mode/switch-tier', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(window.PiEnvironment?.getAuthHeaders() || {}),
            },
            body: JSON.stringify({ tier: tier }),
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();

        if (data.success) {
            // 更新當前等級顯示
            document.getElementById('current-test-tier').textContent = tier.toUpperCase();

            // 更新按鈕狀態
            updateTierButtons(tier);

            // 重新載入工具設定以反映新等級的工具
            if (typeof initToolSettings === 'function') {
                await initToolSettings();
            }

            // 顯示成功訊息
            if (typeof showToast === 'function') {
                showToast(data.message, 'success', 3000);
            }
        } else {
            throw new Error(data.message || '切換失敗');
        }
    } catch (err) {
        console.error('[testMode] Switch tier error:', err);

        if (typeof showToast === 'function') {
            showToast('切換等級失敗: ' + (err.message || '未知錯誤'), 'error');
        }
    } finally {
        // 恢復按鈕狀態
        btn.innerHTML = originalText;
        btn.disabled = false;

        // 重新創建圖標
        if (window.lucide) {
            lucide.createIcons();
        }
    }
}

/**
 * 更新等級按鈕的選中狀態
 */
function updateTierButtons(currentTier) {
    document.querySelectorAll('.test-tier-btn').forEach(btn => {
        const tier = btn.dataset.tier;
        btn.classList.remove('bg-primary/20', 'text-primary', 'bg-accent/10', 'text-accent', 'bg-textMuted/10', 'ring-2', 'ring-primary/50');

        if (tier === currentTier) {
            // 選中狀態
            if (tier === 'premium') {
                btn.classList.add('bg-primary/20', 'text-primary', 'ring-2', 'ring-primary/50');
            } else {
                btn.classList.add('bg-textMuted/10', 'ring-2', 'ring-textMuted/50');
            }
        }
    });
}

// 導出函數供全局使用
window.handleSwitchTestTier = handleSwitchTestTier;
window.initTestMode = initTestMode;
