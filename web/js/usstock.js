/**
 * US Stock Tab - 美股看板
 * Architecture mirrors twstock.js
 */

window.USStockTab = {
    activeSubTab: 'market',
    defaultSymbols: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC'],

    // ── Init ─────────────────────────────────────────────────────────────────

    init: function () {
        this.loadWatchlist();
        this.renderWatchlistControls();
        this.bindEvents();
        this.refreshCurrent(true);
    },

    // ── Watchlist persistence ────────────────────────────────────────────────

    loadWatchlist: function () {
        try {
            const saved = localStorage.getItem('usStockWatchlist');
            if (saved) {
                window.usStockSelectedSymbols = JSON.parse(saved);
            } else {
                window.usStockSelectedSymbols = [...this.defaultSymbols];
                this.saveWatchlist();
            }
        } catch (e) {
            console.warn('[US Stock] Error loading watchlist', e);
            window.usStockSelectedSymbols = [...this.defaultSymbols];
        }
    },

    saveWatchlist: function () {
        try {
            if (!window.usStockSelectedSymbols || window.usStockSelectedSymbols.length === 0) {
                window.usStockSelectedSymbols = [...this.defaultSymbols];
            }
            localStorage.setItem('usStockWatchlist', JSON.stringify(window.usStockSelectedSymbols));
        } catch (e) {
            console.error('[US Stock] Failed to save watchlist', e);
        }
    },

    // ── Add / Remove ─────────────────────────────────────────────────────────

    addStock: async function (symbol) {
        if (!symbol) return;
        const sym = symbol.toUpperCase().replace(/[^A-Z.^]/g, '').trim();
        if (sym.length < 1) return;

        const input = document.getElementById('usStockAddInput');
        if (window.usStockSelectedSymbols.includes(sym)) {
            if (input) input.value = '';
            if (window.showToast) window.showToast(`自選清單已存在「${sym}」`, 'info');
            return;
        }

        const btn = input ? input.nextElementSibling : null;
        let originalIcon = '';
        if (btn) {
            originalIcon = btn.innerHTML;
            btn.innerHTML = '<div class="w-4 h-4 border-2 border-primary/50 border-t-primary rounded-full animate-spin"></div>';
            btn.disabled = true;
        }

        try {
            const res = await fetch(`/api/usstock/market?symbols=${encodeURIComponent(sym)}`);
            if (!res.ok) {
                let msg = `找不到美股代號「${sym}」的交易資料`;
                try { const d = await res.json(); if (d.detail) msg = d.detail; } catch(e) {}
                throw new Error(msg);
            }
            const data = await res.json();

            if (data.stocks && data.stocks.length > 0) {
                window.usStockSelectedSymbols.unshift(sym);
                this.saveWatchlist();
                this.refreshMarketWatch();
                this.refreshMarketInfo();
                if (window.showToast) window.showToast(`已成功加入「${sym}」`, 'success');
            } else {
                if (window.showToast) {
                    window.showToast(`找不到美股代號「${sym}」的交易資料`, 'error');
                }
            }
        } catch (e) {
            console.error('[US Stock] Validation error:', e);
            if (window.showToast) window.showToast(`新增失敗：${e.message}`, 'error');
        } finally {
            if (btn) { btn.innerHTML = originalIcon; btn.disabled = false; }
            if (input) input.value = '';
        }
    },

    removeStock: function (symbol, event) {
        if (event) event.stopPropagation();
        window.usStockSelectedSymbols = window.usStockSelectedSymbols.filter(s => s !== symbol);
        this.saveWatchlist();
        this.refreshMarketWatch();
        this.refreshMarketInfo();
    },

    // ── Watchlist controls render ────────────────────────────────────────────

    renderWatchlistControls: function () {
        const container = document.getElementById('usstock-screener-controls');
        if (!container) return;

        container.innerHTML = `
            <div class="flex flex-wrap items-center justify-between gap-4 mb-4">
                <h3 class="font-bold text-secondary flex items-center gap-2">
                    <i data-lucide="star" class="w-4 h-4 text-yellow-500"></i> My US Stocks
                </h3>
                <div class="flex items-center gap-2">
                    <div class="relative">
                        <input type="text" id="usStockAddInput" placeholder="輸入美股代號 (如 AAPL)" maxlength="10"
                            oninput="this.value = this.value.replace(/[^A-Za-z.^]/g, '').toUpperCase()"
                            class="w-52 bg-background/50 border border-white/10 rounded-lg pl-3 pr-10 py-1.5 text-sm focus:outline-none focus:border-primary transition-colors text-white placeholder-textMuted/50">
                        <button onclick="window.USStockTab.addStock(document.getElementById('usStockAddInput').value)"
                            class="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-textMuted hover:text-primary transition-colors hover:bg-white/5 rounded">
                            <i data-lucide="plus" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        if (window.lucide) window.lucide.createIcons();

        const input = document.getElementById('usStockAddInput');
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') window.USStockTab.addStock(e.target.value);
            });
        }
    },

    // ── Sub-tab switching ────────────────────────────────────────────────────

    switchSubTab: function (tabId) {
        if (this.activeSubTab === tabId) return;

        const marketBtn     = document.getElementById('usstock-btn-market');
        const pulseBtn      = document.getElementById('usstock-btn-pulse');
        const marketContent = document.getElementById('usstock-market-content');
        const pulseContent  = document.getElementById('usstock-pulse-content');

        if (!marketBtn || !pulseBtn || !marketContent || !pulseContent) return;

        const active   = 'usstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background shadow-md';
        const inactive = 'usstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5';

        [marketContent, pulseContent].forEach(el => el.classList.add('hidden'));
        [marketBtn, pulseBtn].forEach(el => el.className = inactive);

        if (tabId === 'market') {
            marketBtn.className = active;
            marketContent.classList.remove('hidden');
        } else if (tabId === 'pulse') {
            pulseBtn.className = active;
            pulseContent.classList.remove('hidden');
        }

        this.activeSubTab = tabId;
        this.refreshCurrent(true);
    },

    refreshCurrent: function (isFirst = false) {
        if (this.activeSubTab === 'market') {
            this.refreshMarketWatch();
            this.refreshMarketInfo();
        } else if (this.activeSubTab === 'pulse') {
            const inputEl = document.getElementById('usstockPulseSearchInput');
            const sym = inputEl ? inputEl.value.trim() : '';
            if (sym) {
                this.refreshAIPulse(sym);
            } else {
                const container = document.getElementById('usstock-pulse-result');
                if (container) {
                    container.innerHTML = `<div class="py-20 text-center text-textMuted uppercase tracking-widest text-sm italic opacity-50 flex flex-col items-center"><i data-lucide="search" class="w-8 h-8 mb-3 opacity-50"></i>請輸入美股代號或從市場首頁點選「深度分析」</div>`;
                    container.classList.remove('hidden');
                    if (window.lucide) window.lucide.createIcons();
                }
            }
        }
    },

    // ── Market Watch ─────────────────────────────────────────────────────────

    refreshMarketWatch: async function () {
        const listContainer = document.getElementById('usstock-screener-list');
        const loader        = document.getElementById('usstock-market-loader');
        if (!listContainer || !loader) return;

        loader.classList.remove('hidden');
        listContainer.innerHTML = '';

        try {
            const syms = window.usStockSelectedSymbols || this.defaultSymbols;
            const url  = `/api/usstock/market?symbols=${encodeURIComponent(syms.join(','))}`;
            const res  = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            this._renderWatchlist(listContainer, data.stocks || []);
        } catch (err) {
            console.error('[US Stock] Market error:', err);
            listContainer.innerHTML = `<div class="p-4 text-center text-danger bg-danger/10 rounded-xl text-sm">無法載入美股數據：${err.message}</div>`;
        } finally {
            loader.classList.add('hidden');
        }
    },

    _renderWatchlist: function (container, items) {
        if (!items || items.length === 0) {
            container.innerHTML = '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">暫無市場數據</p>';
            return;
        }

        const esc = (s) => String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

        const frag = document.createDocumentFragment();
        items.forEach(item => {
            const sym      = esc(item.symbol);
            const name     = esc(item.name || sym);
            const price    = item.price != null ? `$${item.price.toFixed(2)}` : '-';
            const chg      = item.changePercent != null ? parseFloat(item.changePercent) : 0;
            const isPos    = chg > 0;
            const isNeg    = chg < 0;
            const color    = isPos ? 'text-success' : (isNeg ? 'text-danger' : 'text-textMuted');
            const sign     = isPos ? '+' : '';
            const abbr     = sym.substring(0, 2);

            const div = document.createElement('div');
            div.className = 'group bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer';
            div.onclick = () => window.USStockTab.jumpToPulse(sym);
            div.innerHTML = `
                <div class="flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-xs font-bold text-primary border border-white/5 group-hover:scale-110 transition-transform flex-shrink-0">${abbr}</div>
                        <div class="min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="font-bold text-base text-secondary truncate sm:overflow-visible" title="${name}">${name}</span>
                                <span class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60 flex-shrink-0">NASDAQ</span>
                            </div>
                            <div class="text-[11px] text-textMuted font-mono opacity-80">${price}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <div class="text-right">
                            <div class="text-base font-black ${color}">${sign}${chg.toFixed(2)}%</div>
                            <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold mt-1">24H</div>
                        </div>
                        <button onclick="window.USStockTab.showChart('${sym}', event)" class="w-8 h-8 rounded-lg flex items-center justify-center text-textMuted hover:text-primary hover:bg-primary/10 transition-colors ml-2 border border-white/5" title="View Chart">
                            <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                        </button>
                        <button onclick="window.USStockTab.removeStock('${sym}', event)" class="w-8 h-8 rounded-lg flex items-center justify-center text-textMuted hover:text-danger hover:bg-danger/10 transition-colors border border-white/5" title="Remove">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            `;
            frag.appendChild(div);
        });

        container.innerHTML = '';
        container.appendChild(frag);
        if (window.lucide) window.lucide.createIcons();
    },

    jumpToPulse: function (symbol) {
        const inputEl = document.getElementById('usstockPulseSearchInput');
        if (inputEl) inputEl.value = symbol;
        if (this.activeSubTab === 'pulse') {
            this.refreshAIPulse(symbol);
        } else {
            this.switchSubTab('pulse');
        }
    },

    // ── Market Info (indices + news) ─────────────────────────────────────────

    refreshMarketInfo: async function () {
        this.initSectionToggles();
        await Promise.all([
            this._loadIndicesSection(),
            this._loadNewsSection(),
        ]);
    },

    _showLoader: function (id, show) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('hidden', !show);
        el.classList.toggle('flex', show);
    },

    _loadIndicesSection: async function () {
        const container = document.getElementById('usstock-info-indices');
        if (!container) return;
        this._showLoader('usstock-info-indices-loader', true);
        try {
            const res = await fetch('/api/usstock/indices');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const indices = data.indices || [];
            if (!indices.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50 col-span-3">暫無指數資料</p>';
                return;
            }
            container.innerHTML = indices.map(idx => {
                const chg   = idx.change != null ? parseFloat(idx.change) : 0;
                const chgP  = idx.changePercent != null ? parseFloat(idx.changePercent) : 0;
                const color = chg >= 0 ? 'text-success' : 'text-danger';
                const arrow = chg >= 0 ? '↑' : '↓';
                return `
                <div class="relative overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-br from-surface to-background hover:border-primary/30 transition-all duration-200 group cursor-default">
                    <div class="absolute top-0 right-0 w-16 h-16 bg-primary/5 rounded-full blur-2xl group-hover:bg-primary/10 transition-all"></div>
                    <div class="relative p-4">
                        <div class="text-[10px] text-textMuted mb-2 font-bold uppercase tracking-wider">${idx.name}</div>
                        <div class="font-black text-secondary text-lg font-mono">$${idx.price != null ? idx.price.toFixed(2) : '—'}</div>
                        <div class="text-xs ${color} font-bold mt-1">${arrow} ${Math.abs(chg).toFixed(2)} (${chgP.toFixed(2)}%)</div>
                    </div>
                </div>`;
            }).join('');
        } catch (err) {
            console.error('[US Stock] Indices error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4 col-span-3">載入指數失敗：${err.message}</p>`;
        } finally {
            this._showLoader('usstock-info-indices-loader', false);
        }
    },

    _loadNewsSection: async function () {
        const container = document.getElementById('usstock-info-news');
        if (!container) return;
        this._showLoader('usstock-info-news-loader', true);
        try {
            const syms = (window.usStockSelectedSymbols || this.defaultSymbols).slice(0, 5);
            const url  = `/api/usstock/news?symbols=${encodeURIComponent(syms.join(','))}&limit=15`;
            const res  = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            const items = json.data || [];
            if (!items.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50">目前無新聞</p>';
                return;
            }
            container.innerHTML = items.map(item => {
                const pub = item.publisher ? `<span class="text-[9px] bg-yellow-500/10 text-yellow-400 px-1.5 py-0.5 rounded font-mono">${item.publisher}</span>` : '';
                return `
                <div class="bg-surface/40 border border-yellow-500/10 hover:border-yellow-500/30 rounded-xl p-3 transition-colors">
                    <div class="flex items-start gap-3">
                        <div class="flex-shrink-0 w-12 text-center">
                            <div class="text-xs font-black text-yellow-400 font-mono">${item.symbol || '—'}</div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <a href="${item.url || '#'}" target="_blank" rel="noopener noreferrer"
                               class="text-xs text-textMain leading-relaxed line-clamp-2 hover:text-primary transition-colors block">${item.title || '（無標題）'}</a>
                            <div class="flex items-center gap-2 mt-1">${pub}</div>
                        </div>
                    </div>
                </div>`;
            }).join('');
        } catch (err) {
            console.error('[US Stock] News error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4">載入新聞失敗：${err.message}</p>`;
        } finally {
            this._showLoader('usstock-info-news-loader', false);
        }
    },

    // ── Section toggles ──────────────────────────────────────────────────────

    initSectionToggles: function () {
        try {
            const prefs = JSON.parse(localStorage.getItem('usstock_section_prefs') || '{}');
            ['indices', 'news'].forEach(sec => {
                const isHidden  = prefs[sec] === false;
                const bodyEl    = document.getElementById(`usstock-section-body-${sec}`);
                const chevronEl = document.getElementById(`usstock-chevron-${sec}`);
                if (bodyEl && chevronEl) {
                    bodyEl.classList.toggle('hidden', isHidden);
                    chevronEl.classList.toggle('rotate-180', isHidden);
                }
            });
        } catch (e) { /* ignore */ }
    },

    toggleSection: function (key) {
        const bodyEl    = document.getElementById(`usstock-section-body-${key}`);
        const chevronEl = document.getElementById(`usstock-chevron-${key}`);
        if (!bodyEl || !chevronEl) return;

        const wasHidden = bodyEl.classList.contains('hidden');
        bodyEl.classList.toggle('hidden', !wasHidden);
        chevronEl.classList.toggle('rotate-180', !wasHidden);

        try {
            const prefs = JSON.parse(localStorage.getItem('usstock_section_prefs') || '{}');
            prefs[key] = wasHidden; // true = now visible
            localStorage.setItem('usstock_section_prefs', JSON.stringify(prefs));
        } catch (e) { /* ignore */ }
    },

    // ── AI Pulse ─────────────────────────────────────────────────────────────

    refreshAIPulse: async function (symbol) {
        const container = document.getElementById('usstock-pulse-result');
        const loader    = document.getElementById('usstock-pulse-loader');
        if (!container || !loader) return;

        loader.classList.remove('hidden');
        container.classList.add('hidden');

        try {
            const res = await fetch(`/api/usstock/pulse/${encodeURIComponent(symbol.toUpperCase())}`);
            if (!res.ok) {
                let msg = `HTTP ${res.status}`;
                try { const d = await res.json(); if (d.detail) msg = d.detail; } catch (e) {}
                throw new Error(msg);
            }
            const data = await res.json();
            this._renderAIPulse(container, data);
            container.classList.remove('hidden');
        } catch (err) {
            console.error('[US Stock] Pulse error:', err);
            container.innerHTML = `<div class="p-4 text-center text-danger bg-danger/10 rounded-xl text-sm">無法載入「${symbol}」的脈動分析：${err.message}</div>`;
            container.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
        }
    },

    _renderAIPulse: function (container, data) {
        const rep  = data.report || {};
        const tech = data.technical_indicators || {};
        const fund = data.fundamentals || {};
        const chg  = data.change_24h || 0;
        const isPos = chg > 0;
        const isNeg = chg < 0;
        const color = isPos ? 'text-success' : (isNeg ? 'text-danger' : 'text-textMuted');
        const bg    = isPos ? 'bg-success/10' : (isNeg ? 'bg-danger/10' : 'bg-white/5');
        const sign  = isPos ? '+' : '';
        const icon  = isPos ? 'trending-up' : (isNeg ? 'trending-down' : 'minus');

        // ── Helpers ────────────────────────────────────────────────────────
        const fv = (v, d = 2) => (v != null && !isNaN(Number(v))) ? Number(v).toFixed(d) : 'N/A';
        const fmtPct = (v, d = 1) => (v != null && !isNaN(Number(v))) ? (Number(v) * 100).toFixed(d) + '%' : 'N/A';
        const fmtPctDirect = (v, d = 2) => (v != null && !isNaN(Number(v))) ? Number(v).toFixed(d) + '%' : 'N/A';
        const fmtLarge = (v) => {
            if (!v || isNaN(v)) return 'N/A';
            if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T';
            if (v >= 1e9)  return '$' + (v / 1e9).toFixed(2) + 'B';
            if (v >= 1e6)  return '$' + (v / 1e6).toFixed(1) + 'M';
            return '$' + Number(v).toLocaleString();
        };

        // RSI
        const rsiVal  = tech.rsi;
        const rsiSig  = tech.rsi_signal || '';
        const rsiColor = rsiSig === 'oversold' ? 'text-success' : rsiSig === 'overbought' ? 'text-danger' : 'text-secondary';
        const rsiLabelMap = { oversold: ['超賣', 'bg-success/20 text-success'], overbought: ['超買', 'bg-danger/20 text-danger'], neutral: ['中性', 'bg-white/10 text-textMuted'] };
        const [rsiLabelTxt, rsiLabelStyle] = rsiLabelMap[rsiSig] || ['', ''];

        // MACD
        const macdTrend = tech.macd_trend || '';
        const macdHistColor = macdTrend === 'bullish' ? 'text-success' : macdTrend === 'bearish' ? 'text-danger' : 'text-textMuted';

        // MA position
        const close = data.current_price || 0;
        const maPosBadge = (v) => {
            if (!v || !close) return '';
            return close >= v
                ? '<span class="text-[9px] ml-1 px-1 rounded bg-success/20 text-success">上方</span>'
                : '<span class="text-[9px] ml-1 px-1 rounded bg-danger/20 text-danger">下方</span>';
        };

        // Bollinger Bands signal
        const bbSig = tech.bb_signal || '';
        const bbSigMap = { overbought: ['突破上軌', 'text-danger'], oversold: ['跌破下軌', 'text-success'], neutral: ['帶內', 'text-textMuted'] };
        const [bbLbl, bbLblColor] = bbSigMap[bbSig] || ['N/A', 'text-textMuted'];

        // Volume signal
        const volSig = tech.vol_signal || '';
        const volSigMap = { high: ['放量', 'text-success'], low: ['縮量', 'text-danger'], normal: ['正常', 'text-textMuted'] };
        const [volLbl, volLblColor] = volSigMap[volSig] || ['N/A', 'text-textMuted'];

        // Overall signal badge
        const overallSig = tech.summary_en || '';
        const overallMap = { Bullish: ['Bullish', 'bg-success/20 text-success border-success/30'], Bearish: ['Bearish', 'bg-danger/20 text-danger border-danger/30'], Neutral: ['Neutral', 'bg-white/10 text-textMuted border-white/10'] };
        const [overallLbl, overallStyle] = overallMap[overallSig] || ['—', 'bg-white/10 text-textMuted border-white/10'];

        // Analyst recommendation
        const recRaw = (fund.analyst_recommendation || '').toLowerCase();
        const recMap = { buy: ['買入', 'bg-success/20 text-success'], 'strong buy': ['強力買入', 'bg-success/30 text-success'], hold: ['持有', 'bg-yellow-500/20 text-yellow-400'], sell: ['賣出', 'bg-danger/20 text-danger'], 'strong sell': ['強力賣出', 'bg-danger/30 text-danger'] };
        const [recLbl, recStyle] = recMap[recRaw] || (recRaw ? [recRaw, 'bg-white/10 text-textMuted'] : ['N/A', 'bg-white/10 text-textMuted']);

        // 52W progress bar
        const low52  = fund['52_week_low'];
        const high52 = fund['52_week_high'];
        let w52Html  = '<div class="text-xs text-textMuted">N/A</div>';
        if (low52 && high52 && close && high52 > low52) {
            const pct = Math.min(100, Math.max(0, ((close - low52) / (high52 - low52)) * 100));
            w52Html = `
                <div class="flex justify-between text-[9px] text-textMuted mb-1">
                    <span>低 $${fv(low52)}</span><span>現價 ${pct.toFixed(0)}%</span><span>高 $${fv(high52)}</span>
                </div>
                <div class="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-danger via-yellow-500 to-success" style="width:${pct}%"></div>
                </div>`;
        }

        const html = `
            <!-- Hero -->
            <div class="relative overflow-hidden bg-surface/80 backdrop-blur-xl rounded-3xl p-6 mb-6 border border-white/10 shadow-2xl shadow-black/20">
                <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/20 rounded-full blur-3xl opacity-50"></div>
                ${isPos ? '<div class="absolute -bottom-24 -left-24 w-48 h-48 bg-success/10 rounded-full blur-3xl opacity-50"></div>' : ''}
                ${isNeg ? '<div class="absolute -bottom-24 -left-24 w-48 h-48 bg-danger/10 rounded-full blur-3xl opacity-50"></div>' : ''}
                <div class="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div class="flex items-center gap-5">
                        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/20 flex items-center justify-center shadow-inner">
                            <i data-lucide="building-2" class="w-8 h-8 text-primary"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-2 mb-1">
                                <h2 class="text-xl md:text-2xl font-serif text-secondary font-bold">${data.company_name}</h2>
                                <span class="px-2 py-0.5 rounded text-xs font-bold tracking-wider uppercase bg-white/10 text-white border border-white/10">${data.symbol}</span>
                            </div>
                            <div class="text-xs text-textMuted flex items-center gap-2">
                                <i data-lucide="map-pin" class="w-3 h-3"></i> US Stock Exchange
                                ${fund.sector ? `<span class="text-textMuted/60">· ${fund.sector}</span>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="mt-2 md:mt-0 ml-20 md:ml-0 flex flex-col items-start md:items-end">
                        <div class="text-[10px] text-textMuted uppercase tracking-[0.2em] mb-1 font-bold">Current Price</div>
                        <div class="text-4xl font-mono font-black text-secondary tracking-tight mb-2 flex items-center gap-2">
                            <span class="text-xl text-primary font-serif font-medium">$</span>${data.current_price}
                        </div>
                        <div class="inline-flex items-center gap-1.5 text-sm font-bold ${color} ${bg} px-3 py-1 rounded-lg border border-white/5 backdrop-blur-md shadow-sm">
                            <i data-lucide="${icon}" class="w-4 h-4"></i>
                            <span>${sign}${chg}% (24h)</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AI Summary + News -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                <div class="lg:col-span-2">
                    <div class="bg-surface/60 backdrop-blur-md border border-primary/20 rounded-2xl p-6 shadow-lg relative overflow-hidden h-full">
                        <div class="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-primary via-accent to-primary"></div>
                        <h3 class="font-serif text-lg text-primary mb-4 flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                <i data-lucide="brain-circuit" class="w-4 h-4 text-primary"></i>
                            </div>
                            Pulse AI Intelligence Summary
                        </h3>
                        <p class="text-textMain text-sm leading-relaxed whitespace-pre-line ml-11">${rep.summary || ''}</p>
                    </div>
                </div>
                <div>
                    ${rep.highlights && rep.highlights.length > 0 ? `
                        <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6 h-full">
                            <h3 class="font-bold text-secondary mb-4 flex items-center gap-2 text-sm uppercase tracking-wider">
                                <i data-lucide="rss" class="w-4 h-4 text-yellow-500"></i> Market Sentiments
                            </h3>
                            <div class="space-y-3">
                                ${rep.highlights.map(h => `
                                    <a href="${h.url || '#'}" target="_blank" rel="noopener noreferrer"
                                       class="block bg-surfaceHighlight p-3 rounded-lg border border-white/5 hover:border-white/20 transition-colors">
                                        <p class="text-xs text-textMain leading-relaxed line-clamp-3 hover:text-primary transition-colors">${h.title || ''}</p>
                                    </a>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Section A: Technical Analysis -->
            <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6 mb-6">
                <div class="flex items-center justify-between mb-5">
                    <h3 class="font-bold text-secondary flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="activity" class="w-4 h-4 text-accent"></i> Technical Analysis
                    </h3>
                    <span class="text-xs font-bold px-3 py-1 rounded-full border ${overallStyle}">${overallLbl}</span>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <!-- RSI -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">RSI (14)</div>
                        <div class="flex items-end justify-between mb-2">
                            <span class="text-2xl font-black font-mono ${rsiColor}">${rsiVal != null ? Number(rsiVal).toFixed(1) : 'N/A'}</span>
                            ${rsiLabelTxt ? `<span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${rsiLabelStyle}">${rsiLabelTxt}</span>` : ''}
                        </div>
                        ${rsiVal != null ? `<div class="h-1.5 rounded-full bg-white/10 overflow-hidden"><div class="h-full rounded-full" style="width:${Math.min(100,Number(rsiVal))}%;background:${Number(rsiVal)<30?'#86efac':Number(rsiVal)>70?'#fda4af':'#a1a1aa'}"></div></div>` : ''}
                    </div>
                    <!-- MACD -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">MACD (12/26/9)</div>
                        <div class="space-y-1.5">
                            <div class="flex justify-between text-xs"><span class="text-textMuted">MACD</span><span class="font-mono text-secondary">${fv(tech.macd, 3)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">Signal</span><span class="font-mono text-secondary">${fv(tech.macd_signal, 3)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">Histogram</span><span class="font-bold font-mono ${macdHistColor}">${fv(tech.macd_histogram, 3)}</span></div>
                        </div>
                    </div>
                    <!-- Moving Averages -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">移動平均線</div>
                        <div class="space-y-1.5">
                            ${[['MA20', tech.ma_20], ['MA50', tech.ma_50], ['MA200', tech.ma_200]].map(([l,v]) =>
                                `<div class="flex justify-between text-xs items-center"><span class="text-textMuted">${l}</span><span class="font-mono text-secondary">$${fv(v)}${v ? maPosBadge(v) : ''}</span></div>`
                            ).join('')}
                        </div>
                    </div>
                    <!-- Bollinger Bands -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">布林帶 (BB20)</div>
                        <div class="space-y-1.5">
                            <div class="flex justify-between text-xs"><span class="text-textMuted">上軌</span><span class="font-mono text-secondary">$${fv(tech.bb_upper)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">中軌</span><span class="font-mono text-secondary">$${fv(tech.bb_middle)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">下軌</span><span class="font-mono text-secondary">$${fv(tech.bb_lower)}</span></div>
                        </div>
                        <div class="mt-2 text-[10px] font-bold ${bbLblColor}">${bbLbl}</div>
                    </div>
                    <!-- Volume -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">成交量</div>
                        <div class="space-y-1.5">
                            <div class="flex justify-between text-xs"><span class="text-textMuted">今日量</span><span class="font-mono text-secondary">${tech.volume ? Number(tech.volume).toLocaleString() : 'N/A'}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">20日均量</span><span class="font-mono text-secondary">${tech.vol_ma20 ? Number(tech.vol_ma20).toLocaleString() : 'N/A'}</span></div>
                        </div>
                        <div class="mt-2 text-[10px] font-bold ${volLblColor}">${volLbl}</div>
                    </div>
                </div>
            </div>

            <!-- Section B + C: Fundamentals + Analyst -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Section B: Fundamentals -->
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="bar-chart-2" class="w-4 h-4 text-primary"></i> Fundamental Analysis
                    </h3>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">P/E (TTM)</div><div class="font-bold font-mono text-secondary">${fv(fund.pe_ratio)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">Forward P/E</div><div class="font-bold font-mono text-secondary">${fv(fund.forward_pe)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">P/B</div><div class="font-bold font-mono text-secondary">${fv(fund.price_to_book)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">EPS (TTM)</div><div class="font-bold font-mono text-secondary">$${fv(fund.eps)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">殖利率</div><div class="font-bold font-mono ${fund.dividend_yield > 0.02 ? 'text-success' : 'text-secondary'}">${fmtPct(fund.dividend_yield)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">Beta</div><div class="font-bold font-mono text-secondary">${fv(fund.beta)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">ROE</div><div class="font-bold font-mono text-secondary">${fmtPct(fund.roe)}</div></div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5"><div class="text-[9px] text-textMuted uppercase mb-1">利潤率</div><div class="font-bold font-mono text-secondary">${fmtPct(fund.profit_margin)}</div></div>
                    </div>
                    <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                        <div class="text-[9px] text-textMuted uppercase mb-2">52 週高低點</div>
                        ${w52Html}
                    </div>
                </div>

                <!-- Section C: Analyst Consensus -->
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="telescope" class="w-4 h-4 text-accent"></i> Analyst Consensus
                    </h3>
                    <div class="flex items-center gap-3 mb-5 p-4 bg-background/60 rounded-xl border border-white/5">
                        <span class="text-sm font-bold px-3 py-1 rounded-lg ${recStyle}">${recLbl}</span>
                        <div>
                            <div class="text-[10px] text-textMuted">目標價</div>
                            <div class="font-bold font-mono text-secondary">${fund.analyst_target_price != null ? '$' + fv(fund.analyst_target_price) : 'N/A'}</div>
                        </div>
                    </div>
                    <div class="space-y-0">
                        <div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">評估機構數</span><span class="text-xs font-mono text-secondary">${fund.analyst_num_ratings || 'N/A'}</span></div>
                        <div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">營收成長</span><span class="text-xs font-bold font-mono ${fund.revenue_growth > 0 ? 'text-success' : fund.revenue_growth < 0 ? 'text-danger' : 'text-textMuted'}">${fmtPct(fund.revenue_growth)}</span></div>
                        <div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">獲利成長</span><span class="text-xs font-bold font-mono ${fund.earnings_growth > 0 ? 'text-success' : fund.earnings_growth < 0 ? 'text-danger' : 'text-textMuted'}">${fmtPct(fund.earnings_growth)}</span></div>
                        <div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">負債/股東權益</span><span class="text-xs font-mono text-secondary">${fv(fund.debt_to_equity)}</span></div>
                        <div class="flex justify-between py-2"><span class="text-xs text-textMuted">市值</span><span class="text-xs font-mono text-secondary">${fmtLarge(fund.enterprise_value || fund.market_cap)}</span></div>
                    </div>
                    ${fund.industry ? `<div class="mt-4 pt-3 border-t border-white/10 text-[10px] text-textMuted flex items-center gap-1"><i data-lucide="building" class="w-3 h-3"></i> ${fund.industry}</div>` : ''}
                </div>
            </div>
        `;

        container.innerHTML = html;
        if (window.lucide) window.lucide.createIcons();
    },

    // ── Chart ─────────────────────────────────────────────────────────────────

    _chart: null,
    _candleSeries: null,
    _volumeSeries: null,
    _chartSymbol: null,
    _chartInterval: '1d',

    showChart: async function (symbol, event) {
        if (event) event.stopPropagation();

        const section   = document.getElementById('usstock-chart-section');
        const chartEl   = document.getElementById('usstock-chart-container');
        const volumeEl  = document.getElementById('usstock-volume-container');
        const titleEl   = document.getElementById('usstock-chart-title');

        if (!section || !chartEl || typeof LightweightCharts === 'undefined') {
            console.error('[US Stock] Chart elements or LightweightCharts missing');
            return;
        }

        this._chartSymbol = symbol;
        section.classList.remove('hidden');
        if (titleEl) titleEl.textContent = `${symbol} (${this._chartInterval.toUpperCase()})`;
        if (window.lucide) window.lucide.createIcons();

        document.querySelectorAll('.us-chart-interval-btn').forEach(btn => {
            const active = btn.dataset.interval === this._chartInterval;
            btn.classList.toggle('bg-white/10', active);
            btn.classList.toggle('text-primary', active);
            btn.classList.toggle('text-textMuted', !active);
        });

        chartEl.innerHTML = '<div class="animate-pulse text-textMuted h-full flex items-center justify-center">載入歷史數據中...</div>';
        if (volumeEl) { volumeEl.innerHTML = ''; volumeEl.style.display = 'none'; }

        try {
            const res = await fetch(`/api/usstock/klines/${encodeURIComponent(symbol)}?interval=${this._chartInterval}&limit=200`);
            if (!res.ok) { const d = await res.json().catch(()=>{}); throw new Error(d?.detail || `HTTP ${res.status}`); }
            const responseData = await res.json();
            const klineData    = responseData.data || [];

            if (!klineData.length) {
                chartEl.innerHTML = '<div class="text-danger h-full flex items-center justify-center">無法載入數據</div>';
                return;
            }

            const updatedEl = document.getElementById('usstock-chart-updated');
            if (updatedEl) updatedEl.textContent = `載入時間: ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}`;

            chartEl.innerHTML = '';
            if (this._chart) { this._chart.remove(); this._chart = null; }

            this._chart = LightweightCharts.createChart(chartEl, {
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#A0AEC0' },
                grid: { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
                timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true, rightOffset: 5 },
                handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
                handleScale: { mouseWheel: true, pinchScale: true, axisPressedMouseMove: { time: true, price: false } },
            });

            this._chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 }, borderVisible: false });

            this._candleSeries = this._chart.addCandlestickSeries({
                upColor: '#10B981', downColor: '#EF4444', borderVisible: false, wickUpColor: '#10B981', wickDownColor: '#EF4444'
            });
            this._volumeSeries = this._chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol' });

            const candles = klineData.map(k => ({ time: k.time, open: k.open, high: k.high, low: k.low, close: k.close }));
            const volumes = klineData.map(k => ({ time: k.time, value: k.volume, color: k.close >= k.open ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)' }));

            this._candleSeries.setData(candles);
            this._volumeSeries.setData(volumes);
            this._chart.timeScale().fitContent();

            // OHLCV hover
            const fmtVol = v => { if (v>=1e9) return (v/1e9).toFixed(2)+'B'; if (v>=1e6) return (v/1e6).toFixed(2)+'M'; if (v>=1e3) return (v/1e3).toFixed(2)+'K'; return v.toFixed(0); };
            const setHover = (c, v) => {
                if (!c) return;
                const setEl = (id, txt, cls) => { const el = document.getElementById(id); if (el) { el.textContent = txt; if (cls) el.className = cls + ' ml-0.5'; } };
                setEl('us-info-open',   c.open.toFixed(2));
                setEl('us-info-high',   c.high.toFixed(2));
                setEl('us-info-low',    c.low.toFixed(2));
                setEl('us-info-close',  c.close.toFixed(2), c.close >= c.open ? 'text-success' : 'text-danger');
                if (v) setEl('us-info-volume', fmtVol(typeof v === 'object' ? v.value : v));
            };
            if (candles.length) setHover(candles[candles.length-1], volumes[volumes.length-1]);

            this._chart.subscribeCrosshairMove(param => {
                if (!param.time || param.point?.x < 0) { if (candles.length) setHover(candles[candles.length-1], volumes[volumes.length-1]); return; }
                const c = param.seriesData.get(this._candleSeries);
                const v = param.seriesData.get(this._volumeSeries);
                if (c) setHover(c, v);
            });

            const onResize = () => { if (!section.classList.contains('hidden') && this._chart) this._chart.applyOptions({ width: chartEl.clientWidth }); };
            window.removeEventListener('resize', this._onChartResize);
            this._onChartResize = onResize;
            window.addEventListener('resize', onResize);
            setTimeout(onResize, 50);

        } catch (err) {
            console.error('[US Stock] Chart error:', err);
            chartEl.innerHTML = `<div class="text-danger h-full flex flex-col items-center justify-center text-sm p-4 text-center"><i data-lucide="alert-triangle" class="w-8 h-8 mb-2"></i>讀取失敗：${err.message}</div>`;
            if (window.lucide) window.lucide.createIcons();
        }
    },

    closeChart: function () {
        window.removeEventListener('resize', this._onChartResize);
        this._onChartResize = null;
        const section = document.getElementById('usstock-chart-section');
        if (section) section.classList.add('hidden');
        if (this._chart) { this._chart.remove(); this._chart = null; }
        this._chartSymbol = null;
    },

    changeChartInterval: function (interval) {
        if (!this._chartSymbol || this._chartInterval === interval) return;
        this._chartInterval = interval;
        this.showChart(this._chartSymbol);
    },

    // ── Events ────────────────────────────────────────────────────────────────

    bindEvents: function () {
        const btn   = document.getElementById('usstockPulseSearchBtn');
        const input = document.getElementById('usstockPulseSearchInput');
        if (btn && input && !btn.dataset.bound) {
            btn.dataset.bound = 'true';
            btn.addEventListener('click', () => { const s = input.value.trim(); if (s) this.refreshAIPulse(s); });
            input.addEventListener('keypress', (e) => { if (e.key === 'Enter') { const s = input.value.trim(); if (s) this.refreshAIPulse(s); } });
        }
    },
};
