// ========================================
// config.js - 前端配置文件
// ========================================

// 全局配置变量
window.APP_CONFIG = {
    // 调试模式开关 - 在生产环境中设为false以减少日志
    DEBUG_MODE: false,
    
    // 钱包连接超时时间（毫秒）
    WALLET_CONNECT_TIMEOUT: 10000,
    
    // API请求超时时间（毫秒）
    API_REQUEST_TIMEOUT: 15000,
    
    // 重试次数
    MAX_RETRY_ATTEMPTS: 3
};

// 设置全局调试模式标志
window.DEBUG_MODE = window.APP_CONFIG.DEBUG_MODE;