// ========================================
// market-screener.js - Screener + Funding Rates
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
        document.querySelectorAll('.crypto-sub-tab').forEach((btn) => {
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
    },
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
            await new Promise((r) => setTimeout(r, 50));
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
// window.showChart は market-chart.js で export
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
var reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
var chartKlinesData = []; // 儲存當前 K 線數據供更新用
var isChartHovered = false; // 追蹤圖表是否被懸停

// WebSocket 連接
// WebSocket 連接
// WebSocket 連接
var klineWebSocket = null;
var wsReconnectTimer = null;
var wsConnectionCheckTimer = null;
var wsConnected = false;

// Market Watch WebSocket
// Market Watch WebSocket
var marketWsConnected = false;
var marketWebSocket = null;
var tickerReconnectTimer = null;
var tickerReconnectAttempts = 0;
const MAX_TICKET_RECONNECT_ATTEMPTS = 5;
var subscribedTickerSymbols = new Set();
var pendingTickerSymbols = new Set(); // 等待連接後訂閱的 symbols

// 獲取資金費率數據
async function fetchFundingRates() {
    try {
        // 構建 URL，如果有選擇的幣種則傳遞給 API
        let url = '/api/funding-rates';
        if (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0) {
            const pairSymbols = window.SymbolSanitizer
                ? window.SymbolSanitizer.sanitizePairSymbols(window.globalSelectedSymbols)
                : window.globalSelectedSymbols;
            window.globalSelectedSymbols = pairSymbols;
            const validSymbols = window.SymbolSanitizer
                ? window.SymbolSanitizer.sanitizeBaseSymbols(pairSymbols)
                : pairSymbols;

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
        if (typeof showToast === 'function') showToast(window.I18n ? window.I18n.t('crypto.fundingRateLoadFailed') : '資金費率載入失敗，請稍後再試', 'error');
        return null;
    }
}

// 獲取資金費率顏色和狀態
function getFundingRateStyle(rate) {
    if (rate === null || rate === undefined)
        return {
            color: 'text-gray-500',
            bg: 'bg-gray-500/10',
            border: 'border-gray-500/20',
            label: '-',
        };

    const r = parseFloat(rate);
    // 🔥 極高費率 (> 0.1%): 市場過熱
    if (r >= 0.1)
        return {
            color: 'text-red-500 font-bold',
            bg: 'bg-red-500/20',
            border: 'border-red-500/50',
            label: window.I18n ? window.I18n.t('crypto.extremeOverheated') : '極度過熱',
        };

    // 📈 偏高費率 (0.03% - 0.1%): 明顯看多
    if (r >= 0.03)
        return {
            color: 'text-orange-400',
            bg: 'bg-orange-500/10',
            border: 'border-orange-500/30',
            label: window.I18n ? window.I18n.t('crypto.crowdedLongs') : '多頭擁擠',
        };

    // 🐂 正常偏多 (> 0.01%): 溫和看多
    if (r > 0.01)
        return {
            color: 'text-emerald-400',
            bg: 'bg-emerald-500/10',
            border: 'border-emerald-500/20',
            label: window.I18n ? window.I18n.t('crypto.bullish') : '看多',
        };

    // 😐 基準費率 (0% - 0.01%): 市場平靜
    if (r >= 0)
        return {
            color: 'text-gray-400',
            bg: 'bg-gray-500/10',
            border: 'border-gray-500/20',
            label: window.I18n ? window.I18n.t('crypto.neutral') : '中性',
        };

    // 📉 負費率 (< 0%): 空頭擁擠 / 軋空機會 (Cyan/Blue)
    return {
        color: 'text-cyan-400 font-medium',
        bg: 'bg-cyan-500/10',
        border: 'border-cyan-500/30',
        label: window.I18n ? window.I18n.t('crypto.bearishShortSqueeze') : '看空/軋空',
    };
}

async function refreshScreener(showLoading = false, forceRefresh = false) {
    if (isScreenerLoading) return;

    let containers = {
        top: document.getElementById('top-list'),
        topGainers: document.getElementById('top-gainers-list'),
        topLosers: document.getElementById('top-losers-list'),
        highFunding: document.getElementById('high-funding-list'),
        lowFunding: document.getElementById('low-funding-list'),
    };

    // 如果主容器不存在，使用輪詢等待（最多等待 1 秒）
    if (!containers.top) {
        for (let i = 0; i < 10; i++) {
            await new Promise((resolve) => setTimeout(resolve, 100));
            containers = {
                top: document.getElementById('top-list'),
                topGainers: document.getElementById('top-gainers-list'),
                topLosers: document.getElementById('top-losers-list'),
                highFunding: document.getElementById('high-funding-list'),
                lowFunding: document.getElementById('low-funding-list'),
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
        Object.values(containers).forEach((c) => {
            if (c)
                c.innerHTML =
                    '<div class="animate-pulse flex items-center gap-4 p-4"><div class="w-12 h-12 bg-surfaceHighlight rounded-2xl"></div><div class="flex-1 space-y-2"><div class="h-4 bg-surfaceHighlight rounded w-1/3"></div><div class="h-3 bg-surfaceHighlight rounded w-1/4"></div></div></div>';
        });
    }

    isScreenerLoading = true;

    try {
        if (window.SymbolSanitizer) {
            window.globalSelectedSymbols = window.SymbolSanitizer.sanitizePairSymbols(
                window.globalSelectedSymbols || []
            );
        }

        const body = {
            exchange: window.currentFilterExchange || 'okx',
            refresh: forceRefresh,
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
            body: JSON.stringify(body),
        })
            .then(async (res) => {
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({ detail: res.statusText }));
                    throw new Error(errData.detail || `Server Error: ${res.status}`);
                }
                return res.json();
            })
            .then((screenerData) => {
                // --- 處理篩選器結果 (Screener) ---
                if (screenerData && !screenerData.error) {
                    // [Optimization] Auto-populate filter from VOLUME leaders (Hot)
                    if (
                        !window.globalSelectedSymbols ||
                        window.globalSelectedSymbols.length === 0
                    ) {
                        const sourceList = screenerData.top_volume || screenerData.top_gainers;
                        if (sourceList && sourceList.length > 0) {
                            var top5 = sourceList.slice(0, 5);
                            const autoSymbols = top5.map(function (item) {
                                return item.Symbol;
                            });
                            window.globalSelectedSymbols = window.SymbolSanitizer
                                ? window.SymbolSanitizer.sanitizePairSymbols(autoSymbols)
                                : autoSymbols;

                            var indicator = document.getElementById('active-filter-indicator');
                            var filterCount = document.getElementById('filter-count');
                            var globalCount = document.getElementById('global-count-badge');
                            // [Sync] Update Pulse Tab Indicators too
                            var pulseIndicator = document.getElementById(
                                'active-pulse-filter-indicator'
                            );
                            var pulseFilterCount = document.getElementById('pulse-filter-count');
                            var pulseBadge = document.getElementById('pulse-count-badge');

                            if (filterCount)
                                filterCount.innerText = window.globalSelectedSymbols.length;
                            if (globalCount)
                                globalCount.innerText = window.globalSelectedSymbols.length;
                            if (pulseFilterCount)
                                pulseFilterCount.innerText = window.globalSelectedSymbols.length;
                            if (pulseBadge)
                                pulseBadge.innerText = window.globalSelectedSymbols.length;
                        }
                    }

                    // Update UI indicators
                    var count = (window.globalSelectedSymbols || []).length;
                    // ... (省略部分 UI 更新代碼以保持簡潔，主要邏輯不變) ...

                    if (screenerData.last_updated) {
                        if (window.MarketStatus) window.MarketStatus.markSynced('screener');
                    }

                    const topCount = screenerData.top_volume ? screenerData.top_volume.length : 0;
                    console.log(`[Market] Loaded ${topCount} items.`);

                    // 即使篩選後為空，也不要視為錯誤，而是渲染空列表
                    const displayList = screenerData.top_volume || [];
                    renderList(containers.top, displayList.slice(0, 5), 'price_change_24h', '%');

                    renderList(
                        containers.topGainers,
                        screenerData.top_gainers || [],
                        'price_change_24h',
                        '%'
                    );
                    renderList(
                        containers.topLosers,
                        screenerData.top_losers || [],
                        'price_change_24h',
                        '%'
                    );

                    if (topCount === 0) {
                        console.warn(
                            '[Market] Filter returned 0 items. Selected symbols:',
                            window.globalSelectedSymbols
                        );
                    }
                } else {
                    throw new Error(screenerData?.message || 'Unknown error');
                }
            })
            .catch((err) => {
                console.error('Screener Load Failed:', err.message);

                // CRITICAL FIX: Don't clear UI if this was a background refresh (showLoading=false)
                // Only clear and show error if it was a user-initiated or initial load
                if (showLoading || isTopEmpty) {
                    ['top', 'topGainers', 'topLosers'].forEach((key) => {
                        if (containers[key]) {
                            containers[key].innerHTML = `
                            <div class="flex flex-col items-center justify-center py-8 text-center text-red-400">
                                <i data-lucide="wifi-off" class="w-8 h-8 mb-2 opacity-50"></i>
                                <span class="text-sm font-medium">${window.I18n ? window.I18n.t('crypto.loadFailed') : '載入失敗'}</span>
                                <div class="text-xs opacity-50 mt-1 mb-2">${SecurityUtils.escapeHTML(err.message || '')}</div>
                                <button onclick="window.refreshScreener(true, true)" class="text-xs bg-red-500/10 hover:bg-red-500/20 px-3 py-1 rounded-full transition">${window.I18n ? window.I18n.t('crypto.retry') : '重試'}</button>
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
        console.error('Critical Refresh Error:', e);
        isScreenerLoading = false;
        if (typeof showToast === 'function') showToast(window.I18n ? window.I18n.t('crypto.marketRefreshFailed') : '市場數據刷新失敗，請稍後再試', 'error');
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
    fetchFundingRates()
        .then((fundingData) => {
            if (fundingData) {
                if (containers.highFunding && containers.lowFunding) {
                    renderFundingRateList(containers.highFunding, fundingData.top_bullish, 'high');
                    renderFundingRateList(containers.lowFunding, fundingData.top_bearish, 'low');
                }
            } else {
                // Funding Rate 失敗 - 顯示錯誤訊息
                ['highFunding', 'lowFunding'].forEach((key) => {
                    if (containers[key]) {
                        containers[key].innerHTML =
                            `<div class="text-center py-4 text-xs text-textMuted opacity-50">${window.I18n ? window.I18n.t('crypto.noData') : '暫無數據'}</div>`;
                    }
                });
            }
        })
        .catch((err) => {
            console.error('Funding rate fetch error:', err);
            ['highFunding', 'lowFunding'].forEach((key) => {
                if (containers[key]) {
                    containers[key].innerHTML =
                        `<div class="text-center py-4 text-xs text-red-400 opacity-50">${window.I18n ? window.I18n.t('crypto.loadFailed') : '載入失敗'}</div>`;
                }
            });
        });
}

function formatPrice(price) {
    const p = parseFloat(price);
    if (p >= 1000)
        return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (p >= 1) return p.toFixed(2);
    if (p >= 0.01) return p.toFixed(4);
    if (p >= 0.0001) return p.toFixed(6);
    return p.toFixed(8);
}

function renderList(container, items, key, unit) {
    if (!container) return;
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML =
            '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">No signals detected</p>';
        return;
    }

    // 收集所有 symbols 以便訂閱 WebSocket
    const symbolsToSubscribe = [];

    items.forEach((item) => {
        const val = parseFloat(item[key]);
        let signalsHtml = '';
        if (item.signals && Array.isArray(item.signals)) {
            item.signals.forEach((sig) => {
                let colorClass = 'text-secondary bg-white/5';
                if (sig.includes('突破')) colorClass = 'text-accent bg-accent/10';
                else if (sig.includes('爆量') || sig.includes('金叉'))
                    colorClass = 'text-primary bg-primary/10';
                else if (sig.includes('抄底')) colorClass = 'text-success bg-success/10';
                signalsHtml += `<span class="text-[8px] px-1.5 py-0.5 rounded-md ${colorClass} border border-white/5 uppercase font-bold tracking-tighter">${sig.replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, '')}</span>`;
            });
        }

        // RSI 能量條視覺化
        let rsiVisual = '';
        if (key === 'RSI_14') {
            const rsiColor = val > 70 ? 'bg-danger' : val < 30 ? 'bg-success' : 'bg-primary/40';
            rsiVisual = `
                <div class="w-full h-1 bg-white/5 rounded-full mt-2 overflow-hidden flex">
                    <div class="h-full ${rsiColor} transition-all duration-1000" style="width: ${val}%"></div>
                </div>
            `;
        }

        const div = document.createElement('div');
        div.className =
            'group relative bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer overflow-hidden';
        div.dataset.symbol = item.Symbol; // 添加 data-symbol 屬性
        div.onclick = () => {
            showChart(item.Symbol);
        };

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
                    <div class="text-base font-black ticker-change ${key === 'RSI_14' ? (val > 70 ? 'text-danger' : val < 30 ? 'text-success' : 'text-secondary') : val > 0 ? 'text-success' : 'text-danger'}">
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
        container.innerHTML =
            '<p class="text-textMuted text-[10px] italic py-6 text-center opacity-50 uppercase tracking-widest">No data</p>';
        return;
    }

    items.forEach((item) => {
        const rate = item.fundingRate;
        const frStyle = getFundingRateStyle(rate);
        const isPaying = rate > 0;

        const div = document.createElement('div');
        div.className =
            'group bg-surface/20 hover:bg-surface/40 border border-white/5 rounded-2xl p-4 transition-all duration-300 cursor-pointer';
        // User Request: Clicking the card should open Funding History, not K-Line Chart
        div.onclick = () => {
            showFundingHistory(item.symbol);
        };

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
        modal.className =
            'fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-sm hidden';
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
                    ${window.I18n ? window.I18n.t('crypto.fundingHistoryNote') : '最近 14 天的資金費率記錄 (每 8 小時結算一次)'}
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
            overlayContent.innerHTML =
                '<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div><div class="text-xs text-textMuted">' + (window.I18n ? window.I18n.t('crypto.loadingData') : '載入數據中...') + '</div>';
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
                overlayContent.innerHTML = `<div class="text-red-400 text-sm">${window.I18n ? window.I18n.t('crypto.loadFailed') : '載入失敗'}<br><span class="text-xs opacity-70">${typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(data.error) : data.error}</span></div>`;
            }
        } else {
            console.error('History data missing:', data);
            if (overlay && overlayContent) {
                overlayContent.innerHTML = '<div class="text-red-400 text-sm">' + (window.I18n ? window.I18n.t('crypto.noHistoryData') : '無歷史數據可用') + '</div>';
            }
        }
    } catch (e) {
        console.error('Fetch failed:', e);
        if (overlay && overlayContent) {
            overlayContent.innerHTML = `<div class="text-red-400 text-sm">${window.I18n ? window.I18n.t('crypto.loadFailed') : '載入失敗'}<br><span class="text-xs opacity-70">${SecurityUtils.escapeHTML(e.message || '')}</span></div>`;
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
