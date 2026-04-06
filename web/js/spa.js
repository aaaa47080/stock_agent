// ========================================
// spa.js - Single Page Application Core
// ========================================

// AppStore is the single source of truth for active tab
AppStore.set('activeTab', 'chat');

// Helper to get activeTab from AppStore (source of truth) with localStorage fallback
function getActiveTab() {
    return AppStore.get('activeTab') || localStorage.getItem('activeTab') || 'chat';
}

var VALID_TABS = [
    'chat', 'crypto', 'twstock', 'usstock', 'commodity', 'forex', 'hkstock', 'astock', 'jpstock', 'instock',
    'wallet', 'friends', 'forum', 'safety', 'settings', 'admin',
];

// ========================================
// Navigation Logic (Updated with Smooth Transitions)
// ========================================

/**
 * Switch to a different tab with smooth transition
 * @param {string} tabId - The tab ID to switch to
 * @param {boolean} fromPopState - Whether this is triggered by browser back/forward
 * @returns {Promise<void>}
 */
async function switchTab(tabId, fromPopState = false) {
    if (!VALID_TABS.includes(tabId)) {
        console.warn(`Invalid tab '${tabId}', falling back to 'chat'`);
        tabId = 'chat';
    }

    // [Security] Strict Login Check
    if (window.AuthManager && !window.AuthManager.isLoggedIn()) {
        const modal = document.getElementById('login-modal');
        if (modal && modal.classList.contains('hidden')) {
            console.warn('⚠️ Access denied: User not logged in. Showing login modal.');
            modal.classList.remove('hidden');
        }
        tabId = 'chat';
    }

    const currentTab = document.querySelector('.tab-content:not(.hidden)');
    const targetTab = document.getElementById(tabId + '-tab');

    if (currentTab && currentTab.id !== tabId + '-tab') {
        // 1. 先讓當前頁面淡出
        currentTab.style.opacity = '0';
        currentTab.style.transform = 'translateY(-5px)';
        currentTab.style.transition = 'all 0.2s ease-in';

        return new Promise((resolve) => {
            setTimeout(async () => {
                await executeTabSwitch(tabId, fromPopState);
                resolve();
            }, 150);
        });
    } else {
        return await executeTabSwitch(tabId, fromPopState);
    }
}
window.switchTab = switchTab;

// 監聽瀏覽器返回/前進按鈕
window.addEventListener('popstate', (event) => {
    let targetTab = 'chat';

    if (event.state && event.state.tab) {
        targetTab = event.state.tab;
    } else if (window.location.hash) {
        const hashTab = window.location.hash.replace('#', '');
        if (VALID_TABS.includes(hashTab)) {
            targetTab = hashTab;
        }
    }

    // 使用 fromPopState=true 避免再次 pushState
    switchTab(targetTab, true);
});

/**
 * Navigate to forum (save current tab for return)
 */
function navigateToForum() {
    // 保存當前 tab 到 sessionStorage
    const currentTab = getActiveTab();
    sessionStorage.setItem('returnToTab', currentTab);
    smoothNavigate('/static/index.html#forum');
}
window.navigateToForum = navigateToForum;

/**
 * Execute the actual tab switching logic
 * @param {string} tabId - The tab ID to switch to
 * @param {boolean} fromPopState - Whether this is triggered by browser back/forward
 * @returns {Promise<void>}
 */
