/**
 * Security Utilities - XSS 防護和安全處理
 *
 * 使用方法:
 * 1. 在 HTML 中引入: <script src="/static/js/security-utils.js"></script>
 * 2. 在 post.html 的 head 中添加 DOMPurify:
 *    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>
 */

window.SecurityUtils = {
    /**
     * HTML 轉義函數 - 防止 XSS 攻擊
     * @param {string} str - 需要轉義的字符串
     * @returns {string} - 轉義後的字符串
     */
    escapeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * 清理 HTML - 使用 DOMPurify 移除危險標籤和屬性
     * @param {string} html - 需要清理的 HTML
     * @returns {string} - 清理後的安全 HTML
     */
    sanitizeHTML(html) {
        if (!html) return '';

        // 檢查 DOMPurify 是否已加載
        if (typeof DOMPurify === 'undefined') {
            console.warn('[Security] DOMPurify not loaded, falling back to text-only rendering');
            return this.escapeHTML(html);
        }

        // 配置 DOMPurify
        const config = {
            // 允許的標籤
            ALLOWED_TAGS: [
                'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote', 'img', 'hr',
                'table', 'thead', 'tbody', 'tr', 'th', 'td'
            ],
            // 允許的屬性
            ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class'],
            // 允許的 URI 協議
            ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
            // 禁止危險屬性
            FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick'],
            // 禁止危險標籤
            FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input'],
            // 移除所有事件處理器
            ALLOW_DATA_ATTR: false,
            // 確保鏈接安全
            SAFE_FOR_TEMPLATES: true
        };

        return DOMPurify.sanitize(html, config);
    },

    /**
     * 渲染 Markdown 並清理 - 安全地渲染用戶輸入的 Markdown
     * @param {string} markdown - Markdown 文本
     * @returns {string} - 安全的 HTML
     */
    renderMarkdownSafely(markdown) {
        if (!markdown) return '';

        // 檢查 markdown-it 是否已加載
        if (typeof markdownit === 'undefined') {
            console.warn('[Security] markdown-it not loaded, rendering as plain text');
            return this.escapeHTML(markdown);
        }

        // 渲染 Markdown
        const md = markdownit({
            html: false,        // 不允許 HTML 標籤
            xhtmlOut: true,     // 使用 XHTML 標準
            breaks: true,       // 將換行符轉換為 <br>
            linkify: true,      // 自動轉換 URL 為鏈接
            typographer: true   // 啟用排版替換
        });

        const rendered = md.render(markdown);

        // 使用 DOMPurify 進一步清理
        return this.sanitizeHTML(rendered);
    },

    /**
     * 創建安全的文本節點
     * @param {string} text - 文本內容
     * @returns {Text} - 文本節點
     */
    createTextNode(text) {
        return document.createTextNode(text || '');
    },

    /**
     * 創建安全的鏈接元素
     * @param {string} href - 鏈接地址
     * @param {string} text - 鏈接文本
     * @param {object} options - 其他選項（如 className）
     * @returns {HTMLAnchorElement} - 鏈接元素
     */
    createSafeLink(href, text, options = {}) {
        const a = document.createElement('a');

        // 驗證 URL
        try {
            const url = new URL(href, window.location.origin);
            // 只允許 http, https, mailto 協議
            if (!['http:', 'https:', 'mailto:'].includes(url.protocol)) {
                console.warn(`[Security] Blocked unsafe URL protocol: ${url.protocol}`);
                a.href = '#';
            } else {
                a.href = href;
            }
        } catch (e) {
            console.warn('[Security] Invalid URL:', href);
            a.href = '#';
        }

        // 設置文本內容（自動轉義）
        a.textContent = text || '';

        // 設置其他屬性
        if (options.className) a.className = options.className;
        if (options.target) a.target = options.target;

        // 如果是外部鏈接，添加安全屬性
        if (options.target === '_blank') {
            a.rel = 'noopener noreferrer';
        }

        return a;
    },

    /**
     * URL 編碼 - 防止 URL 注入
     * @param {string} str - 需要編碼的字符串
     * @returns {string} - 編碼後的字符串
     */
    encodeURL(str) {
        if (!str) return '';
        return encodeURIComponent(str);
    },

    /**
     * 驗證並清理用戶輸入
     * @param {string} input - 用戶輸入
     * @param {object} options - 驗證選項
     * @returns {object} - { valid: boolean, value: string, error: string }
     */
    validateInput(input, options = {}) {
        const result = {
            valid: true,
            value: input,
            error: null
        };

        // 檢查必填
        if (options.required && (!input || input.trim().length === 0)) {
            result.valid = false;
            result.error = 'This field is required';
            return result;
        }

        // 檢查長度
        if (options.minLength && input.length < options.minLength) {
            result.valid = false;
            result.error = `Minimum length is ${options.minLength}`;
            return result;
        }

        if (options.maxLength && input.length > options.maxLength) {
            result.valid = false;
            result.error = `Maximum length is ${options.maxLength}`;
            return result;
        }

        // 檢查正則表達式
        if (options.pattern && !options.pattern.test(input)) {
            result.valid = false;
            result.error = options.patternError || 'Invalid format';
            return result;
        }

        // 移除多餘的空白字符
        if (options.trim !== false) {
            result.value = input.trim();
        }

        return result;
    },

    /**
     * CSP 違規報告處理器
     */
    initCSPReporting() {
        document.addEventListener('securitypolicyviolation', (e) => {
            console.error('[CSP Violation]', {
                blockedURI: e.blockedURI,
                violatedDirective: e.violatedDirective,
                originalPolicy: e.originalPolicy,
                sourceFile: e.sourceFile,
                lineNumber: e.lineNumber
            });

            // 可以選擇發送到服務器
            // fetch('/api/security/csp-report', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify({...})
            // });
        });
    }
};

// 自動初始化 CSP 報告
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        SecurityUtils.initCSPReporting();
    });
} else {
    SecurityUtils.initCSPReporting();
}

// 導出到全局
window.SecurityUtils = SecurityUtils;
