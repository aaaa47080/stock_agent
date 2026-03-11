// ========================================
// alerts.js - 價格警告與提醒 UI 邏輯
// ========================================

let _alertSymbol = '';
let _alertMarket = '';

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

function closeAlertModal() {
    document.getElementById('alert-modal').classList.add('hidden');
}

async function submitAlert() {
    const condition = document.getElementById('alert-condition').value;
    const target = parseFloat(document.getElementById('alert-target').value);
    const repeat = document.getElementById('alert-repeat').checked;

    const t = key => (window.I18n ? window.I18n.t(key) : key);

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
            const t = key => (window.I18n ? window.I18n.t(key) : key);
            if (typeof window.showToast === 'function')
                window.showToast(t('modals.priceAlert.deleteFailed'), 'error');
        }
    } catch (e) {
        const t = key => (window.I18n ? window.I18n.t(key) : key);
        if (typeof window.showToast === 'function')
            window.showToast(t('modals.priceAlert.deleteFailed'), 'error');
    }
}

function renderAlertList(alerts) {
    const t = key => (window.I18n ? window.I18n.t(key) : key);
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
