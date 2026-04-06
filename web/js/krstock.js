// ============================================================
// Korea Stock Market Tab — 韓股市場
// Follows the same pattern as instock.js / jpstock.js
// ============================================================

const KRStockTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    AVAILABLE_SYMBOLS: [
        // 科技 / 半導體
        { symbol: '005930.KS', name: '三星電子 Samsung',             group: '科技/半導體' },
        { symbol: '000660.KS', name: 'SK 海力士 SK Hynix',           group: '科技/半導體' },
        { symbol: '066570.KS', name: 'LG電子 LG Electronics',        group: '科技/半導體' },
        { symbol: '034730.KS', name: 'SK 控股 SK Holdings',          group: '科技/半導體' },
        // 汽車
        { symbol: '005380.KS', name: '現代汽車 Hyundai Motor',       group: '汽車' },
        { symbol: '000270.KS', name: '起亞 Kia',                     group: '汽車' },
        { symbol: '012330.KS', name: '現代摩比斯 Mobis',             group: '汽車' },
        // 化學 / 材料
        { symbol: '051910.KS', name: 'LG 化學 LG Chem',              group: '化學/材料' },
        { symbol: '096770.KS', name: 'SK 創新 SK Innovation',        group: '化學/材料' },
        { symbol: '003670.KS', name: '浦項鋼鐵 POSCO',               group: '化學/材料' },
        // 金融
        { symbol: '105560.KS', name: 'KB 金融 KB Financial',         group: '金融' },
        { symbol: '055550.KS', name: '新韓金融 Shinhan',             group: '金融' },
        { symbol: '086790.KS', name: '韓亞金融 Hana Financial',      group: '金融' },
        // 生技 / 醫療
        { symbol: '207940.KS', name: '三星生物 Samsung Biologics',   group: '生技/醫療' },
        { symbol: '068270.KS', name: 'Celltrion',                    group: '生技/醫療' },
        // 消費 / 食品
        { symbol: '004370.KS', name: '農心 Nongshim',                group: '消費/食品' },
        { symbol: '097950.KS', name: 'CJ 第一製糖',                  group: '消費/食品' },
        // 電信
        { symbol: '017670.KS', name: 'SK 電信 SK Telecom',           group: '電信' },
        { symbol: '030200.KS', name: 'KT',                           group: '電信' },
        // KOSDAQ
        { symbol: '035420.KQ', name: 'Naver',                        group: 'KOSDAQ' },
        { symbol: '035720.KQ', name: 'Kakao',                        group: 'KOSDAQ' },
        { symbol: '247540.KQ', name: 'EcoPro BM',                    group: 'KOSDAQ' },
        { symbol: '086520.KQ', name: 'EcoPro',                       group: 'KOSDAQ' },
        { symbol: '196170.KQ', name: 'Alteogen',                     group: 'KOSDAQ' },
        // ETF
        { symbol: '069500.KS', name: 'KODEX 200 ETF',                group: 'ETF' },
        { symbol: '133690.KS', name: 'TIGER Nasdaq100 ETF',          group: 'ETF' },
    ],
    STORAGE_KEY: 'krstock_selected_symbols',
    DEFAULT_SELECTED: [
        '005930.KS', '000660.KS', '005380.KS', '035420.KQ',
        '051910.KS', '105560.KS', '017670.KS', '069500.KS',
    ],

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

    showPicker() {
        const listEl = document.getElementById('krstock-list');
        if (!listEl) return;
        const selected = new Set(this.getActiveSymbols());
        const groups = {};
        this.AVAILABLE_SYMBOLS.forEach(s => {
            if (!groups[s.group]) groups[s.group] = [];
            groups[s.group].push(s);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的韓股（至少 1 個）</p>
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
                                        class="krstock-sym-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="KRStockTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="KRStockTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.krstock-sym-check:checked');
        const selected = Array.from(checks).map(c => c.value);
        if (selected.length === 0) {
            if (typeof showToast === 'function') showToast('請至少選擇一個標的', 'error');
            return;
        }
        this._saveActiveSymbols(selected);
        this.renderMarket();
    },

    init() {
        if (window.MarketStatus) {
            window.MarketStatus.startMarketAutoRefresh(
                'krstock',
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

    switchSubTab(subTab, symbol) {
        this.activeSubTab = subTab;
        const marketEl = document.getElementById('krstock-market-section');
        const pulseEl  = document.getElementById('krstock-pulse-section');
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

    renderMarket: async function () {
        const listEl = document.getElementById('krstock-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('krstock');
        listEl.innerHTML = `<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">${typeof t === 'function' ? t('common.loading') : '載入中...'}</p></div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const active = this.getActiveSymbols();
            const url = `/api/krstock/market?symbols=${active.join(',')}`;
            const data = await AppAPI.get(url);

            listEl.innerHTML = '';
            (data.stocks || []).forEach(item => {
                const isUp = item.changePercent >= 0;
                const color = isUp ? 'text-success' : 'text-danger';
                const arrow = isUp ? '▲' : '▼';
                const symbol = escapeHtml(item.symbol);
                const cardCode = symbol.replace('.KS', '').replace('.KQ', '').slice(0, 2);
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
                                    <div class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60">${symbol} · ${item.currency || 'KRW'}</div>
                                </div>
                                <div class="text-right flex-shrink-0">
                                    <div class="text-sm font-black ${color}">${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                                    <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold">24H</div>
                                </div>
                            </div>
                            <div class="flex items-center justify-between mt-1.5">
                                <div class="text-[11px] text-textMuted font-mono opacity-80">${item.price.toLocaleString(undefined, {maximumFractionDigits: 0})} ${item.currency || 'KRW'}</div>
                                <div class="text-xs font-bold ${color}">${arrow} ${item.change >= 0 ? '+' : ''}${item.change.toFixed(0)}</div>
                            </div>
                        </div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('krstock');
                window.MarketStatus.updateMarketStatusBar('krstock', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('krstock-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/krstock/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }
            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp   = d.change_24h >= 0;
            const color  = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';
            const currency = d.currency || 'KRW';

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
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 0})} <span class="text-sm font-normal text-textMuted">${currency}</span></div>
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
                    <div id="krstock-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="KRStockTab.changeInterval('${iv}')" id="krstock-interval-${iv}"
                                    class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">
                                    ${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}
                                </button>`).join('')}
                            </div>
                        </div>
                        <div id="krstock-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('krstock-chart');
        if (!chartEl) return;
        this.destroyChart();
        try {
            const res = await AppAPI.get(`/api/krstock/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
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
            console.warn('[KRStockTab] chart load failed:', e);
        }
    },

    changeInterval(interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`krstock-interval-${iv}`);
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

window.KRStockTab = KRStockTab;
export { KRStockTab };
