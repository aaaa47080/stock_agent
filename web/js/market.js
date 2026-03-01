// ========================================
// market.js - 市場篩選功能
// ========================================
console.log('[Market] Script loading...');

// 資金費率快取
// 資金費率快取
var fundingRateData = {};
var isScreenerLoading = false;
var marketInitialized = false;
var isFirstLoad = true;

/**
 * Crypto 專區控制器
 * 管理 Market Watch 與 AI Pulse 的子標籤切換
 */
window.CryptoTab = {
    activeSubTab: 'market', // 'market' | 'pulse'

    switchSubTab: function (tabId) {
        if (this.activeSubTab === tabId) return;

        // 1. 更新按鈕選中狀態
        document.querySelectorAll('.crypto-sub-tab').forEach(btn => {
            if (btn.id === `crypto-tab-${tabId}`) {
                btn.classList.add('bg-primary', 'text-background', 'shadow-md');
                btn.classList.remove('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
            } else {
                btn.classList.remove('bg-primary', 'text-background', 'shadow-md');
                btn.classList.add('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
            }
        });

        // 2. 切換內容區域顯示
        const contentMarket = document.getElementById('crypto-content-market');
        const contentPulse = document.getElementById('crypto-content-pulse');

        if (contentMarket && contentPulse) {
            if (tabId === 'market') {
                contentMarket.classList.remove('hidden');
                contentPulse.classList.add('hidden');
            } else {
                contentMarket.classList.add('hidden');
                contentPulse.classList.remove('hidden');
            }
        }

        this.activeSubTab = tabId;

        // 3. 觸發對應的資料載入與 UI 更新
        this.refreshCurrent(true); // force refresh on switch usually isn't needed, but good for first time
    },

    refreshCurrent: function (isFirstLoadForTab = false) {
        if (this.activeSubTab === 'market') {
            if (typeof window.refreshScreener === 'function') {
                window.refreshScreener(isFirstLoadForTab);
            }
        } else if (this.activeSubTab === 'pulse') {
            if (typeof window.checkMarketPulse === 'function') {
                window.checkMarketPulse(false); // checkMarketPulse in pulse.js
            }
        }
    }
};

/**
 * 主要初始化函數 - 確保組件已注入並加載數據
 * 這是進入 Crypto 頁面時唯一需要調用的函數
 */
async function initCrypto() {
    console.log('[Crypto] initCrypto called');

    // 1. 確保組件已注入
    if (window.Components && !window.Components.isInjected('crypto')) {
        console.log('[Crypto] Injecting component...');
        await window.Components.inject('crypto');
    }

    // 2. 等待 DOM 元素出現
    let topList = document.getElementById('top-list');
    if (!topList) {
        for (let i = 0; i < 10; i++) {
            await new Promise(r => setTimeout(r, 50));
            topList = document.getElementById('top-list');
            if (topList) break;
        }
    }

    if (!topList) {
        console.error('[Crypto] top-list not found after injection!');
        return;
    }

    console.log('[Crypto] DOM ready, loading data...');
    marketInitialized = true;

    // 3. 加載數據
    // 先嘗試從 localStorage 載入保存的選擇，避免發送無效的預設請求
    if (typeof loadSavedSymbolSelection === 'function') {
        loadSavedSymbolSelection();
    } else {
        console.warn('[Crypto] loadSavedSymbolSelection not found! Check if filter.js is loaded.');
    }

    // Double check: 允許空列表，這會觸發後端的 "Auto" 模式 (返回市值前排行)
    if (!window.globalSelectedSymbols) {
        window.globalSelectedSymbols = [];
    }

    // 初期化時總是先載入當前 active 的 sub-tab
    window.CryptoTab.refreshCurrent();
}

window.initCrypto = initCrypto; // Export initCrypto for global usage

// Define refreshScreener before exporting it ensuring it is hoisted or available
// However, since it's an async function defined below, we might need to rely on var hoisting or assignment.
// Best practice for reloadable scripts: assign directly to window

window.refreshScreener = refreshScreener; // 確保 filter.js 與 HTML onclick 也能呼叫
window.showChart = showChart;
window.showFundingHistory = showFundingHistory;
var chart = null;
var candleSeries = null;
var volumeSeries = null;

// Chart state variables
// Chart state variables
var currentChartSymbol = null;
var currentChartInterval = '1h';
var autoRefreshEnabled = true; // 預設開啟即時更新
var autoRefreshTimer = null;
var chartKlinesData = []; // 儲存當前 K 線數據供更新用
var isChartHovered = false; // 追蹤圖表是否被懸停

// WebSocket 連接
// WebSocket 連接
// WebSocket 連接
var klineWebSocket = null;
var wsReconnectTimer = null;
var wsConnected = false;

// Market Watch WebSocket
// Market Watch WebSocket
var marketWsConnected = false;
var marketWebSocket = null;
var tickerReconnectTimer = null;
var subscribedTickerSymbols = new Set();
var pendingTickerSymbols = new Set(); // 等待連接後訂閱的 symbols

// 獲取資金費率數據
async function fetchFundingRates() {
    try {
        // 構建 URL，如果有選擇的幣種則傳遞給 API
        let url = '/api/funding-rates';
        if (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0) {
            // 過濾掉無效的符號（如 "PROGRESS" 等非幣種符號）
            const validSymbols = window.globalSelectedSymbols.filter(sym => {
                // 只接受看起來像幣種的符號（2-10個字母，不包含特殊詞彙）
                const invalidKeywords = ['PROGRESS', 'ALL', 'NONE', 'LOADING'];
                return sym &&
                    sym.length >= 2 &&
                    sym.length <= 10 &&
                    /^[A-Z0-9]+$/.test(sym) &&
                    !invalidKeywords.includes(sym.toUpperCase());
            });

            if (validSymbols.length > 0) {
                // 將選擇的幣種轉換為逗號分隔的字符串
                const symbolsParam = validSymbols.join(',');
                url += `?symbols=${encodeURIComponent(symbolsParam)}`;
                console.log(`[Funding] Fetching rates for selected symbols: ${symbolsParam}`);
            } else {
                console.log('[Funding] No valid symbols selected, fetching Top 10 extremes');
            }
        } else {
            console.log('[Funding] No symbols selected, fetching Top 10 extremes');
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error(res.statusText);
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

async function refreshScreener(showLoading = false, forceRefresh = false) {
    if (isScreenerLoading) return;

    let containers = {
        'top': document.getElementById('top-list'),
        'topGainers': document.getElementById('top-gainers-list'),
        'topLosers': document.getElementById('top-losers-list'),
        'highFunding': document.getElementById('high-funding-list'),
        'lowFunding': document.getElementById('low-funding-list')
    };

    // 如果主容器不存在，使用輪詢等待（最多等待 1 秒）
    if (!containers.top) {
        for (let i = 0; i < 10; i++) {
            await new Promise(resolve => setTimeout(resolve, 100));
            containers = {
                'top': document.getElementById('top-list'),
                'topGainers': document.getElementById('top-gainers-list'),
                'topLosers': document.getElementById('top-losers-list'),
                'highFunding': document.getElementById('high-funding-list'),
                'lowFunding': document.getElementById('low-funding-list')
            };
            if (containers.top) break;
        }
        if (!containers.top) {
            console.warn('[Market] top-list not found after waiting, skipping refreshScreener');
            return;
        }
    }
    console.log('[Market] containers found, loading data...');

    // 如果容器是空的，強制顯示 loading，確保用戶知道正在加載
    const isTopEmpty = containers.top && containers.top.children.length === 0;
    if (showLoading || isTopEmpty) {
        Object.values(containers).forEach(c => {
            if (c) c.innerHTML = '<div class="animate-pulse flex items-center gap-4 p-4"><div class="w-12 h-12 bg-surfaceHighlight rounded-2xl"></div><div class="flex-1 space-y-2"><div class="h-4 bg-surfaceHighlight rounded w-1/3"></div><div class="h-3 bg-surfaceHighlight rounded w-1/4"></div></div></div>';
        });
    }

    isScreenerLoading = true;

    try {
        const body = {
            exchange: window.currentFilterExchange || 'okx',
            refresh: forceRefresh
        };
        if (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0) {
            body.symbols = window.globalSelectedSymbols;
        }
        // 獨立處理兩個請求，互不影響
        // 1. Fetch Screener Data
        // 獨立處理兩個請求，互不影響，並且不使用 Promise.all 阻塞
        // 1. Fetch Screener Data (Fast)
        fetch('/api/screener', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
            .then(async res => {
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({ detail: res.statusText }));
                    throw new Error(errData.detail || `Server Error: ${res.status}`);
                }
                return res.json();
            })
            .then(screenerData => {
                // --- 處理篩選器結果 (Screener) ---
                if (screenerData && !screenerData.error) {
                    // [Optimization] Auto-populate filter from VOLUME leaders (Hot)
                    if (!window.globalSelectedSymbols || window.globalSelectedSymbols.length === 0) {
                        const sourceList = screenerData.top_volume || screenerData.top_gainers;
                        if (sourceList && sourceList.length > 0) {
                            var top5 = sourceList.slice(0, 5);
                            window.globalSelectedSymbols = top5.map(function (item) { return item.Symbol; });

                            var indicator = document.getElementById('active-filter-indicator');
                            var filterCount = document.getElementById('filter-count');
                            var globalCount = document.getElementById('global-count-badge');
                            // [Sync] Update Pulse Tab Indicators too
                            var pulseIndicator = document.getElementById('active-pulse-filter-indicator');
                            var pulseFilterCount = document.getElementById('pulse-filter-count');
                            var pulseBadge = document.getElementById('pulse-count-badge');

                            if (filterCount) filterCount.innerText = window.globalSelectedSymbols.length;
                            if (globalCount) globalCount.innerText = window.globalSelectedSymbols.length;
                            if (pulseFilterCount) pulseFilterCount.innerText = window.globalSelectedSymbols.length;
                            if (pulseBadge) pulseBadge.innerText = window.globalSelectedSymbols.length;
                        }
                    }

                    // Update UI indicators
                    var count = (window.globalSelectedSymbols || []).length;
                    // ... (省略部分 UI 更新代碼以保持簡潔，主要邏輯不變) ...

                    if (screenerData.last_updated) {
                        const date = new Date(screenerData.last_updated);
                        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                        const lastUpdatedEl = document.getElementById('screener-last-updated');
                        if (lastUpdatedEl) lastUpdatedEl.textContent = `(更新於: ${timeStr})`;
                    }

                    const topCount = screenerData.top_volume ? screenerData.top_volume.length : 0;
                    console.log(`[Market] Loaded ${topCount} items.`);

                    // 即使篩選後為空，也不要視為錯誤，而是渲染空列表
                    const displayList = screenerData.top_volume || [];
                    renderList(containers.top, displayList.slice(0, 5), 'price_change_24h', '%');

                    renderList(containers.topGainers, screenerData.top_gainers || [], 'price_change_24h', '%');
                    renderList(containers.topLosers, screenerData.top_losers || [], 'price_change_24h', '%');

                    if (topCount === 0) {
                        console.warn('[Market] Filter returned 0 items. Selected symbols:', window.globalSelectedSymbols);
                    }
                } else {
                    throw new Error(screenerData?.message || 'Unknown error');
                }
            })
            .catch(err => {
                console.error("Screener Load Failed:", err.message);

                // CRITICAL FIX: Don't clear UI if this was a background refresh (showLoading=false)
                // Only clear and show error if it was a user-initiated or initial load
                if (showLoading || isTopEmpty) {
                    ['top', 'topGainers', 'topLosers'].forEach(key => {
                        if (containers[key]) {
                            containers[key].innerHTML = `
                            <div class="flex flex-col items-center justify-center py-8 text-center text-red-400">
                                <i data-lucide="wifi-off" class="w-8 h-8 mb-2 opacity-50"></i>
                                <span class="text-sm font-medium">載入失敗</span>
                                <div class="text-xs opacity-50 mt-1 mb-2">${err.message}</div>
                                <button onclick="window.refreshScreener(true, true)" class="text-xs bg-red-500/10 hover:bg-red-500/20 px-3 py-1 rounded-full transition">重試</button>
                            </div>`;
                        }
                    });
                    if (window.lucide) window.lucide.createIcons();
                } else {
                    // Background refresh failed - just log it, don't destroy existing data
                    console.warn('[Market] Background refresh failed, keeping existing data.');
                }
            })
            .finally(() => {
                // Screener loaded, stop main loading spinner
                isScreenerLoading = false;
            });

    } catch (e) {
        console.error("Critical Refresh Error:", e);
        isScreenerLoading = false;
    }

    // 2. Fetch Funding Rates (Completely Independent & Non-Blocking)
    // Show loading state immediately
    if (containers.highFunding && containers.lowFunding) {
        const loadingSkeleton = `
            <div class="animate-pulse space-y-3">
                <div class="bg-surfaceHighlight/50 h-16 rounded-2xl"></div>
                <div class="bg-surfaceHighlight/50 h-16 rounded-2xl"></div>
                <div class="bg-surfaceHighlight/50 h-16 rounded-2xl"></div>
            </div>
        `;
        containers.highFunding.innerHTML = loadingSkeleton;
        containers.lowFunding.innerHTML = loadingSkeleton;
    }

    // Fetch funding rates asynchronously without blocking
    fetchFundingRates().then(fundingData => {
        if (fundingData) {
            if (containers.highFunding && containers.lowFunding) {
                renderFundingRateList(containers.highFunding, fundingData.top_bullish, 'high');
                renderFundingRateList(containers.lowFunding, fundingData.top_bearish, 'low');
            }
        } else {
            // Funding Rate 失敗 - 顯示錯誤訊息
            ['highFunding', 'lowFunding'].forEach(key => {
                if (containers[key]) {
                    containers[key].innerHTML = `<div class="text-center py-4 text-xs text-textMuted opacity-50">暫無數據</div>`;
                }
            });
        }
    }).catch(err => {
        console.error('Funding rate fetch error:', err);
        ['highFunding', 'lowFunding'].forEach(key => {
            if (containers[key]) {
                containers[key].innerHTML = `<div class="text-center py-4 text-xs text-red-400 opacity-50">載入失敗</div>`;
            }
        });
    });
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
        container.innerHTML = '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">No signals detected</p>';
        return;
    }

    // 收集所有 symbols 以便訂閱 WebSocket
    const symbolsToSubscribe = [];

    items.forEach(item => {
        const val = parseFloat(item[key]);
        let signalsHtml = '';
        if (item.signals && Array.isArray(item.signals)) {
            item.signals.forEach(sig => {
                let colorClass = 'text-secondary bg-white/5';
                if (sig.includes('突破')) colorClass = 'text-accent bg-accent/10';
                else if (sig.includes('爆量') || sig.includes('金叉')) colorClass = 'text-primary bg-primary/10';
                else if (sig.includes('抄底')) colorClass = 'text-success bg-success/10';
                signalsHtml += `<span class="text-[8px] px-1.5 py-0.5 rounded-md ${colorClass} border border-white/5 uppercase font-bold tracking-tighter">${sig.replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, '')}</span>`;
            });
        }

        // RSI 能量條視覺化
        let rsiVisual = '';
        if (key === 'RSI_14') {
            const rsiColor = val > 70 ? 'bg-danger' : (val < 30 ? 'bg-success' : 'bg-primary/40');
            rsiVisual = `
                <div class="w-full h-1 bg-white/5 rounded-full mt-2 overflow-hidden flex">
                    <div class="h-full ${rsiColor} transition-all duration-1000" style="width: ${val}%"></div>
                </div>
            `;
        }

        const div = document.createElement('div');
        div.className = "group relative bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer overflow-hidden";
        div.dataset.symbol = item.Symbol; // 添加 data-symbol 屬性
        div.onclick = () => { showChart(item.Symbol); };

        // 收集 symbol 用於 WebSocket 訂閱
        symbolsToSubscribe.push(item.Symbol);

        div.innerHTML = `
            <div class="flex items-center justify-between gap-4">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-xs font-bold text-primary border border-white/5 group-hover:scale-110 transition-transform">${item.Symbol.substring(0, 2)}</div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-base text-secondary truncate">${item.Symbol}</span>
                        </div>
                        <div class="text-[11px] text-textMuted font-mono opacity-80 ticker-price">$${formatPrice(item.Close)}</div>
                    </div>
                </div>

                <div class="text-right">
                    <div class="text-base font-black ticker-change ${key === 'RSI_14' ? (val > 70 ? 'text-danger' : (val < 30 ? 'text-success' : 'text-secondary')) : (val > 0 ? 'text-success' : 'text-danger')}">
                        ${val > 0 && key !== 'RSI_14' ? '+' : ''}${val.toFixed(2)}${unit}
                    </div>
                    <div class="flex flex-wrap justify-end gap-1 mt-1">
                        ${hasSignals(item) ? signalsHtml : `<span class="text-[9px] text-textMuted uppercase opacity-40 font-bold">${key === 'RSI_14' ? 'RSI Index' : '24H Perf'}</span>`}
                    </div>
                </div>
            </div>
            ${rsiVisual}
        `;
        container.appendChild(div);
    });

    // 訂閱 WebSocket 即時更新
    if (symbolsToSubscribe.length > 0 && window.subscribeTickerSymbols) {
        window.subscribeTickerSymbols(symbolsToSubscribe);
    }
}

function hasSignals(item) {
    return item.signals && Array.isArray(item.signals) && item.signals.length > 0;
}

function renderFundingRateList(container, items, type) {
    if (!container) return;
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">No data</p>';
        return;
    }

    items.forEach(item => {
        const rate = item.fundingRate;
        const frStyle = getFundingRateStyle(rate);
        const isPaying = rate > 0;

        const div = document.createElement('div');
        div.className = "group bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer";
        // User Request: Clicking the card should open Funding History, not K-Line Chart
        div.onclick = () => { showFundingHistory(item.symbol); };

        div.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-[10px] font-bold ${frStyle.color} border border-white/5 group-hover:rotate-12 transition-transform">${item.symbol.substring(0, 2)}</div>
                    <div>
                        <div class="font-bold text-sm text-secondary">${item.symbol}</div>
                        <div class="text-[9px] flex items-center gap-1 mt-0.5">
                            <span class="${isPaying ? 'text-danger' : 'text-success'} font-bold uppercase tracking-tighter">${isPaying ? 'Longs Paying' : 'Shorts Paying'}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-base font-mono font-black ${frStyle.color}">${rate >= 0 ? '+' : ''}${rate.toFixed(4)}%</div>
                    <button onclick="event.stopPropagation(); showFundingHistory('${item.symbol}')" class="text-[10px] text-primary/60 hover:text-primary mt-1 flex items-center justify-end gap-1 ml-auto font-bold uppercase tracking-widest">
                        History <i data-lucide="bar-chart-2" class="w-3 h-3"></i>
                    </button>
                </div>
            </div>
        `;
        container.appendChild(div);
        lucide.createIcons({ root: div });
    });
}

// 顯示資金費率歷史圖表
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
                    <!-- Loading/Error Overlay -->
                    <div id="funding-chart-overlay" class="absolute inset-0 flex items-center justify-center bg-surface/80 backdrop-blur-sm hidden z-10">
                        <div id="funding-overlay-content" class="text-center"></div>
                    </div>
                </div>
                <div class="mt-4 text-center text-xs text-textMuted">
                    最近 14 天的資金費率記錄 (每 8 小時結算一次)
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

    const symbolEl = document.getElementById('history-symbol');
    if (symbolEl) symbolEl.innerText = symbol;

    // 清空舊圖表（如果不銷毀，Chart.js 可能會報錯或顯示舊數據）
    if (historyChartInstance) {
        historyChartInstance.destroy();
        historyChartInstance = null;
    }

    // 獲取 Overlay 元素
    const overlay = document.getElementById('funding-chart-overlay');
    const overlayContent = document.getElementById('funding-overlay-content');

    try {
        const url = `/api/funding-rate-history/${encodeURIComponent(symbol)}`;
        console.log(`Fetching history from: ${url}`);

        // Show loading state using overlay
        if (overlay && overlayContent) {
            overlay.classList.remove('hidden');
            overlayContent.innerHTML = '<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div><div class="text-xs text-textMuted">載入數據中...</div>';
        }

        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }

        const data = await res.json();

        if (data.data && data.data.length > 0) {
            // Hide overlay on success
            if (overlay) overlay.classList.add('hidden');
            renderHistoryChart(data.data);
        } else if (data.error) {
            console.error('API returned error:', data.error);
            if (overlay && overlayContent) {
                overlayContent.innerHTML = `<div class="text-red-400 text-sm">載入失敗<br><span class="text-xs opacity-70">${data.error}</span></div>`;
            }
        } else {
            console.error('History data missing:', data);
            if (overlay && overlayContent) {
                overlayContent.innerHTML = '<div class="text-red-400 text-sm">無歷史數據可用</div>';
            }
        }
    } catch (e) {
        console.error('Fetch failed:', e);
        if (overlay && overlayContent) {
            overlayContent.innerHTML = `<div class="text-red-400 text-sm">載入失敗<br><span class="text-xs opacity-70">${e.message}</span></div>`;
        }
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

var historyChartInstance = null;

function renderHistoryChart(historyData) {
    const ctx = document.getElementById('fundingHistoryChart').getContext('2d');

    if (historyChartInstance) {
        historyChartInstance.destroy();
    }

    const labels = historyData.map(d => {
        const date = new Date(parseInt(d.time));
        return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
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
                        label: function (context) {
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

// ========================================
// Chart Functionality (Moved from Watchlist)
// ========================================

// 根據價格大小決定小數位
function getPriceDecimals(price) {
    const p = Math.abs(price);
    if (p >= 1000) return 2;
    if (p >= 1) return 2;
    if (p >= 0.01) return 4;
    if (p >= 0.0001) return 6;
    return 8;
}

// 格式化價格顯示
function formatChartPrice(price, decimals) {
    return price.toFixed(decimals);
}

// 格式化成交量顯示
function formatVolume(vol) {
    if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
    if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
    if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
    return vol.toFixed(2);
}

// 更新 OHLCV 顯示
function updateOHLCVDisplay(kline, openEl, highEl, lowEl, closeEl, volEl, decimals) {
    if (!kline) return;

    const isUp = kline.close >= kline.open;
    const color = isUp ? 'text-success' : 'text-danger';

    if (openEl) openEl.textContent = formatChartPrice(kline.open, decimals);
    if (highEl) highEl.textContent = formatChartPrice(kline.high, decimals);
    if (lowEl) lowEl.textContent = formatChartPrice(kline.low, decimals);
    if (closeEl) {
        closeEl.textContent = formatChartPrice(kline.close, decimals);
        closeEl.className = color;
    }
    if (volEl && kline.volume !== undefined) {
        volEl.textContent = formatVolume(kline.volume);
    }
}

async function showChart(symbol, interval = null) {
    const symbolChanged = symbol && symbol !== currentChartSymbol;
    const intervalChanged = interval && interval !== currentChartInterval;

    if (symbol) currentChartSymbol = symbol;
    if (interval) currentChartInterval = interval;

    // 如果 WebSocket 已連接且幣種或週期改變，重新訂閱
    if (autoRefreshEnabled && wsConnected && (symbolChanged || intervalChanged)) {
        unsubscribeKline();
        setTimeout(() => subscribeKline(currentChartSymbol, currentChartInterval), 100);
    }

    // 自動啟動即時更新（如果預設開啟但尚未連接）
    if (autoRefreshEnabled && !wsConnected) {
        startAutoRefresh();
    }

    // 確保按鈕狀態正確更新
    updateWsStatus(wsConnected);

    // 更新時間顯示
    const updatedEl = document.getElementById('chart-updated');
    if (updatedEl) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        // Only update if it's not already showing LIVE status
        if (!updatedEl.textContent.includes('即時')) {
            updatedEl.textContent = `更新: ${timeStr}`;
        }
    }

    // Update active button state
    document.querySelectorAll('.chart-interval-btn').forEach(btn => {
        if (btn.dataset.interval === currentChartInterval) {
            btn.classList.add('bg-white/10', 'text-primary');
            btn.classList.remove('text-textMuted');
        } else {
            btn.classList.remove('bg-white/10', 'text-primary');
            btn.classList.add('text-textMuted');
        }
    });

    const chartSection = document.getElementById('chart-section');
    const chartContainer = document.getElementById('chart-container');
    const volumeContainer = document.getElementById('volume-container');

    if (!chartSection || !chartContainer) {
        console.error("Chart DOM elements missing");
        return;
    }

    chartSection.classList.remove('hidden');
    lucide.createIcons();

    const titleEl = document.getElementById('chart-title');
    if (titleEl) titleEl.textContent = `${currentChartSymbol} (${currentChartInterval.toUpperCase()})`;

    // 更新自動更新按鈕狀態
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');
    if (autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-primary', 'bg-primary/10');
            btn.classList.remove('text-textMuted');
        }
        if (status) status.textContent = wsConnected ? 'LIVE' : '連接中...';
    }

    chartContainer.innerHTML = '<div class="animate-pulse text-textMuted h-full flex items-center justify-center">載入數據中...</div>';
    if (volumeContainer) { volumeContainer.innerHTML = ''; volumeContainer.style.display = ''; }

    try {
        const res = await fetch('/api/klines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: currentChartSymbol,
                interval: currentChartInterval,
                limit: 200
            })
        });
        const data = await res.json();

        if (!data.klines || data.klines.length === 0) {
            chartContainer.innerHTML = '<div class="text-danger h-full flex items-center justify-center">無法載入數據</div>';
            return;
        }

        // 更新時間顯示
        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl && data.updated_at) {
            const date = new Date(data.updated_at);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            updatedEl.textContent = `更新: ${timeStr}`;
        }

        // 計算價格精度
        const samplePrice = data.klines[data.klines.length - 1]?.close || 1;
        const priceDecimals = getPriceDecimals(samplePrice);

        chartContainer.innerHTML = '';
        if (chart) chart.remove();

        // chart-container has CSS h-[52vh], read actual rendered height with fallback
        const chartHeight = chartContainer.clientHeight || Math.floor(window.innerHeight * 0.52);

        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartHeight,
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: 'rgba(51, 65, 85, 0.3)' }, horzLines: { color: 'rgba(51, 65, 85, 0.3)' } },
            timeScale: { borderColor: '#334155', timeVisible: true },
            rightPriceScale: { autoScale: true, scaleMargins: { top: 0.1, bottom: 0.1 } },
            handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
            handleScale: { axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: { time: true, price: true }, mouseWheel: true, pinch: true },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal }
        });

        candleSeries = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            borderDownColor: '#ef4444',
            priceFormat: { type: 'price', precision: priceDecimals, minMove: Math.pow(10, -priceDecimals) }
        });
        candleSeries.setData(data.klines);

        // 儲存 klines 數據以便 crosshair 查詢
        const klinesMap = {};
        data.klines.forEach(k => { klinesMap[k.time] = k; });

        // Remove old volume chart reference
        if (window.volumeChart) {
            window.volumeChart.remove();
            window.volumeChart = null;
        }

        // Populate volume data
        const volumeData = data.klines.map(k => ({
            time: k.time,
            value: k.volume || 0,
            color: k.close >= k.open ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)'
        }));

        // Create separate volume chart
        if (volumeContainer) {
            window.volumeChart = LightweightCharts.createChart(volumeContainer, {
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8' },
                grid: { vertLines: { color: 'rgba(51, 65, 85, 0.2)' }, horzLines: { color: 'rgba(51, 65, 85, 0.1)' } },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: '#334155', scaleMargins: { top: 0.1, bottom: 0.05 } },
                timeScale: { visible: false },
                handleScroll: { mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false },
                handleScale: { mouseWheel: false, pinchScale: false },
            });
            volumeSeries = window.volumeChart.addHistogramSeries({ priceFormat: { type: 'volume' } });
            volumeSeries.setData(volumeData);
            // Sync time scales
            let _syncingRange = false;
            chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (_syncingRange || !range || !window.volumeChart) return;
                _syncingRange = true;
                window.volumeChart.timeScale().setVisibleLogicalRange(range);
                _syncingRange = false;
            });
            window.volumeChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (_syncingRange || !range || !chart) return;
                _syncingRange = true;
                chart.timeScale().setVisibleLogicalRange(range);
                _syncingRange = false;
            });
        }

        chart.timeScale().fitContent();

        // 監聽 Resize 事件以動態調整佈局 (使用 requestAnimationFrame 優化性能)
        let resizeFrame = null;
        const adaptiveResizeHandler = () => {
            if (resizeFrame) cancelAnimationFrame(resizeFrame);

            resizeFrame = requestAnimationFrame(() => {
                if (!chart || !chartContainer) return;
                chart.applyOptions({ width: chartContainer.clientWidth });
                if (window.volumeChart && volumeContainer) {
                    window.volumeChart.applyOptions({ width: volumeContainer.clientWidth });
                }
            });
        };

        // Remove old listeners to prevent duplicates
        if (window._marketResizeHandler) {
            window.removeEventListener('resize', window._marketResizeHandler);
        }
        window._marketResizeHandler = adaptiveResizeHandler;
        window.addEventListener('resize', adaptiveResizeHandler);

        // Crosshair 移動時更新 OHLCV 資訊
        chart.subscribeCrosshairMove(param => {
            const infoOpen = document.getElementById('info-open');
            const infoHigh = document.getElementById('info-high');
            const infoLow = document.getElementById('info-low');
            const infoClose = document.getElementById('info-close');
            const infoVolume = document.getElementById('info-volume');
            const currentPriceDisplay = document.getElementById('current-price-display');

            if (!param.time || !param.seriesData) {
                // 滑鼠離開圖表，顯示最新數據
                isChartHovered = false;
                const lastKline = data.klines[data.klines.length - 1];
                if (lastKline) {
                    updateOHLCVDisplay(lastKline, infoOpen, infoHigh, infoLow, infoClose, infoVolume, priceDecimals);

                    // 恢復顯示最新價格
                    if (currentPriceDisplay) {
                        const formattedPrice = lastKline.close.toFixed(priceDecimals);
                        const isUp = lastKline.close >= lastKline.open;
                        currentPriceDisplay.textContent = `$${formattedPrice}`;
                        currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                    }
                }
                if (window.volumeChart) window.volumeChart.clearCrosshairPosition();
                return;
            }

            // 滑鼠在圖表上，顯示懸停位置的數據
            isChartHovered = true;
            const kline = klinesMap[param.time];
            if (kline) {
                updateOHLCVDisplay(kline, infoOpen, infoHigh, infoLow, infoClose, infoVolume, priceDecimals);

                // 顯示懸停位置的價格
                if (currentPriceDisplay) {
                    const formattedPrice = kline.close.toFixed(priceDecimals);
                    const isUp = kline.close >= kline.open;
                    currentPriceDisplay.textContent = `$${formattedPrice}`;
                    currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                }
                // Sync crosshair to volume chart
                if (window.volumeChart && volumeSeries && kline.volume != null) {
                    window.volumeChart.setCrosshairPosition(kline.volume, param.time, volumeSeries);
                }
            }
        });

        // Store the latest kline for reference when not hovering
        const latestKline = data.klines[data.klines.length - 1];
        if (latestKline) {
            // Store for later use when WebSocket updates come in
            window.currentChartKlines = data.klines; // Keep track of current klines
            window.currentChartPriceDecimals = priceDecimals; // Keep track of current decimals
        }

        // 初始顯示最新 K 線數據
        const lastKline = data.klines[data.klines.length - 1];
        if (lastKline) {
            updateOHLCVDisplay(
                lastKline,
                document.getElementById('info-open'),
                document.getElementById('info-high'),
                document.getElementById('info-low'),
                document.getElementById('info-close'),
                document.getElementById('info-volume'),
                priceDecimals
            );

            // 顯示大尺寸當前價格
            const currentPriceDisplay = document.getElementById('current-price-display');
            if (currentPriceDisplay) {
                const formattedPrice = lastKline.close.toFixed(priceDecimals);
                const isUp = lastKline.close >= lastKline.open;
                currentPriceDisplay.textContent = `$${formattedPrice}`;
                currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
            }
        }

        // 追蹤當前價格軸邊距
        let currentMargins = { top: 0.1, bottom: 0.1 };

        // 自定義滾輪行為
        chartContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = chartContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const chartWidth = rect.width;
            const chartHeight = rect.height;
            const priceScaleWidth = 70;
            const timeScaleHeight = 30;

            const zoomIn = e.deltaY < 0;
            const factor = zoomIn ? 0.9 : 1.1;

            if (x > chartWidth - priceScaleWidth) {
                chart.priceScale('right').applyOptions({ autoScale: false });
                const adjustment = zoomIn ? -0.03 : 0.03;
                currentMargins.top = Math.max(0.02, Math.min(0.4, currentMargins.top + adjustment));
                currentMargins.bottom = Math.max(0.02, Math.min(0.4, currentMargins.bottom + adjustment));
                chart.priceScale('right').applyOptions({
                    scaleMargins: { top: currentMargins.top, bottom: currentMargins.bottom }
                });
            } else if (y > chartHeight - timeScaleHeight) {
                const timeScale = chart.timeScale();
                const range = timeScale.getVisibleLogicalRange();
                if (range) {
                    const center = (range.from + range.to) / 2;
                    const halfRange = (range.to - range.from) / 2 * factor;
                    timeScale.setVisibleLogicalRange({ from: center - halfRange, to: center + halfRange });
                }
            } else {
                chart.priceScale('right').applyOptions({ autoScale: true });
                currentMargins = { top: 0.1, bottom: 0.1 };
                const timeScale = chart.timeScale();
                const range = timeScale.getVisibleLogicalRange();
                if (range) {
                    const center = (range.from + range.to) / 2;
                    const halfRange = (range.to - range.from) / 2 * factor;
                    timeScale.setVisibleLogicalRange({ from: center - halfRange, to: center + halfRange });
                }
            }
        }, { passive: false });

        // 雙擊重置
        chartContainer.addEventListener('dblclick', () => {
            chart.priceScale('right').applyOptions({ autoScale: true });
            currentMargins = { top: 0.1, bottom: 0.1 };
            chart.timeScale().fitContent();
        });

        // Auto-resize handler is now managed inside showChart for adaptive logic
        /* 
        const resizeHandler = () => { ... } 
        window.addEventListener('resize', resizeHandler);
        */

    } catch (err) {
        console.error(err);
        chartContainer.innerHTML = '<div class="text-danger h-full flex items-center justify-center">連線錯誤</div>';
    }
}

// 關閉圖表
function closeChart() {
    const chartSection = document.getElementById('chart-section');
    if (chartSection) {
        chartSection.classList.add('hidden');
    }
    // 停止自動更新
    stopAutoRefresh();
    // 清理圖表資源
    if (window.volumeChart) {
        window.volumeChart.remove();
        window.volumeChart = null;
    }
}

function changeChartInterval(interval) {
    if (!currentChartSymbol) return;

    // 如果 WebSocket 已連接，重新訂閱新的時間週期
    if (autoRefreshEnabled && wsConnected) {
        unsubscribeKline();
        currentChartInterval = interval;
        subscribeKline(currentChartSymbol, interval);
    }

    showChart(currentChartSymbol, interval);
}

// ========================================
// WebSocket 即時更新功能
// ========================================

function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/klines`;
}

function connectWebSocket() {
    if (klineWebSocket && klineWebSocket.readyState === WebSocket.OPEN) {
        return;
    }

    const wsUrl = getWebSocketUrl();
    console.log('連接 WebSocket:', wsUrl);

    try {
        klineWebSocket = new WebSocket(wsUrl);

        klineWebSocket.onopen = () => {
            console.log('WebSocket 連接成功');
            wsConnected = true;
            updateWsStatus(true);

            // 如果已經有訂閱，重新訂閱
            if (currentChartSymbol && autoRefreshEnabled) {
                subscribeKline(currentChartSymbol, currentChartInterval);
            }

            // Start live time updates when WebSocket is connected and auto-refresh is enabled
            if (autoRefreshEnabled) {
                startLiveTimeUpdates();
            }
        };

        klineWebSocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error('WebSocket 消息解析錯誤:', e);
            }
        };

        klineWebSocket.onclose = (event) => {
            console.log('WebSocket 連接關閉:', event.code, event.reason);
            wsConnected = false;
            updateWsStatus(false);
            stopLiveTimeUpdates(); // Stop live time updates when disconnected

            // 自動重連
            if (autoRefreshEnabled) {
                wsReconnectTimer = setTimeout(() => {
                    console.log('嘗試重新連接 WebSocket...');
                    connectWebSocket();
                }, 3000);
            }
        };

        klineWebSocket.onerror = (error) => {
            console.error('WebSocket 錯誤:', error);
            wsConnected = false;
            updateWsStatus(false);
        };

    } catch (e) {
        console.error('WebSocket 連接失敗:', e);
    }
}

function disconnectWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    if (klineWebSocket) {
        klineWebSocket.close();
        klineWebSocket = null;
    }
    wsConnected = false;
}

function subscribeKline(symbol, interval) {
    if (!klineWebSocket || klineWebSocket.readyState !== WebSocket.OPEN) {
        console.warn('WebSocket 未連接，無法訂閱');
        return;
    }

    klineWebSocket.send(JSON.stringify({
        action: 'subscribe',
        symbol: symbol,
        interval: interval
    }));
    console.log(`訂閱: ${symbol} ${interval}`);
}

function unsubscribeKline() {
    if (!klineWebSocket || klineWebSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    klineWebSocket.send(JSON.stringify({ action: 'unsubscribe' }));
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'kline':
            updateChartWithKline(message.data);
            break;
        case 'subscribed':
            console.log(`已訂閱: ${message.symbol} ${message.interval}`);
            break;
        case 'unsubscribed':
            console.log('已取消訂閱');
            break;
        case 'pong':
            // 心跳回應
            break;
        case 'error':
            console.error('WebSocket 錯誤:', message.message);
            break;
    }
}

function updateChartWithKline(kline) {
    if (!chart || !candleSeries) return;

    // 更新或添加 K 線
    const klineData = {
        time: kline.time,
        open: kline.open,
        high: kline.high,
        low: kline.low,
        close: kline.close
    };

    // 使用 update 方法更新最新 K 線
    candleSeries.update(klineData);

    // 更新成交量
    if (volumeSeries && kline.volume !== undefined) {
        volumeSeries.update({
            time: kline.time,
            value: kline.volume,
            color: kline.close >= kline.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'
        });
    }

    // 更新大尺寸當前價格顯示
    const currentPriceDisplay = document.getElementById('current-price-display');
    if (currentPriceDisplay) {
        const priceDecimals = getPriceDecimals(kline.close);
        const formattedPrice = kline.close.toFixed(priceDecimals);
        const isUp = kline.close >= kline.open;
        currentPriceDisplay.textContent = `$${formattedPrice}`;
        currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
    }

    // 更新時間顯示
    const updatedEl = document.getElementById('chart-updated');
    if (updatedEl) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        updatedEl.textContent = `即時 ${timeStr}`;
    }

    // 更新 OHLCV 顯示 (僅在圖表未被懸停時)
    if (!isChartHovered) {
        const priceDecimals = getPriceDecimals(kline.close);
        updateOHLCVDisplay(
            kline,
            document.getElementById('info-open'),
            document.getElementById('info-high'),
            document.getElementById('info-low'),
            document.getElementById('info-close'),
            document.getElementById('info-volume'),
            priceDecimals
        );
    }

    // 更新存儲的 K 線數據，以便在未懸停時顯示最新數據
    if (window.currentChartKlines && window.currentChartKlines.length > 0) {
        // 更新最後一根 K 線
        const lastIdx = window.currentChartKlines.length - 1;
        if (window.currentChartKlines[lastIdx].time === kline.time) {
            window.currentChartKlines[lastIdx] = kline;
        } else {
            // 如果是新時間的 K 線，添加到末尾
            window.currentChartKlines.push(kline);
            // 保持最多 200 根 K 線
            if (window.currentChartKlines.length > 200) {
                window.currentChartKlines.shift();
            }
        }
    }
}

