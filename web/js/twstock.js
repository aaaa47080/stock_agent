/**
 * TW Stock Module
 *
 * Handles the logic and rendering for the top-level "TW Stock" navigation tab.
 * Includes sub-tab switching between "Market Watch" and "AI Pulse".
 */

window.TWStockTab = {
    activeSubTab: 'market', // 'market' | 'pulse'
    defaultSymbols: ['2330', '2317', '2454', '2308', '2881', '2412', '2882', '2891', '1301', '2002'],

    initTwStock: function () {
        this.loadTwStockSelection();
        this.renderWatchlistControls();
        this.bindEvents();
        this.refreshCurrent(true);
    },

    loadTwStockSelection: function () {
        try {
            const saved = localStorage.getItem('twStockWatchlist');
            if (saved) {
                window.twStockSelectedSymbols = JSON.parse(saved);
            } else {
                window.twStockSelectedSymbols = [...this.defaultSymbols];
                this.saveTwStockSelection();
            }
        } catch (e) {
            console.warn('[TW Stock] Error loading watchlist from localStorage', e);
            window.twStockSelectedSymbols = [...this.defaultSymbols];
        }
    },

    saveTwStockSelection: function () {
        try {
            if (!window.twStockSelectedSymbols || window.twStockSelectedSymbols.length === 0) {
                window.twStockSelectedSymbols = [...this.defaultSymbols];
            }
            localStorage.setItem('twStockWatchlist', JSON.stringify(window.twStockSelectedSymbols));
        } catch (e) {
            console.error('[TW Stock] Failed to save watchlist', e);
        }
    },

    addTwStock: async function (symbol) {
        if (!symbol) return;
        const sym = symbol.toUpperCase().trim();
        if (sym.length < 2) return;

        const input = document.getElementById('twStockAddInput');
        if (window.twStockSelectedSymbols.includes(sym)) {
            if (input) input.value = '';
            if (window.showToast) window.showToast(`自選清單已存在「${sym}」`, 'info');
            return;
        }

        // Show loading state on button
        const btn = input ? input.nextElementSibling : null;
        let originalIcon = '';
        if (btn) {
            originalIcon = btn.innerHTML;
            btn.innerHTML = '<div class="w-4 h-4 border-2 border-primary/50 border-t-primary rounded-full animate-spin"></div>';
            btn.disabled = true;
        }

        try {
            // Validate symbol with backend
            const authHeaders = typeof _getAuthHeaders === 'function' ? await _getAuthHeaders() : {};
            const res = await fetch(`/api/twstock/market?symbols=${encodeURIComponent(sym)}`, { headers: authHeaders });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            if (data.top_performers && data.top_performers.length > 0) {
                // Symbol valid! Add to watchlist
                window.twStockSelectedSymbols.unshift(sym);
                this.saveTwStockSelection();
                this.refreshMarketWatch();
                this.refreshMarketInfo(); // Update News, Dividend, PE
                if (window.showToast) window.showToast(`已成功加入「${sym}」`, 'success');
            } else {
                // Invalid symbol or no data returned
                if (window.showToast) {
                    window.showToast(`找不到台股代號「${sym}」的交易資料，或該股票已下市。`, 'error');
                } else {
                    alert(`找不到台股代號「${sym}」。`);
                }
            }
        } catch (e) {
            console.error('[TW Stock] Validation error:', e);
            if (window.showToast) window.showToast(`新增失敗：無法連線驗證代號`, 'error');
        } finally {
            // Restore UI state
            if (btn) {
                btn.innerHTML = originalIcon;
                btn.disabled = false;
            }
            if (input) input.value = '';
        }
    },

    removeTwStock: function (symbol, event) {
        if (event) {
            event.stopPropagation(); // prevent jumping to pulse
        }
        window.twStockSelectedSymbols = window.twStockSelectedSymbols.filter(s => s !== symbol);
        this.saveTwStockSelection();
        this.refreshMarketWatch();
        this.refreshMarketInfo(); // Update News, Dividend, PE
    },

    renderWatchlistControls: function () {
        const controlsContainer = document.getElementById('twstock-screener-controls');
        if (!controlsContainer) return;

        controlsContainer.innerHTML = `
            <div class="flex items-center gap-2 mb-4">
                <h3 class="font-bold text-secondary flex items-center gap-2 flex-shrink-0">
                    <i data-lucide="star" class="w-4 h-4 text-yellow-500"></i> My TW Stocks
                </h3>
                <div class="flex-1 min-w-0">
                    <div class="relative">
                        <input type="text" id="twStockAddInput" placeholder="輸入台股代號 (如 2330)" maxlength="6"
                            oninput="this.value = this.value.replace(/[^0-9A-Za-z]/g, '').toUpperCase()"
                            class="w-full bg-background/50 border border-white/10 rounded-lg pl-3 pr-10 py-1.5 text-sm focus:outline-none focus:border-primary transition-colors text-white placeholder-textMuted/50">
                        <button onclick="window.TWStockTab.addTwStock(document.getElementById('twStockAddInput').value)" class="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-textMuted hover:text-primary transition-colors hover:bg-white/5 rounded">
                            <i data-lucide="plus" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        if (window.lucide) window.lucide.createIcons();

        // Add enter key support
        const input = document.getElementById('twStockAddInput');
        if (input) {
            input.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    window.TWStockTab.addTwStock(e.target.value);
                }
            });
        }
    },

    switchSubTab: function (tabId) {
        if (this.activeSubTab === tabId) return;

        console.log(`[TW Stock] Switching sub-tab to: ${tabId}`);

        // Update button states
        const marketBtn = document.getElementById('twstock-btn-market');
        const pulseBtn = document.getElementById('twstock-btn-pulse');
        const marketContent = document.getElementById('twstock-market-content');
        const pulseContent = document.getElementById('twstock-pulse-content');

        if (!marketBtn || !pulseBtn || !marketContent || !pulseContent) {
            console.error('[TW Stock] Cannot find DOM elements for tab switching.');
            return;
        }

        const activeClass = "twstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background shadow-md";
        const inactiveClass = "twstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5";

        // Hide all content panes
        [marketContent, pulseContent].forEach(el => el && el.classList.add('hidden'));
        [marketBtn, pulseBtn].forEach(el => el && (el.className = inactiveClass));

        if (tabId === 'market') {
            marketBtn.className = activeClass;
            marketContent.classList.remove('hidden');
        } else if (tabId === 'pulse') {
            pulseBtn.className = activeClass;
            pulseContent.classList.remove('hidden');
        }

        this.activeSubTab = tabId;

        // Fetch new data for the active tab
        this.refreshCurrent(true);
    },

    refreshCurrent: function (isFirstLoadForTab = false) {
        if (this.activeSubTab === 'market') {
            this.refreshMarketWatch();
            // Also load TWSE market info below the watchlist
            this.refreshMarketInfo();
        } else if (this.activeSubTab === 'pulse') {
            // Check if there's a selected symbol in the UI
            const inputEl = document.getElementById('twstockPulseSearchInput');
            const symbol = inputEl ? inputEl.value.trim() : '';
            if (symbol) {
                this.refreshAIPulse(symbol);
            } else {
                // Ignore empty symbol and show a prompt
                const pulseContainer = document.getElementById('twstock-pulse-result');
                if (pulseContainer) {
                    pulseContainer.innerHTML = `<div class="py-20 text-center text-textMuted uppercase tracking-widest text-sm italic opacity-50 flex flex-col items-center"><i data-lucide="search" class="w-8 h-8 mb-3 opacity-50"></i>請輸入台股代號或從市場首頁點選「深度分析」</div>`;
                    pulseContainer.classList.remove('hidden');
                    if (window.lucide) window.lucide.createIcons();
                }
            }
        }
    },

    refreshMarketWatch: async function () {
        const listContainer = document.getElementById('twstock-screener-list');
        const loader = document.getElementById('twstock-market-loader');

        if (!listContainer || !loader) return;

        loader.classList.remove('hidden');
        listContainer.innerHTML = '';

        try {
            const authHeaders = typeof _getAuthHeaders === 'function' ? await _getAuthHeaders() : {};
            let url = '/api/twstock/market';

            // Append symbols if we have a watchlist
            if (window.twStockSelectedSymbols && window.twStockSelectedSymbols.length > 0) {
                url += `?symbols=${encodeURIComponent(window.twStockSelectedSymbols.join(','))}`;
            }

            const response = await fetch(url, {
                headers: authHeaders
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            const topPerformers = data.top_performers || [];

            this.renderMarketList(listContainer, topPerformers);
        } catch (error) {
            console.error('[TW Stock] Market API Error:', error);
            listContainer.innerHTML = `<div class="p-4 text-center text-danger bg-danger/10 rounded-xl text-sm">無法載入台股市場數據：${error.message}</div>`;
        } finally {
            loader.classList.add('hidden');
        }
    },

    renderMarketList: function (container, items) {
        if (!items || items.length === 0) {
            container.innerHTML = '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">暫無市場數據</p>';
            return;
        }

        // Helper to escape HTML to prevent XSS
        const escapeHtml = (unsafe) => {
            if (!unsafe) return '';
            return String(unsafe)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };

        const fragment = document.createDocumentFragment();
        items.forEach(item => {
            const sym = escapeHtml(item.Symbol || 'N/A');
            const name = escapeHtml(item.Name || sym);
            const exchange = escapeHtml(item.Exchange || '台股');
            const price = item.Close ? parseFloat(item.Close).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-';
            const change = item.price_change_24h ? parseFloat(item.price_change_24h) : 0;
            const isPos = change > 0;
            const isNeg = change < 0;
            const colorClass = isPos ? 'text-success' : (isNeg ? 'text-danger' : 'text-textMuted');
            const sign = isPos ? '+' : '';

            const div = document.createElement('div');
            div.className = 'group bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer';
            div.onclick = () => window.TWStockTab.jumpToPulse(sym);
            div.innerHTML = `
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-xs font-bold text-primary border border-white/5 group-hover:scale-110 transition-transform flex-shrink-0 mt-0.5">${sym.substring(0, 2)}</div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0">
                                <div class="font-bold text-sm text-secondary leading-tight">${name}</div>
                                <div class="text-[9px] text-textMuted font-bold tracking-wider uppercase opacity-60">${exchange}</div>
                            </div>
                            <div class="text-right flex-shrink-0">
                                <div class="text-sm font-black ${colorClass}">${sign}${change.toFixed(2)}%</div>
                                <div class="text-[9px] text-textMuted uppercase opacity-40 font-bold">24H</div>
                            </div>
                        </div>
                        <div class="flex items-center justify-between mt-1.5">
                            <div class="text-[11px] text-textMuted font-mono opacity-80">NT$${price}</div>
                            <div class="flex items-center gap-1">
                                <button onclick="window.TWStockTab.showTwChart('${sym}', event)" class="w-7 h-7 rounded-lg flex items-center justify-center text-textMuted hover:text-primary hover:bg-primary/10 transition-colors border border-white/5" title="View Chart">
                                    <i data-lucide="bar-chart-2" class="w-3.5 h-3.5"></i>
                                </button>
                                <button onclick="openAlertModal('${sym}', 'tw_stock'); event.stopPropagation();" class="w-7 h-7 rounded-lg flex items-center justify-center text-yellow-400 hover:text-yellow-300 hover:bg-yellow-400/10 transition-colors border border-white/5" title="設定價格警報"><span class="text-xs leading-none">🔔</span></button>
                                <button onclick="window.TWStockTab.removeTwStock('${sym}', event)" class="w-7 h-7 rounded-lg flex items-center justify-center text-textMuted hover:text-danger hover:bg-danger/10 transition-colors border border-white/5" title="Remove from Watchlist">
                                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            fragment.appendChild(div);
        });

        container.innerHTML = '';
        container.appendChild(fragment);
        if (window.lucide) window.lucide.createIcons();
    },

    refreshAIPulse: async function (symbol) {
        const pulseContainer = document.getElementById('twstock-pulse-result');
        const loader = document.getElementById('twstock-pulse-loader');

        if (!pulseContainer || !loader) return;

        loader.classList.remove('hidden');
        pulseContainer.classList.add('hidden');

        try {
            const authHeaders = typeof _getAuthHeaders === 'function' ? await _getAuthHeaders() : {};
            const response = await fetch(`/api/twstock/pulse/${encodeURIComponent(symbol)}`, {
                headers: authHeaders
            });

            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try {
                    const errData = await response.json();
                    if (errData.detail) errorMsg = errData.detail;
                } catch (e) { }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            this.renderAIPulse(pulseContainer, data);
            pulseContainer.classList.remove('hidden');

            const titleEl = document.getElementById('twstock-pulse-title');
            if (titleEl) titleEl.textContent = `Taiwan Stock AI Pulse: ${data.company_name || symbol}`;

        } catch (error) {
            console.error('[TW Stock] Pulse API Error:', error);
            pulseContainer.innerHTML = `<div class="p-4 text-center text-danger bg-danger/10 rounded-xl text-sm">無法載入「${symbol}」的脈動分析：${error.message}</div>`;
            pulseContainer.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
        }
    },

    renderAIPulse: function (container, data) {
        const rep  = data.report || {};
        const tech = data.technical_indicators || {};
        const fund = data.fundamentals || {};
        const inst = data.institutional || {};

        const isPos = data.change_24h > 0;
        const isNeg = data.change_24h < 0;
        const colorClass = isPos ? 'text-success' : (isNeg ? 'text-danger' : 'text-textMuted');
        const bgClass    = isPos ? 'bg-success/10' : (isNeg ? 'bg-danger/10' : 'bg-white/5');
        const sign       = isPos ? '+' : '';
        const icon       = isPos ? 'trending-up' : (isNeg ? 'trending-down' : 'minus');

        // ── Helpers ────────────────────────────────────────────────────────
        const fv = (v, d = 2) => (v != null && !isNaN(Number(v))) ? Number(v).toFixed(d) : 'N/A';
        const fvPct = (v, d = 1) => (v != null && !isNaN(Number(v))) ? Number(v).toFixed(d) + '%' : 'N/A';
        const fmtMktCap = (v) => {
            if (!v || isNaN(v)) return 'N/A';
            if (v >= 1e12) return (v / 1e12).toFixed(2) + ' 兆';
            if (v >= 1e8)  return (v / 1e8).toFixed(1) + ' 億';
            return Number(v).toLocaleString();
        };
        const parseInst = (v) => {
            if (!v || v === 'N/A' || v === '') return null;
            const n = parseInt(String(v).replace(/,/g, ''), 10);
            return isNaN(n) ? null : n;
        };
        const instRow = (label, raw) => {
            const n = parseInst(raw);
            if (n === null) return `<div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0"><span class="text-xs text-textMuted">${label}</span><span class="text-xs text-textMuted font-mono">N/A</span></div>`;
            const c  = n > 0 ? 'text-success' : 'text-danger';
            const ic = n > 0 ? 'arrow-up' : 'arrow-down';
            return `<div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0"><span class="text-xs text-textMuted">${label}</span><span class="text-xs font-bold font-mono ${c} flex items-center gap-1"><i data-lucide="${ic}" class="w-3 h-3"></i>${n > 0 ? '+' : ''}${n.toLocaleString()} 股</span></div>`;
        };
        const pctRow = (label, raw, isAlready100 = false) => {
            if (raw == null || isNaN(Number(raw))) return `<div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0"><span class="text-xs text-textMuted">${label}</span><span class="text-xs text-textMuted font-mono">N/A</span></div>`;
            const val = isAlready100 ? Number(raw) : Number(raw) * 100;
            const c   = val > 0 ? 'text-success' : (val < 0 ? 'text-danger' : 'text-textMuted');
            return `<div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0"><span class="text-xs text-textMuted">${label}</span><span class="text-xs font-bold font-mono ${c}">${val > 0 ? '+' : ''}${val.toFixed(1)}%</span></div>`;
        };

        // RSI colour & label
        const rsiVal = tech.rsi_14;
        const rsiColor      = rsiVal == null ? 'text-textMuted' : rsiVal < 30 ? 'text-success' : rsiVal > 70 ? 'text-danger' : 'text-secondary';
        const rsiLabelText  = rsiVal == null ? '' : rsiVal < 30 ? '超賣' : rsiVal > 70 ? '超買' : '中性';
        const rsiLabelStyle = rsiVal == null ? '' : rsiVal < 30 ? 'bg-success/20 text-success' : rsiVal > 70 ? 'bg-danger/20 text-danger' : 'bg-white/10 text-textMuted';

        // MACD
        const macdObj  = (typeof tech.macd === 'object' && tech.macd !== null) ? tech.macd : {};
        const macdHist = macdObj.histogram;
        const macdHistColor = macdHist == null ? 'text-textMuted' : macdHist > 0 ? 'text-success' : 'text-danger';

        // MA position
        const close = data.current_price || 0;
        const maPosBadge = (maVal) => {
            if (!maVal || !close) return '';
            return close >= maVal
                ? '<span class="text-[9px] ml-1 px-1 rounded bg-success/20 text-success">上方</span>'
                : '<span class="text-[9px] ml-1 px-1 rounded bg-danger/20 text-danger">下方</span>';
        };

        // 52W progress bar
        const low52  = fund['52w_low'];
        const high52 = fund['52w_high'];
        let w52Html  = '<div class="text-xs text-textMuted">N/A</div>';
        if (low52 && high52 && close && high52 > low52) {
            const pct = Math.min(100, Math.max(0, ((close - low52) / (high52 - low52)) * 100));
            w52Html = `
                <div class="flex justify-between text-[9px] text-textMuted mb-1">
                    <span>低 ${fv(low52)}</span><span>現價 ${pct.toFixed(0)}%</span><span>高 ${fv(high52)}</span>
                </div>
                <div class="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-danger via-yellow-500 to-success" style="width:${pct}%"></div>
                </div>`;
        }

        const maArr = tech.ma || {};

        const html = `
            <!-- Hero Price Section -->
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
                                <i data-lucide="map-pin" class="w-3 h-3"></i> Taiwan Stock Exchange (TWSE)
                            </div>
                        </div>
                    </div>
                    <div class="mt-2 md:mt-0 ml-20 md:ml-0 flex flex-col items-start md:items-end">
                        <div class="text-[10px] text-textMuted uppercase tracking-[0.2em] mb-1 font-bold">Current Price</div>
                        <div class="text-4xl font-mono font-black text-secondary tracking-tight mb-2 flex items-center gap-2">
                            <span class="text-xl text-primary font-serif font-medium">$</span>${data.current_price}
                        </div>
                        <div class="inline-flex items-center gap-1.5 text-sm font-bold ${colorClass} ${bgClass} px-3 py-1 rounded-lg border border-white/5 backdrop-blur-md shadow-sm">
                            <i data-lucide="${icon}" class="w-4 h-4"></i>
                            <span>${sign}${data.change_24h}% (24h)</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AI Summary + News -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                <div class="lg:col-span-2">
                    <div class="bg-surface/60 backdrop-blur-md border border-primary/20 rounded-2xl p-6 shadow-lg shadow-primary/5 relative overflow-hidden h-full">
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
                <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                    <i data-lucide="activity" class="w-4 h-4 text-accent"></i> Technical Analysis
                </h3>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <!-- RSI -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">RSI (14)</div>
                        <div class="flex items-end justify-between mb-2">
                            <span class="text-2xl font-black font-mono ${rsiColor}">${rsiVal != null ? Number(rsiVal).toFixed(1) : 'N/A'}</span>
                            ${rsiLabelText ? `<span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${rsiLabelStyle}">${rsiLabelText}</span>` : ''}
                        </div>
                        ${rsiVal != null ? `<div class="h-1.5 rounded-full bg-white/10 overflow-hidden"><div class="h-full rounded-full" style="width:${Math.min(100,Number(rsiVal))}%;background:${Number(rsiVal)<30?'#86efac':Number(rsiVal)>70?'#fda4af':'#a1a1aa'}"></div></div>` : ''}
                    </div>
                    <!-- MACD -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">MACD (12/26/9)</div>
                        <div class="space-y-1.5">
                            <div class="flex justify-between text-xs"><span class="text-textMuted">MACD</span><span class="font-mono text-secondary">${fv(macdObj.macd, 3)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">Signal</span><span class="font-mono text-secondary">${fv(macdObj.signal, 3)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">Histogram</span><span class="font-bold font-mono ${macdHistColor}">${fv(macdHist, 3)}</span></div>
                        </div>
                    </div>
                    <!-- KD -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">KD 隨機指標</div>
                        <div class="space-y-1.5">
                            <div class="flex justify-between text-xs"><span class="text-textMuted">K 值</span><span class="font-bold font-mono text-secondary">${fv((tech.kd||{}).k)}</span></div>
                            <div class="flex justify-between text-xs"><span class="text-textMuted">D 值</span><span class="font-bold font-mono text-secondary">${fv((tech.kd||{}).d)}</span></div>
                        </div>
                    </div>
                    <!-- MA -->
                    <div class="bg-background/80 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors">
                        <div class="text-[10px] text-textMuted uppercase tracking-wider mb-2">移動平均線</div>
                        <div class="space-y-1.5">
                            ${[['MA5', maArr.ma5], ['MA20', maArr.ma20], ['MA60', maArr.ma60]].map(([l,v]) =>
                                `<div class="flex justify-between text-xs items-center"><span class="text-textMuted">${l}</span><span class="font-mono text-secondary">${fv(v)}${v ? maPosBadge(v) : ''}</span></div>`
                            ).join('')}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Section B + C: Fundamentals + Institutional -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Section B: Fundamentals -->
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="bar-chart-2" class="w-4 h-4 text-primary"></i> Fundamental Analysis
                    </h3>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">本益比 P/E</div>
                            <div class="font-bold font-mono text-secondary">${fv(fund.pe_ratio)}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">股價淨值比 P/B</div>
                            <div class="font-bold font-mono text-secondary">${fv(fund.pb_ratio)}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">EPS (TTM)</div>
                            <div class="font-bold font-mono text-secondary">${fv(fund.eps_ttm)}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">殖利率</div>
                            <div class="font-bold font-mono ${fund.dividend_yield_pct > 4 ? 'text-success' : 'text-secondary'}">${fund.dividend_yield_pct != null ? fv(fund.dividend_yield_pct) + '%' : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">毛利率</div>
                            <div class="font-bold font-mono text-secondary">${fund.profit_margins != null ? fvPct(fund.profit_margins * 100) : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">市值</div>
                            <div class="font-bold font-mono text-secondary text-xs">${fmtMktCap(fund.market_cap)}</div>
                        </div>
                    </div>
                    <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                        <div class="text-[9px] text-textMuted uppercase mb-2">52 週高低點</div>
                        ${w52Html}
                    </div>
                </div>

                <!-- Section C: Institutional -->
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="users" class="w-4 h-4 text-yellow-500"></i> 三大法人籌碼
                    </h3>
                    <div class="space-y-0">
                        ${instRow('外資買賣超', inst.foreign_net)}
                        ${instRow('投信買賣超', inst.investment_trust)}
                        ${instRow('自營商買賣超', inst.dealer_net)}
                    </div>
                    <div class="mt-3 pt-3 border-t border-white/10">
                        ${instRow('三大法人合計', inst.total_3party_net)}
                    </div>
                    ${inst.date ? `<div class="mt-3 text-[10px] text-textMuted flex items-center gap-1"><i data-lucide="calendar" class="w-3 h-3"></i> 資料日期：${inst.date}</div>` : ''}
                    ${inst.note ? `<div class="mt-2 text-[10px] text-textMuted/70 leading-relaxed border-t border-white/5 pt-2">${inst.note}</div>` : ''}
                </div>
            </div>

            ${(data.monthly_revenue || data.dividend_info) ? `
            <!-- Section D + E: Monthly Revenue + Dividend -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                ${data.monthly_revenue ? `
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="trending-up" class="w-4 h-4 text-success"></i> 月營收
                        ${data.monthly_revenue.ym ? `<span class="text-[10px] text-textMuted font-normal ml-1">${data.monthly_revenue.ym}</span>` : ''}
                    </h3>
                    <div class="grid grid-cols-2 gap-3">
                        <div class="col-span-2 bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">當月營收</div>
                            <div class="font-bold font-mono text-secondary text-lg">${data.monthly_revenue.current_revenue ? Number(String(data.monthly_revenue.current_revenue).replace(/,/g,'')).toLocaleString() + ' 千元' : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">月增率 MoM</div>
                            <div class="font-bold font-mono ${Number(data.monthly_revenue.mom_pct) > 0 ? 'text-success' : Number(data.monthly_revenue.mom_pct) < 0 ? 'text-danger' : 'text-secondary'}">${data.monthly_revenue.mom_pct != null ? (Number(data.monthly_revenue.mom_pct) > 0 ? '+' : '') + Number(data.monthly_revenue.mom_pct).toFixed(1) + '%' : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">年增率 YoY</div>
                            <div class="font-bold font-mono ${Number(data.monthly_revenue.yoy_pct) > 0 ? 'text-success' : Number(data.monthly_revenue.yoy_pct) < 0 ? 'text-danger' : 'text-secondary'}">${data.monthly_revenue.yoy_pct != null ? (Number(data.monthly_revenue.yoy_pct) > 0 ? '+' : '') + Number(data.monthly_revenue.yoy_pct).toFixed(1) + '%' : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">累計營收</div>
                            <div class="font-bold font-mono text-secondary text-xs">${data.monthly_revenue.ytd_revenue ? Number(String(data.monthly_revenue.ytd_revenue).replace(/,/g,'')).toLocaleString() + ' 千元' : 'N/A'}</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">累計年增率</div>
                            <div class="font-bold font-mono ${Number(data.monthly_revenue.ytd_yoy_pct) > 0 ? 'text-success' : Number(data.monthly_revenue.ytd_yoy_pct) < 0 ? 'text-danger' : 'text-secondary'}">${data.monthly_revenue.ytd_yoy_pct != null ? (Number(data.monthly_revenue.ytd_yoy_pct) > 0 ? '+' : '') + Number(data.monthly_revenue.ytd_yoy_pct).toFixed(1) + '%' : 'N/A'}</div>
                        </div>
                    </div>
                </div>
                ` : '<div></div>'}

                ${data.dividend_info ? `
                <div class="bg-surface/40 backdrop-blur-sm border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary mb-5 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <i data-lucide="gift" class="w-4 h-4 text-yellow-500"></i> 股利資訊
                        ${data.dividend_info.year ? `<span class="text-[10px] text-textMuted font-normal ml-1">${data.dividend_info.year} 年度</span>` : ''}
                    </h3>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">現金股利</div>
                            <div class="font-bold font-mono ${Number(data.dividend_info.cash_dividend) > 0 ? 'text-success' : 'text-secondary'}">${data.dividend_info.cash_dividend || 'N/A'} 元</div>
                        </div>
                        <div class="bg-background/60 rounded-lg p-3 border border-white/5">
                            <div class="text-[9px] text-textMuted uppercase mb-1">股票股利</div>
                            <div class="font-bold font-mono text-secondary">${data.dividend_info.stock_dividend || 'N/A'} 元</div>
                        </div>
                    </div>
                    <div class="space-y-0">
                        ${data.dividend_info.board_date ? `<div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">董事會日期</span><span class="text-xs font-mono text-secondary">${data.dividend_info.board_date}</span></div>` : ''}
                        ${data.dividend_info.shareholder_mtg ? `<div class="flex justify-between py-2 border-b border-white/5"><span class="text-xs text-textMuted">股東會日期</span><span class="text-xs font-mono text-secondary">${data.dividend_info.shareholder_mtg}</span></div>` : ''}
                        ${data.dividend_info.progress ? `<div class="flex justify-between py-2"><span class="text-xs text-textMuted">決議進度</span><span class="text-xs text-secondary text-right max-w-[60%]">${data.dividend_info.progress}</span></div>` : ''}
                    </div>
                </div>
                ` : '<div></div>'}
            </div>
            ` : ''}
        `;

        container.innerHTML = html;
        if (window.lucide) window.lucide.createIcons();
    },

    jumpToPulse: function (symbol) {
        const inputEl = document.getElementById('twstockPulseSearchInput');
        if (inputEl) inputEl.value = symbol;
        if (this.activeSubTab === 'pulse') {
            this.refreshAIPulse(symbol);
        } else {
            this.switchSubTab('pulse');
        }
    },

    // Chart logic
    twChart: null,
    twCandleSeries: null,
    twVolumeSeries: null,
    twCurrentChartSymbol: null,
    twCurrentChartInterval: '1d',

    showTwChart: async function (symbol, event) {
        if (event) {
            event.stopPropagation();
        }

        const chartSection = document.getElementById('twstock-chart-section');
        const chartContainer = document.getElementById('twstock-chart-container');
        const volumeContainer = document.getElementById('twstock-volume-container');
        const titleEl = document.getElementById('twstock-chart-title');

        if (!chartSection || !chartContainer || typeof LightweightCharts === 'undefined') {
            console.error('[TW Stock] Chart elements or LightweightCharts missing');
            return;
        }

        this.twCurrentChartSymbol = symbol;
        chartSection.classList.remove('hidden');
        if (window.lucide) window.lucide.createIcons();
        if (titleEl) titleEl.textContent = `${symbol} (${this.twCurrentChartInterval.toUpperCase()})`;

        // Update active interval button UI
        document.querySelectorAll('.tw-chart-interval-btn').forEach(btn => {
            if (btn.dataset.interval === this.twCurrentChartInterval) {
                btn.classList.add('bg-white/10', 'text-primary');
                btn.classList.remove('text-textMuted');
            } else {
                btn.classList.remove('bg-white/10', 'text-primary');
                btn.classList.add('text-textMuted');
            }
        });

        chartContainer.innerHTML = '<div class="animate-pulse text-textMuted h-full flex items-center justify-center">載入歷史數據中...</div>';
        if (volumeContainer) volumeContainer.innerHTML = '';

        try {
            const authHeaders = typeof _getAuthHeaders === 'function' ? await _getAuthHeaders() : {};
            const res = await fetch(`/api/twstock/klines/${encodeURIComponent(symbol)}?interval=${this.twCurrentChartInterval}&limit=200`, {
                headers: authHeaders
            });

            if (!res.ok) {
                let msg = `HTTP ${res.status} `;
                try { const d = await res.json(); msg = d.detail || msg; } catch (e) { }
                throw new Error(msg);
            }

            const responseData = await res.json();
            const data = responseData.data || [];

            if (data.length === 0) {
                chartContainer.innerHTML = '<div class="text-danger h-full flex items-center justify-center">無法載入數據或無歷史交易紀錄</div>';
                return;
            }

            // Update timestamp
            const updatedEl = document.getElementById('twstock-chart-updated');
            if (updatedEl) {
                const now = new Date();
                updatedEl.textContent = `載入時間: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} `;
            }

            chartContainer.innerHTML = '';
            if (this.twChart) {
                this.twChart.remove();
                this.twChart = null;
            }

            // Show volume container as separate panel
            if (volumeContainer) {
                volumeContainer.innerHTML = '';
                volumeContainer.style.display = '';
            }

            this.twChart = LightweightCharts.createChart(chartContainer, {
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#A0AEC0' },
                grid: { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
                timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true, rightOffset: 5 },
                handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
                handleScale: { mouseWheel: true, pinchScale: true, axisPressedMouseMove: { time: true, price: false } },
            });

            this.twCandleSeries = this.twChart.addCandlestickSeries({
                upColor: '#10B981', downColor: '#EF4444', borderVisible: false, wickUpColor: '#10B981', wickDownColor: '#EF4444'
            });

            // Create separate volume chart
            if (this.twVolumeChart) { this.twVolumeChart.remove(); this.twVolumeChart = null; }
            this.twVolumeSeries = null;
            if (volumeContainer) {
                this.twVolumeChart = LightweightCharts.createChart(volumeContainer, {
                    layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#A0AEC0' },
                    grid: { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.02)' } },
                    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                    rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)', scaleMargins: { top: 0.1, bottom: 0.05 } },
                    timeScale: { visible: false },
                    handleScroll: { mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false },
                    handleScale: { mouseWheel: false, pinchScale: false },
                });
                this.twVolumeSeries = this.twVolumeChart.addHistogramSeries({
                    priceFormat: { type: 'volume' },
                });
            }

            // Map data
            const formattedKlines = data.map(k => ({
                time: k.time,
                open: k.open,
                high: k.high,
                low: k.low,
                close: k.close
            }));

            const formattedVolume = data.map(k => ({
                time: k.time,
                value: k.volume,
                color: k.close >= k.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'
            }));

            this.twCandleSeries.setData(formattedKlines);
            if (this.twVolumeSeries) this.twVolumeSeries.setData(formattedVolume);
            this.twChart.timeScale().fitContent();
            if (this.twVolumeChart) {
                this.twVolumeChart.timeScale().fitContent();
                let _syncingRange = false;
                this.twChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                    if (_syncingRange || !range || !this.twVolumeChart) return;
                    _syncingRange = true;
                    this.twVolumeChart.timeScale().setVisibleLogicalRange(range);
                    _syncingRange = false;
                });
                this.twVolumeChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                    if (_syncingRange || !range || !this.twChart) return;
                    _syncingRange = true;
                    this.twChart.timeScale().setVisibleLogicalRange(range);
                    _syncingRange = false;
                });
            }

            // Helper functions for formatting
            const formatPrice = (price) => price.toFixed(2);
            const formatVolume = (vol) => {
                if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
                if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
                if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
                return vol.toFixed(2);
            };

            const openEl = document.getElementById('tw-info-open');
            const highEl = document.getElementById('tw-info-high');
            const lowEl = document.getElementById('tw-info-low');
            const closeEl = document.getElementById('tw-info-close');
            const volEl = document.getElementById('tw-info-volume');

            const setHoverData = (kline, volumeData) => {
                if (!kline) return;
                const isUp = kline.close >= kline.open;
                const color = isUp ? 'text-success' : 'text-danger';

                if (openEl) openEl.textContent = formatPrice(kline.open);
                if (highEl) highEl.textContent = formatPrice(kline.high);
                if (lowEl) lowEl.textContent = formatPrice(kline.low);
                if (closeEl) {
                    closeEl.textContent = formatPrice(kline.close);
                    closeEl.className = color + " ml-0.5";
                }
                if (volEl && volumeData) {
                    // For histogram series, the value is just a number or an object with value
                    const v = typeof volumeData === 'object' && volumeData.value !== undefined ? volumeData.value : volumeData;
                    volEl.textContent = formatVolume(v);
                }
            };

            // Set initial data to the last bar
            if (formattedKlines.length > 0) {
                setHoverData(formattedKlines[formattedKlines.length - 1], formattedVolume[formattedVolume.length - 1]);
            }

            // Hover tooltips
            this.twChart.subscribeCrosshairMove(param => {
                if (param.point === undefined || !param.time || param.point.x < 0 || param.point.x > chartContainer.clientWidth || param.point.y < 0 || param.point.y > chartContainer.clientHeight) {
                    // Reset to last candle when mouse leaves chart
                    if (formattedKlines.length > 0) {
                        setHoverData(formattedKlines[formattedKlines.length - 1], formattedVolume[formattedVolume.length - 1]);
                    }
                    if (this.twVolumeChart) this.twVolumeChart.clearCrosshairPosition();
                    return;
                }
                const dataPoint = param.seriesData.get(this.twCandleSeries);
                // Look up volume by time since it's on a separate chart
                const volData = formattedVolume.find(v => v.time === param.time);
                if (dataPoint) {
                    setHoverData(dataPoint, volData);
                }
                // Sync crosshair position to volume chart
                if (this.twVolumeChart && this.twVolumeSeries && volData) {
                    this.twVolumeChart.setCrosshairPosition(volData.value, param.time, this.twVolumeSeries);
                }
            });

            // Handle resize — remove old handler first to prevent leaks
            window.removeEventListener('resize', this._twChartResizeHandler);
            const onResize = () => {
                if (chartSection && !chartSection.classList.contains('hidden') && this.twChart) {
                    this.twChart.applyOptions({ width: chartContainer.clientWidth });
                    if (this.twVolumeChart && volumeContainer) {
                        this.twVolumeChart.applyOptions({ width: volumeContainer.clientWidth });
                    }
                }
            };
            this._twChartResizeHandler = onResize;
            window.addEventListener('resize', onResize);

            // Trigger initial resize to fit vertically
            setTimeout(onResize, 50);

        } catch (error) {
            console.error('[TW Stock] Chart Data Error:', error);
            chartContainer.innerHTML = `<div class="text-danger h-full flex flex-col items-center justify-center text-sm p-4 text-center">
            <i data-lucide="alert-triangle" class="w-8 h-8 mb-2"></i>
        讀取失敗：${error.message}
            </div>`;
            if (window.lucide) window.lucide.createIcons();
        }
    },

    closeTwChart: function () {
        window.removeEventListener('resize', this._twChartResizeHandler);
        this._twChartResizeHandler = null;
        const section = document.getElementById('twstock-chart-section');
        if (section) section.classList.add('hidden');
        if (this.twChart) {
            this.twChart.remove();
            this.twChart = null;
        }
        if (this.twVolumeChart) {
            this.twVolumeChart.remove();
            this.twVolumeChart = null;
        }
        this.twVolumeSeries = null;
        this.twCurrentChartSymbol = null;
    },

    changeChartInterval: function (interval) {
        if (!this.twCurrentChartSymbol || this.twCurrentChartInterval === interval) return;
        this.twCurrentChartInterval = interval;
        this.showTwChart(this.twCurrentChartSymbol); // re-fetch and render
    },

    bindEvents: function () {
        const searchBtn = document.getElementById('twstockPulseSearchBtn');
        const inputEl = document.getElementById('twstockPulseSearchInput');

        if (searchBtn && inputEl && !searchBtn.dataset.bound) {
            searchBtn.dataset.bound = 'true';
            searchBtn.addEventListener('click', () => {
                const sym = inputEl.value.trim();
                if (sym) {
                    this.refreshAIPulse(sym);
                }
            });
            inputEl.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const sym = inputEl.value.trim();
                    if (sym) {
                        this.refreshAIPulse(sym);
                    }
                }
            });
        }
    },

    // ── Market Info Tab ───────────────────────────────────────────────────────

    initSectionToggles: function () {
        try {
            const prefs = JSON.parse(localStorage.getItem('twstock_section_prefs') || '{}');
            const sections = ['pe', 'news', 'dividend', 'foreign'];
            sections.forEach(sec => {
                const isHidden = prefs[sec] === false; // visible by default
                const bodyEl = document.getElementById(`twstock-section-body-${sec}`);
                const chevronEl = document.getElementById(`twstock-chevron-${sec}`);
                if (bodyEl && chevronEl) {
                    if (isHidden) {
                        bodyEl.classList.add('hidden');
                        chevronEl.classList.add('rotate-180');
                    } else {
                        bodyEl.classList.remove('hidden');
                        chevronEl.classList.remove('rotate-180');
                    }
                }
            });
        } catch (e) {
            console.warn('[TW Stock] Error parsing section prefs:', e);
        }
    },

    toggleSection: function (sectionKey) {
        const bodyEl = document.getElementById(`twstock-section-body-${sectionKey}`);
        const chevronEl = document.getElementById(`twstock-chevron-${sectionKey}`);
        if (!bodyEl || !chevronEl) return;

        const isCurrentlyHidden = bodyEl.classList.contains('hidden');
        if (isCurrentlyHidden) {
            bodyEl.classList.remove('hidden');
            chevronEl.classList.remove('rotate-180');
        } else {
            bodyEl.classList.add('hidden');
            chevronEl.classList.add('rotate-180');
        }

        // Save preference
        try {
            const prefs = JSON.parse(localStorage.getItem('twstock_section_prefs') || '{}');
            prefs[sectionKey] = isCurrentlyHidden; // true if now visible
            localStorage.setItem('twstock_section_prefs', JSON.stringify(prefs));
        } catch (e) {
            console.warn('[TW Stock] Error saving section prefs:', e);
        }
    },

    refreshMarketInfo: async function () {
        this.initSectionToggles();
        const authHeaders = typeof _getAuthHeaders === 'function' ? await _getAuthHeaders() : {};

        // Load all 4 sections in parallel
        await Promise.all([
            this._loadNewsSection(authHeaders),
            this._loadPESection(authHeaders),
            this._loadDividendSection(authHeaders),
            this._loadForeignSection(authHeaders),
        ]);
    },

    _showLoader: function (loaderId, show) {
        const el = document.getElementById(loaderId);
        if (!el) return;
        el.classList.toggle('hidden', !show);
        el.classList.toggle('flex', show);
    },

    _loadNewsSection: async function (authHeaders) {
        const container = document.getElementById('twstock-info-news');
        if (!container) return;
        this._showLoader('twstock-info-news-loader', true);
        try {
            const symbols = window.twStockSelectedSymbols || [];
            let url = '/api/twstock/opendata/news?limit=15';
            if (symbols.length > 0) {
                url += `&symbols=${encodeURIComponent(symbols.join(','))}`;
            }

            const res = await fetch(url, { headers: authHeaders });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            const items = json.data || [];
            if (!items.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50">目前無重大訊息</p>';
                return;
            }
            container.innerHTML = items.map(item => `
            <div class="bg-surface/40 border border-yellow-500/10 hover:border-yellow-500/30 rounded-xl p-3 transition-colors cursor-default">
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0 w-12 text-center">
                        <div class="text-xs font-black text-yellow-400 font-mono">${item.code || '—'}</div>
                        <div class="text-[10px] text-textMuted opacity-60 truncate">${item.name || ''}</div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-textMain leading-relaxed line-clamp-2">${item.subject || '（無主旨）'}</p>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="text-[10px] text-textMuted opacity-50">${item.date || ''} ${item.time || ''}</span>
                            ${item.rule ? `<span class="text-[9px] bg-yellow-500/10 text-yellow-400 px-1.5 py-0.5 rounded font-mono">${item.rule}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
            `).join('');
        } catch (err) {
            console.error('[TW Info] News error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4">載入重大訊息失敗：${err.message}</p>`;
        } finally {
            this._showLoader('twstock-info-news-loader', false);
        }
    },

    _loadPESection: async function (authHeaders) {
        const container = document.getElementById('twstock-info-pe');
        if (!container) return;
        const symbols = window.twStockSelectedSymbols || ['2330', '2317', '2454', '2881', '2882'];
        this._showLoader('twstock-info-pe-loader', true);
        try {
            const targets = symbols.slice(0, 20); // Render up to 20 PE cards
            const results = await Promise.all(
                targets.map(code =>
                    fetch(`/api/twstock/opendata/pe_ratio/${code}`, { headers: authHeaders })
                        .then(r => r.ok ? r.json() : null)
                        .catch(() => null)
                )
            );
            const valid = results.filter(Boolean).filter(r => !r.error);
            if (!valid.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50 col-span-full">無法取得估值資料（交易所休市中或無自選股）</p>';
                return;
            }
            container.innerHTML = valid.map(d => {
                const pe = parseFloat(d.pe_ratio) || 0;
                const dy = parseFloat(d.dividend_yield) || 0;
                const pb = parseFloat(d.pb_ratio) || 0;
                // Color-code PE: green=cheap, yellow=fair, red=expensive
                const peColor = pe <= 0 ? 'text-textMuted' : pe < 15 ? 'text-success' : pe < 25 ? 'text-yellow-400' : 'text-danger';
                const dyColor = dy <= 0 ? 'text-textMuted' : dy > 4 ? 'text-success' : 'text-secondary';
                return `
            <div class="relative overflow-hidden rounded-2xl border border-white/8 bg-gradient-to-br from-surface to-background hover:border-primary/30 transition-all duration-200 group cursor-default">
                        <!--Subtle glow accent-->
                        <div class="absolute top-0 right-0 w-16 h-16 bg-primary/5 rounded-full blur-2xl group-hover:bg-primary/10 transition-all"></div>
                        <div class="relative p-4">
                            <!-- Stock header -->
                            <div class="flex items-start justify-between mb-4">
                                <div>
                                    <div class="font-black text-primary font-mono text-base leading-none">${d.code}</div>
                                    <div class="text-[11px] text-textMuted mt-0.5 truncate max-w-[90px]">${d.name || ''}</div>
                                </div>
                                <div class="text-[9px] text-textMuted/40 font-mono pt-0.5">${d.date || ''}</div>
                            </div>
                            <!-- Metrics row -->
                            <div class="grid grid-cols-3 gap-1">
                                <div class="bg-background/60 rounded-xl p-2 text-center">
                                    <div class="text-[9px] text-textMuted uppercase tracking-wider mb-1 font-bold">P/E</div>
                                    <div class="font-black text-sm ${peColor} font-mono">${pe > 0 ? pe.toFixed(1) : '—'}</div>
                                </div>
                                <div class="bg-background/60 rounded-xl p-2 text-center">
                                    <div class="text-[9px] text-textMuted uppercase tracking-wider mb-1 font-bold">殖利率</div>
                                    <div class="font-black text-sm ${dyColor} font-mono">${dy > 0 ? dy.toFixed(2) + '%' : '—'}</div>
                                </div>
                                <div class="bg-background/60 rounded-xl p-2 text-center">
                                    <div class="text-[9px] text-textMuted uppercase tracking-wider mb-1 font-bold">P/B</div>
                                    <div class="font-black text-sm text-secondary font-mono">${pb > 0 ? pb.toFixed(2) : '—'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
            `;
            }).join('');
        } catch (err) {
            console.error('[TW Info] PE error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4 col-span-full">載入本益比失敗：${err.message}</p>`;
        } finally {
            this._showLoader('twstock-info-pe-loader', false);
        }
    },

    _loadDividendSection: async function (authHeaders) {
        const container = document.getElementById('twstock-info-dividend');
        if (!container) return;
        this._showLoader('twstock-info-div-loader', true);
        try {
            const symbols = window.twStockSelectedSymbols || [];
            let url = '/api/twstock/opendata/dividend?limit=20';
            if (symbols.length > 0) {
                url += `&symbols=${encodeURIComponent(symbols.join(','))}`;
            }

            const res = await fetch(url, { headers: authHeaders });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            const items = (json.data || []).filter(d => d.cash_dividend && d.cash_dividend !== '' && d.cash_dividend !== '0');
            if (!items.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50">目前無股利分派資料</p>';
                return;
            }
            container.innerHTML = items.slice(0, 20).map(d => `
            <div class="bg-surface/40 border border-success/10 hover:border-success/30 rounded-xl p-3 transition-colors">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center flex-shrink-0">
                            <span class="text-success font-black text-xs font-mono">${(d.code || '—').substring(0, 4)}</span>
                        </div>
                        <div>
                            <div class="font-bold text-sm text-secondary">${d.name || d.code}</div>
                            <div class="text-[10px] text-textMuted opacity-60">${d.year || ''} 年度・${d.progress || ''}</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="font-black text-success text-base">$${d.cash_dividend || '—'}</div>
                        <div class="text-[10px] text-textMuted opacity-60">現金股利/股</div>
                    </div>
                </div>
                    ${d.shareholder_meeting ? `<div class="mt-2 pt-2 border-t border-white/5 text-[10px] text-textMuted flex items-center gap-1"><i data-lucide="calendar" class="w-3 h-3"></i> 股東會：${d.shareholder_meeting}</div>` : ''}
                </div>
            `).join('');
            if (window.lucide) window.lucide.createIcons();
        } catch (err) {
            console.error('[TW Info] Dividend error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4">載入股利資料失敗：${err.message}</p>`;
        } finally {
            this._showLoader('twstock-info-div-loader', false);
        }
    },

    _loadForeignSection: async function (authHeaders) {
        const container = document.getElementById('twstock-info-foreign');
        if (!container) return;
        this._showLoader('twstock-info-foreign-loader', true);
        try {
            const res = await fetch('/api/twstock/opendata/foreign_holding', { headers: authHeaders });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            const items = json.data || [];
            if (!items.length) {
                container.innerHTML = '<p class="text-textMuted text-xs italic text-center py-6 opacity-50">無外資持股資料</p>';
                return;
            }
            container.innerHTML = `
            <table class="w-full text-xs">
                    <thead>
                        <tr class="text-textMuted uppercase tracking-wider border-b border-white/10">
                            <th class="text-left py-2 px-2 font-bold opacity-60">排名</th>
                            <th class="text-left py-2 px-2 font-bold opacity-60">代號</th>
                            <th class="text-left py-2 px-2 font-bold opacity-60">名稱</th>
                            <th class="text-right py-2 px-2 font-bold opacity-60">持股%</th>
                            <th class="text-right py-2 px-2 font-bold opacity-60 hidden sm:table-cell">可投%</th>
                            <th class="text-right py-2 px-2 font-bold opacity-60 hidden sm:table-cell">上限%</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                        ${items.map((d, i) => {
                const pct = parseFloat(d.held_pct) || 0;
                const barW = Math.min(100, pct);
                return `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2 px-2 text-textMuted font-mono">${d.rank || (i + 1)}</td>
                                    <td class="py-2 px-2 font-mono text-primary font-bold">${d.code}</td>
                                    <td class="py-2 px-2 text-secondary truncate max-w-[80px]">${d.name}</td>
                                    <td class="py-2 px-2 text-right">
                                        <div class="flex items-center justify-end gap-1.5">
                                            <div class="w-12 h-1.5 bg-white/10 rounded-full overflow-hidden hidden sm:block">
                                                <div class="h-full bg-accent rounded-full" style="width:${barW}%"></div>
                                            </div>
                                            <span class="font-bold text-accent">${pct.toFixed(1)}%</span>
                                        </div>
                                    </td>
                                    <td class="py-2 px-2 text-right text-textMuted hidden sm:table-cell">${d.available_pct || '—'}%</td>
                                    <td class="py-2 px-2 text-right text-textMuted hidden sm:table-cell">${d.upper_limit_pct || '—'}%</td>
                                </tr>
                            `;
            }).join('')}
                    </tbody>
                </table>
            `;
        } catch (err) {
            console.error('[TW Info] Foreign holding error:', err);
            container.innerHTML = `<p class="text-danger text-xs text-center py-4">載入外資持股失敗：${err.message}</p>`;
        } finally {
            this._showLoader('twstock-info-foreign-loader', false);
        }
    }
};

async function initTwStock() {
    console.log('[TW Stock] initTwStock called');
    if (window.Components && !window.Components.isInjected('twstock')) {
        await window.Components.inject('twstock');
    }

    const marketBtn = document.getElementById('twstock-btn-market');
    const pulseBtn = document.getElementById('twstock-btn-pulse');

    // Bind click events if not already done
    if (marketBtn && !marketBtn.dataset.bound) {
        marketBtn.addEventListener('click', () => window.TWStockTab.switchSubTab('market'));
        marketBtn.dataset.bound = "true";
    }

    if (pulseBtn && !pulseBtn.dataset.bound) {
        pulseBtn.addEventListener('click', () => window.TWStockTab.switchSubTab('pulse'));
        pulseBtn.dataset.bound = "true";
    }

    window.TWStockTab.bindEvents();

    // Refresh current sub-tab data (avoid switchSubTab early-return when already on same tab)
    window.TWStockTab.refreshCurrent(true);
}

// Global exposure
window.initTwStock = initTwStock;
