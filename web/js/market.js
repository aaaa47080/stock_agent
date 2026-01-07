// ========================================
// market.js - 市場篩選功能
// ========================================

// 資金費率快取
let fundingRateData = {};

// 獲取資金費率數據
async function fetchFundingRates() {
    try {
        const res = await fetch('/api/funding-rates');
        const data = await res.json();
        if (data.data) {
            fundingRateData = data.data;
        }
        return data;
    } catch (err) {
        console.error('獲取資金費率失敗:', err);
        return null;
    }
}

// 獲取資金費率顏色和狀態
function getFundingRateStyle(rate) {
    if (rate === null || rate === undefined) return { color: 'text-gray-500', bg: 'bg-gray-500/10', border: 'border-gray-500/20', label: '-' };

    const r = parseFloat(rate);
    // 🔥 極高費率 (> 0.1%): 市場過熱
    if (r >= 0.1) return { color: 'text-red-500 font-bold', bg: 'bg-red-500/20', border: 'border-red-500/50', label: '極度過熱' };

    // 📈 偏高費率 (0.03% - 0.1%): 明顯看多
    if (r >= 0.03) return { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', label: '多頭擁擠' };

    // 🐂 正常偏多 (> 0.01%): 溫和看多
    if (r > 0.01) return { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: '看多' };

    // 😐 基準費率 (0% - 0.01%): 市場平靜
    if (r >= 0) return { color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20', label: '中性' };

    // 📉 負費率 (< 0%): 空頭擁擠 / 軋空機會 (Cyan/Blue)
    return { color: 'text-cyan-400 font-medium', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', label: '看空/軋空' };
}

async function refreshScreener(showLoading = false) {
    const containers = {
        'top': document.getElementById('top-list'),
        'oversold': document.getElementById('oversold-list'),
        'overbought': document.getElementById('overbought-list'),
        'highFunding': document.getElementById('high-funding-list'),
        'lowFunding': document.getElementById('low-funding-list')
    };

    if (showLoading) {
        Object.values(containers).forEach(c => {
            if (c) c.innerHTML = '<div class="animate-pulse space-y-2"><div class="h-4 bg-surface rounded w-3/4"></div><div class="h-4 bg-surface rounded w-1/2"></div></div>';
        });
    }

    try {
        const body = { exchange: currentFilterExchange };
        if (globalSelectedSymbols.length > 0) {
            body.symbols = globalSelectedSymbols;
        }

        // 同時獲取篩選器數據和資金費率
        const [screenerRes, fundingRes] = await Promise.all([
            fetch('/api/screener', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            }),
            fetchFundingRates()
        ]);

        const data = await screenerRes.json();

        if (isFirstLoad && globalSelectedSymbols.length === 0) {
            if (data.top_performers && data.top_performers.length > 0) {
                globalSelectedSymbols = data.top_performers.map(item => item.Symbol);
                const indicator = document.getElementById('active-filter-indicator');
                if (indicator) {
                    indicator.classList.remove('hidden');
                    document.getElementById('filter-count').innerText = globalSelectedSymbols.length;
                }
                document.getElementById('global-count-badge').innerText = globalSelectedSymbols.length;
            }
            isFirstLoad = false;
        }

        if (data.last_updated) {
            const date = new Date(data.last_updated);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            document.getElementById('screener-last-updated').textContent = `(更新於: ${timeStr})`;
        }

        renderList(containers.top, data.top_performers, 'price_change_24h', '%');
        renderList(containers.oversold, data.oversold, 'RSI_14', '');
        renderList(containers.overbought, data.overbought, 'RSI_14', '');

        // 渲染資金費率分類
        if (fundingRes && containers.highFunding && containers.lowFunding) {
            renderFundingRateList(containers.highFunding, fundingRes.top_bullish, 'high');
            renderFundingRateList(containers.lowFunding, fundingRes.top_bearish, 'low');
        }
    } catch (err) {
        console.error(err);
        if (showLoading) {
            Object.values(containers).forEach(c => {
                if (c) c.innerHTML = '<div class="text-red-400 text-sm">載入失敗</div>';
            });
        }
    }
}

function formatPrice(price) {
    const p = parseFloat(price);
    if (p >= 1000) return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (p >= 1) return p.toFixed(2);
    if (p >= 0.01) return p.toFixed(4);
    if (p >= 0.0001) return p.toFixed(6);
    return p.toFixed(8);
}

function renderList(container, items, key, unit) {
    if (!container) return;
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<p class="text-textMuted text-sm italic">No data</p>';
        return;
    }

    items.forEach(item => {
        const val = parseFloat(item[key]);
        let signalsHtml = '';
        if (item.signals && Array.isArray(item.signals)) {
            item.signals.forEach(sig => {
                let colorClass = 'bg-surfaceHighlight text-secondary';
                let icon = '';
                if (sig.includes('突破')) { colorClass = 'bg-accent/20 text-accent border border-accent/30'; icon = '🚀'; }
                else if (sig.includes('爆量')) { colorClass = 'bg-primary/20 text-primary border border-primary/30'; icon = '📈'; }
                else if (sig.includes('金叉')) { colorClass = 'bg-primary/20 text-primary border border-primary/30'; icon = '✨'; }
                else if (sig.includes('抄底')) { colorClass = 'bg-accent/20 text-accent border border-accent/30'; icon = '💎'; }
                signalsHtml += `<span class="text-[9px] px-1 py-0.5 rounded ${colorClass} whitespace-nowrap">${icon}${sig}</span>`;
            });
        }

        // 獲取該幣種的資金費率
        const symbol = item.Symbol.replace('USDT', '').replace('-', '');
        const fundingInfo = fundingRateData[symbol];
        const fundingRate = fundingInfo ? fundingInfo.fundingRate : null;
        const frStyle = getFundingRateStyle(fundingRate);

        const div = document.createElement('div');
        div.className = "flex items-center justify-between p-4 hover:bg-surfaceHighlight rounded-2xl transition group cursor-pointer border border-transparent hover:border-white/5";
        div.onclick = () => { switchTab('chat'); quickAsk(`${item.Symbol} 分析`); };

        const hasSignals = item.signals && item.signals.length > 0;

        div.innerHTML = `
            <div class="flex items-center gap-3 min-w-0 flex-1">
                <div class="w-10 h-10 bg-gradient-to-br from-surface to-surfaceHighlight rounded-xl flex items-center justify-center text-xs font-bold shrink-0 text-primary">${item.Symbol.substring(0, 2)}</div>
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                        <span class="font-semibold text-sm text-secondary">${item.Symbol}</span>
                        <span class="text-xs text-textMuted font-medium">$${formatPrice(item.Close)}</span>
                    </div>
                    <div class="flex flex-wrap gap-1 mt-1">
                        ${hasSignals ? signalsHtml : ''}
                        ${fundingRate !== null ? `<span class="text-[9px] px-1 py-0.5 rounded ${frStyle.bg} ${frStyle.color} border border-current/20 whitespace-nowrap" title="Funding Rate: ${fundingRate.toFixed(4)}%">💰${fundingRate >= 0 ? '+' : ''}${fundingRate.toFixed(3)}%</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="text-right shrink-0 ml-2">
                <div class="text-sm font-bold ${key === 'RSI_14' ? (val > 70 ? 'text-danger' : (val < 40 ? 'text-success' : 'text-secondary')) : (val > 0 ? 'text-success' : 'text-danger')}">
                    ${val > 0 && key !== 'RSI_14' ? '+' : ''}${val.toFixed(2)}${unit}
                </div>
                <div class="text-[10px] text-textMuted">${key === 'RSI_14' ? 'RSI' : '24H'}</div>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderFundingRateList(container, items, type) {
    if (!container) return;
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<p class="text-textMuted text-sm italic">No data</p>';
        return;
    }

    items.forEach(item => {
        const rate = item.fundingRate;
        const frStyle = getFundingRateStyle(rate);
        const fullInfo = fundingRateData[item.symbol] || {};

        // 下次預估費率及其樣式
        const nextRate = fullInfo.nextFundingRate;
        const nextStyle = nextRate !== null ? getFundingRateStyle(nextRate) : null;

        // 處理下次結算時間
        let nextDisplay = 'N/A';
        if (nextRate !== null) {
            nextDisplay = (nextRate >= 0 ? '+' : '') + nextRate.toFixed(4) + '%';
        } else if (fullInfo.nextFundingTime) {
            const now = Date.now();
            const nextTime = parseInt(fullInfo.nextFundingTime);
            const diffHours = Math.round((nextTime - now) / (1000 * 60 * 60));
            nextDisplay = `~${diffHours > 0 ? diffHours : 0}h`;
        }

        const div = document.createElement('div');
        div.className = "flex flex-col p-4 hover:bg-surfaceHighlight rounded-2xl transition group cursor-pointer border border-transparent hover:border-white/5 mb-2";
        div.onclick = () => { switchTab('chat'); quickAsk(`${item.symbol} funding rate`); };

        div.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-10 h-10 ${frStyle.bg || 'bg-surface'} rounded-xl flex items-center justify-center text-[10px] font-bold shrink-0 ${frStyle.color}">${item.symbol.substring(0, 2)}</div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-1.5">
                            <span class="font-bold text-sm text-secondary">${item.symbol}</span>
                            <span class="text-[9px] px-1 py-0.5 rounded ${frStyle.bg} ${frStyle.color} ${frStyle.border || 'border border-current/20'}">${frStyle.label}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-sm font-black ${frStyle.color}">${rate >= 0 ? '+' : ''}${rate.toFixed(4)}%</div>
                    <div class="text-[9px] text-textMuted uppercase tracking-tighter">Current</div>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-3 mt-2 pt-3 border-t border-white/5">
                <div class="flex flex-col">
                    <span class="text-[9px] text-textMuted">Next</span>
                    <span class="text-[10px] font-medium ${nextStyle ? nextStyle.color : 'text-textMuted'}">
                        ${nextDisplay}
                    </span>
                </div>
                <div class="text-right flex flex-col items-end">
                    <span class="text-[9px] text-textMuted">History</span>
                    <button onclick="event.stopPropagation(); showFundingHistory('${item.symbol}')"
                            class="text-[10px] text-primary hover:text-primary/80 hover:underline flex items-center gap-1 mt-0.5">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                        </svg>
                        Chart
                    </button>
                </div>
            </div>

            <!-- Progress bar -->
            <div class="w-full bg-background h-1.5 rounded-full mt-3 overflow-hidden" title="Range: ${fullInfo.minFundingRate || '?'}% ~ ${fullInfo.maxFundingRate || '?'}%">
                <div class="${rate >= 0 ? 'bg-primary' : 'bg-accent'} h-full rounded-full"
                     style="width: ${Math.min(100, (Math.abs(rate) / (rate >= 0 ? fullInfo.maxFundingRate : Math.abs(fullInfo.minFundingRate))) * 100)}%">
                </div>
            </div>
            <div class="flex justify-between text-[8px] text-textMuted/50 mt-1">
                <span>Min: ${fullInfo.minFundingRate !== undefined ? fullInfo.minFundingRate + '%' : 'N/A'}</span>
                <span>Max: ${fullInfo.maxFundingRate !== undefined ? fullInfo.maxFundingRate + '%' : 'N/A'}</span>
            </div>
        `;
        container.appendChild(div);
    });
}

// 顯示資金費率歷史圖表
async function showFundingHistory(symbol) {
    // 建立或獲取 Modal
    let modal = document.getElementById('funding-history-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'funding-history-modal';
        modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-sm hidden';
        modal.innerHTML = `
            <div class="bg-surface border border-white/5 rounded-3xl w-[90%] max-w-2xl p-6 shadow-2xl transform transition-all scale-95 opacity-0" id="funding-modal-content">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-xl font-serif text-secondary flex items-center gap-2">
                        <span id="history-symbol" class="text-primary"></span> Funding Rate History
                    </h3>
                    <button onclick="closeFundingHistory()" class="w-8 h-8 rounded-full bg-background flex items-center justify-center text-textMuted hover:text-secondary transition">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div class="h-64 w-full relative">
                    <canvas id="fundingHistoryChart"></canvas>
                </div>
                <div class="mt-4 text-center text-xs text-textMuted">
                    Last 100 settlement records (typically every 8 hours)
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // 顯示 Modal
    modal.classList.remove('hidden');
    // 動畫效果
    setTimeout(() => {
        const content = document.getElementById('funding-modal-content');
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);

    document.getElementById('history-symbol').innerText = symbol;

    // 獲取數據
    try {
        const url = `/api/funding-rate-history/${encodeURIComponent(symbol)}`;
        console.log(`Fetching history from: ${url}`); // Debug Log

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }

        const data = await res.json();

        if (data.data) {
            renderHistoryChart(data.data);
        } else {
            console.error('History data missing:', data);
            alert('無法獲取歷史數據: ' + (data.error || '未知錯誤'));
        }
    } catch (e) {
        console.error('Fetch failed:', e);
        alert('載入失敗，請檢查網絡或伺服器日誌');
    }
}

function closeFundingHistory() {
    const modal = document.getElementById('funding-history-modal');
    const content = document.getElementById('funding-modal-content');
    if (modal && content) {
        content.classList.remove('scale-100', 'opacity-100');
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => {
            modal.classList.add('hidden');
        }, 300);
    }
}

let historyChartInstance = null;

function renderHistoryChart(historyData) {
    const ctx = document.getElementById('fundingHistoryChart').getContext('2d');

    if (historyChartInstance) {
        historyChartInstance.destroy();
    }

    const labels = historyData.map(d => {
        const date = new Date(parseInt(d.time));
        return `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:00`;
    });

    const rates = historyData.map(d => d.rate);
    const colors = rates.map(r => r >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)');
    const borders = rates.map(r => r >= 0 ? 'rgba(34, 197, 94, 1)' : 'rgba(239, 68, 68, 1)');

    historyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '資金費率 (%)',
                data: rates,
                backgroundColor: colors,
                borderColor: borders,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: { color: '#94a3b8' },
                    beginAtZero: false
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        display: true,
                        color: '#64748b',
                        maxTicksLimit: 10
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#e2e8f0',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: function(context) {
                            return `費率: ${context.raw.toFixed(4)}%`;
                        }
                    }
                },
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'xy'
                    },
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'xy',
                    }
                }
            }
        }
    });
}
