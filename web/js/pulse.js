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
    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
    if (!timestamp) return t('pulse.unknownTime');
    const seconds = Math.floor((new Date() - new Date(timestamp)) / 1000);
    if (seconds / 31536000 > 1) return Math.floor(seconds / 31536000) + t('pulse.yearsAgo');
    if (seconds / 2592000 > 1) return Math.floor(seconds / 2592000) + t('pulse.monthsAgo');
    if (seconds / 86400 > 1) return Math.floor(seconds / 86400) + t('pulse.daysAgo');
    if (seconds / 3600 > 1) return Math.floor(seconds / 3600) + t('pulse.hoursAgo');
    if (seconds / 60 > 1) return Math.floor(seconds / 60) + t('pulse.minsAgo');
    return seconds < 10 ? t('pulse.justNow') : Math.floor(seconds) + t('pulse.secsAgo');
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

    // [Sync] Ensure we use the shared "Top 5" selection from Market module
    // If no selection exists, trigger Market initialization to populate Top 5
    if (!window.globalSelectedSymbols || window.globalSelectedSymbols.length === 0) {
        if (typeof window.initMarket === 'function') {
            console.log('[Pulse] No selection found, initializing Market to get Top 5...');
            await window.initMarket();
        }
    }

    const targets = (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0)
        ? window.globalSelectedSymbols
        : ['BTC', 'ETH', 'SOL', 'PI']; // Failsafe fallback

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
        if (!window.globalSelectedSymbols || window.globalSelectedSymbols.length === 0) {
            if (typeof window.initMarket === 'function') await window.initMarket();
        }

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
                ${(window.I18n ? window.I18n.t('pulse.deepAnalysis') : 'Deep Analysis')}
            </button>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
}

/**
 * Build translated summary from i18n data or fallback
 */
function _buildPulseSummary(report, t) {
    const i18n = report.summary_i18n;
    if (i18n) {
        const trend = i18n.trend === 'up' ? t('pulse.up24h') : t('pulse.down24h');
        const rsi = t('pulse.' + i18n.rsi_status);
        const price = formatPrice(i18n.price);
        const reason = i18n.reason_key ? t(i18n.reason_key) : '';
        return `<strong>[${t('pulse.quickPreview')}]</strong> ${i18n.symbol} ${t('pulse.currentPrice')} ${price}, 24H ${trend} ${i18n.change_pct.toFixed(2)}%. RSI: ${rsi} (${i18n.rsi_value}). ${reason}`;
    }
    return report.summary || '';
}

/**
 * Build translated key points from i18n data or fallback
 */
function _buildPulseKeyPoints(report, t) {
    if (report.key_points_i18n && report.key_points_i18n.length > 0) {
        return report.key_points_i18n.map(kp => {
            const label = t('pulse.' + kp.key);
            if (kp.key === 'priceAction') {
                return `<strong>${label}</strong>: 1H ${kp.values.h1}, 24H ${kp.values.h24}`;
            } else if (kp.key === 'techSignals') {
                const macdKey = 'pulse.macd' + kp.values.macd;
                const volBase = (kp.values.volume || 'Normal').split(' ')[0];
                const volKey = 'pulse.volume' + volBase;
                const volExtra = kp.values.volume.includes('(') ? ' ' + kp.values.volume.match(/\(.*\)/)?.[0] : '';
                return `<strong>${label}</strong>: MACD ${t(macdKey)}, ${t('pulse.volume')} ${t(volKey)}${volExtra}`;
            } else if (kp.key === 'newsActivity') {
                return `<strong>${label}</strong>: ${kp.values.count} ${t('pulse.newsFound')}`;
            }
            return `<strong>${label}</strong>`;
        });
    }
    return report.key_points || [];
}

/**
 * Render Pulse Card
 */
