// ========================================
// LanguageSwitcher.js - 語系切換器組件
// ========================================

class LanguageSwitcher {
    constructor(containerSelector = '.lang-switcher-container') {
        this.container = document.querySelector(containerSelector);
        this.currentLang = this.getSavedLanguage() || this.detectBrowserLanguage();
        this.isOpen = false;

        if (this.container) {
            this.init();
        }
    }

    getSavedLanguage() {
        try {
            return localStorage.getItem('selectedLanguage');
        } catch (e) {
            return null;
        }
    }

    detectBrowserLanguage() {
        const lang = navigator.language || navigator.userLanguage || 'en';
        return (lang === 'zh-TW' || lang === 'zh-HK') ? 'zh-TW' : 'en';
    }

    init() {
        this.render();
        this.attachEvents();
        this.syncWithI18n();
    }

    syncWithI18n() {
        // 監聽語言變更事件，同步切換器狀態
        window.addEventListener('languageChanged', (e) => {
            this.currentLang = e.detail.language;
            this.render();
        });
    }

    render() {
        if (!this.container) return;

        const flags = { 'zh-TW': '🇹🇼', 'en': '🇺🇸' };
        const names = { 'zh-TW': '繁體中文', 'en': 'English' };

        this.container.innerHTML = `
            <div class="lang-switcher">
                <div class="lang-trigger" role="button" tabindex="0" aria-label="Language selector" aria-expanded="${this.isOpen ? 'true' : 'false'}">
                    <span class="lang-flag">${flags[this.currentLang] || '🇺🇸'}</span>
                    <span class="lang-name">${names[this.currentLang] || 'English'}</span>
                    <svg class="lang-arrow ${this.isOpen ? 'rotate-180' : ''}" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </div>
                <div class="lang-dropdown ${this.isOpen ? '' : 'hidden'}" role="menu">
                    <div class="lang-option ${this.currentLang === 'zh-TW' ? 'active' : ''}" role="menuitem" data-lang="zh-TW" tabindex="0">
                        <span class="lang-flag">🇹🇼</span>
                        <span class="lang-name">繁體中文</span>
                    </div>
                    <div class="lang-option ${this.currentLang === 'en' ? 'active' : ''}" role="menuitem" data-lang="en" tabindex="0">
                        <span class="lang-flag">🇺🇸</span>
                        <span class="lang-name">English</span>
                    </div>
                </div>
            </div>
        `;

        // 重新綁定事件
        this.attachEvents();
    }

    attachEvents() {
        const switcher = this.container.querySelector('.lang-switcher');
        if (!switcher) return;

        const trigger = switcher.querySelector('.lang-trigger');
        const dropdown = switcher.querySelector('.lang-dropdown');
        const options = switcher.querySelectorAll('.lang-option');

        // 移除舊的監聽器（避免重複）
        const newTrigger = trigger.cloneNode(true);
        trigger.parentNode.replaceChild(newTrigger, trigger);

        const updatedTrigger = switcher.querySelector('.lang-trigger');

        // 切換下拉顯示
        updatedTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        // 鍵盤支援
        updatedTrigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.toggle();
            }
        });

        // 選項點擊事件
        options.forEach(option => {
            const newOption = option.cloneNode(true);
            option.parentNode.replaceChild(newOption, option);

            newOption.addEventListener('click', (e) => {
                const lang = e.currentTarget.dataset.lang;
                this.changeLanguage(lang);
            });

            newOption.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const lang = e.currentTarget.dataset.lang;
                    this.changeLanguage(lang);
                }
            });
        });

        // 點擊外部關閉
        document.removeEventListener('click', this.handleOutsideClick);
        this.handleOutsideClick = () => this.close();
        document.addEventListener('click', this.handleOutsideClick);
    }

    toggle() {
        this.isOpen = !this.isOpen;
        this.render();
    }

    open() {
        this.isOpen = true;
        this.render();
    }

    close() {
        this.isOpen = false;
        this.render();
    }

    async changeLanguage(lang) {
        if (lang === this.currentLang) {
            this.close();
            return;
        }

        this.currentLang = lang;

        try {
            localStorage.setItem('selectedLanguage', lang);
        } catch (e) {
            console.warn('Failed to save language preference:', e);
        }

        // 呼叫 I18n 模組切換語言
        if (window.I18n) {
            await window.I18n.changeLanguage(lang);
        }

        this.close();
    }
}

// 暴露到全域，供其他模組使用
window.LanguageSwitcher = LanguageSwitcher;
