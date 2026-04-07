// ============================================================
// HK Stock Market Tab — 港股市場
// Follows the same pattern as commodity.js / usstock.js
// ============================================================

const HKStockTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    // ── 可選標的完整清單（分組）─────────────────────────────────
    AVAILABLE_SYMBOLS: [
        // 科技 / 互聯網
        { symbol: '0700.HK', name: '騰訊 Tencent',        name_zh: '騰訊',         name_en: 'Tencent',        group: '科技/互聯網' },
        { symbol: '9988.HK', name: '阿里巴巴 Alibaba',     name_zh: '阿里巴巴',     name_en: 'Alibaba',        group: '科技/互聯網' },
        { symbol: '3690.HK', name: '美團 Meituan',         name_zh: '美團',         name_en: 'Meituan',        group: '科技/互聯網' },
        { symbol: '9618.HK', name: '京東 JD.com',          name_zh: '京東',         name_en: 'JD.com',         group: '科技/互聯網' },
        { symbol: '0992.HK', name: '聯想 Lenovo',          name_zh: '聯想',         name_en: 'Lenovo',         group: '科技/互聯網' },
        { symbol: '0241.HK', name: '阿里健康',             name_zh: '阿里健康',     name_en: 'Alibaba Health', group: '科技/互聯網' },
        // 金融
        { symbol: '0005.HK', name: '匯豐 HSBC',            name_zh: '匯豐',         name_en: 'HSBC',           group: '金融' },
        { symbol: '0939.HK', name: '建設銀行',             name_zh: '建設銀行',     name_en: 'CCB',            group: '金融' },
        { symbol: '1398.HK', name: '工商銀行',             name_zh: '工商銀行',     name_en: 'ICBC',           group: '金融' },
        { symbol: '3988.HK', name: '中國銀行',             name_zh: '中國銀行',     name_en: 'Bank of China',  group: '金融' },
        { symbol: '0011.HK', name: '恒生銀行',             name_zh: '恒生銀行',     name_en: 'Hang Seng Bank', group: '金融' },
        { symbol: '2318.HK', name: '中國平安',             name_zh: '中國平安',     name_en: 'Ping An',        group: '金融' },
        // 地產 / 基建
        { symbol: '0016.HK', name: '新鴻基地產',           name_zh: '新鴻基地產',   name_en: 'Sun Hung Kai',   group: '地產/基建' },
        { symbol: '0001.HK', name: '長和 CK Hutchison',    name_zh: '長和',         name_en: 'CK Hutchison',   group: '地產/基建' },
        { symbol: '0002.HK', name: '中電控股',             name_zh: '中電控股',     name_en: 'CLP Holdings',   group: '地產/基建' },
        // 消費 / 娛樂
        { symbol: '0291.HK', name: '華潤啤酒',             name_zh: '華潤啤酒',     name_en: 'CR Beer',        group: '消費/娛樂' },
        { symbol: '0027.HK', name: '銀河娛樂',             name_zh: '銀河娛樂',     name_en: 'Galaxy Entertainment', group: '消費/娛樂' },
        { symbol: '1928.HK', name: '金沙中國',             name_zh: '金沙中國',     name_en: 'Sands China',    group: '消費/娛樂' },
        // 醫療 / 生物
        { symbol: '1177.HK', name: '中國生物製藥',         name_zh: '中國生物製藥', name_en: 'Sino Biopharm',  group: '醫療/生物' },
        { symbol: '6160.HK', name: '百濟神州',             name_zh: '百濟神州',     name_en: 'BeiGene',        group: '醫療/生物' },
        // 汽車 / 新能源
        { symbol: '0175.HK', name: '吉利汽車',             name_zh: '吉利汽車',     name_en: 'Geely Auto',     group: '汽車/新能源' },
        { symbol: '2015.HK', name: '理想汽車',             name_zh: '理想汽車',     name_en: 'Li Auto',        group: '汽車/新能源' },
        { symbol: '9866.HK', name: '蔚來 NIO',             name_zh: '蔚來',         name_en: 'NIO',            group: '汽車/新能源' },
        // 交易所
        { symbol: '0388.HK', name: '港交所 HKEX',          name_zh: '港交所',       name_en: 'HKEX',           group: '交易所' },
        // ETF
        { symbol: '2800.HK', name: '盈富基金 (恒指ETF)',   name_zh: '盈富基金 (恒指ETF)', name_en: 'Tracker Fund (HSI ETF)', group: 'ETF' },
        { symbol: '3032.HK', name: '恒生科技ETF',          name_zh: '恒生科技ETF',  name_en: 'HS Tech ETF',    group: 'ETF' },
    ],
    getStockName(item) {
        const lang = window.I18n?.getLanguage?.() || 'zh-TW';
        if (lang === 'en') return item.name_en || item.name || '';
        return item.name_zh || item.name || '';
    },
    STORAGE_KEY: 'hkstock_selected_symbols',
    DEFAULT_SELECTED: ['0700.HK', '9988.HK', '0005.HK', '0388.HK', '3690.HK', '2318.HK', '0939.HK', '2800.HK'],

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
        const listEl = document.getElementById('hkstock-list');
        if (!listEl) return;
        const selected = new Set(this.getActiveSymbols());
        const groups = {};
        this.AVAILABLE_SYMBOLS.forEach(s => {
            if (!groups[s.group]) groups[s.group] = [];
            groups[s.group].push(s);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的港股（至少 1 個）</p>
                ${Object.entries(groups).map(([group, syms]) => `
                    <div class="mb-5">
                        <div class="text-[10px] uppercase tracking-wider text-textMuted/50 mb-2 pl-1">${group}</div>
                        <div class="space-y-2">
                            ${syms.map(s => `
                                <label class="flex items-center justify-between bg-surface border ${selected.has(s.symbol) ? 'border-primary/40 bg-primary/5' : 'border-white/5'} rounded-xl px-4 py-3 cursor-pointer hover:border-primary/30 transition">
                                    <div>
                                        <span class="text-sm font-bold text-secondary">${escapeHtml(window.I18n?.getLanguage?.() === 'en' ? (s.name_en || s.name) : (s.name_zh || s.name))}</span>
                                        <span class="text-xs text-textMuted ml-2">${s.symbol}</span>
                                    </div>
                                    <input type="checkbox" value="${s.symbol}" ${selected.has(s.symbol) ? 'checked' : ''}
                                        class="hkstock-sym-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="HKStockTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="HKStockTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.hkstock-sym-check:checked');
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
        window.addEventListener('languageChanged', () => {
            if (this.activeSubTab === 'market') this.renderMarket();
        });
        if (window.MarketStatus) {
            window.MarketStatus.startMarketAutoRefresh(
                'hkstock',
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
        const marketEl = document.getElementById('hkstock-market-section');
        const pulseEl  = document.getElementById('hkstock-pulse-section');
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
        const listEl = document.getElementById('hkstock-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('hkstock');
        listEl.innerHTML = `<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">${typeof t === 'function' ? t('common.loading') : '載入中...'}</p></div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const active = this.getActiveSymbols();
            const url = `/api/hkstock/market?symbols=${active.join(',')}`;
            const data = await AppAPI.get(url);

            listEl.innerHTML = '';
            (data.stocks || []).forEach(item => {
                const isUp = item.changePercent >= 0;
                const color = isUp ? 'text-success' : 'text-danger';
                const arrow = isUp ? '▲' : '▼';
                const symbol = escapeHtml(item.symbol);
                const cardCode = symbol.replace('.HK', '').slice(0, 2);
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
                                    <div class="font-bold text-sm text-secondary leading-tight">${escapeHtml(this.getStockName(item))}</div>
                                    <div class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60">${symbol} · ${item.currency || 'HKD'}</div>
                                </div>
                                <div class="text-right flex-shrink-0">
                                    <div class="text-sm font-black ${color}">${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                                    <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold">24H</div>
                                </div>
                            </div>
                            <div class="flex items-center justify-between mt-1.5">
                                <div class="text-[11px] text-textMuted font-mono opacity-80">${item.price.toLocaleString(undefined, { maximumFractionDigits: 3 })} ${item.currency || 'HKD'}</div>
                                <div class="text-xs font-bold ${color}">${arrow} ${item.change >= 0 ? '+' : ''}${item.change.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('hkstock');
                window.MarketStatus.updateMarketStatusBar('hkstock', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────
    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('hkstock-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/hkstock/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }
            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp   = d.change_24h >= 0;
            const color  = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';
            const currency = d.currency || 'HKD';

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
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 3})} <span class="text-sm font-normal text-textMuted">${currency}</span></div>
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
                    <div id="hkstock-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="HKStockTab.changeInterval('${iv}')" id="hkstock-interval-${iv}"
                                    class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">
                                    ${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}
                                </button>`).join('')}
                            </div>
                        </div>
                        <div id="hkstock-chart" style="height: 200px;"></div>
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
        const chartEl = document.getElementById('hkstock-chart');
        if (!chartEl) return;
        this.destroyChart();
        try {
            const res = await AppAPI.get(`/api/hkstock/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
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
            console.warn('[HKStockTab] chart load failed:', e);
        }
    },

    changeInterval(interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`hkstock-interval-${iv}`);
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

    addStock: async function(symbol) {
        if (!symbol) return;
        const sym = symbol.toUpperCase().trim();
        if (!sym) return;

        const active = this.getActiveSymbols();
        if (active.includes(sym)) {
            if (window.showToast) window.showToast(`${sym} 已在自選清單`, 'info');
            const input = document.getElementById('hkstock-add-input');
            if (input) input.value = '';
            return;
        }

        const input = document.getElementById('hkstock-add-input');
        const btn = input ? input.nextElementSibling : null;
        let originalIcon = '';
        if (btn) { originalIcon = btn.innerHTML; btn.innerHTML = '<div class="w-4 h-4 border-2 border-primary/50 border-t-primary rounded-full animate-spin"></div>'; btn.disabled = true; }

        try {
            const data = await AppAPI.get(`/api/hkstock/market?symbols=${encodeURIComponent(sym)}`);
            if (data.stocks && data.stocks.length > 0) {
                active.unshift(sym);
                this._saveActiveSymbols(active);
                this.renderMarket();
                if (window.showToast) window.showToast(`已加入 ${sym}`, 'success');
            } else {
                if (window.showToast) window.showToast(`找不到 ${sym}，請確認代碼`, 'error');
            }
        } catch(e) {
            if (window.showToast) window.showToast('查詢失敗：' + e.message, 'error');
        } finally {
            if (btn) { btn.innerHTML = originalIcon; btn.disabled = false; }
            if (input) input.value = '';
        }
    },

    removeStock: function(symbol, event) {
        if (event) event.stopPropagation();
        const active = this.getActiveSymbols().filter(s => s !== symbol);
        if (active.length === 0) { if (window.showToast) window.showToast('至少保留一個標的', 'error'); return; }
        this._saveActiveSymbols(active);
        this.renderMarket();
    },
};

window.HKStockTab = HKStockTab;
export { HKStockTab };