async function executeTabSwitch(tabId, fromPopState = false) {
    // Check if the target tab is enabled in user preferences
    if (window.NavPreferences && !NavPreferences.isItemEnabled(tabId)) {
        window.APP_CONFIG?.DEBUG_MODE &&
            console.log(`Tab '${tabId}' is disabled, redirecting to first enabled tab`);
        const enabledItems = NavPreferences.getEnabledItems();
        if (enabledItems.length > 0) {
            tabId = enabledItems[0].id;
        }
    }

    localStorage.setItem('activeTab', tabId);
    AppStore.set('activeTab', tabId); // source of truth

    // 更新瀏覽器歷史記錄（只有非 popstate 觸發時才 push）
    if (!fromPopState && window.location.hash !== '#' + tabId) {
        history.pushState({ tab: tabId }, '', '#' + tabId);
    }

    // Close any open stock chart overlays (they are fixed-position, not inside tab DOM)
    if (window.TWStockTab && typeof window.TWStockTab.closeTwChart === 'function')
        window.TWStockTab.closeTwChart();
    if (window.USStockTab && typeof window.USStockTab.closeChart === 'function')
        window.USStockTab.closeChart();
    // Close price alert modal if open
    if (typeof window.closeAlertModal === 'function') window.closeAlertModal();

    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach((el) => {
        el.classList.add('hidden');
        el.style.opacity = '';
        el.style.transform = '';
        el.style.transition = '';
    });

    // Dynamic Component Injection (Lazy Loading)
    if (
        [
            'crypto',
            'twstock',
            'usstock',
            'settings',
            'friends',
            'forum',
            'safety',
            'admin',
        ].includes(tabId)
    ) {
        if (window.Components && typeof window.Components.inject === 'function') {
            await window.Components.inject(tabId);
        }
    }

    // [Sidebar Visibility Logic]
    // Show chat sidebar only in analysis/research tabs where users might want to chat
    // Utility/admin tabs (wallet, assets, friends, forum, safety, settings, admin) don't need it
    const tabsWithSidebar = ['chat'];
    const globalSidebar = document.getElementById('chat-sidebar');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
    if (globalSidebar) {
        if (tabsWithSidebar.includes(tabId)) {
            // Show sidebar in analysis tabs - users can ask AI about what they see
            globalSidebar.style.display = '';
            globalSidebar.classList.remove('hidden');
        } else {
            // Hide sidebar in utility/admin tabs - not relevant there
            globalSidebar.style.setProperty('display', 'none', 'important');
            globalSidebar.classList.add('hidden');
            if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
        }
    }

    // Show target tab
    const target = document.getElementById(tabId + '-tab');
    if (target) {
        target.classList.remove('hidden');
    }

    // Update Nav Icons
    document.querySelectorAll('.nav-btn').forEach((btn) => {
        const icon = btn.querySelector('i');
        const label = btn.querySelector('span');

        if (icon) {
            icon.classList.remove('text-primary');
            icon.classList.add('text-textMuted');
        }
        btn.classList.remove('bg-white/5', 'text-primary');
        btn.classList.add('text-textMuted');
    });

    // Highlight Active
    const activeBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
    if (activeBtn) {
        const icon = activeBtn.querySelector('i');
        const label = activeBtn.querySelector('span');

        if (icon) {
            icon.classList.remove('text-textMuted');
            icon.classList.add('text-primary');
        }
        activeBtn.classList.remove('text-textMuted');
        activeBtn.classList.add('bg-white/5', 'text-primary');
    }

    // Trigger tab-specific initialization
    if (tabId === 'crypto') {
        if (typeof connectTickerWebSocket === 'function') connectTickerWebSocket();
        if (typeof initCrypto === 'function') {
            await initCrypto();
        }
    }
    if (tabId === 'twstock') {
        if (window.TWStockTab && typeof window.TWStockTab.initTwStock === 'function') {
            window.TWStockTab.initTwStock();
        }
        if (typeof window.loadUserAlerts === 'function') window.loadUserAlerts();
    }
    if (tabId === 'usstock') {
        if (window.USStockTab && typeof window.USStockTab.init === 'function') {
            window.USStockTab.init();
        }
        if (typeof window.loadUserAlerts === 'function') window.loadUserAlerts();
    }
    if (tabId === 'commodity' && typeof CommodityTab !== 'undefined') CommodityTab.init();
    if (tabId === 'forex' && typeof ForexTab !== 'undefined') ForexTab.init();
    if (tabId === 'hkstock' && typeof HKStockTab !== 'undefined') HKStockTab.init();
    if (tabId === 'astock'  && typeof AStockTab  !== 'undefined') AStockTab.init();
    if (tabId === 'jpstock' && typeof JPStockTab !== 'undefined') JPStockTab.init();
    if (tabId === 'instock' && typeof INStockTab !== 'undefined') INStockTab.init();
    if (tabId === 'wallet') {
        if (window.WalletApp) window.WalletApp.init();
    }
    if (tabId === 'friends') {
        if (window.SocialHub) window.SocialHub.init();
    }
    if (tabId === 'safety') {
        if (window.SafetyTab) window.SafetyTab.init();
    }
    if (tabId === 'forum') {
        if (window.ForumApp) window.ForumApp.init();
    }
    if (tabId === 'admin') {
        if (window.AdminPanel) AdminPanel.init();
    }
    if (tabId === 'settings') {
        // Settings 內容是動態注入，需在注入後重新同步已登入身份顯示（username / UID）
        if (window.AuthManager && typeof window.AuthManager._updateUI === 'function') {
            window.AuthManager._updateUI(window.AuthManager.isLoggedIn());
        }
        // ✅ 效能優化：並行執行所有 settings 初始化，而非依序等待
        const settingsInits = [];
        if (typeof loadSettingsWalletStatus === 'function')
            settingsInits.push(Promise.resolve(loadSettingsWalletStatus()));
        if (typeof loadPremiumStatus === 'function')
            settingsInits.push(Promise.resolve(loadPremiumStatus()));
        if (typeof updateLLMStatusUI === 'function')
            settingsInits.push(Promise.resolve(updateLLMStatusUI()));
                if (!AppStore.get('settingsHeavyInitAt')) AppStore.set('settingsHeavyInitAt', 0);
                const now = Date.now();
                if (now - AppStore.get('settingsHeavyInitAt') > 15000) {
                    AppStore.set('settingsHeavyInitAt', now);
            if (typeof window.initToolSettings === 'function') {
                settingsInits.push(Promise.resolve(window.initToolSettings()));
            }
            if (typeof window.initTestMode === 'function') {
                settingsInits.push(Promise.resolve(window.initTestMode()));
            }
        }
        if (typeof updatePriceDisplays === 'function') updatePriceDisplays();
        if (
            window.PremiumManager &&
            typeof window.PremiumManager.updatePriceDisplay === 'function'
        ) {
            window.PremiumManager.updatePriceDisplay();
        }
        if (typeof window.updateAvailableModels === 'function') window.updateAvailableModels();
        // 並行發出所有 API 請求
        Promise.allSettled(settingsInits).catch((e) => console.warn('Settings init error:', e));
    }
    if (tabId === 'chat') {
        if (typeof initChat === 'function') initChat();
        // ✅ 效能優化：checkApiKeyStatus 加 TTL 快取，避免每次切換都打後端 API
        const now = Date.now();
        if (!AppStore.get('lastApiKeyCheck') || now - AppStore.get('lastApiKeyCheck') > 30000) {
            AppStore.set('lastApiKeyCheck', now);
            // 確保 APIKeyManager 已初始化
            if (typeof checkApiKeyStatus === 'function' && window.APIKeyManager) {
                checkApiKeyStatus();
            }
        }
    }

    if (typeof onTabSwitch === 'function') onTabSwitch(tabId);
}
window.executeTabSwitch = executeTabSwitch;

