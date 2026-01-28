// ========================================
// logger.js - 全局日誌控制系統
// ========================================

(function () {
    // 保存原始的 console 方法
    const originalConsole = {
        log: console.log,
        debug: console.debug,
        info: console.info,
        warn: console.warn,
        error: console.error
    };

    // 暴露原始 console 供緊急調試使用
    window._console = originalConsole;

    // 定義空函數
    const noop = function () { };

    function initLogger() {
        const debugMode = window.APP_CONFIG && window.APP_CONFIG.DEBUG_MODE;

        if (!debugMode) {
            // 在生產模式下，屏蔽普通日誌
            console.log = noop;
            console.debug = noop;
            console.info = noop;

            // 保留警告和錯誤，但可以選擇性地過濾
            // console.warn = noop; 

            // 可以在這裡添加日誌收集邏輯，例如發送到後端
        } else {
            // 恢復原始方法 (如果需要在運行時切換)
            console.log = originalConsole.log;
            console.debug = originalConsole.debug;
            console.info = originalConsole.info;
        }

        // 始終保留一條系統消息
        if (!debugMode) {
            originalConsole.log(
                "%c CryptoMind %c AI Agent Online ",
                "background:#35495e ; padding: 1px; border-radius: 3px 0 0 3px;  color: #fff",
                "background:#d4b693 ; padding: 1px; border-radius: 0 3px 3px 0;  color: #fff"
            );
        }
    }

    // 立即初始化
    initLogger();

    // 監聽配置變化 (如果 APP_CONFIG 是動態的)
    // 這裡假設 APP_CONFIG 已經在 config.js 中定義
})();
