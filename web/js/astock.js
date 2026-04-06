// ============================================================
// A-Share Market Tab — 陸股（滬深 A 股）
// Follows the same pattern as hkstock.js
// ============================================================

const AStockTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    // ── 可選標的完整清單（分組）─────────────────────────────────
    AVAILABLE_SYMBOLS: [
        // 消費 / 白酒
        { symbol: '600519.SS', name: '貴州茅台',   group: '消費/白酒' },
        { symbol: '000858.SZ', name: '五糧液',     group: '消費/白酒' },
        { symbol: '600887.SS', name: '伊利股份',   group: '消費/白酒' },
        { symbol: '603288.SS', name: '海天味業',   group: '消費/白酒' },
        // 金融 / 銀行
        { symbol: '600036.SS', name: '招商銀行',   group: '金融/銀行' },
        { symbol: '601318.SS', name: '中國平安',   group: '金融/銀行' },
        { symbol: '601398.SS', name: '工商銀行',   group: '金融/銀行' },
        { symbol: '601288.SS', name: '農業銀行',   group: '金融/銀行' },
        { symbol: '600000.SS', name: '浦發銀行',   group: '金融/銀行' },
        // 科技 / 半導體
        { symbol: '688981.SS', name: '中芯國際',   group: '科技/半導體' },
        { symbol: '002475.SZ', name: '立訊精密',   group: '科技/半導體' },
        { symbol: '300059.SZ', name: '東方財富',   group: '科技/半導體' },
        // 新能源 / 汽車
        { symbol: '002594.SZ', name: '比亞迪',     group: '新能源/汽車' },
        { symbol: '300750.SZ', name: '寧德時代',   group: '新能源/汽車' },
        { symbol: '601012.SS', name: '隆基綠能',   group: '新能源/汽車' },
        // 醫療 / 生物
        { symbol: '600276.SS', name: '恒瑞醫藥',   group: '醫療/生物' },
        { symbol: '300015.SZ', name: '愛爾眼科',   group: '醫療/生物' },
        { symbol: '600196.SS', name: '復星醫藥',   group: '醫療/生物' },
        // 能源
        { symbol: '600028.SS', name: '中國石化',   group: '能源' },
        { symbol: '601857.SS', name: '中國石油',   group: '能源' },
        { symbol: '600941.SS', name: '中國移動',   group: '能源' },
        // 地產
        { symbol: '000002.SZ', name: '萬科A',      group: '地產' },
        { symbol: '600048.SS', name: '保利發展',   group: '地產' },
        // ETF
        { symbol: '510300.SS', name: '滬深300ETF', group: 'ETF' },
        { symbol: '510500.SS', name: '中證500ETF', group: 'ETF' },
        { symbol: '159915.SZ', name: '創業板ETF',  group: 'ETF' },
    ],
    STORAGE_KEY: 'astock_selected_symbols',
    DEFAULT_SELECTED: ['600519.SS', '000858.SZ', '600036.SS', '002594.SZ', '300750.SZ', '600028.SS', '601318.SS', '510300.SS'],

    getActiveSymbols() {
        try {
            const saved = localStorage.getItem(this.STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (Array.isArray(parsed) && parsed.length > 0) return parsed;
            }
        } catch (_) {}
        return [...this.DEFAULT_SELECTED];
    },

    _saveActiveSymbols(symbols) {
        try { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(symbols)); } catch (_) {}
    },

    // ── Picker ────────────────────────────────────────────────
    showPicker() {
        const listEl = document.getElementById('astock-list');
        if (!listEl) return;
        const selected = new Set(this.getActiveSymbols());
        const groups = {};
        this.AVAILABLE_SYMBOLS.forEach(s => {
            if (!groups[s.group]) groups[s.group] = [];
            groups[s.group].push(s);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的 A 股（至少 1 個）</p>
                ${Object.entries(groups).map(([group, syms]) => `
                    <div class="mb-5">
                        <div class="text-[10px] uppercase tracking-wider text-textMuted/50 mb-2 pl-1">${group}</div>
                        <div class="space-y-2">
                            ${syms.map(s => `
                                <label class="flex items-center justify-between bg-surface border ${selected.has(s.symbol) ? 'border-primary/40 bg-primary/5' : 'border-white/5'} rounded-xl px-4 py-3 cursor-pointer hover:border-primary/30 transition">
                                    <div>
                                        <span class="text-sm font-bold text-secondary">${escapeHtml(s.name)}</span>
                                        <span class="text-xs text-textMuted ml-2">${s.symbol}</span>
                                    </div>
                                    <input type="checkbox" value="${s.symbol}" ${selected.has(s.symbol) ? 'checked' : ''}
                                        class="astock-sym-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="AStockTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="AStockTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.astock-sym-check:checked');
        const selected = Array.from(checks).map(c => c.value);
        if (selected.length === 0) {
            if (typeof showToast === 'function') showToast('請至少選擇一個標的', 'error');
            return;
        }
        this._saveActiveSymbols(selected);
        this.renderMarket();
    },

    // ── Init ──────────────────────────────────────────────────
    init() {
        if (window.MarketStatus) {
            window.MarketStatus.startMarketAutoRefresh(
                'astock',
                () => this.refreshCurrent(),
                () => this.lastUpdatedAt
            );
        }
        this.renderMarket();
    },

    refreshCurrent() {
        if (this.activeSubTab === 'pulse' && this.activeSymbol) {
            return this.renderPulse(this.activeSymbol);
        }
        return this.renderMarket();
    },

    // ── Sub-tab switching ─────────────────────────────────────
    switchSubTab(subTab, symbol) {
        this.activeSubTab = subTab;
        const marketEl = document.getElementById('astock-market-section');
        const pulseEl  = document.getElementById('astock-pulse-section');
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

    backToMarket() { this.switchSubTab('market'); },

    // ── Market View ───────────────────────────────────────────
    renderMarket: async function () {
        const listEl = document.getElementById('astock-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('astock');
        listEl.innerHTML = `<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">載入中...</p></div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const active = this.getActiveSymbols();
            const data = await AppAPI.get(`/api/astock/market?symbols=${active.join(',')}`);

            listEl.innerHTML = '';
            (data.stocks || []).forEach(item => {
                const isUp = item.changePercent >= 0;
                const color = isUp ? 'text-success' : 'text-danger';
                const arrow = isUp ? '▲' : '▼';
                const symbol = escapeHtml(item.symbol);
                const cardCode = symbol
                    .replace('.SS', '')
                    .replace('.SZ', '')
                    .slice(0, 2);
                const card = document.createElement('div');
                card.className =
                    'group bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div class="flex items-start gap-3">
                        <div class="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-xs font-bold text-primary border border-white/5 group-hover:scale-110 transition-transform flex-shrink-0 mt-0.5">${cardCode}</div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-start justify-between gap-2">
                                <div class="min-w-0">
                                    <div class="font-bold text-sm text-secondary leading-tight">${escapeHtml(item.name)}</div>
                                    <div class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60">${symbol} · ${item.currency || 'CNY'}</div>
                                </div>
                                <div class="text-right flex-shrink-0">
                                    <div class="text-sm font-black ${color}">${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                                    <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold">24H</div>
                                </div>
                            </div>
                            <div class="flex items-center justify-between mt-1.5">
                                <div class="text-[11px] text-textMuted font-mono opacity-80">${item.price.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${item.currency || 'CNY'}</div>
                                <div class="text-xs font-bold ${color}">${arrow} ${Math.abs(item.changePercent).toFixed(2)}%</div>
                            </div>
                        </div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('astock');
                window.MarketStatus.updateMarketStatusBar('astock', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────
    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('astock-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/astock/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }
            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp   = d.change_24h >= 0;
            const color  = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';
            const currency = d.currency || 'CNY';

            const summarySection = userProvider
                ? `<div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="flex items-center gap-2 mb-3">
                            <h4 class="text-xs uppercase tracking-wider text-textMuted">市場脈動</h4>
                            ${isDeep ? '<span class="text-[9px] px-1.5 py-0.5 bg-primary/20 text-primary rounded border border-primary/30 flex items-center gap-1"><i data-lucide="zap" class="w-2.5 h-2.5"></i>AI 深度分析</span>' : ''}
                        </div>
                        <p class="text-sm text-secondary leading-relaxed">${escapeHtml(d.report?.summary || '')}</p>
                   </div>`
                : `<div class="bg-surface border border-primary/20 rounded-2xl p-5">
                        <div class="flex flex-col items-center text-center gap-3 py-2">
                            <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                                <i data-lucide="key" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <p class="text-sm font-bold text-secondary mb-1">連結 AI 金鑰</p>
                                <p class="text-xs text-textMuted">在設定中填入 API Key 可啟用 AI 深度分析</p>
                            </div>
                            <button onclick="switchTab('settings')" class="px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary text-xs rounded-xl border border-primary/30 transition flex items-center gap-1.5">
                                <i data-lucide="settings" class="w-3.5 h-3.5"></i>前往設定
                            </button>
                        </div>
                   </div>`;

            pulseEl.innerHTML = `
                <div class="space-y-4">
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="text-textMuted text-xs uppercase tracking-wider mb-1">${escapeHtml(d.name)}</div>
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 2})} <span class="text-sm font-normal text-textMuted">${currency}</span></div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(2)}% 24H</div>
                    </div>
                    ${summarySection}
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">技術指標</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${(d.report?.key_points || []).map(pt => `
                                <div class="bg-background rounded-xl px-3 py-2 text-xs">
                                    <span class="text-textMuted">${escapeHtml(pt.split(':')[0])}:</span>
                                    <span class="text-secondary font-mono ml-1">${escapeHtml(pt.split(':').slice(1).join(':').trim())}</span>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div id="astock-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="AStockTab.changeInterval('${iv}')" id="astock-interval-${iv}"
                                    class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">
                                    ${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}
                                </button>`).join('')}
                            </div>
                        </div>
                        <div id="astock-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Chart ─────────────────────────────────────────────────
    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('astock-chart');
        if (!chartEl) return;
        this.destroyChart();
        try {
            const res = await AppAPI.get(`/api/astock/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            const klines = res.data || [];
            if (!klines.length) return;
            if (typeof LightweightCharts === 'undefined') return;
            this.chartInstance = LightweightCharts.createChart(chartEl, {
                width: chartEl.clientWidth, height: 200,
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
            console.warn('[AStockTab] chart load failed:', e);
        }
    },

    changeInterval(interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`astock-interval-${iv}`);
            if (!btn) return;
            btn.className = iv === interval
                ? 'text-xs px-2 py-1 rounded-lg bg-primary text-background transition'
                : 'text-xs px-2 py-1 rounded-lg bg-surface text-textMuted hover:bg-surfaceHighlight transition';
        });
        if (this.activeSymbol) this.loadChart(this.activeSymbol, interval);
    },

    destroyChart() {
        if (this.chartInstance) {
            try { this.chartInstance.remove(); } catch (_) {}
            this.chartInstance = null;
            this.chartSeries = null;
        }
    },
};

window.AStockTab = AStockTab;
export { AStockTab };
