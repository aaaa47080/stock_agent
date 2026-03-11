// ========================================
// Application Initialization
// ========================================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM fully loaded, starting controlled initialization...');

    // 頁面淡入效果
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.25s ease-in';
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });

    // 等待核心組件就緒的輔助函式
    const waitForGlobal = (key, timeout = 3000) => {
        return new Promise(resolve => {
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
    console.log('Waiting for core systems...');
    await Promise.all([
        waitForGlobal('Components').then(v => console.log('Components ready:', !!v)),
        waitForGlobal('initializeAuth').then(v => console.log('Auth ready:', !!v)),
        waitForGlobal('initializeUIStatus').then(v => console.log('UI ready:', !!v)),
        waitForGlobal('NavPreferences').then(v => console.log('NavPreferences ready:', !!v)),
    ]);

    console.log('Core systems ready status:', {
        Components: !!window.Components,
        Auth: !!window.initializeAuth,
        UI: !!window.initializeUIStatus,
        NavPreferences: !!window.NavPreferences,
    });

    // 0. 初始化 i18n（必須在 renderNavButtons 之前完成）
    if (window.I18n) {
        try {
            await window.I18n.init();
            console.log('i18n ready');
        } catch (e) {
            console.error('i18n Init Error:', e);
        }
    }

    // 1. 初始化認證系統（支援測試模式自動登入）
    if (typeof window.initializeAuth === 'function') {
        try {
            await window.initializeAuth();
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
    if (typeof window.renderNavButtons === 'function') {
        window.renderNavButtons();
    }

    // 2.5 初始化語系切換器
    if (window.LanguageSwitcher) {
        new window.LanguageSwitcher('.lang-switcher-container');
    }

    // 2.6 初始化通知組件（手機版 + 桌面版）
    if (window.NotificationBell && window.NotificationService) {
        const mobileBell = document.getElementById('notification-bell-mobile');
        const desktopBell = document.getElementById('notification-bell-desktop');
        if (mobileBell) {
            window.notificationBell = new window.NotificationBell(mobileBell);
        }
        if (desktopBell) {
            window.notificationBellDesktop = new window.NotificationBell(desktopBell);
        }
        console.log('NotificationBell initialized (global)');
    }

    // 監聽語言切換事件，重新渲染導覽列標籤
    window.addEventListener('languageChanged', () => {
        if (typeof window.renderNavButtons === 'function') {
            window.renderNavButtons();
        }
    });

    // 3. 載入預設分頁（優先順序：sessionStorage returnToTab > URL hash > localStorage）
    const validTabs = [
        'chat',
        'crypto',
        'twstock',
        'usstock',
        'wallet',
        'assets',
        'friends',
        'forum',
        'safety',
        'settings',
        'admin',
    ];
    const returnToTab = sessionStorage.getItem('returnToTab');
    const hashTab = window.location.hash.replace('#', '');
    const savedTab = localStorage.getItem('activeTab') || 'chat';

    // 優先使用 returnToTab（從論壇返回），其次 hash，最後 localStorage
    let initialTab;
    if (returnToTab && validTabs.includes(returnToTab)) {
        initialTab = returnToTab;
        sessionStorage.removeItem('returnToTab'); // 使用後清除
    } else if (validTabs.includes(hashTab)) {
        initialTab = hashTab;
    } else {
        initialTab = savedTab;
    }
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
        if (typeof window.switchTab === 'function') {
            await window.switchTab(initialTab, true); // fromPopState=true 避免重複 pushState
        }
    } catch (e) {
        console.error('Initial Tab Error:', e);
    }

    // 3. 更新 UI 狀態
    if (typeof window.initializeUIStatus === 'function') {
        try {
            window.initializeUIStatus();
        } catch (e) {
            console.error('UI Init Error:', e);
        }
    }

    // 4. 延遲啟動 Ticker WebSocket
    setTimeout(() => {
        const currentTab = localStorage.getItem('activeTab');
        if (currentTab === 'market') {
            if (typeof window.connectTickerWebSocket === 'function')
                window.connectTickerWebSocket();
        } else {
            setTimeout(() => {
                if (typeof window.connectTickerWebSocket === 'function')
                    window.connectTickerWebSocket();
            }, 5000);
        }
    }, 1000);

    // 5. 預加載 Market 和 Pulse 數據（背景執行）
    setTimeout(async () => {
        console.log('Preloading market data...');
        // 預先注入並初始化 market 和 pulse
        if (typeof window.initMarket === 'function') {
            await window.initMarket();
        }
        if (typeof window.initPulse === 'function') {
            await window.initPulse();
        }
        console.log('Market data preloaded');
    }, 2000);

    // 6. Ensure UI Status is updated correctly after all components are loaded
    // Sometimes initializeUIStatus runs too early before API Key Manager has loaded from local storage
    setTimeout(() => {
        if (typeof window.checkApiKeyStatus === 'function') {
            window.checkApiKeyStatus();
        }
    }, 500);
});

// WebSocket Status Debugging
window.checkWebSocketStatus = function () {
    console.log('=== WebSocket Status ===');
    console.log('Ticker WS Connected:', window.marketWsConnected || false);
    console.log('K-line WS Connected:', window.wsConnected || false);
    console.log('Ticker WS Object:', window.marketWebSocket ? 'Exists' : 'Not Found');
    console.log('K-line WS Object:', window.klineWebSocket ? 'Exists' : 'Not Found');
    console.log('Auto-refresh Enabled:', window.autoRefreshEnabled || false);
    console.log('Current Chart Symbol:', window.currentChartSymbol || 'None');
    console.log('Subscribed Ticker Symbols:', Array.from(window.subscribedTickerSymbols || []));
    console.log('Pending Ticker Symbols:', Array.from(window.pendingTickerSymbols || []));
};