function restoreUiStateAfterResume() {
    const savedTab = getActiveTab();
    const validTabs = new Set([
        'chat',
        'crypto',
        'twstock',
        'usstock',
        'commodity',
        'forex',
        'hkstock',
        'astock',
        'jpstock',
        'instock',
        'wallet',
        'friends',
        'forum',
        'safety',
        'settings',
        'admin',
    ]);

    if (!validTabs.has(savedTab)) {
        return;
    }

    const hasVisibleTab = Array.from(document.querySelectorAll('.tab-content')).some(
        (element) => !element.classList.contains('hidden')
    );

    if (!hasVisibleTab || AppStore.get('activeTab') !== savedTab) {
        switchTab(savedTab, true).catch((error) => {
            console.warn('Resume UI restore failed:', error);
        });
    }
}

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        restoreUiStateAfterResume();
    }
});

window.addEventListener('pageshow', restoreUiStateAfterResume);

// ========================================
// Navigation Rendering & Feature Menu
// ========================================

/**
 * Render navigation buttons based on user preferences
 */
function renderNavButtons() {
    if (window.GlobalNav && typeof window.GlobalNav.renderNavButtons === 'function') {
        window.GlobalNav.renderNavButtons();
        return;
    }
}
window.renderNavButtons = renderNavButtons;

/**
 * Feature Menu Manager
 * Handles the navigation customization modal
 */