function updateWsStatus(connected) {
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');

    if (connected && autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-success', 'bg-success/10');
            btn.classList.remove('text-primary', 'bg-primary/10', 'text-textMuted');
        }
        if (status) status.textContent = 'LIVE';
    } else if (autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-warning', 'bg-warning/10');
            btn.classList.remove('text-success', 'bg-success/10', 'text-textMuted');
        }
        if (status) status.textContent = '...';
    }
}

// Timer for updating live time display
let liveTimeUpdateTimer = null;

function startLiveTimeUpdates() {
    if (liveTimeUpdateTimer) {
        clearInterval(liveTimeUpdateTimer);
    }

    liveTimeUpdateTimer = setInterval(() => {
        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl && wsConnected && autoRefreshEnabled) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            updatedEl.textContent = `即時 ${timeStr}`;
        }
    }, 1000); // Update every second
}

function stopLiveTimeUpdates() {
    if (liveTimeUpdateTimer) {
        clearInterval(liveTimeUpdateTimer);
        liveTimeUpdateTimer = null;
    }
}

// 自動更新功能（使用 WebSocket）
function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');

    if (autoRefreshEnabled) {
        btn.classList.add('text-primary', 'bg-primary/10');
        btn.classList.remove('text-textMuted');
        status.textContent = '連接中...';
        startAutoRefresh();
    } else {
        btn.classList.remove('text-primary', 'bg-primary/10', 'text-success', 'bg-success/10', 'text-warning', 'bg-warning/10');
        btn.classList.add('text-textMuted');
        status.textContent = 'OFF';
        stopAutoRefresh();
    }
}

