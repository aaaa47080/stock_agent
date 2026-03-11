// ========================================
// chat.js - Legacy compatibility shim
// 職責：為舊頁面或快取中的舊引用，轉接到模組化 chat scripts
// ========================================

(function () {
    if (window.__legacyChatShimLoaded) return;
    window.__legacyChatShimLoaded = true;

    const requiredGlobals = [
        'sendMessage',
        'loadSessions',
        'initChat',
        'renderStoredBotMessage',
        'submitHITLAnswer',
    ];

    const hasModularChatLoaded = requiredGlobals.every((key) => typeof window[key] === 'function');
    if (hasModularChatLoaded) {
        console.warn('[chat.js] Legacy shim loaded after modular chat scripts; skipping.');
        return;
    }

    const scriptOrder = [
        '/static/js/chat-state.js?v=1',
        '/static/js/chat-sessions.js?v=1',
        '/static/js/chat-stream-ui.js?v=1',
        '/static/js/chat-hitl.js?v=1',
        '/static/js/chat-analysis.js?v=1',
        '/static/js/chat-history.js?v=1',
        '/static/js/chat-init.js?v=1',
    ];

    function loadScriptSequentially(index) {
        if (index >= scriptOrder.length) {
            console.warn('[chat.js] Legacy shim delegated to modular chat scripts.');
            return;
        }

        const src = scriptOrder[index];
        const alreadyLoaded = Array.from(document.scripts).some((script) => script.src.includes(src.split('?')[0]));
        if (alreadyLoaded) {
            loadScriptSequentially(index + 1);
            return;
        }

        const script = document.createElement('script');
        script.src = src;
        script.defer = false;
        script.async = false;
        script.onload = function () {
            loadScriptSequentially(index + 1);
        };
        script.onerror = function () {
            console.error(`[chat.js] Failed to load dependency: ${src}`);
        };
        document.head.appendChild(script);
    }

    loadScriptSequentially(0);
})();
