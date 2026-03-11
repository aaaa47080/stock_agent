// ========================================
// modals.js - Modal Management System
// ========================================

// ========================================
// Price Alert Modal
// ========================================

// Private variables for price alert state
let _alertSymbol = null;
let _alertMarket = null;

/**
 * Open the price alert modal for a specific symbol
 * @param {string} symbol - Stock/crypto symbol
 * @param {string} market - Market type (twstock, usstock, crypto)
 */
function openAlertModal(symbol, market) {
    _alertSymbol = symbol;
    _alertMarket = market;
    document.getElementById('alert-symbol-label').textContent = symbol + ' (' + market + ')';
    document.getElementById('alert-target').value = '';
    document.getElementById('alert-repeat').checked = false;
    document.getElementById('alert-modal').classList.remove('hidden');
    // Re-init Lucide icons (X button inside modal)
    if (typeof lucide !== 'undefined') lucide.createIcons();
    // Re-apply i18n translations
    if (window.I18n && typeof window.I18n.updatePageContent === 'function')
        window.I18n.updatePageContent();
}

/**
 * Close the price alert modal
 */
function closeAlertModal() {
    document.getElementById('alert-modal').classList.add('hidden');
}

/**
 * Submit a new price alert
 */
async function submitAlert() {
    const condition = document.getElementById('alert-condition').value;
    const target = parseFloat(document.getElementById('alert-target').value);
    const repeat = document.getElementById('alert-repeat').checked;

    const t = (key) => (window.I18n ? window.I18n.t(key) : key);

    if (!target || isNaN(target) || target <= 0) {
        if (typeof window.showToast === 'function')
            window.showToast(t('modals.priceAlert.invalidTarget'), 'error');
        return;
    }

    try {
        const token =
            window.AuthManager &&
            window.AuthManager.currentUser &&
            window.AuthManager.currentUser.accessToken;
        const resp = await fetch('/api/alerts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
            body: JSON.stringify({
                symbol: _alertSymbol,
                market: _alertMarket,
                condition,
                target,
                repeat,
            }),
        });
        if (resp.ok) {
            if (typeof window.showToast === 'function')
                window.showToast('✅ ' + t('modals.priceAlert.confirm'));
            closeAlertModal();
            loadUserAlerts();
        } else {
            const err = await resp.json().catch(() => ({}));
            if (typeof window.showToast === 'function')
                window.showToast(err.detail || t('modals.priceAlert.setFailed'), 'error');
        }
    } catch (e) {
        if (typeof window.showToast === 'function')
            window.showToast(t('modals.priceAlert.networkError'), 'error');
    }
}

/**
 * Load user's price alerts from the server
 */
async function loadUserAlerts() {
    try {
        const token =
            window.AuthManager &&
            window.AuthManager.currentUser &&
            window.AuthManager.currentUser.accessToken;
        if (!token) return;
        const resp = await fetch('/api/alerts', { headers: { Authorization: 'Bearer ' + token } });
        if (!resp.ok) return;
        const data = await resp.json();
        renderAlertList(data.alerts || []);
    } catch (e) {
        // silent fail — user may not be logged in
    }
}

/**
 * Delete a user's price alert
 * @param {string} alertId - The alert ID to delete
 */
async function deleteUserAlert(alertId) {
    try {
        const token =
            window.AuthManager &&
            window.AuthManager.currentUser &&
            window.AuthManager.currentUser.accessToken;
        const resp = await fetch('/api/alerts/' + alertId, {
            method: 'DELETE',
            headers: { Authorization: 'Bearer ' + token },
        });
        if (resp.ok) {
            loadUserAlerts();
        } else {
            const t = (key) => (window.I18n ? window.I18n.t(key) : key);
            if (typeof window.showToast === 'function')
                window.showToast(t('modals.priceAlert.deleteFailed'), 'error');
        }
    } catch (e) {
        const t = (key) => (window.I18n ? window.I18n.t(key) : key);
        if (typeof window.showToast === 'function')
            window.showToast(t('modals.priceAlert.deleteFailed'), 'error');
    }
}

/**
 * Render the list of user's price alerts
 * @param {Array} alerts - Array of alert objects
 */
function renderAlertList(alerts) {
    const t = (key) => (window.I18n ? window.I18n.t(key) : key);
    // condition labels come from i18n
    const condMap = {
        above: t('modals.priceAlert.above'),
        below: t('modals.priceAlert.below'),
        change_pct_up: t('modals.priceAlert.changePctUp'),
        change_pct_down: t('modals.priceAlert.changePctDown'),
    };
    const noAlertsHtml =
        '<p class="text-textMuted text-xs py-1">' + t('modals.priceAlert.noAlerts') + '</p>';
    const deleteLabel = t('modals.priceAlert.deleteAlert');

    const containerIds = ['alert-list-twstock', 'alert-list-usstock'];
    containerIds.forEach(function (cid) {
        const container = document.getElementById(cid);
        if (!container) return;
        if (alerts.length === 0) {
            container.innerHTML = noAlertsHtml;
            return;
        }
        container.innerHTML = alerts
            .map(function (a) {
                const label = condMap[a.condition] || a.condition;
                return (
                    '<div class="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">' +
                    '<span class="text-secondary text-xs font-mono">' +
                    a.symbol +
                    ' <span class="text-primary">' +
                    label +
                    '</span> ' +
                    a.target +
                    (a.repeat ? ' <span class="text-textMuted">🔁</span>' : '') +
                    '</span>' +
                    '<button onclick="deleteUserAlert(\'' +
                    a.id +
                    '\')" ' +
                    'class="text-danger hover:brightness-125 text-xs ml-2 transition">' +
                    deleteLabel +
                    '</button>' +
                    '</div>'
                );
            })
            .join('');
    });
}

// Expose alert functions globally so onclick handlers and tab init can call them
window.openAlertModal = openAlertModal;
window.closeAlertModal = closeAlertModal;
window.submitAlert = submitAlert;
window.loadUserAlerts = loadUserAlerts;
window.deleteUserAlert = deleteUserAlert;
window.renderAlertList = renderAlertList;

// ── End Price Alert UI ─────────────────────────────────────────────────

// ========================================
// Legal Modal
// ========================================

const LEGAL_PAGE_MAP = {
    terms: 'terms-of-service.html',
    privacy: 'privacy-policy.html',
    guidelines: 'community-guidelines.html',
};

/**
 * Show a legal page in the modal
 * @param {string} type - Type of legal page (terms, privacy, guidelines)
 */
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

/**
 * Update the legal modal content language
 * @param {string} lang - Language code ('zh-TW' or 'en')
 */
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

/**
 * Close the legal modal
 */
function closeLegalModal() {
    const modal = document.getElementById('legal-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    const contentArea = document.querySelector('#legal-content > div');
    if (contentArea) contentArea.innerHTML = '';
    delete modal.dataset.type;
}

// Re-render legal content on language change
window.addEventListener('languageChanged', (e) => {
    const modal = document.getElementById('legal-modal');
    if (modal && !modal.classList.contains('hidden')) {
        const lang = e.detail?.language || (window.I18n ? window.I18n.getLanguage() : 'en');
        _updateLegalLanguage(lang);
    }
});

// Expose legal functions globally
window.showLegalPage = showLegalPage;
window.closeLegalModal = closeLegalModal;