function startAutoRefresh() {
    // 連接 WebSocket
    connectWebSocket();

    // 訂閱當前幣種
    if (currentChartSymbol) {
        // 等待連接建立後訂閱
        const checkConnection = setInterval(() => {
            if (wsConnected) {
                subscribeKline(currentChartSymbol, currentChartInterval);
                clearInterval(checkConnection);
                // Start live time updates when connection is established
                startLiveTimeUpdates();
            }
        }, 100);

        // 5秒後停止檢查
        setTimeout(() => clearInterval(checkConnection), 5000);
    }
}

function stopAutoRefresh() {
    unsubscribeKline();
    disconnectWebSocket();
    stopLiveTimeUpdates(); // Stop live time updates when auto-refresh stops

    autoRefreshEnabled = false;
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');
    if (btn) {
        btn.classList.remove('text-primary', 'bg-primary/10', 'text-success', 'bg-success/10', 'text-warning', 'bg-warning/10');
        btn.classList.add('text-textMuted');
    }
    if (status) status.textContent = 'OFF';
}

// 保留輪詢作為備用方案
async function refreshChartData() {
    if (!currentChartSymbol || !chart || !candleSeries) return;

    try {
        const res = await fetch('/api/klines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: currentChartSymbol,
                interval: currentChartInterval,
                limit: 200
            })
        });
        const data = await res.json();

        if (!data.klines || data.klines.length === 0) return;

        candleSeries.setData(data.klines);
        chartKlinesData = data.klines;

        if (volumeSeries) {
            const volumeData = data.klines.map(k => ({
                time: k.time,
                value: k.volume || 0,
                color: k.close >= k.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'
            }));
            volumeSeries.setData(volumeData);
        }

        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            updatedEl.textContent = `更新: ${timeStr}`;
        }

        const lastKline = data.klines[data.klines.length - 1];
        if (lastKline) {
            const priceDecimals = getPriceDecimals(lastKline.close);
            // 更新 OHLCV 顯示 (僅在圖表未被懸停時)
            if (!isChartHovered) {
                updateOHLCVDisplay(
                    lastKline,
                    document.getElementById('info-open'),
                    document.getElementById('info-high'),
                    document.getElementById('info-low'),
                    document.getElementById('info-close'),
                    document.getElementById('info-volume'),
                    priceDecimals
                );

                // 更新大尺寸當前價格顯示 (僅在圖表未被懸停時)
                const currentPriceDisplay = document.getElementById('current-price-display');
                if (currentPriceDisplay) {
                    const formattedPrice = lastKline.close.toFixed(priceDecimals);
                    const isUp = lastKline.close >= lastKline.open;
                    currentPriceDisplay.textContent = `$${formattedPrice}`;
                    currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                }
            }
        }

    } catch (err) {
        console.error('Refresh failed:', err);
    }
}

