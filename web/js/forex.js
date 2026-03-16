// ============================================================
// Forex Market Tab — 外匯市場
// Follows the same pattern as commodity.js / usstock.js
// ============================================================

window.ForexTab = {
    activeSubTab: 'market',
    activeSymbol: null,
    chartInstance: null,
    chartSeries: null,
    currentInterval: '1d',

    DEFAULT_PAIRS: [
        { symbol: 'TWD=X',    name: 'USD/TWD', desc: '美元 / 台幣' },
        { symbol: 'EURUSD=X', name: 'EUR/USD', desc: '歐元 / 美元' },
        { symbol: 'GBPUSD=X', name: 'GBP/USD', desc: '英鎊 / 美元' },
        { symbol: 'JPY=X',    name: 'USD/JPY', desc: '美元 / 日圓' },
        { symbol: 'AUDUSD=X', name: 'AUD/USD', desc: '澳幣 / 美元' },
        { symbol: 'CNY=X',    name: 'USD/CNY', desc: '美元 / 人民幣'},
    ],

    // ── Init ──────────────────────────────────────────────────

    init: function () {
        this.renderMarket();
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
        listEl.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i><p class="text-sm">載入中...</p></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch('/api/forex/market');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            listEl.innerHTML = '';
            (data.pairs || []).forEach(item => {
                const isUp   = item.changePercent >= 0;
                const color  = isUp ? 'text-success' : 'text-danger';
                const arrow  = isUp ? '▲' : '▼';
                // Find display info
                const meta   = this.DEFAULT_PAIRS.find(p => p.symbol === item.symbol);
                const desc   = meta?.desc || item.name;

                const card = document.createElement('div');
                card.className = 'bg-surface border border-white/5 rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:border-primary/30 transition';
                card.onclick = () => this.switchSubTab('pulse', item.symbol);
                card.innerHTML = `
                    <div>
                        <div class="font-bold text-secondary text-sm">${item.name}</div>
                        <div class="text-xs text-textMuted">${desc}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono font-bold text-secondary">${item.rate.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-xs font-bold ${color}">${arrow} ${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(3)}%</div>
                    </div>`;
                listEl.appendChild(card);
            });

            const updEl = document.getElementById('forex-last-updated');
            if (updEl && data.last_updated) {
                updEl.textContent = '更新: ' + new Date(data.last_updated).toLocaleTimeString('zh-TW');
            }
        } catch (e) {
            listEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Pulse View ────────────────────────────────────────────

    renderPulse: async function (symbol) {
        const pulseEl = document.getElementById('forex-pulse-content');
        if (!pulseEl) return;
        pulseEl.innerHTML = '<div class="text-center text-textMuted py-10"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i></div>';
        if (window.lucide) lucide.createIcons();

        try {
            const res = await fetch(`/api/forex/pulse/${encodeURIComponent(symbol)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const d = await res.json();

            const isUp  = d.change_24h >= 0;
            const color = isUp ? 'text-success' : 'text-danger';

            pulseEl.innerHTML = `
                <div class="space-y-4">
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <div class="text-textMuted text-xs uppercase tracking-wider mb-1">${d.name}</div>
                        <div class="text-3xl font-serif text-secondary font-bold">${d.rate?.toLocaleString(undefined, {maximumFractionDigits: 6})}</div>
                        <div class="text-sm font-bold ${color} mt-1">${d.change_24h > 0 ? '+' : ''}${d.change_24h?.toFixed(3)}% 24H</div>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">市場脈動</h4>
                        <p class="text-sm text-secondary leading-relaxed">${d.report?.summary || ''}</p>
                    </div>
                    <div class="bg-surface border border-white/5 rounded-2xl p-5">
                        <h4 class="text-xs uppercase tracking-wider text-textMuted mb-3">技術指標</h4>
                        <div class="grid grid-cols-2 gap-2">
                            ${(d.report?.key_points || []).map(pt => `
                                <div class="bg-background rounded-xl px-3 py-2 text-xs">
                                    <span class="text-textMuted">${pt.split(':')[0]}:</span>
                                    <span class="text-secondary font-mono ml-1">${pt.split(':').slice(1).join(':').trim()}</span>
                                </div>`).join('')}
                        </div>
                    </div>
                    <div id="forex-chart-container" class="bg-surface border border-white/5 rounded-2xl p-4">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs uppercase tracking-wider text-textMuted">走勢圖</span>
                            <div class="flex gap-1">
                                ${['1d','1wk','1mo'].map(iv => `<button onclick="ForexTab.changeInterval('${iv}')" id="forex-interval-${iv}" class="text-xs px-2 py-1 rounded-lg ${iv === '1d' ? 'bg-primary text-background' : 'bg-surface text-textMuted hover:bg-surfaceHighlight'} transition">${iv === '1d' ? '日' : iv === '1wk' ? '週' : '月'}</button>`).join('')}
                            </div>
                        </div>
                        <div id="forex-chart" style="height: 200px;"></div>
                    </div>
                </div>`;
            if (window.lucide) lucide.createIcons();
            this.loadChart(symbol, this.currentInterval);
        } catch (e) {
            pulseEl.innerHTML = `<div class="text-center text-danger py-10 text-sm">載入失敗：${e.message}</div>`;
        }
    },

    // ── Chart ─────────────────────────────────────────────────

    loadChart: async function (symbol, interval) {
        const chartEl = document.getElementById('forex-chart');
        if (!chartEl) return;
        this.destroyChart();

        try {
            const res = await fetch(`/api/forex/klines/${encodeURIComponent(symbol)}?interval=${interval}&limit=200`);
            if (!res.ok) return;
            const data = await res.json();
            const klines = data.data || [];
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
