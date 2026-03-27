// ========================================
// toolSettings.js - AI 工具設定 UI 控制器
// ========================================

const _CATEGORY_LABELS = {
    crypto_basic: '加密貨幣基礎',
    technical: '技術分析',
    derivatives: '衍生品市場',
    news: '新聞資訊',
    onchain: '鏈上數據',
    tw_stock: '台灣股市',
    us_stock: '美國股市',
    general: '通用工具',
};

const _CATEGORY_ICONS = {
    crypto_basic: 'bitcoin',
    technical: 'bar-chart-2',
    derivatives: 'activity',
    news: 'newspaper',
    onchain: 'database',
    tw_stock: 'trending-up',
    us_stock: 'dollar-sign',
    general: 'wrench',
};

let _currentUserTier = 'free';
let _toolSettingsLoaded = false;
let _toolSettingsRetryScheduled = false;
let _toolSettingsLoadPromise = null;
let _toolSettingsWatchdogId = null;

const TOOL_SETTINGS_DIAGNOSTICS_KEY = 'tool_settings_diagnostics_v1';

function readToolSettingsDiagnostics() {
    try {
        const raw = sessionStorage.getItem(TOOL_SETTINGS_DIAGNOSTICS_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

function writeToolSettingsDiagnostics(entries) {
    try {
        sessionStorage.setItem(
            TOOL_SETTINGS_DIAGNOSTICS_KEY,
            JSON.stringify(entries.slice(-80))
        );
    } catch (_) {}
}

function pushToolSettingsDiagnostic(event, data) {
    const entries = readToolSettingsDiagnostics();
    entries.push({
        at: new Date().toISOString(),
        event,
        data: data || {},
    });
    writeToolSettingsDiagnostics(entries);
}

window.getToolSettingsDiagnostics = function () {
    return readToolSettingsDiagnostics();
};

function _showLoginRequired(container) {
    _toolSettingsLoaded = false;
    _currentUserTier = 'free';
    container.innerHTML = `<p class="text-sm text-textMuted text-center py-4">登入後可查看工具設定</p>`;
    const notice = document.getElementById('tool-settings-free-notice');
    if (notice) notice.classList.remove('hidden');
}

/**
 * 初始化工具設定頁面 — 從後端拉取工具清單並渲染
 */
async function initToolSettings() {
    const container = document.getElementById('tool-settings-list');
    if (!container) return;

    if (_toolSettingsLoadPromise) {
        pushToolSettingsDiagnostic('init:reuseInflight');
        return _toolSettingsLoadPromise;
    }

    _toolSettingsLoadPromise = (async () => {
        const currentUser = window.AuthManager?.currentUser || null;
        pushToolSettingsDiagnostic('init:start', {
            user_id: currentUser?.user_id || currentUser?.uid || null,
            pi_uid: currentUser?.pi_uid || null,
            active_tab: typeof AppStore !== 'undefined' ? AppStore.get('activeTab') : null,
        });
        container.innerHTML = `
            <div class="flex items-center justify-center py-8 text-textMuted">
                <i data-lucide="loader" class="w-5 h-5 animate-spin mr-2"></i>
                <span class="text-sm">載入中...</span>
            </div>`;
        AppUtils.refreshIcons();
        clearTimeout(_toolSettingsWatchdogId);
        _toolSettingsWatchdogId = setTimeout(() => {
            if (_toolSettingsLoadPromise) {
                pushToolSettingsDiagnostic('init:watchdogTimeout');
                container.innerHTML = `
                    <div class="text-center py-4 space-y-2">
                        <p class="text-sm text-yellow-400">工具設定載入逾時，請重試</p>
                        <button onclick="initToolSettings()" class="px-4 py-2 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-sm font-bold transition">
                            重新載入
                        </button>
                    </div>`;
            }
        }, 12000);

        try {
            const data = await AppAPI.get('/api/user/tools', { timeout: 10000 });
            _currentUserTier = data.user_tier || 'free';
            _toolSettingsLoaded = true;
            _toolSettingsRetryScheduled = false;
            pushToolSettingsDiagnostic('init:success', {
                user_tier: _currentUserTier,
                tool_count: Array.isArray(data.tools) ? data.tools.length : 0,
            });
            renderToolList(container, data.tools || []);
        } catch (err) {
            pushToolSettingsDiagnostic('init:error', {
                status: err?.status || 0,
                message: err?.message || 'unknown',
            });
            console.error('[toolSettings] fetch error:', err);
            if (err?.status === 401 || err?.status === 403) {
                const hasKnownUser =
                    !!window.AuthManager?.currentUser?.user_id ||
                    !!window.AuthManager?.currentUser?.uid ||
                    !!window.AuthManager?.currentUser?.pi_uid;
                const loginInProgress =
                    window._piLoginInProgress ||
                    (typeof AppStore !== 'undefined' && AppStore.get('piLoginInProgress'));

                if ((hasKnownUser || loginInProgress) && !_toolSettingsRetryScheduled) {
                    _toolSettingsRetryScheduled = true;
                    setTimeout(() => {
                        _toolSettingsRetryScheduled = false;
                        initToolSettings().catch((retryErr) =>
                            console.error('[toolSettings] delayed retry failed:', retryErr)
                        );
                    }, 600);
                    return;
                }

                _showLoginRequired(container);
                return;
            }
            container.innerHTML = `
                <div class="text-center py-4 space-y-2">
                    <p class="text-sm text-red-400">載入失敗，請稍後再試。</p>
                    <button onclick="initToolSettings()" class="px-4 py-2 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-sm font-bold transition">
                        重新載入
                    </button>
                </div>`;
        } finally {
            clearTimeout(_toolSettingsWatchdogId);
            _toolSettingsLoadPromise = null;
        }
    })();

    return _toolSettingsLoadPromise;
}

/**
 * 依 category 分組並渲染可折疊工具卡片
 */
function renderToolList(container, tools) {
    if (tools.length === 0) {
        container.innerHTML = `<p class="text-sm text-textMuted text-center py-4">尚無可用工具</p>`;
        return;
    }

    // Group by category (preserve insertion order from backend)
    const groups = {};
    tools.forEach((t) => {
        if (!groups[t.category]) groups[t.category] = [];
        groups[t.category].push(t);
    });

    const html = Object.entries(groups)
        .map(([cat, items], idx) => {
            const label = _CATEGORY_LABELS[cat] || cat;
            const icon = _CATEGORY_ICONS[cat] || 'tool';
            const rows = items.map((t) => _renderToolRow(t)).join('');
            const total = items.length;
            const enabled = items.filter((t) => !t.locked && t.is_enabled).length;
            const catId = `tool-cat-${cat}`;
            // First category expanded by default, rest collapsed
            const expanded = idx === 0;

            return `
            <div class="mb-1">
                <button onclick="toggleToolCategory('${catId}')"
                    class="w-full flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/5 transition group"
                    aria-expanded="${expanded}">
                    <div class="flex items-center gap-2">
                        <i data-lucide="${icon}" class="w-3.5 h-3.5 text-primary opacity-60"></i>
                        <span class="text-xs font-bold text-textMuted uppercase tracking-wider">${label}</span>
                        <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-white/5 text-textMuted font-mono">${enabled}/${total}</span>
                    </div>
                    <i data-lucide="chevron-down" class="w-3.5 h-3.5 text-textMuted transition-transform duration-200 ${expanded ? 'rotate-180' : ''}"></i>
                </button>
                <div id="${catId}" class="space-y-1.5 overflow-hidden transition-all duration-200 ${expanded ? 'mt-1.5' : 'max-h-0'}">
                    ${rows}
                </div>
            </div>`;
        })
        .join('');

    container.innerHTML = html;
    AppUtils.refreshIcons();

    // Show upgrade notice for free users
    const notice = document.getElementById('tool-settings-free-notice');
    if (notice) {
        if (_currentUserTier === 'free') {
            notice.classList.remove('hidden');
        } else {
            notice.classList.add('hidden');
        }
    }
}

function _renderToolRow(tool) {
    const isPremiumLocked = tool.locked;
    const quotaBadge =
        tool.quota_type === 'shared_limited'
            ? `<span class="text-[10px] text-yellow-400/70 font-mono ml-1">有額度</span>`
            : '';
    const tierBadge =
        tool.tier_required === 'premium'
            ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-yellow-400/10 text-yellow-400 font-bold ml-1">PREMIUM</span>`
            : '';

    if (isPremiumLocked) {
        // Free user sees locked premium tool — greyed out, no toggle
        return `
            <div class="flex items-center gap-3 p-3 rounded-xl bg-background/50 border border-white/5 opacity-50 select-none">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center flex-wrap">
                        <span class="text-sm text-secondary truncate">${tool.display_name}</span>
                        ${tierBadge}${quotaBadge}
                    </div>
                    <p class="text-xs text-textMuted mt-0.5 truncate">${tool.description}</p>
                </div>
                <i data-lucide="lock" class="w-4 h-4 text-yellow-400/60 flex-shrink-0"></i>
            </div>`;
    }

    const checked = tool.is_enabled ? 'checked' : '';
    const canToggle = _currentUserTier === 'premium';
    const disabledAttr = canToggle ? '' : 'disabled';
    const wrapperClass = canToggle ? 'cursor-pointer' : 'cursor-not-allowed opacity-60';
    const toggleTitle = canToggle ? '' : 'title="升級 Premium 可自訂工具"';

    return `
        <div class="flex items-center gap-3 p-3 rounded-xl bg-background/50 border border-white/5 hover:border-white/10 transition">
            <div class="flex-1 min-w-0">
                <div class="flex items-center flex-wrap">
                    <span class="text-sm text-secondary truncate">${tool.display_name}</span>
                    ${tierBadge}${quotaBadge}
                </div>
                <p class="text-xs text-textMuted mt-0.5 truncate">${tool.description}</p>
            </div>
            <label class="relative inline-flex items-center flex-shrink-0 ${wrapperClass}" ${toggleTitle}>
                <input type="checkbox" class="sr-only peer" ${checked} ${disabledAttr}
                    onchange="toggleToolPreference('${tool.tool_id}', this.checked, this)">
                <div class="w-10 h-6 bg-white/10 peer-focus:outline-none rounded-full peer
                    peer-checked:after:translate-x-full peer-checked:after:border-white
                    after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                    after:bg-white after:border-gray-300 after:border after:rounded-full
                    after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
            </label>
        </div>`;
}

/**
 * 展開 / 折疊工具分類
 */
function toggleToolCategory(catId) {
    const panel = document.getElementById(catId);
    const btn = panel?.previousElementSibling;
    if (!panel || !btn) return;

    const isOpen = btn.getAttribute('aria-expanded') === 'true';
    if (isOpen) {
        panel.style.maxHeight = panel.scrollHeight + 'px';
        requestAnimationFrame(() => {
            panel.style.maxHeight = '0';
            panel.classList.add('mt-0');
            panel.classList.remove('mt-1.5');
        });
        btn.setAttribute('aria-expanded', 'false');
        const icon = btn.querySelector('[data-lucide="chevron-down"]');
        if (icon) icon.classList.remove('rotate-180');
    } else {
        panel.style.maxHeight = panel.scrollHeight + 'px';
        panel.classList.add('mt-1.5');
        panel.classList.remove('mt-0');
        btn.setAttribute('aria-expanded', 'true');
        const icon = btn.querySelector('[data-lucide="chevron-down"]');
        if (icon) icon.classList.add('rotate-180');
        // Remove max-height after transition
        panel.addEventListener(
            'transitionend',
            () => {
                panel.style.maxHeight = 'none';
            },
            { once: true }
        );
    }
}

/**
 * 呼叫 API 更新工具偏好（付費會員）
 */
async function toggleToolPreference(toolId, isEnabled, checkboxEl) {
    if (_currentUserTier !== 'premium') return;

    try {
        const res = await AppAPI.put(`/api/user/tools/${toolId}/preference`, { is_enabled: isEnabled });
        // Success — checkbox already reflects new state
    } catch (err) {
        console.error('[toolSettings] toggle error:', err);
        // Revert checkbox on failure
        if (checkboxEl) checkboxEl.checked = !isEnabled;
        if (typeof showToast === 'function') showToast('更新失敗，請稍後再試', 'error');
    }
}

window.initToolSettings = initToolSettings;
window.toggleToolPreference = toggleToolPreference;
window.toggleToolCategory = toggleToolCategory;
window.isToolSettingsLoaded = () => _toolSettingsLoaded;

window.addEventListener('auth:ready', () => {
    const container = document.getElementById('tool-settings-list');
    if (!container) return;
    initToolSettings().catch((err) =>
        console.error('[toolSettings] auth:ready reload failed:', err)
    );
});

window.addEventListener('auth:initialized', (event) => {
    const container = document.getElementById('tool-settings-list');
    if (!container) return;
    if (event?.detail?.isLoggedIn) {
        initToolSettings().catch((err) =>
            console.error('[toolSettings] auth:initialized reload failed:', err)
        );
    }
});

export {
    initToolSettings,
    toggleToolPreference,
    toggleToolCategory,
};