const FeatureMenu = {
    _tempPreferences: null,
    _modal: null,

    /**
     * Open the feature menu modal
     */
    open() {
        if (!window.NavPreferences) {
            console.error('NavPreferences not loaded');
            return;
        }

        // Inject feature menu component if not already in DOM
        if (!document.getElementById('feature-menu-modal')) {
            if (window.Components && window.Components.featureMenu) {
                const container = document.createElement('div');
                container.innerHTML = window.Components.featureMenu;
                document.body.appendChild(container.firstElementChild);
            } else {
                console.error('Feature menu component not available');
                return;
            }
        }

        this._modal = document.getElementById('feature-menu-modal');
        const itemsContainer = document.getElementById('feature-menu-items');
        const warningBanner = document.getElementById('feature-menu-warning');

        // Store current preferences for temp state
        const currentEnabled = NavPreferences.loadPreferences().enabledItems;
        this._tempPreferences = new Set(currentEnabled);

        // Clear and render items
        itemsContainer.innerHTML = '';

        window.NAV_ITEMS.forEach((item) => {
            // Skip locked items - they are always enabled and not configurable
            if (item.locked) return;

            const isEnabled = this._tempPreferences.has(item.id);
            const itemEl = document.createElement('div');
            itemEl.className = `feature-menu-item ${!isEnabled ? 'disabled' : ''}`;
            itemEl.dataset.itemId = item.id;

            // Use i18n key if available, otherwise fall back to label
            const labelText =
                item.i18nKey && window.I18n ? window.I18n.t(item.i18nKey) : item.label;

            itemEl.innerHTML = `
                <div class="feature-item-icon">
                    <i data-lucide="${item.icon}"></i>
                </div>
                <span class="feature-item-label">${labelText}</span>
                <div class="feature-toggle ${isEnabled ? 'enabled' : ''}"></div>
            `;

            itemEl.addEventListener('click', () => this.toggleItem(item.id, itemEl));
            itemsContainer.appendChild(itemEl);
        });

        // Initialize Lucide icons
        AppUtils.refreshIcons();

        // Show modal with animation
        this._modal.classList.remove('hidden');
        requestAnimationFrame(() => {
            this._modal
                .querySelector('.feature-menu-content')
                .classList.add('modal-content-active');
        });
    },

    /**
     * Toggle a navigation item on/off
     */
    toggleItem(itemId, element) {
        // Locked items cannot be toggled
        const navItem = window.NAV_ITEMS.find((i) => i.id === itemId);
        if (navItem && navItem.locked) return;

        const isCurrentlyEnabled = this._tempPreferences.has(itemId);

        if (isCurrentlyEnabled) {
            // Check if we can disable (minimum 2 items)
            if (this._tempPreferences.size <= NavPreferences.MIN_ENABLED_ITEMS) {
                // Show warning and shake animation
                const warningBanner = document.getElementById('feature-menu-warning');
                warningBanner.classList.remove('hidden');
                element.classList.add('shake');
                setTimeout(() => element.classList.remove('shake'), 400);

                // Auto-hide warning after 3 seconds
                setTimeout(() => warningBanner.classList.add('hidden'), 3000);
                return;
            }
            this._tempPreferences.delete(itemId);
        } else {
            this._tempPreferences.add(itemId);
        }

        // Update UI
        const toggle = element.querySelector('.feature-toggle');
        if (this._tempPreferences.has(itemId)) {
            toggle.classList.add('enabled');
            element.classList.remove('disabled');
        } else {
            toggle.classList.remove('enabled');
            element.classList.add('disabled');
        }

        // Hide warning if we have enough items
        const warningBanner = document.getElementById('feature-menu-warning');
        if (this._tempPreferences.size >= NavPreferences.MIN_ENABLED_ITEMS) {
            warningBanner.classList.add('hidden');
        }
    },

    /**
     * Save changes and close modal
     */
    save() {
        if (this._tempPreferences.size < NavPreferences.MIN_ENABLED_ITEMS) {
            if (typeof showToast === 'function') {
                showToast(
                    `At least ${NavPreferences.MIN_ENABLED_ITEMS} items must be enabled`,
                    'warning'
                );
            }
            return;
        }

        // Save preferences
        const preferences = {
            version: NavPreferences.PREFERENCES_VERSION,
            enabledItems: Array.from(this._tempPreferences),
        };
        NavPreferences.savePreferences(preferences);

        // Re-render navigation
        renderNavButtons();

        // Close modal
        this.close();

        // Show success feedback
        this.showToast('Navigation preferences saved');
    },

    /**
     * Reset to defaults
     */
    resetToDefaults() {
        if (typeof showConfirm === 'function') {
            showConfirm({
                title: window.i18next?.t('settings.navigation.reset') || 'Reset to Default',
                message: 'Reset all navigation items to default?',
                confirmText: window.i18next?.t('common.confirm') || 'Confirm',
                cancelText: window.i18next?.t('common.cancel') || 'Cancel',
            }).then((confirmed) => {
                if (confirmed) {
                    NavPreferences.resetToDefaults();
                    renderNavButtons();
                    this.close();
                    this.showToast('Navigation reset to defaults');
                }
            });
        } else {
            NavPreferences.resetToDefaults();
            renderNavButtons();
            this.close();
            this.showToast('Navigation reset to defaults');
        }
    },

    /**
     * Close the modal without saving
     */
    close() {
        if (this._modal) {
            const content = this._modal.querySelector('.feature-menu-content');
            content.classList.remove('modal-content-active');

            setTimeout(() => {
                this._modal.classList.add('hidden');
                this._tempPreferences = null;
            }, 200);
        }
    },

    /**
     * Show a toast notification (delegates to global showToast)
     */
    showToast(message) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, 'success');
        }
    },
};

