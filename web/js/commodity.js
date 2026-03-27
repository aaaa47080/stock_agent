// ============================================================
// Commodity Market Tab
// Follows the same pattern as usstock.js / twstock.js
// ============================================================

const CommodityTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    DEFAULT_SYMBOLS: [
        { symbol: 'GC=F',  name: t('commodity.gold'),   unit: 'USD/oz'  },
        { symbol: 'CL=F',  name: t('commodity.wtiCrude'), unit: 'USD/bbl' },
        { symbol: 'SI=F',  name: t('commodity.silver'),   unit: 'USD/oz'  },
        { symbol: 'NG=F',  name: t('commodity.naturalGas'), unit: 'USD/MMBtu'},
        { symbol: 'HG=F',  name: t('commodity.copper'),   unit: 'USD/lb'  },
        { symbol: 'BZ=F',  name: t('commodity.brentCrude'), unit: 'USD/bbl'},
    ],

    // ── Init ──────────────────────────────────────────────────

    init: function () {
        if (window.MarketStatus) {
            window.MarketStatus.startMarketAutoRefresh(
                'commodity',
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
        const marketEl = document.getElementById('commodity-market-section');
        const pulseEl  = document.getElementById('commodity-pulse-section');
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
        const listEl = document.getElementById('commodity-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('commodity');
        listEl.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">' + t('common.loading') + '</p></div>';
        AppUtils.refreshIcons();

        try {
            const data = await AppAPI.get('/api/commodity/market');

            listEl.innerHTML = '';
            (data.commodities || []).forEach(item => {
                const isUp   = item.changePercent >= 0;
                const color  = isUp ? 'text-success' : 'text-danger';
                const arrow  = isUp ? '▲' : '▼';
                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${escapeHtml(item.name)}</div>
                        <div class="text-xs text-textMuted">${escapeHtml(item.symbol)} · ${escapeHtml(item.unit)}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.price.toLocaleString(undefined, {maximumFractionDigits: 4})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('commodity');
                window.MarketStatus.updateMarketStatusBar('commodity', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">${t('marketPage.loadFailedDetail')}${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('commodity-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/commodity/pulse/${encodeURIComponent(symbol)}`;
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
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 4})} <span class="text-sm font-normal text-textMuted">${escapeHtml(d.unit)}</span></div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(2)}% 24H</div>
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
                    <div id="commodity-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">${t('marketPage.trendChart')}</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="CommodityTab.changeInterval('${iv}')" id="commodity-interval-${iv}" class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">${iv === '1d' ? t('marketPage.intervalDay') : iv === '1wk' ? t('marketPage.intervalWeek') : t('marketPage.intervalMonth')}</button>`).join('')}
                            </div>
                        </div>
                        <div id="commodity-chart" style="height: 200px;"></div>
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
        const chartEl = document.getElementById('commodity-chart');
        if (!chartEl) return;
        this.destroyChart();

        try {
            const res = await AppAPI.get(`/api/commodity/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            const klines = res.data || [];
            if (!klines.length) return;

            if (typeof LightweightCharts === 'undefined') return;
            this.chartInstance = LightweightCharts.createChart(chartEl, {
                width: chartEl.clientWidth,
                height: 200,
                layout: { background: { color: 'transparent' }, textColor: '#8899a6' },
                grid: { vertLines: { color: '#1a2332' }, horzLines: { color: '#1a2332' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: '#1a2332' },
                timeScale: { borderColor: '#1a2332', timeVisible: true },
            });
            this.chartSeries = this.chartInstance.addCandlestickSeries({
                upColor: '#22c55e', downColor: '#ef4444',
                borderUpColor: '#22c55e', borderDownColor: '#ef4444',
                wickUpColor: '#22c55e', wickDownColor: '#ef4444',
            });
            this.chartSeries.setData(klines.map(k => ({
                time: k.time, open: k.open, high: k.high, low: k.low, close: k.close,
            })));
            this.chartInstance.timeScale().fitContent();
        } catch (e) {
            console.warn('[CommodityTab] chart load failed:', e);
        }
    },

    changeInterval: function (interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`commodity-interval-${iv}`);
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

window.CommodityTab = CommodityTab;
export { CommodityTab };
