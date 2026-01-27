// ========================================
// pulse.js - 市場脈動功能
// ========================================

// Ensure currentPulseData exists
if (typeof window.currentPulseData === 'undefined') {
    window.currentPulseData = {};
}
let currentPulseData = window.currentPulseData;

// 初始化狀態
let pulseInitialized = false;

/**
 * 智能價格格式化
 */
function formatPrice(price) {
    if (price === null || price === undefined || isNaN(price)) return '$0.00';
    const absPrice = Math.abs(price);
    if (absPrice >= 1) return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (absPrice >= 0.01) return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    if (absPrice >= 0.0001) return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 6, maximumFractionDigits: 6 });
    if (absPrice === 0) return '$0.00';
    return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 });
}

/**
 * 將時間戳轉換為「多久以前」
 */
function getTimeAgo(timestamp) {
    if (!timestamp) return "未知時間";
    const seconds = Math.floor((new Date() - new Date(timestamp)) / 1000);
    if (seconds / 31536000 > 1) return Math.floor(seconds / 31536000) + " 年前";
    if (seconds / 2592000 > 1) return Math.floor(seconds / 2592000) + " 個月前";
    if (seconds / 86400 > 1) return Math.floor(seconds / 86400) + " 天前";
    if (seconds / 3600 > 1) return Math.floor(seconds / 3600) + " 小時前";
    if (seconds / 60 > 1) return Math.floor(seconds / 60) + " 分鐘前";
    return seconds < 10 ? "剛剛" : Math.floor(seconds) + " 秒前";
}

/**
 * 主要初始化函數 - 確保組件已注入並加載數據
 * 這是進入 Pulse 頁面時唯一需要調用的函數
 */
async function initPulse() {
    console.log('[Pulse] initPulse called');

    // 1. 確保組件已注入
    if (window.Components && !window.Components.isInjected('pulse')) {
        console.log('[Pulse] Injecting component...');
        await window.Components.inject('pulse');
    }

    // 2. 等待 DOM 元素出現
    let grid = document.getElementById('pulse-grid');
    if (!grid) {
        // 等待最多 500ms
        for (let i = 0; i < 10; i++) {
            await new Promise(r => setTimeout(r, 50));
            grid = document.getElementById('pulse-grid');
            if (grid) break;
        }
    }

    if (!grid) {
        console.error('[Pulse] pulse-grid not found after injection!');
        return;
    }

    console.log('[Pulse] pulse-grid found, loading data...');

    // 3. 創建 loading 卡片並加載數據
    await loadPulseData(true);

    pulseInitialized = true;
}

/**
 * 加載 Pulse 數據
 */
async function loadPulseData(showLoading = false) {
    const grid = document.getElementById('pulse-grid');
    if (!grid) {
        console.warn('[Pulse] Cannot load data: pulse-grid not found');
        return;
    }

    const targets = (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0)
        ? window.globalSelectedSymbols
        : ['BTC', 'ETH', 'SOL', 'PI'];

    // 創建 loading placeholder
    if (showLoading || grid.children.length === 0) {
        grid.innerHTML = targets.map(symbol => `
            <div id="pulse-card-${symbol}" class="bg-surface rounded-3xl border border-white/5 p-5 h-[300px] flex flex-col items-center justify-center">
                <div class="typing-indicator">
                    <div class="typing-dots flex gap-1"><span></span><span></span><span></span></div>
                    <span class="ml-2 text-textMuted text-sm">Analyzing ${symbol}...</span>
                </div>
            </div>
        `).join('');
    }

    // 並行加載所有數據
    await Promise.all(targets.map(symbol => fetchPulseForSymbol(symbol, false)));

    // 開始輪詢進度（如果有後台任務）
    pollAnalysisProgress();
}

/**
 * 舊的 checkMarketPulse 函數（保持兼容性）
 */
async function checkMarketPulse(showLoading = false, forceRefresh = false) {
    if (!pulseInitialized) {
        await initPulse();
    } else {
        await loadPulseData(showLoading);
    }
}

/**
 * 刷新按鈕
 */