// Expose FeatureMenu globally
window.FeatureMenu = FeatureMenu;

// ========================================
// Application Initialization
// ========================================

// Initialize Greeting Time
const hour = new Date().getHours();
const greeting = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
const greetingTimeEl = document.getElementById('greeting-time');
if (greetingTimeEl) {
    greetingTimeEl.innerText = greeting;
}

document.addEventListener('DOMContentLoaded', async () => {
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('DOM fully loaded, starting controlled initialization...');

    // 頁面淡入效果
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.25s ease-in';
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });

    // 等待核心組件就緒的輔助函式
    const waitForGlobal = (key, timeout = 3000) => {
        return new Promise((resolve) => {
            if (window[key]) return resolve(window[key]);
            const start = Date.now();
            // ✅ 效能優化：polling 間隔從 100ms 降到 10ms，加快啟動速度
            const interval = setInterval(() => {
                if (window[key] || Date.now() - start > timeout) {
                    clearInterval(interval);
                    resolve(window[key]);
                }
            }, 10);
        });
    };

    // 確保核心腳本都已載入
    window.APP_CONFIG?.DEBUG_MODE && console.log('Waiting for core systems...');
    await Promise.all([
        waitForGlobal('Components').then(
            (v) => window.APP_CONFIG?.DEBUG_MODE && console.log('Components ready:', !!v)
        ),
        waitForGlobal('initializeAuth').then(
            (v) => window.APP_CONFIG?.DEBUG_MODE && console.log('Auth ready:', !!v)
        ),
        waitForGlobal('initializeUIStatus').then(
            (v) => window.APP_CONFIG?.DEBUG_MODE && console.log('UI ready:', !!v)
        ),
    ]);

    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Core systems ready status:', {
            Components: !!window.Components,
            Auth: !!window.initializeAuth,
            UI: !!window.initializeUIStatus,
        });

    // 0. 初始化 i18n（必須在 renderNavButtons 之前完成）
    if (window.I18n) {
        try {
            await window.I18n.init();
            window.APP_CONFIG?.DEBUG_MODE && console.log('i18n ready');
        } catch (e) {
            console.error('i18n Init Error:', e);
        }
    }

    // 1. 初始化認證系統（支援測試模式自動登入）
    if (typeof initializeAuth === 'function') {
        try {
            await initializeAuth();
        } catch (e) {
            console.error('Auth Init Error:', e);
        }
    }

    // 1.5 載入已保存的 API Key 狀態（必須在 Auth 完成後）
    if (typeof window.loadSavedApiKeys === 'function') {
        try {
            await window.loadSavedApiKeys();
        } catch (e) {
            console.error('Load API Keys Error:', e);
        }
    }

    // 2. Render navigation buttons based on user preferences
    renderNavButtons();

    // 2.5 初始化語系切換器
    if (window.LanguageSwitcher) {
        new LanguageSwitcher('.lang-switcher-container');
    }

    // 2.6 初始化通知組件（手機版 + 桌面版）
    if (window.NotificationBell && window.NotificationService) {
        const mobileBell = document.getElementById('notification-bell-mobile');
        const desktopBell = document.getElementById('notification-bell-desktop');
        if (mobileBell) {
            window.notificationBell = new NotificationBell(mobileBell);
        }
        if (desktopBell) {
            window.notificationBellDesktop = new NotificationBell(desktopBell);
        }
        window.APP_CONFIG?.DEBUG_MODE && console.log('NotificationBell initialized (global)');
    }

    // 監聽語言切換事件，重新渲染導覽列標籤
    window.addEventListener('languageChanged', () => {
        renderNavButtons();
    });

    // 3. 載入預設分頁（優先順序：sessionStorage returnToTab > URL hash > localStorage）
    const returnToTab = sessionStorage.getItem('returnToTab');
    const hashTab = window.location.hash.replace('#', '');
    const savedTab = getActiveTab();
    const normalizedSavedTab = VALID_TABS.includes(savedTab) ? savedTab : 'chat';

    // 優先使用 returnToTab（從論壇返回），其次 hash，最後 localStorage
    let initialTab;
    if (returnToTab && VALID_TABS.includes(returnToTab)) {
        initialTab = returnToTab;
        sessionStorage.removeItem('returnToTab'); // 使用後清除
    } else if (VALID_TABS.includes(hashTab)) {
        initialTab = hashTab;
    } else {
        initialTab = normalizedSavedTab;
    }

    const loginModal = document.getElementById('login-modal');
    const shouldLockGuestLanding =
        AppStore.get('forceGuestLandingTab') === true ||
        (!!window.AuthManager &&
            !window.AuthManager.isLoggedIn() &&
            loginModal &&
            !loginModal.classList.contains('hidden'));
    if (shouldLockGuestLanding) {
        initialTab = 'chat';
    }

    window.APP_CONFIG?.DEBUG_MODE &&
        console.log(
            'Initial tab switching to:',
            initialTab,
            '(returnTo:',
            returnToTab,
            ', hash:',
            hashTab,
            ', saved:',
            savedTab,
            ')'
        );

    // 清除 hash 並設置正確的初始歷史狀態
    history.replaceState({ tab: initialTab }, '', '#' + initialTab);

    try {
        await switchTab(initialTab, true); // fromPopState=true 避免重複 pushState
    } catch (e) {
        console.error('Initial Tab Error:', e);
    }

    // 3. 更新 UI 狀態
    if (typeof initializeUIStatus === 'function') {
        try {
            initializeUIStatus();
        } catch (e) {
            console.error('UI Init Error:', e);
        }
    }

    // 4. 延遲啟動 Ticker WebSocket（僅在 market/commodity/forex tab 時立即啟動）
    setTimeout(() => {
        const currentTab = getActiveTab();
        const marketTabs = ['market', 'crypto', 'twstock', 'usstock', 'commodity', 'forex'];
        if (marketTabs.includes(currentTab)) {
            if (typeof connectTickerWebSocket === 'function') connectTickerWebSocket();
        }
    }, 1000);

    // 5. 預加載 Market 和 Pulse 數據（僅在 market 相關 tab 時執行）
    setTimeout(async () => {
        const currentTab = getActiveTab();
        const marketTabs = ['market', 'crypto', 'twstock', 'usstock', 'commodity', 'forex'];
        if (!marketTabs.includes(currentTab)) return;

        window.APP_CONFIG?.DEBUG_MODE && console.log('Preloading market data...');
        if (typeof initMarket === 'function') {
            await initMarket();
        }
        if (typeof initPulse === 'function') {
            await initPulse();
        }
        window.APP_CONFIG?.DEBUG_MODE && console.log('Market data preloaded');
    }, 2000);
});

// ========================================
// WebSocket Status Debugging
// ========================================

/**
 * Check and display WebSocket connection status
 */
function checkWebSocketStatus() {
    window.APP_CONFIG?.DEBUG_MODE && console.log('=== WebSocket Status ===');
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Ticker WS Connected:', window.marketWsConnected || false);
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('K-line WS Connected:', window.wsConnected || false);
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Ticker WS Object:', window.marketWebSocket ? 'Exists' : 'Not Found');
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('K-line WS Object:', window.klineWebSocket ? 'Exists' : 'Not Found');
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Auto-refresh Enabled:', window.autoRefreshEnabled || false);
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Current Chart Symbol:', window.currentChartSymbol || 'None');
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Subscribed Ticker Symbols:', Array.from(window.subscribedTickerSymbols || []));
    window.APP_CONFIG?.DEBUG_MODE &&
        console.log('Pending Ticker Symbols:', Array.from(window.pendingTickerSymbols || []));
}
window.checkWebSocketStatus = checkWebSocketStatus;

export {
    switchTab,
    executeTabSwitch,
    navigateToForum,
    renderNavButtons,
    FeatureMenu,
    checkWebSocketStatus,
};
