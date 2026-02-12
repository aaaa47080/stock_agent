// ========================================
// LanguageSwitcher.js - 語系切換器組件 (Nav Bar Compact Version)
// ========================================

class LanguageSwitcher {
    constructor(containerSelector = '.lang-switcher-container') {
        // Support both selector string and DOM element
        if (typeof containerSelector === 'string') {
            this.container = document.querySelector(containerSelector);
        } else if (containerSelector instanceof HTMLElement) {
            this.container = containerSelector;
        } else {
            this.container = null;
        }

        this.currentLang = this.getSavedLanguage() || this.detectBrowserLanguage();
        this.isOpen = false;

        if (this.container) {
            this.init();
        }
    }

    /**
     * Static init method for easy initialization from other modules
     * @param {string|HTMLElement} container - Selector string or DOM element
     */
    static init(container) {
        return new LanguageSwitcher(container);
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
        this.syncWithI18n();
    }

    syncWithI18n() {
        // Listen for language change events
        window.addEventListener('languageChanged', (e) => {
            this.currentLang = e.detail.language;
            this.updateDisplay();
        });

        // If I18n is already initialized, sync with its current language
        if (window.I18n && window.I18n.isReady && window.I18n.isReady()) {
            const i18nLang = window.I18n.getLanguage();
            if (i18nLang && i18nLang !== this.currentLang) {
                this.currentLang = i18nLang;
                this.updateDisplay();
            }
        }
    }

    render() {
        if (!this.container) return;

        const flags = { 'zh-TW': '🇹🇼', 'en': '🇺🇸' };
        const names = { 'zh-TW': '繁體中文', 'en': 'English' };

        this.container.innerHTML = `
            <div class="lang-switcher">
                <button class="lang-trigger" type="button" aria-label="Language selector" aria-expanded="false">
                    <span class="lang-flag">${flags[this.currentLang] || '🇺🇸'}</span>
                </button>
                <div class="lang-dropdown hidden" role="menu">
                    <div class="lang-option ${this.currentLang === 'zh-TW' ? 'active' : ''}" role="menuitem" data-lang="zh-TW" tabindex="0">
                        <span class="lang-flag">🇹🇼</span>
                        <span class="lang-option-name">繁體中文</span>
                    </div>
                    <div class="lang-option ${this.currentLang === 'en' ? 'active' : ''}" role="menuitem" data-lang="en" tabindex="0">
                        <span class="lang-flag">🇺🇸</span>
                        <span class="lang-option-name">English</span>
                    </div>
                </div>
            </div>
        `;

        this.attachEvents();
    }

    updateDisplay() {
        if (!this.container) return;
        const flags = { 'zh-TW': '🇹🇼', 'en': '🇺🇸' };
        const flagEl = this.container.querySelector('.lang-trigger .lang-flag');
        if (flagEl) {
            flagEl.textContent = flags[this.currentLang] || '🇺🇸';
        }
        // Update active state
        this.container.querySelectorAll('.lang-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.lang === this.currentLang);
        });
    }

    attachEvents() {
        const switcher = this.container.querySelector('.lang-switcher');
        if (!switcher) return;

        const trigger = switcher.querySelector('.lang-trigger');
        const dropdown = switcher.querySelector('.lang-dropdown');
        const options = switcher.querySelectorAll('.lang-option');

        // Toggle dropdown
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this.isOpen = !this.isOpen;
            dropdown.classList.toggle('hidden', !this.isOpen);
            trigger.setAttribute('aria-expanded', this.isOpen ? 'true' : 'false');
        });

        // Keyboard support for trigger
        trigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                trigger.click();
            }
        });

        // Option click events
        options.forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const lang = e.currentTarget.dataset.lang;
                this.changeLanguage(lang);
            });

            option.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    const lang = e.currentTarget.dataset.lang;
                    this.changeLanguage(lang);
                }
            });
        });

        // Close on outside click
        this._outsideClickHandler = () => {
            if (this.isOpen) {
                this.isOpen = false;
                dropdown.classList.add('hidden');
                trigger.setAttribute('aria-expanded', 'false');
            }
        };
        document.addEventListener('click', this._outsideClickHandler);
    }

    async changeLanguage(lang) {
        if (lang === this.currentLang) {
            this._closeDropdown();
            return;
        }

        this.currentLang = lang;

        try {
            localStorage.setItem('selectedLanguage', lang);
        } catch (e) {
            console.warn('Failed to save language preference:', e);
        }

        // Call I18n module to switch language
        if (window.I18n) {
            await window.I18n.changeLanguage(lang);
        }

        this.updateDisplay();
        this._closeDropdown();

        // Re-render nav buttons to update labels
        if (typeof renderNavButtons === 'function') {
            renderNavButtons();
        }
    }

    _closeDropdown() {
        this.isOpen = false;
        const dropdown = this.container.querySelector('.lang-dropdown');
        const trigger = this.container.querySelector('.lang-trigger');
        if (dropdown) dropdown.classList.add('hidden');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }
}

// Expose globally
window.LanguageSwitcher = LanguageSwitcher;