// ========================================
// Market Watch Ticker WebSocket
// ========================================

function getTickerWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/tickers`;
}

function connectTickerWebSocket() {
    if (marketWebSocket && marketWebSocket.readyState === WebSocket.OPEN) {
        return;
    }

    const wsUrl = getTickerWebSocketUrl();
    console.log('連接 Ticker WebSocket:', wsUrl);

    try {
        marketWebSocket = new WebSocket(wsUrl);

        marketWebSocket.onopen = () => {
            console.log('Ticker WebSocket 連接成功');
            marketWsConnected = true;
            updateTickerWsStatus(true);

            // 訂閱等待中的 symbols
            if (pendingTickerSymbols.size > 0) {
                const symbols = Array.from(pendingTickerSymbols);
                pendingTickerSymbols.clear();
                subscribeTickerSymbols(symbols);
            }

            // 重新訂閱之前的 symbols
            if (subscribedTickerSymbols.size > 0) {
                const symbols = Array.from(subscribedTickerSymbols);
                subscribedTickerSymbols.clear(); // 清空以便重新添加
                subscribeTickerSymbols(symbols);
            }
        };

        marketWebSocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleTickerMessage(message);
            } catch (e) {
                console.error('Ticker WebSocket 消息解析錯誤:', e);
            }
        };

        marketWebSocket.onclose = (event) => {
            console.log('Ticker WebSocket 連接關閉:', event.code);
            marketWsConnected = false;
            updateTickerWsStatus(false);

            // 自動重連
            tickerReconnectTimer = setTimeout(() => {
                console.log('嘗試重新連接 Ticker WebSocket...');
                connectTickerWebSocket();
            }, 3000);
        };

        marketWebSocket.onerror = (error) => {
            console.error('Ticker WebSocket 錯誤:', error);
            marketWsConnected = false;
            updateTickerWsStatus(false);
        };

    } catch (e) {
        console.error('Ticker WebSocket 連接失敗:', e);
    }
}

function disconnectTickerWebSocket() {
    if (tickerReconnectTimer) {
        clearTimeout(tickerReconnectTimer);
        tickerReconnectTimer = null;
    }

    if (marketWebSocket) {
        marketWebSocket.close();
        marketWebSocket = null;
    }
    marketWsConnected = false;
    subscribedTickerSymbols.clear();
}

function subscribeTickerSymbols(symbols) {
    // 過濾已訂閱的
    const newSymbols = symbols.filter(s => !subscribedTickerSymbols.has(s.toUpperCase()));
    if (newSymbols.length === 0) return;

    if (!marketWebSocket || marketWebSocket.readyState !== WebSocket.OPEN) {
        // WebSocket 未連接，加入等待列表
        newSymbols.forEach(s => pendingTickerSymbols.add(s.toUpperCase()));
        console.log(`Ticker WebSocket 未連接，已排隊等待: ${newSymbols.join(', ')}`);
        return;
    }

    marketWebSocket.send(JSON.stringify({
        action: 'subscribe',
        symbols: newSymbols
    }));

    newSymbols.forEach(s => subscribedTickerSymbols.add(s.toUpperCase()));
    console.log(`訂閱 Ticker: ${newSymbols.join(', ')}`);
}

function unsubscribeTickerSymbols(symbols) {
    if (!marketWebSocket || marketWebSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    marketWebSocket.send(JSON.stringify({
        action: 'unsubscribe',
        symbols: symbols
    }));

    symbols.forEach(s => subscribedTickerSymbols.delete(s.toUpperCase()));
}

function handleTickerMessage(message) {
    switch (message.type) {
        case 'ticker':
            // console.log(`收到 Ticker 更新: ${message.symbol}`, message.data);
            updateMarketWatchItem(message.symbol, message.data);
            break;
        case 'subscribed':
            console.log(`✅ 已訂閱 Ticker: ${message.symbols.join(', ')}`);
            break;
        case 'unsubscribed':
            console.log(`已取消訂閱 Ticker`);
            break;
        case 'unsubscribed_all':
            console.log(`已取消所有 Ticker 訂閱`);
            break;
        case 'pong':
            break;
        case 'error':
            console.error('Ticker WebSocket 錯誤:', message.message);
            break;
        default:
            console.log('未知 Ticker 消息:', message);
    }
}

function updateMarketWatchItem(symbol, ticker) {
    // 尋找所有顯示該 symbol 的元素並更新價格
    // symbol 可能是 "BTC-USDT", "BTC", "BTCUSDT" 等格式
    // 統一處理為不帶後綴的格式
    const normalizedSymbol = symbol.toUpperCase()
        .replace('-USDT', '')
        .replace('USDT', '')
        .replace('-', '');

    // 更新所有列表中的價格
    const containers = ['top-list', 'oversold-list', 'overbought-list'];
    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (!container) return;

        // 查找包含該 symbol 的卡片
        const cards = container.querySelectorAll('[data-symbol]');

        cards.forEach(card => {
            const cardSymbol = (card.dataset.symbol || '').toUpperCase()
                .replace('-USDT', '')
                .replace('USDT', '')
                .replace('-', '');

            if (cardSymbol && cardSymbol === normalizedSymbol) {
                // 更新價格
                const priceEl = card.querySelector('.ticker-price');
                if (priceEl && ticker.last) {
                    const oldPrice = priceEl.textContent;
                    const newPrice = `$${formatPrice(ticker.last)}`;

                    if (oldPrice !== newPrice) {
                        priceEl.textContent = newPrice;
                        // 閃爍效果
                        priceEl.classList.add('price-flash');
                        setTimeout(() => priceEl.classList.remove('price-flash'), 300);
                    }
                }

                // 更新 24h 漲跌幅
                const changeEl = card.querySelector('.ticker-change');
                if (changeEl && ticker.change24h !== undefined) {
                    const change = ticker.change24h;
                    const isUp = change >= 0;
                    changeEl.textContent = `${isUp ? '+' : ''}${change.toFixed(2)}%`;
                    changeEl.className = `text-base font-black ticker-change ${isUp ? 'text-success' : 'text-danger'}`;
                }
            }
        });
    });
}

function updateTickerWsStatus(connected) {
    const indicator = document.getElementById('ticker-ws-indicator');
    if (indicator) {
        if (connected) {
            indicator.classList.add('bg-success');
            indicator.classList.remove('bg-gray-500');
            indicator.title = '即時更新已連接';
        } else {
            indicator.classList.remove('bg-success');
            indicator.classList.add('bg-gray-500');
            indicator.title = '即時更新已斷開';
        }
    }
}

// 自動啟動 Ticker WebSocket (當頁面在 Market Watch 標籤時)
function initTickerWebSocket() {
    // 延遲啟動，等待頁面載入
    setTimeout(() => {
        connectTickerWebSocket();
    }, 1000);
}

// Make globally accessible
window.showChart = showChart;
window.changeChartInterval = changeChartInterval;
window.closeChart = closeChart;
window.toggleAutoRefresh = toggleAutoRefresh;
window.connectTickerWebSocket = connectTickerWebSocket;
window.disconnectTickerWebSocket = disconnectTickerWebSocket;
window.subscribeTickerSymbols = subscribeTickerSymbols;
// 處理瀏覽器分頁切換 (Visibility Change)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('[Market] Tab hidden, pausing updates to save resources.');
        // Optionally clear interval if we wanted to be very strict, 
        // but app.js handles the main interval. 
        // We just note it here.
    } else {
        console.log('[Market] Tab visible, checking for stale data...');
        // 如果當前在 Market Watch 頁面，且數據可能過期，則刷新
        // 檢查是否在前台
        const marketTab = document.getElementById('market-content');
        if (marketTab && !marketTab.classList.contains('hidden')) {
            // 延遲一點點確保網路恢復
            setTimeout(() => {
                console.log('[Market] Resuming updates, forcing refresh...');
                refreshScreener(false, true); // Silent refresh, force update
            }, 500);
        }
    }
});

window.refreshScreener = refreshScreener; // CRITICAL: Export for index.html to call
window.showFundingHistory = showFundingHistory;
window.closeFundingHistory = closeFundingHistory;

