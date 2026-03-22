// ========================================
// i18n.js - 國際化初始化模組
// ========================================

(function () {
    'use strict';

    let i18n = null;

    // 從 LocalStorage 讀取儲存的語言偏好
    function getSavedLanguage() {
        try {
            return localStorage.getItem('selectedLanguage');
        } catch (e) {
            console.warn('LocalStorage not available:', e);
            return null;
        }
    }

    // 偵測瀏覽器語言
    function detectBrowserLanguage() {
        const lang = navigator.language || navigator.userLanguage || 'en';
        const baseLang = lang.split('-')[0];
        if (baseLang === 'zh') {
            return 'zh-TW';
        }
        return 'en';
    }

    // 更新頁面所有帶 data-i18n 的元素
    function updatePageContent() {
        const elements = document.querySelectorAll('[data-i18n]');
        elements.forEach((el) => {
            const key = el.getAttribute('data-i18n');
            if (!i18n || !key) return;

            const argsAttr = el.getAttribute('data-i18n-args');
            let translation;

            try {
                if (argsAttr) {
                    const args = JSON.parse(argsAttr);
                    translation = i18n.t(key, args);
                } else {
                    translation = i18n.t(key);
                }
            } catch (e) {
                console.warn(`Translation error for key "${key}":`, e);
                return;
            }

            // 檢查是否需要更新特定屬性
            const targetAttr = el.getAttribute('data-i18n-attr');

            if (targetAttr === 'placeholder') {
                el.placeholder = translation;
            } else if (targetAttr === 'title') {
                el.title = translation;
            } else if (targetAttr) {
                el.setAttribute(targetAttr, translation);
            } else {
                el.textContent = translation;
            }
        });

        // 更新 html lang 屬性
        if (i18n) {
            document.documentElement.lang = i18n.language;
        }
    }

    // 初始化 i18next
    async function initI18n() {
        // 載入翻譯檔
        const [zhTW, en] = await Promise.all([
            fetch('/static/js/i18n/zh-TW.json?v=6')
                .then((r) => r.json())
                .catch(() => ({})),
            fetch('/static/js/i18n/en.json?v=6')
                .then((r) => r.json())
                .catch(() => ({})),
        ]);

        // 確定使用的語言
        const savedLang = getSavedLanguage();
        const browserLang = detectBrowserLanguage();
        const language = savedLang || browserLang;

        // 初始化 i18next
        i18n = window.i18next;

        if (!i18n) {
            console.warn(
                'i18next library not found on window. ' +
                'Ensure the i18next CDN script is loaded before this module.'
            );
            // Fallback: expose a no-op t() function so callers don't crash
            window.I18n = {
                init: initI18n,
                t: function (key, options) { return key; },
                isReady: function () { return false; },
                changeLanguage: async function () {},
                getLanguage: function () { return 'en'; },
                updatePageContent: updatePageContent,
            };
            return;
        }

        try {
            await i18n.init({
                lng: language,
                fallbackLng: 'en',
                resources: {
                    'zh-TW': { translation: zhTW },
                    en: { translation: en },
                },
                interpolation: {
                    escapeValue: false, // Frontend hardcoded translation resources, no user input
                },
            });

            // 等待 DOM 準備好後更新內容
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', updatePageContent);
            } else {
                updatePageContent();
            }

            // 監聽語言切換事件
            i18n.on('languageChanged', (lng) => {
                updatePageContent();
                // 觸發自定義事件，讓其他組件知道語言已切換
                window.dispatchEvent(
                    new CustomEvent('languageChanged', { detail: { language: lng } })
                );
            });

            // 觸發初始化完成事件，讓其他組件知道 i18n 已準備好
            window.dispatchEvent(
                new CustomEvent('languageChanged', { detail: { language: language } })
            );

            window.APP_CONFIG?.DEBUG_MODE &&
                console.log('i18n initialized with language:', language);
        } catch (error) {
            console.error('Failed to initialize i18n:', error);
        }
    }

    // 暴露給外部的 API
    window.I18n = {
        init: initI18n,
        t: function (key, options) {
            return i18n ? i18n.t(key, options) : key;
        },
        // 檢查 i18n 是否已完全初始化
        isReady: function () {
            return i18n !== null;
        },
        changeLanguage: async function (lang) {
            if (i18n) {
                await i18n.changeLanguage(lang);
                try {
                    localStorage.setItem('selectedLanguage', lang);
                } catch (e) {
                    console.warn('Failed to save language preference:', e);
                }
                // 手動觸發事件，確保所有組件都能收到通知
                window.dispatchEvent(
                    new CustomEvent('languageChanged', { detail: { language: lang } })
                );
            }
        },
        getLanguage: function () {
            return i18n ? i18n.language : 'en';
        },
        // 供組件動態注入後呼叫，更新新加入的 data-i18n 元素
        updatePageContent: updatePageContent,
    };
})();

// Side-effect module — I18n is on window for backward compatibility.
export {};
