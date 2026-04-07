// ============================================================
// JP Stock Market Tab — 日股市場
// Follows the same pattern as hkstock.js / astock.js
// ============================================================

const JPStockTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',
    lastUpdatedAt: null,

    // ── 可選標的完整清單（分組）─────────────────────────────────
    AVAILABLE_SYMBOLS: [
        // 汽車
        { symbol: '7203.T', name: '豐田汽車 Toyota',              name_zh: '豐田汽車', name_en: 'Toyota',                  group: '汽車' },
        { symbol: '7267.T', name: '本田 Honda',                   name_zh: '本田',     name_en: 'Honda',                   group: '汽車' },
        { symbol: '7201.T', name: '日產 Nissan',                  name_zh: '日產',     name_en: 'Nissan',                  group: '汽車' },
        { symbol: '7269.T', name: '鈴木 Suzuki',                  name_zh: '鈴木',     name_en: 'Suzuki',                  group: '汽車' },
        { symbol: '7270.T', name: '速霸陸 Subaru',                name_zh: '速霸陸',   name_en: 'Subaru',                  group: '汽車' },
        // 科技 / 電子
        { symbol: '6758.T', name: '索尼 Sony',                    name_zh: '索尼',     name_en: 'Sony',                    group: '科技/電子' },
        { symbol: '6861.T', name: '基恩士 Keyence',               name_zh: '基恩士',   name_en: 'Keyence',                 group: '科技/電子' },
        { symbol: '6501.T', name: '日立 Hitachi',                 name_zh: '日立',     name_en: 'Hitachi',                 group: '科技/電子' },
        { symbol: '6752.T', name: '松下 Panasonic',               name_zh: '松下',     name_en: 'Panasonic',               group: '科技/電子' },
        { symbol: '6702.T', name: '富士通 Fujitsu',               name_zh: '富士通',   name_en: 'Fujitsu',                 group: '科技/電子' },
        { symbol: '6723.T', name: '瑞薩電子 Renesas',             name_zh: '瑞薩電子', name_en: 'Renesas',                 group: '科技/電子' },
        // 半導體 / 設備
        { symbol: '8035.T', name: '東京威力科創 TEL',             name_zh: '東京威力科創', name_en: 'TEL',                 group: '半導體/設備' },
        { symbol: '4063.T', name: '信越化學 Shin-Etsu',           name_zh: '信越化學', name_en: 'Shin-Etsu',               group: '半導體/設備' },
        // 金融
        { symbol: '8306.T', name: '三菱UFJ銀行 MUFG',            name_zh: '三菱UFJ銀行', name_en: 'MUFG',                 group: '金融' },
        { symbol: '8316.T', name: '三井住友 SMFG',               name_zh: '三井住友', name_en: 'SMFG',                    group: '金融' },
        { symbol: '8411.T', name: '瑞穗銀行 Mizuho',             name_zh: '瑞穗銀行', name_en: 'Mizuho',                  group: '金融' },
        { symbol: '8604.T', name: '野村控股 Nomura',              name_zh: '野村控股', name_en: 'Nomura',                  group: '金融' },
        // 零售 / 消費
        { symbol: '9983.T', name: '迅銷 Fast Retailing (Uniqlo)', name_zh: '迅銷',     name_en: 'Fast Retailing (Uniqlo)', group: '零售/消費' },
        { symbol: '2914.T', name: '日本菸草 JT',                  name_zh: '日本菸草', name_en: 'JT',                      group: '零售/消費' },
        { symbol: '2802.T', name: '味之素 Ajinomoto',             name_zh: '味之素',   name_en: 'Ajinomoto',               group: '零售/消費' },
        { symbol: '2503.T', name: '麒麟 Kirin',                   name_zh: '麒麟',     name_en: 'Kirin',                   group: '零售/消費' },
        // 電信
        { symbol: '9432.T', name: 'NTT',                          name_zh: 'NTT',      name_en: 'NTT',                     group: '電信' },
        { symbol: '9433.T', name: 'KDDI',                         name_zh: 'KDDI',     name_en: 'KDDI',                    group: '電信' },
        { symbol: '9434.T', name: '軟銀 SoftBank',                name_zh: '軟銀',     name_en: 'SoftBank',                group: '電信' },
        // 醫療 / 製藥
        { symbol: '4502.T', name: '武田藥品 Takeda',              name_zh: '武田藥品', name_en: 'Takeda',                  group: '醫療/製藥' },
        // ETF
        { symbol: '1306.T', name: 'TOPIX ETF (野村)',             name_zh: 'TOPIX ETF (野村)', name_en: 'TOPIX ETF (Nomura)', group: 'ETF' },
    ],
    getStockName(item) {
        const lang = window.I18n?.getLanguage?.() || 'zh-TW';
        if (lang === 'en') return item.name_en || item.name || '';
        return item.name_zh || item.name || '';
    },

    STORAGE_KEY: 'jpstock_selected_symbols',
    DEFAULT_SELECTED: [
        '7203.T', '6758.T', '8306.T', '9983.T',
        '8035.T', '9432.T', '4502.T', '1306.T',
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

    // ── Picker ────────────────────────────────────────────────
    showPicker() {
        const listEl = document.getElementById('jpstock-list');
        if (!listEl) return;
        const selected = new Set(this.getActiveSymbols());
        const groups = {};
        this.AVAILABLE_SYMBOLS.forEach(s => {
            if (!groups[s.group]) groups[s.group] = [];
            groups[s.group].push(s);
        });
        listEl.innerHTML = `
            <div>
                <p class="text-xs text-textMuted mb-4">勾選要顯示的日股（至少 1 個）</p>
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
                                        class="jpstock-sym-check w-4 h-4 accent-primary">
                                </label>`).join('')}
                        </div>
                    </div>`).join('')}
                <div class="flex gap-2 mt-2 pb-4">
                    <button onclick="JPStockTab.renderMarket()"
                        class="flex-1 py-3 bg-surface border border-white/10 text-textMuted font-bold rounded-xl hover:bg-surfaceHighlight transition text-sm">
                        取消
                    </button>
                    <button onclick="JPStockTab._applyPicker()"
                        class="flex-1 py-3 bg-primary text-background font-bold rounded-xl hover:opacity-90 transition text-sm">
                        確認套用
                    </button>
                </div>
            </div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();
    },

    _applyPicker() {
        const checks = document.querySelectorAll('.jpstock-sym-check:checked');
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
                'jpstock',
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
        const marketEl = document.getElementById('jpstock-market-section');
        const pulseEl  = document.getElementById('jpstock-pulse-section');
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
        const listEl = document.getElementById('jpstock-list');
        if (!listEl) return;
        if (window.MarketStatus) window.MarketStatus.markSynced('jpstock');
        listEl.innerHTML = `<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">${typeof t === 'function' ? t('common.loading') : '載入中...'}</p></div>`;
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const active = this.getActiveSymbols();
            const url = `/api/jpstock/market?symbols=${active.join(',')}`;
            const data = await AppAPI.get(url);

            listEl.innerHTML = '';
            (data.stocks || []).forEach(item => {
                const isUp = item.changePercent >= 0;
                const color = isUp ? 'text-success' : 'text-danger';
                const arrow = isUp ? '▲' : '▼';
                const symbol = escapeHtml(item.symbol);
                const cardCode = symbol.replace('.T', '').slice(0, 2);
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
                                    <div class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60">${symbol} · ${item.currency || 'JPY'}</div>
                                </div>
                                <div class="text-right flex-shrink-0">
                                    <div class="text-sm font-black ${color}">${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%</div>
                                    <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold">24H</div>
                                </div>
                            </div>
                            <div class="flex items-center justify-between mt-1.5">
                                <div class="text-[11px] text-textMuted font-mono opacity-80">${item.price.toLocaleString(undefined, {maximumFractionDigits: 1})} ${item.currency || 'JPY'}</div>
                                <div class="text-xs font-bold ${color}">${arrow} ${item.change >= 0 ? '+' : ''}${item.change.toFixed(1)}</div>
                            </div>
                        </div>
                    </div>`;
                listEl.appendChild(card);
            });

            this.lastUpdatedAt = data.last_updated || new Date().toISOString();
            if (window.MarketStatus) {
                window.MarketStatus.markSynced('jpstock');
                window.MarketStatus.updateMarketStatusBar('jpstock', this.lastUpdatedAt);
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${escapeHtml(e.message)}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────
    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('jpstock-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (typeof AppUtils !== 'undefined') AppUtils.refreshIcons();

        try {
            const userProvider = await window.APIKeyManager?.getCurrentProvider();
            let url = `/api/jpstock/pulse/${encodeURIComponent(symbol)}`;
            const customHeaders = {};
            if (userProvider) {
                url += '?deep_analysis=true';
                customHeaders['X-User-LLM-Provider'] = userProvider;
            }
            const d = await AppAPI.get(url, { headers: customHeaders });

            const isUp   = d.change_24h >= 0;
            const color  = isUp ? 'text-success' : 'text-danger';
            const isDeep = d.source_mode === 'deep_analysis';
            const currency = d.currency || 'JPY';

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
                        <div class="text-3xl font-serif text-secondary font-bold">${d.current_price?.toLocaleString(undefined, {maximumFractionDigits: 1})} <span class="text-sm font-normal text-textMuted">${currency}</span></div>
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
                    <div id="jpstock-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="JPStockTab.changeInterval('${iv}')" id="jpstock-interval-${iv}"
                                    class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">
                                    ${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}
                                </button>`).join('')}
                            </div>
                        </div>
                        <div id="jpstock-chart" style="height: 200px;"></div>
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
        const chartEl = document.getElementById('jpstock-chart');
        if (!chartEl) return;
        this.destroyChart();
        try {
            const res = await AppAPI.get(`/api/jpstock/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
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
            console.warn('[JPStockTab] chart load failed:', e);
        }
    },

    changeInterval(interval) {
        this.currentInterval = interval;
        ['1d', '1wk', '1mo'].forEach(iv => {
            const btn = document.getElementById(`jpstock-interval-${iv}`);
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
            const input = document.getElementById('jpstock-add-input');
            if (input) input.value = '';
            return;
        }

        const input = document.getElementById('jpstock-add-input');
        const btn = input ? input.nextElementSibling : null;
        let originalIcon = '';
        if (btn) { originalIcon = btn.innerHTML; btn.innerHTML = '<div class="w-4 h-4 border-2 border-primary/50 border-t-primary rounded-full animate-spin"></div>'; btn.disabled = true; }

        try {
            const data = await AppAPI.get(`/api/jpstock/market?symbols=${encodeURIComponent(sym)}`);
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

window.JPStockTab = JPStockTab;
export { JPStockTab };