async function refreshMarketPulse() {
    const btn = document.getElementById('pulse-refresh-btn');
    const icon = btn?.querySelector('i');
    if (btn) btn.disabled = true;
    if (icon) icon.classList.add('animate-spin');

    try {
        const targets = (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0)
            ? window.globalSelectedSymbols
            : ['BTC', 'ETH', 'SOL', 'PI'];
        const userKey = window.APIKeyManager?.getCurrentKey();

        if (userKey) {
            console.log("[Pulse] Using User Key for Deep Refresh...");
            await Promise.allSettled(targets.map(symbol => triggerDeepAnalysis(symbol)));
            await loadPulseData(false);
        } else {
            console.log("[Pulse] Triggering Background Public Refresh...");
            const res = await fetch('/api/market-pulse/refresh-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbols: targets })
            });
            if (!res.ok) throw new Error("Refresh failed");
            pollAnalysisProgress();
        }
    } catch (e) {
        console.error("Market Pulse Refresh Error:", e);
    } finally {
        setTimeout(() => {
            if (btn) btn.disabled = false;
            if (icon) icon.classList.remove('animate-spin');
            if (window.lucide) lucide.createIcons();
        }, 1000);
    }
}

/**
 * 獲取單個幣種的 Pulse 數據
 */
async function fetchPulseForSymbol(symbol, forceRefresh = false, deepAnalysis = false) {
    const card = document.getElementById(`pulse-card-${symbol}`);
    if (!card) {
        console.warn(`[Pulse] Card not found for ${symbol}`);
        return;
    }

    try {
        const sourcesQuery = (window.selectedNewsSources || ['google', 'cryptocompare', 'cryptopanic', 'newsapi']).join(',');
        const refreshParam = forceRefresh ? '&refresh=true' : '';
        const deepParam = deepAnalysis ? '&deep_analysis=true' : '';

        const headers = {};
        if (deepAnalysis) {
            const userKey = window.APIKeyManager?.getCurrentKey();
            if (userKey) {
                headers['X-User-LLM-Key'] = userKey.key;
                headers['X-User-LLM-Provider'] = userKey.provider;
            }
        }

        const res = await fetch(`/api/market-pulse/${symbol}?sources=${sourcesQuery}${refreshParam}${deepParam}`, { headers });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || `Server Error: ${res.status}`);
        }

        const data = await res.json();
        const report = data.report || { summary: data.explanation, key_points: [], highlights: [], risks: [] };

        // 處理等待狀態
        if (data.status === 'pending' || data.source_mode === 'awaiting_update') {
            renderPendingCard(card, data);
            return;
        }

        // 正常渲染
        if (report.summary) {
            currentPulseData[symbol] = data;
            renderPulseCard(card, data, report);
        }
    } catch (e) {
        console.error(`[Pulse] Error fetching ${symbol}:`, e);
        renderErrorCard(card, symbol, e.message);
    }
}

/**
 * 渲染等待中的卡片
 */
