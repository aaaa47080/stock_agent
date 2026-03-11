// ========================================
// legal.js - 法律與條款頁面 Modal 邏輯
// ========================================

const LEGAL_PAGE_MAP = {
    terms: 'terms-of-service.html',
    privacy: 'privacy-policy.html',
    guidelines: 'community-guidelines.html',
};

async function showLegalPage(type) {
    const filename = LEGAL_PAGE_MAP[type];
    if (!filename) return;

    const modal = document.getElementById('legal-modal');
    const contentArea = document.querySelector('#legal-content > div');
    const titleEl = document.getElementById('legal-title');
    const backEl = document.getElementById('legal-back-text');

    // Show modal with loading
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    contentArea.innerHTML =
        '<div class="flex items-center justify-center py-20"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>';

    const lang = window.I18n ? window.I18n.getLanguage() : 'en';
    backEl.textContent = lang === 'zh-TW' ? '返回' : 'Back';

    try {
        const res = await fetch(`/static/legal/${filename}`);
        const html = await res.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const zhDiv = doc.getElementById('content-zh');
        const enDiv = doc.getElementById('content-en');

        if (!zhDiv || !enDiv) {
            contentArea.innerHTML =
                '<p class="text-center text-textMuted py-20">Content not found.</p>';
            return;
        }

        // Store both versions
        contentArea.innerHTML = '';
        const zhClone = zhDiv.cloneNode(true);
        const enClone = enDiv.cloneNode(true);
        zhClone.id = 'legal-content-zh';
        enClone.id = 'legal-content-en';
        contentArea.appendChild(zhClone);
        contentArea.appendChild(enClone);

        // Show correct language
        _updateLegalLanguage(lang);

        // Set title from nav-title in the fetched doc
        const navTitle = doc.getElementById('nav-title');
        if (navTitle) {
            const zhTitle = navTitle.textContent;
            // Find EN title from the toggle logic
            const titles = {
                terms: { 'zh-TW': '服務條款', en: 'Terms of Service' },
                privacy: { 'zh-TW': '隱私權政策', en: 'Privacy Policy' },
                guidelines: { 'zh-TW': '社群守則', en: 'Community Guidelines' },
            };
            titleEl.textContent = (titles[type] && titles[type][lang]) || zhTitle;
            modal.dataset.type = type;
        }
    } catch (e) {
        contentArea.innerHTML = `<p class="text-center text-danger py-20">Failed to load: ${SecurityUtils.escapeHTML(e.message || '')}</p>`;
    }

    if (window.lucide) lucide.createIcons();
}

function _updateLegalLanguage(lang) {
    const zh = document.getElementById('legal-content-zh');
    const en = document.getElementById('legal-content-en');
    if (!zh || !en) return;

    if (lang === 'zh-TW') {
        zh.classList.remove('hidden');
        en.classList.add('hidden');
    } else {
        zh.classList.add('hidden');
        en.classList.remove('hidden');
    }

    const backEl = document.getElementById('legal-back-text');
    if (backEl) backEl.textContent = lang === 'zh-TW' ? '返回' : 'Back';

    const titleEl = document.getElementById('legal-title');
    const modal = document.getElementById('legal-modal');
    const type = modal?.dataset?.type;
    if (titleEl && type) {
        const titles = {
            terms: { 'zh-TW': '服務條款', en: 'Terms of Service' },
            privacy: { 'zh-TW': '隱私權政策', en: 'Privacy Policy' },
            guidelines: { 'zh-TW': '社群守則', en: 'Community Guidelines' },
        };
        titleEl.textContent = (titles[type] && titles[type][lang]) || '';
    }
}

function closeLegalModal() {
    const modal = document.getElementById('legal-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    const contentArea = document.querySelector('#legal-content > div');
    if (contentArea) contentArea.innerHTML = '';
    delete modal.dataset.type;
}

// Re-render legal content on language change
window.addEventListener('languageChanged', e => {
    const modal = document.getElementById('legal-modal');
    if (modal && !modal.classList.contains('hidden')) {
        const lang = e.detail?.language || (window.I18n ? window.I18n.getLanguage() : 'en');
        _updateLegalLanguage(lang);
    }
});

window.showLegalPage = showLegalPage;
window.closeLegalModal = closeLegalModal;
