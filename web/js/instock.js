// ============================================================
// India Stock Market Tab — 印度股市
// Follows the same pattern as jpstock.js / astock.js
// ============================================================

const INStockTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    AVAILABLE_SYMBOLS: [
        // 能源 / 石化
        { symbol: 'RELIANCE.NS',   name: '信實工業 Reliance',          group: '能源/石化' },
        { symbol: 'ONGC.NS',       name: '國家石油 ONGC',              group: '能源/石化' },
        { symbol: 'NTPC.NS',       name: '國家電力 NTPC',              group: '能源/石化' },
        // 資訊科技
        { symbol: 'TCS.NS',        name: '塔塔顧問 TCS',               group: '資訊科技' },
        { symbol: 'INFY.NS',       name: '印孚瑟斯 Infosys',           group: '資訊科技' },
        { symbol: 'WIPRO.NS',      name: '威普羅 Wipro',               group: '資訊科技' },
        { symbol: 'HCLTECH.NS',    name: 'HCL Technologies',           group: '資訊科技' },
        { symbol: 'TECHM.NS',      name: '科技馬辛德拉 Tech Mahindra', group: '資訊科技' },
        // 金融 / 銀行
        { symbol: 'HDFCBANK.NS',   name: 'HDFC 銀行',                  group: '金融/銀行' },
        { symbol: 'ICICIBANK.NS',  name: 'ICICI 銀行',                 group: '金融/銀行' },
        { symbol: 'SBIN.NS',       name: '印度國家銀行 SBI',           group: '金融/銀行' },
        { symbol: 'KOTAKBANK.NS',  name: '科塔克銀行 Kotak',           group: '金融/銀行' },
        { symbol: 'AXISBANK.NS',   name: 'Axis 銀行',                  group: '金融/銀行' },
        // 消費 / 零售
        { symbol: 'HINDUNILVR.NS', name: '聯合利華印度 HUL',           group: '消費/零售' },
        { symbol: 'ITC.NS',        name: 'ITC',                        group: '消費/零售' },
        { symbol: 'ASIANPAINT.NS', name: '亞洲塗料 Asian Paints',      group: '消費/零售' },
        { symbol: 'TITAN.NS',      name: '泰坦公司 Titan',             group: '消費/零售' },
        // 汽車
        { symbol: 'TATAMOTORS.NS', name: '塔塔汽車 Tata Motors',       group: '汽車' },
        { symbol: 'MARUTI.NS',     name: '馬魯蒂 Maruti Suzuki',       group: '汽車' },
        { symbol: 'M&M.NS',        name: '馬辛德拉 Mahindra',          group: '汽車' },
        // 製藥 / 醫療
        { symbol: 'SUNPHARMA.NS',  name: '太陽製藥 Sun Pharma',        group: '製藥/醫療' },
        { symbol: 'DRREDDY.NS',    name: "雷迪博士 Dr. Reddy's",       group: '製藥/醫療' },
        // 電信
        { symbol: 'BHARTIARTL.NS', name: '巴帝電信 Airtel',            group: '電信' },
        // 鋼鐵 / 金屬
        { symbol: 'TATASTEEL.NS',  name: '塔塔鋼鐵 Tata Steel',        group: '鋼鐵/金屬' },
        { symbol: 'JSWSTEEL.NS',   name: 'JSW 鋼鐵',                   group: '鋼鐵/金屬' },
        // ETF
        { symbol: 'NIFTYBEES.NS',  name: 'Nifty50 ETF (Nippon)',       group: 'ETF' },
    ],
    STORAGE_KEY: 'instock_selected_symbols',
    DEFAULT_SELECTED: [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS',
        'TATAMOTORS.NS', 'BHARTIARTL.NS', 'SUNPHARMA.NS', 'NIFTYBEES.NS',
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
        const listEl = document.getElementById('instock-list');
        if (!listEl) return;
        const selected = new Set(this.getActiveSymbols());
        const groups = {};
        this.AVAILABLE_SYMBOLS.forEach(s => {
            if (!groups[s.group]) groups[s.group] = [];
            groups[s.group].push(s);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的印度股（至少 1 個）</p>
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
                                        class="instock-sym-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="INStockTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="INStockTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.instock-sym-check:checked');
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
                'instock',
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
        const marketEl = document.getElementById('instock-market-section');
        const pulseEl  = document.getElementById('instock-pulse-section');
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
        const listEl = document.getElementById('instock-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('instock');
        listEl.innerHTML = `<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">${typeof t === 'function' ? t('common.loading') : '載入中...'}</p></div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const active = this.getActiveSymbols();
            const url = `/api/instock/market?symbols=${active.join(',')}`;
            const data = await AppAPI.get(url);

            listEl.innerHTML = '';
            (data.stocks || []).forEach(item => {
                const isUp  = item.changePercent >= 0;
                const color = isUp ? 'text-success' : 'text-danger';
                const arrow = isUp ? '▲' : '▼';
                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${escapeHtml(item.name)}</div>
                        <div class="text-xs text-textMuted">${escapeHtml(item.symbol)} · ${item.currency || 'INR'}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.price.toLocaleString(undefined, {maximumFractionDigits: 2})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('instock');
                window.MarketStatus.updateMarketStatusBar('instock', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('instock-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/instock/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }
            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp   = d.change_24h >= 0;
            const color  = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';
            const currency = d.currency || 'INR';

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
                    <div id="instock-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="INStockTab.changeInterval('${iv}')" id="instock-interval-${iv}"
                                    class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">
                                    ${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}
                                </button>`).join('')}
                            </div>
                        </div>
                        <div id="instock-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('instock-chart');
        if (!chartEl) return;
        this.destroyChart();
        try {
            const res = await AppAPI.get(`/api/instock/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
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
            console.warn('[INStockTab] chart load failed:', e);
        }
    },

    changeInterval(interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`instock-interval-${iv}`);
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

window.INStockTab = INStockTab;
export { INStockTab };