function renderPendingCard(card, data) {
    card.className = "bg-surface rounded-3xl border border-dashed border-white/10 p-6 h-full flex flex-col items-center justify-center min-h-[200px]";
    card.innerHTML = `
        <div class="text-center">
            <div class="w-12 h-12 bg-background rounded-full flex items-center justify-center mx-auto mb-3">
                <i data-lucide="clock" class="w-6 h-6 text-textMuted"></i>
            </div>
            <h3 class="font-serif text-lg text-secondary mb-2">${data.symbol}</h3>
            <p class="text-textMuted text-sm mb-4">Awaiting scheduled update</p>
            <button onclick="triggerDeepAnalysis('${data.symbol}')" class="px-4 py-2.5 bg-primary/10 text-primary hover:bg-primary/20 rounded-xl transition flex items-center gap-2 mx-auto border border-primary/20">
                <i data-lucide="zap" class="w-4 h-4"></i>
                Deep Analysis
            </button>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
}

/**
 * 渲染 Pulse 卡片
 */
function renderPulseCard(card, data, report) {
    const isPositive = data.change_24h > 0;
    const timeString = getTimeAgo(data.timestamp);
    const uniqueSources = data.news_sources ? [...new Set(data.news_sources.map(n => n.source.split(' ')[0]))].join(', ') : '';

    card.className = "bg-surface rounded-3xl border border-white/5 p-0 h-full flex flex-col hover:border-primary/20 transition duration-300 overflow-hidden";

    let html = `
        <div class="p-5 border-b border-white/5 bg-background/30">
            <div class="flex justify-between items-start mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 ${isPositive ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'} rounded-xl flex items-center justify-center">
                        <i data-lucide="${isPositive ? 'trending-up' : 'trending-down'}" class="w-5 h-5"></i>
                    </div>
                    <div>
                        <h3 class="font-serif text-lg flex items-center gap-2 text-secondary">
                            ${data.symbol}
                            <span class="text-[10px] font-normal text-textMuted/50 bg-background px-1.5 py-0.5 rounded-lg border border-white/5">${timeString}</span>
                        </h3>
                        <div class="text-xs text-textMuted">
                            ${formatPrice(data.current_price)}
                            <span class="ml-1 ${isPositive ? 'text-success' : 'text-danger'}">
                                ${data.change_24h > 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                            </span>
                        </div>
                    </div>
                </div>
                <span class="px-2 py-1 rounded-lg bg-background text-[10px] text-textMuted border border-white/5">1H: ${data.change_1h > 0 ? '+' : ''}${data.change_1h.toFixed(2)}%</span>
            </div>
            <p class="text-secondary/90 text-sm font-light leading-relaxed">${report.summary}</p>
        </div>
    `;

    html += `<div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">`;

    if (report.key_points?.length > 0) {
        html += `
            <div>
                <h4 class="text-xs font-bold text-accent mb-2 flex items-center gap-1 uppercase tracking-wider">
                    <i data-lucide="sparkles" class="w-3 h-3"></i> Key Points
                </h4>
                <ul class="space-y-2">
                    ${report.key_points.map((point, idx) => `
                        <li class="flex gap-2 text-xs text-secondary/80">
                            <span class="text-primary/50 font-mono">${idx + 1}.</span>
                            <span>${point}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    if (report.highlights?.length > 0) {
        html += `
            <div>
                <h4 class="text-xs font-bold text-accent mb-2 flex items-center gap-1 uppercase tracking-wider">
                    <i data-lucide="zap" class="w-3 h-3"></i> Highlights
                </h4>
                <div class="space-y-2">
                    ${report.highlights.map(item => `
                        <div class="bg-background/50 rounded-xl p-3 border border-white/5">
                            <div class="text-xs font-semibold text-secondary mb-1">${item.title}</div>
                            <div class="text-[11px] text-textMuted leading-normal">${item.content}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    if (report.risks?.length > 0) {
        html += `
            <div>
                <h4 class="text-xs font-bold text-danger mb-2 flex items-center gap-1 uppercase tracking-wider">
                    <i data-lucide="alert-triangle" class="w-3 h-3"></i> Risks
                </h4>
                <ul class="space-y-1">
                    ${report.risks.map(risk => `
                        <li class="flex gap-2 text-xs text-textMuted">
                            <i data-lucide="alert-circle" class="w-3 h-3 text-danger/50 mt-0.5 shrink-0"></i>
                            <span>${risk}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    html += `</div>`;

    const sourceMode = data.source_mode || 'public_cache';
    const sourceBadge = sourceMode === 'deep_analysis'
        ? `<span class="px-1.5 py-0.5 bg-primary/20 text-primary rounded-lg border border-primary/30 flex items-center gap-1"><i data-lucide="zap" class="w-2.5 h-2.5"></i>Deep</span>`
        : `<span class="px-1.5 py-0.5 bg-background text-textMuted rounded-lg border border-white/5">Public</span>`;

    html += `
        <div class="p-4 border-t border-white/5 bg-background/30 flex justify-between items-center text-[10px] text-textMuted">
            <div class="flex items-center gap-2">
                ${sourceBadge}
                <span title="${uniqueSources}">Refs: ${data.news_sources ? data.news_sources.length : 0}</span>
            </div>
            <div class="flex gap-2">
                <button onclick="showNewsList('${data.symbol}')" class="px-2.5 py-1.5 hover:bg-surfaceHighlight rounded-lg transition text-accent flex items-center gap-1">
                    <i data-lucide="newspaper" class="w-3 h-3"></i> News
                </button>
                <button onclick="triggerDeepAnalysis('${data.symbol}')" class="px-2.5 py-1.5 hover:bg-primary/10 rounded-lg transition text-primary flex items-center gap-1 border border-primary/10">
                    <i data-lucide="microscope" class="w-3 h-3"></i> Deep
                </button>
                <button onclick="switchTab('chat'); quickAsk('${data.symbol} analysis')" class="px-2.5 py-1.5 bg-accent/10 text-accent hover:bg-accent/20 rounded-lg transition flex items-center gap-1 border border-accent/20">
                    <i data-lucide="bot" class="w-3 h-3"></i> Detail
                </button>
            </div>
        </div>
    `;

    card.innerHTML = html;
    if (window.lucide) lucide.createIcons();
}

/**
 * 渲染錯誤卡片
 */
function renderErrorCard(card, symbol, errorMsg) {
    card.innerHTML = `
        <div class="p-6 h-full flex flex-col items-center justify-center min-h-[200px] text-center text-red-400">
            <i data-lucide="alert-octagon" class="w-8 h-8 mb-2 opacity-80"></i>
            <h3 class="text-sm font-bold mb-1">載入失敗</h3>
            <p class="text-xs opacity-70 mb-4 px-2 line-clamp-2">${errorMsg}</p>
            <button onclick="fetchPulseForSymbol('${symbol}', true)" class="text-xs bg-red-500/10 hover:bg-red-500/20 px-4 py-2 rounded-xl transition border border-red-500/20">
                重試
            </button>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
}

/**
 * 深度分析
 */
async function triggerDeepAnalysis(symbol) {
    const userKey = window.APIKeyManager?.getCurrentKey();

    if (!userKey) {
        if (typeof showAlert === 'function') {
            showAlert({
                title: '未設置 API Key',
                message: '請先在設定中配置您的 API Key 才能使用深度分析功能。',
                type: 'warning',
                confirmText: '前往設定'
            }).then(() => {
                if (typeof switchTab === 'function') switchTab('settings');
            });
        }
        return;
    }

    const card = document.getElementById(`pulse-card-${symbol}`);
    if (card) {
        card.innerHTML = `
            <div class="p-6 h-full flex flex-col items-center justify-center min-h-[200px]">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mb-3"></div>
                <div class="text-amber-400 text-sm font-medium">深度分析中...</div>
                <div class="text-slate-500 text-xs mt-1">使用 ${userKey.provider.toUpperCase()} 進行即時分析</div>
            </div>
        `;
    }

    try {
        await fetchPulseForSymbol(symbol, false, true);
    } catch (e) {
        console.error('Deep analysis failed:', e);
        await fetchPulseForSymbol(symbol, false, false);
    }
}

/**
 * 顯示新聞列表
 */
function showNewsList(symbol) {
    const data = currentPulseData[symbol];
    if (!data || !data.news_sources) return;

    const modal = document.getElementById('news-modal');
    const listContent = document.getElementById('news-list-content');
    const symbolTitle = document.getElementById('news-modal-symbol');

    if (symbolTitle) symbolTitle.innerText = symbol;
    if (listContent) listContent.innerHTML = '';

    if (!data.news_sources || data.news_sources.length === 0) {
        listContent.innerHTML = `<div class="text-slate-500 text-center py-4">暫無相關新聞</div>`;
    } else {
        data.news_sources.forEach(news => {
            const item = document.createElement('div');
            item.className = 'bg-slate-800/50 border border-slate-700 p-3 rounded-xl hover:bg-slate-800 transition group';
            const linkHtml = news.url && news.url !== '#'
                ? `<a href="${news.url}" target="_blank" class="text-[10px] text-blue-500 hover:underline">查看原文</a>`
                : `<span class="text-[10px] text-slate-500">無連結</span>`;
            item.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-400 rounded border border-blue-500/20">${news.source || '未知來源'}</span>
                </div>
                <h4 class="text-sm font-semibold text-slate-200 mb-2 group-hover:text-blue-300 transition line-clamp-2">${news.title || '無標題'}</h4>
                ${linkHtml}
            `;
            listContent.appendChild(item);
        });
    }
    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

// --- Analysis Progress Polling ---
let isPollingProgress = false;

async function pollAnalysisProgress() {
    if (isPollingProgress) return;
    isPollingProgress = true;

    const container = document.getElementById('analysis-progress-container');
    const bar = document.getElementById('analysis-progress-bar');
    const text = document.getElementById('analysis-progress-text');

    if (!container || !bar || !text) {
        isPollingProgress = false;
        return;
    }

    try {
        while (true) {
            const res = await fetch('/api/market-pulse/progress');
            if (!res.ok) break;

            const status = await res.json();

            if (status.is_running && status.total > 0) {
                container.classList.remove('hidden');
                const pct = (status.completed / status.total) * 100;
                bar.style.width = `${pct}%`;
                text.innerText = `${status.completed}/${status.total} (${pct.toFixed(1)}%)`;
                await new Promise(r => setTimeout(r, 2000));
            } else {
                if (!container.classList.contains('hidden')) {
                    bar.style.width = '100%';
                    text.innerText = '完成';
                    await new Promise(r => setTimeout(r, 2000));
                    container.classList.add('hidden');
                    loadPulseData(false);
                }
                break;
            }
        }
    } catch (e) {
        console.error("Progress poll error:", e);
    } finally {
        isPollingProgress = false;
    }
}

// ========================================
// Export all functions to window
// ========================================
window.initPulse = initPulse;
window.checkMarketPulse = checkMarketPulse;
window.refreshMarketPulse = refreshMarketPulse;
window.loadPulseData = loadPulseData;
window.fetchPulseForSymbol = fetchPulseForSymbol;
window.triggerDeepAnalysis = triggerDeepAnalysis;
window.showNewsList = showNewsList;
window.formatPrice = formatPrice;
window.getTimeAgo = getTimeAgo;

console.log('[Pulse] Module loaded');
