// ============================================================
// Forex Market Tab
// Follows the same pattern as commodity.js / usstock.js
// ============================================================

const ForexTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    // ── 可選貨幣對完整清單（分組）──────────────────────────────
    AVAILABLE_PAIRS: [
        { symbol: 'TWD=X',    name: 'USD/TWD', group: '亞太' },
        { symbol: 'JPY=X',    name: 'USD/JPY', group: '亞太' },
        { symbol: 'CNY=X',    name: 'USD/CNY', group: '亞太' },
        { symbol: 'HKD=X',    name: 'USD/HKD', group: '亞太' },
        { symbol: 'AUDUSD=X', name: 'AUD/USD', group: '亞太' },
        { symbol: 'NZDUSD=X', name: 'NZD/USD', group: '亞太' },
        { symbol: 'KRW=X',    name: 'USD/KRW', group: '亞太' },
        { symbol: 'EURUSD=X', name: 'EUR/USD', group: '歐美' },
        { symbol: 'GBPUSD=X', name: 'GBP/USD', group: '歐美' },
        { symbol: 'USDCHF=X', name: 'USD/CHF', group: '歐美' },
        { symbol: 'USDCAD=X', name: 'USD/CAD', group: '歐美' },
        { symbol: 'EURGBP=X', name: 'EUR/GBP', group: '歐美' },
        { symbol: 'EURJPY=X', name: 'EUR/JPY', group: '交叉盤' },
        { symbol: 'GBPJPY=X', name: 'GBP/JPY', group: '交叉盤' },
        { symbol: 'AUDJPY=X', name: 'AUD/JPY', group: '交叉盤' },
    ],
    STORAGE_KEY: 'forex_selected_pairs',
    DEFAULT_SELECTED: ['TWD=X', 'EURUSD=X', 'GBPUSD=X', 'JPY=X', 'AUDUSD=X', 'CNY=X'],

    getActivePairs() {
        try {
            const saved = localStorage.getItem(this.STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed) && parsed.length > 0) return parsed;
            }
        } catch (_) {}
        return [...this.DEFAULT_SELECTED];
    },

    _saveActivePairs(pairs) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(pairs));
    },

    showPicker() {
        const listEl = document.getElementById('forex-list');
        if (!listEl) return;
        const selected = new Set(this.getActivePairs());
        const groups = {};
        this.AVAILABLE_PAIRS.forEach(p => {
            if (!groups[p.group]) groups[p.group] = [];
            groups[p.group].push(p);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的貨幣對（至少 1 個）</p>
                ${Object.entries(groups).map(([group, pairs]) => `
                    <div class="mb-5">
                        <div class="text-[10px] uppercase tracking-wider text-textMuted/50 mb-2 pl-1">${group}</div>
                        <div class="space-y-2">
                            ${pairs.map(p => `
                                <label class="flex items-center justify-between bg-surface border ${selected.has(p.symbol) ? 'border-primary/40 bg-primary/5' : 'border-white/5'} rounded-xl px-4 py-3 cursor-pointer hover:border-primary/30 transition">
                                    <span class="text-sm font-bold text-secondary font-mono">${escapeHtml(p.name)}</span>
                                    <input type="checkbox" value="${p.symbol}" ${selected.has(p.symbol) ? 'checked' : ''}
                                        class="forex-pair-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="ForexTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="ForexTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.forex-pair-check:checked');
        const selected = Array.from(checks).map(c => c.value);
        if (selected.length === 0) {
            if (typeof showToast === 'function') showToast('請至少選擇一個貨幣對', 'error');
            return;
        }
        this._saveActivePairs(selected);
        this.renderMarket();
    },

    // ── Init ──────────────────────────────────────────────────

    init: function () {
        if (window.MarketStatus) {
            window.MarketStatus.startMarketAutoRefresh(
                'forex',
                () => this.refreshCurrent(),
                () => this.lastUpdatedAt
            );
        }
        this.renderMarket();
    },

    refreshCurrent: function () {
        if (this.activeSubTab === 'pulse' && this.activeSymbol) {
            return this.renderPulse(this.activeSymbol);
        }
        return this.renderMarket();
    },

    // ── Sub-tab switching ─────────────────────────────────────

    switchSubTab: function (subTab, symbol) {
        this.activeSubTab = subTab;
        const marketEl = document.getElementById('forex-market-section');
        const pulseEl  = document.getElementById('forex-pulse-section');
        if (!marketEl || !pulseEl) return;

        if (subTab === 'market') {
            marketEl.classList.remove('hidden');
            pulseEl.classList.add('hidden');
            this.destroyChart();
        } else if (subTab === 'pulse' && symbol) {
            this.activeSymbol = symbol;
            marketEl.classList.add('hidden');
            pulseEl.classList.remove('hidden');
            this.renderPulse(symbol);
        }
    },

    backToMarket: function () {
        this.switchSubTab('market');
    },

    // ── Market View ───────────────────────────────────────────

    renderMarket: async function () {
        const listEl = document.getElementById('forex-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('forex');
        listEl.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">' + t('common.loading') + '</p></div>';
        AppUtils.refreshIcons();

        try {
            const active = this.getActivePairs();
            const url = active.length ? `/api/forex/market?pairs=${active.join(',')}` : '/api/forex/market';
            const data = await AppAPI.get(url);

            listEl.innerHTML = '';
            (data.pairs || []).forEach(item => {
                const isUp   = item.changePercent >= 0;
                const color  = isUp ? 'text-success' : 'text-danger';
                const arrow  = isUp ? '▲' : '▼';
                // Find display info (covers all 15 AVAILABLE_PAIRS)
                const meta   = this.AVAILABLE_PAIRS.find(p => p.symbol === item.symbol);
                const desc   = meta?.name || item.name;

                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${escapeHtml(item.name)}</div>
                        <div class="text-xs text-textMuted">${escapeHtml(desc)}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.rate.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(3)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('forex');
                window.MarketStatus.updateMarketStatusBar('forex', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">${t('marketPage.loadFailedDetail')}${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('forex-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/forex/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }

            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp  = d.change_24h >= 0;
            const color = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';

            const summarySection = userProvider
                ? `<div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="flex items-center gap-2 mb-3">
                            <h4 class="text-xs uppercase tracking-wider text-textMuted">${t('pulse.title')}</h4>
                            ${isDeep ? '<span class="text-[9px] px-1.5 py-0.5 bg-primary/20 text-primary rounded border border-primary/30 flex items-center gap-1"><i data-lucide="zap" class="w-2.5 h-2.5"></i>' + t('marketPage.aiDeepAnalysis') + '</span>' : ''}
                        </div>
                        <p class="text-sm text-secondary leading-relaxed">${escapeHtml(d.report?.summary || '')}</p>
                   </div>`
                : `<div class="bg-surface border border-primary/20 rounded-2xl p-5">
                        <div class="flex flex-col items-center text-center gap-3 py-2">
                            <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                                <i data-lucide="key" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <p class="text-sm font-bold text-secondary mb-1">${t('marketPage.connectApiKey')}</p>
                                <p class="text-xs text-textMuted">${t('marketPage.connectApiKeyDesc')}</p>
                            </div>
                            <button onclick="switchTab('settings')" class="px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary text-xs rounded-xl border border-primary/30 transition flex items-center gap-1.5">
                                <i data-lucide="settings" class="w-3.5 h-3.5"></i>${t('pulse.goToSettings')}
                            </button>
                        </div>
                   </div>`;

            pulseEl.innerHTML = `
                <div class="space-y-4">
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="text-textMuted text-xs uppercase tracking-wider mb-1">${escapeHtml(d.name)}</div>
                        <div class="text-3xl font-serif text-secondary font-bold">${d.rate?.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(3)}% 24H</div>
                    </div>
                    ${summarySection}
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">${t('marketPage.technicalIndicators')}</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${(d.report?.key_points || []).map(pt => `
                                <div class="bg-background rounded-xl px-3 py-2 text-xs">
                                    <span class="text-textMuted">${escapeHtml(pt.split(':')[0])}:</span>
                                    <span class="text-secondary font-mono ml-1">${escapeHtml(pt.split(':').slice(1).join(':').trim())}</span>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div id="forex-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">${t('marketPage.trendChart')}</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="ForexTab.changeInterval('${iv}')" id="forex-interval-${iv}" class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">${iv === '1d' ? t('marketPage.intervalDay') : iv === '1wk' ? t('marketPage.intervalWeek') : t('marketPage.intervalMonth')}</button>`).join('')}
                            </div>
                        </div>
                        <div id="forex-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            AppUtils.refreshIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">${t('marketPage.loadFailedDetail')}${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Chart ─────────────────────────────────────────────────

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('forex-chart');
        if (!chartEl) return;
        this.destroyChart();

        try {
            const res = await AppAPI.get(`/api/forex/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            const klines = res.data || [];
            if (!klines.length) return;

            if (typeof LightweightCharts === 'undefined') return;
            this.chartInstance = LightweightCharts.createChart(chartEl, {
                width: chartEl.clientWidth,
                height: 200,
                layout: { background: { color: 'transparent' }, textColor: '#8899a6' },
                grid: { vertLines: { color: '#1a2332' }, horzLines: { color: '#1a2332' } },
                rightPriceScale: { borderColor: '#1a2332' },
                timeScale: { borderColor: '#1a2332', timeVisible: true },
            });
            this.chartSeries = this.chartInstance.addLineSeries({
                color: '#8B5CF6', lineWidth: 2,
            });
            this.chartSeries.setData(klines.map(k => ({ time: k.time, value: k.close })));
            this.chartInstance.timeScale().fitContent();
        } catch (e) {
            console.warn('[ForexTab] chart load failed:', e);
        }
    },

    changeInterval: function (interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`forex-interval-${iv}`);
            if (!btn) return;
            btn.className = iv === interval
                ? 'text-xs px-2 py-1 rounded-lg bg-primary text-background transition'
                : 'text-xs px-2 py-1 rounded-lg bg-surface text-textMuted hover:bg-surfaceHighlight transition';
        });
        if (this.activeSymbol) this.loadChart(this.activeSymbol, interval);
    },

    destroyChart: function () {
        if (this.chartInstance) {
            try { this.chartInstance.remove(); } catch (_) {}
            this.chartInstance = null;
            this.chartSeries = null;
        }
    },
};

window.ForexTab = ForexTab;
export { ForexTab };
