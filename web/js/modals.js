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
    AppUtils.refreshIcons();
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
        await AppAPI.post('/api/alerts', {
            symbol: _alertSymbol,
            market: _alertMarket,
            condition,
            target,
            repeat,
        });
        if (typeof window.showToast === 'function')
            window.showToast('✅ ' + t('modals.priceAlert.confirm'));
        closeAlertModal();
        loadUserAlerts();
    } catch (e) {
        if (typeof window.showToast === 'function')
            window.showToast(e.message || t('modals.priceAlert.setFailed'), 'error');
    }
}

/**
 * Load user's price alerts from the server
 */
async function loadUserAlerts() {
    try {
        if (!AppAPI.getToken()) return;
        const data = await AppAPI.get('/api/alerts');
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
    const t = (key) => (window.I18n ? window.I18n.t(key) : key);
    try {
        await AppAPI.delete('/api/alerts/' + alertId);
        loadUserAlerts();
    } catch (e) {
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
                    (a.repeat
                        ? ' <span class="text-textMuted">' +
                          t('modals.priceAlert.repeatBadge') +
                          '</span>'
                        : '') +
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
export { openAlertModal, closeAlertModal, submitAlert, loadUserAlerts, deleteUserAlert, renderAlertList };

// ── End Price Alert UI ─────────────────────────────────────────────────