function renderPulseCard(card, data, report) {
    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
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
            <p class="text-secondary/90 text-sm font-light leading-relaxed">${_buildPulseSummary(report, t)}</p>
        </div>
    `;

    html += `<div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">`;

    if (report.key_points?.length > 0) {
        const kpItems = _buildPulseKeyPoints(report, t);
        html += `
            <div>
                <h4 class="text-xs font-bold text-accent mb-2 flex items-center gap-1 uppercase tracking-wider">
                    <i data-lucide="sparkles" class="w-3 h-3"></i> ${t('pulse.keyPoints')}
                </h4>
                <ul class="space-y-2">
                    ${kpItems.map((point, idx) => `
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
                    <i data-lucide="zap" class="w-3 h-3"></i> ${t('pulse.highlights')}
                </h4>
                <div class="space-y-2">
                    ${report.highlights.map(item => `
                        <div class="bg-background/50 rounded-xl p-3 border border-white/5">
                            <div class="text-xs font-semibold text-secondary mb-1">${item.title_key ? t('pulse.' + item.title_key) : item.title}</div>
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
                    <i data-lucide="alert-triangle" class="w-3 h-3"></i> ${t('pulse.risks')}
                </h4>
                <ul class="space-y-1">
                    ${(report.risks_i18n || report.risks).map(risk => `
                        <li class="flex gap-2 text-xs text-textMuted">
                            <i data-lucide="alert-circle" class="w-3 h-3 text-danger/50 mt-0.5 shrink-0"></i>
                            <span>${risk.startsWith('pulse.') ? t(risk) : risk}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    html += `</div>`;

    const sourceMode = data.source_mode || 'public_cache';
    const sourceBadge = sourceMode === 'deep_analysis'
        ? `<span class="px-1.5 py-0.5 bg-primary/20 text-primary rounded-lg border border-primary/30 flex items-center gap-1"><i data-lucide="zap" class="w-2.5 h-2.5"></i>${t('pulse.deep')}</span>`
        : `<span class="px-1.5 py-0.5 bg-background text-textMuted rounded-lg border border-white/5">${t('pulse.public')}</span>`;

    html += `
        <div class="p-4 border-t border-white/5 bg-background/30 flex justify-between items-center text-[10px] text-textMuted">
            <div class="flex items-center gap-2">
                ${sourceBadge}
                <span title="${uniqueSources}">Refs: ${data.news_sources ? data.news_sources.length : 0}</span>
            </div>
            <div class="flex gap-2">
                <button onclick="showNewsList('${data.symbol}')" class="px-2.5 py-1.5 hover:bg-surfaceHighlight rounded-lg transition text-accent flex items-center gap-1">
                    <i data-lucide="newspaper" class="w-3 h-3"></i> ${t('pulse.news')}
                </button>
                <button onclick="triggerDeepAnalysis('${data.symbol}')" class="px-2.5 py-1.5 hover:bg-primary/10 rounded-lg transition text-primary flex items-center gap-1 border border-primary/10">
                    <i data-lucide="microscope" class="w-3 h-3"></i> ${t('pulse.deep')}
                </button>
                <button onclick="switchTab('chat'); quickAsk('${data.symbol} analysis')" class="px-2.5 py-1.5 bg-accent/10 text-accent hover:bg-accent/20 rounded-lg transition flex items-center gap-1 border border-accent/20">
                    <i data-lucide="bot" class="w-3 h-3"></i> ${t('pulse.detail')}
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
    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
    card.innerHTML = `
        <div class="p-6 h-full flex flex-col items-center justify-center min-h-[200px] text-center text-red-400">
            <i data-lucide="alert-octagon" class="w-8 h-8 mb-2 opacity-80"></i>
            <h3 class="text-sm font-bold mb-1">${t('pulse.loadFailed')}</h3>
            <p class="text-xs opacity-70 mb-4 px-2 line-clamp-2">${errorMsg}</p>
            <button onclick="fetchPulseForSymbol('${symbol}', true)" class="text-xs bg-red-500/10 hover:bg-red-500/20 px-4 py-2 rounded-xl transition border border-red-500/20">
                ${t('pulse.retry')}
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
        const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
        if (typeof showAlert === 'function') {
            showAlert({
                title: t('pulse.noApiKeyTitle'),
                message: t('pulse.noApiKeyMessage'),
                type: 'warning',
                confirmText: t('pulse.goToSettings')
            }).then(() => {
                if (typeof switchTab === 'function') switchTab('settings');
            });
        }
        return;
    }

    const card = document.getElementById(`pulse-card-${symbol}`);
    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
    if (card) {
        card.innerHTML = `
            <div class="p-6 h-full flex flex-col items-center justify-center min-h-[200px]">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mb-3"></div>
                <div class="text-amber-400 text-sm font-medium">${t('pulse.deepAnalyzing')}</div>
                <div class="text-slate-500 text-xs mt-1">${t('pulse.usingProvider', {provider: userKey.provider.toUpperCase()})}</div>
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

    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
    if (!data.news_sources || data.news_sources.length === 0) {
        listContent.innerHTML = `<div class="text-slate-500 text-center py-4">${t('pulse.noNews')}</div>`;
    } else {
        data.news_sources.forEach(news => {
            const item = document.createElement('div');
            item.className = 'bg-slate-800/50 border border-slate-700 p-3 rounded-xl hover:bg-slate-800 transition group';
            const linkHtml = news.url && news.url !== '#'
                ? `<a href="${news.url}" target="_blank" class="text-[10px] text-blue-500 hover:underline">${t('pulse.viewOriginal')}</a>`
                : `<span class="text-[10px] text-slate-500">${t('pulse.noLink')}</span>`;
            item.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-400 rounded border border-blue-500/20">${news.source || t('pulse.unknownSource')}</span>
                </div>
                <h4 class="text-sm font-semibold text-slate-200 mb-2 group-hover:text-blue-300 transition line-clamp-2">${news.title || t('pulse.noTitle')}</h4>
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
                    const t = window.I18n ? window.I18n.t.bind(window.I18n) : (k) => k;
                    text.innerText = t('pulse.done');
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

/**
 * Re-render all pulse cards with current language (called on language change)
 */
function reRenderPulseCards() {
    for (const [symbol, data] of Object.entries(currentPulseData)) {
        const card = document.getElementById(`pulse-card-${symbol}`);
        if (!card || !data) continue;
        const report = data.report || { summary: data.explanation, key_points: [], highlights: [], risks: [] };
        if (report.summary) {
            renderPulseCard(card, data, report);
        }
    }
}

// Listen for language changes to re-render cards
window.addEventListener('languageChanged', () => {
    console.log('[Pulse] Language changed, re-rendering cards...');
    reRenderPulseCards();
});

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
