// ========================================
// pulse.js - 市場脈動功能
// ========================================

/**
 * 智能價格格式化 - 根據價格大小自動調整小數位數
 * @param {number} price - 價格
 * @returns {string} - 格式化後的價格字符串
 */
function formatPrice(price) {
    if (price === null || price === undefined || isNaN(price)) {
        return '$0.00';
    }

    const absPrice = Math.abs(price);

    if (absPrice >= 1) {
        // 價格 >= $1: 顯示 2 位小數
        return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (absPrice >= 0.01) {
        // 價格 >= $0.01: 顯示 4 位小數
        return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    } else if (absPrice >= 0.0001) {
        // 價格 >= $0.0001: 顯示 6 位小數
        return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 6, maximumFractionDigits: 6 });
    } else {
        // 非常小的價格: 顯示 8 位小數或使用科學記號
        if (absPrice === 0) {
            return '$0.00';
        }
        // 顯示有效數字（最多 8 位小數）
        return '$' + price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 });
    }
}

/**
 * 將時間戳轉換為「多久以前」
 */
function getTimeAgo(timestamp) {
    if (!timestamp) return "未知時間";
    const date = new Date(timestamp);
    const seconds = Math.floor((new Date() - date) / 1000);

    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + " 年前";
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + " 個月前";
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + " 天前";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " 小時前";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " 分鐘前";
    return seconds < 10 ? "剛剛" : Math.floor(seconds) + " 秒前";
}

async function checkMarketPulse(showLoading = false, forceRefresh = false) {
    const grid = document.getElementById('pulse-grid');
    let targets = globalSelectedSymbols.length > 0 ? globalSelectedSymbols : ['BTC', 'ETH', 'SOL', 'PI'];
    if (showLoading && grid) {
        grid.innerHTML = '';
        targets.forEach(symbol => {
            const el = document.createElement('div');
            el.className = 'bg-surface rounded-3xl border border-white/5 p-5 h-[300px] flex flex-col items-center justify-center';
            el.innerHTML = `<div class="typing-indicator"><div class="typing-dots flex gap-1"><span></span><span></span><span></span></div><span class="ml-2 text-textMuted text-sm">Analyzing ${symbol}...</span></div>`;
            el.id = `pulse-card-${symbol}`; grid.appendChild(el);
        });
    }
    targets.forEach(symbol => fetchPulseForSymbol(symbol, forceRefresh));
}

async function refreshMarketPulse() {
    const btn = document.getElementById('pulse-refresh-btn');
    const icon = document.getElementById('pulse-refresh-icon');
    if (btn) btn.disabled = true;
    if (icon) icon.classList.add('animate-spin');

    try {
        // Identify targets to refresh
        let targets = globalSelectedSymbols.length > 0 ? globalSelectedSymbols : ['BTC', 'ETH', 'SOL', 'PI'];
        const userKey = window.APIKeyManager?.getCurrentKey();

        if (userKey) {
            // [Premium] 使用用戶 Key 進行並行深度分析
            console.log("Using User Key for Deep Refresh...");
            const promises = targets.map(symbol => triggerDeepAnalysis(symbol));
            await Promise.allSettled(promises);
            // 完成後重新讀取快取以更新 UI
            await checkMarketPulse(false, false);
        } else {
            // [Free] 觸發後台公共更新
            console.log("Triggering Background Public Refresh...");
            const res = await fetch('/api/market-pulse/refresh-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbols: targets })
            });

            if (!res.ok) throw new Error("Refresh failed");

            // 開始輪詢進度，直到完成
            pollAnalysisProgress();
        }

    } catch (e) {
        console.error("Market Pulse Refresh Error:", e);
        // alert("重新整理失敗，請稍後再試"); // Suppress alert on network cancel (e.g. F5)
    } finally {
        setTimeout(() => {
            if (btn) btn.disabled = false;
            if (icon) icon.classList.remove('animate-spin');
            lucide.createIcons();
        }, 1000);
    }
}

async function fetchPulseForSymbol(symbol, forceRefresh = false, deepAnalysis = false) {
    const cardId = `pulse-card-${symbol}`;
    let card = document.getElementById(cardId); if (!card) return;
    try {
        const sourcesQuery = selectedNewsSources.join(',');
        const refreshParam = forceRefresh ? '&refresh=true' : '';
        const deepParam = deepAnalysis ? '&deep_analysis=true' : '';

        // 只有在深度分析模式下才發送用戶 API Key
        const headers = {};
        if (deepAnalysis) {
            const userKey = window.APIKeyManager?.getCurrentKey();
            if (userKey) {
                headers['X-User-LLM-Key'] = userKey.key;
                headers['X-User-LLM-Provider'] = userKey.provider;
            }
        }

        const res = await fetch(`/api/market-pulse/${symbol}?sources=${sourcesQuery}${refreshParam}${deepParam}`, {
            headers: headers
        });
        
        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errData.detail || `Server Error: ${res.status}`);
        }

        const data = await res.json();

        const report = data.report || {
            summary: data.explanation,
            key_points: [],
            highlights: [],
            risks: []
        };

        // 處理等待排程更新的情況
        if (data.status === 'pending' || data.source_mode === 'awaiting_update') {
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
            lucide.createIcons();
            return;
        }

        if (report.summary) {
            currentPulseData[symbol] = data;
            const isPositive = data.change_24h > 0;

            const timeString = getTimeAgo(data.timestamp);
            const uniqueSources = data.news_sources ? [...new Set(data.news_sources.map(n => n.source.split(' ')[0]))].join(', ') : '';

            card.className = "bg-surface rounded-3xl border border-white/5 p-0 h-full flex flex-col hover:border-primary/20 transition duration-300 overflow-hidden";

            // 1. Header Section (Price & Summary)
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

            // 2. Body Section (Scrollable)
            html += `<div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">`;

            // Key Points
            if (report.key_points && report.key_points.length > 0) {
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

            // Highlights
            if (report.highlights && report.highlights.length > 0) {
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

            // Risks
            if (report.risks && report.risks.length > 0) {
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

            html += `</div>`; // End Body

            // 3. Footer Section
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
                        <button onclick="showNewsList('${symbol}')" class="px-2.5 py-1.5 hover:bg-surfaceHighlight rounded-lg transition text-accent flex items-center gap-1">
                            <i data-lucide="newspaper" class="w-3 h-3"></i> News
                        </button>
                        <button onclick="triggerDeepAnalysis('${symbol}')" class="px-2.5 py-1.5 hover:bg-primary/10 rounded-lg transition text-primary flex items-center gap-1 border border-primary/10" title="Deep analysis with your API Key">
                            <i data-lucide="microscope" class="w-3 h-3"></i> Deep
                        </button>
                        <button onclick="switchTab('chat'); quickAsk('${data.symbol} analysis')" class="px-2.5 py-1.5 bg-accent/10 text-accent hover:bg-accent/20 rounded-lg transition flex items-center gap-1 border border-accent/20">
                            <i data-lucide="bot" class="w-3 h-3"></i> Detail
                        </button>
                    </div>
                </div>
            `;

            card.innerHTML = html;
            lucide.createIcons();
        }
    } catch (e) {
        console.error(e);
        
        // Error Handling & UI Feedback
        let errorMsg = e.message || "未知錯誤";
        let isQuota = false;
        
        if (errorMsg.includes("429") || errorMsg.includes("quota")) {
            isQuota = true;
            errorMsg = "API 配額已滿";
            if (window.showError) {
                window.showError(`分析 ${symbol} 失敗`, "API 配額已滿或請求過於頻繁。請稍後再試或檢查您的金鑰。", true);
            }
        }

        // Update Card UI to show error
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
        lucide.createIcons();
    }
}

/**
 * 觸發深度分析 - 使用用戶的私人 API Key 進行即時分析
 */
async function triggerDeepAnalysis(symbol) {
    const userKey = window.APIKeyManager?.getCurrentKey();

    if (!userKey) {
        alert('請先在設定中配置您的 API Key（OpenAI / Google / OpenRouter）才能使用深度分析功能。');
        return;
    }

    const card = document.getElementById(`pulse-card-${symbol}`);
    if (card) {
        // 顯示載入狀態
        const originalContent = card.innerHTML;
        card.innerHTML = `
            <div class="p-6 h-full flex flex-col items-center justify-center min-h-[200px]">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400 mb-3"></div>
                <div class="text-amber-400 text-sm font-medium">深度分析中...</div>
                <div class="text-slate-500 text-xs mt-1">使用 ${userKey.provider.toUpperCase()} 進行即時分析</div>
            </div>
        `;
    }

    try {
        await fetchPulseForSymbol(symbol, false, true); // deepAnalysis = true
    } catch (e) {
        console.error('Deep analysis failed:', e);
        alert('深度分析失敗，請檢查您的 API Key 是否正確。');
        // 恢復原始內容
        if (card) {
            await fetchPulseForSymbol(symbol, false, false);
        }
    }
}

function showNewsList(symbol) {
    const data = currentPulseData[symbol]; if (!data || !data.news_sources) return;
    const modal = document.getElementById('news-modal');
    const listContent = document.getElementById('news-list-content');
    
    const symbolTitle = document.getElementById('news-modal-symbol');
    if (symbolTitle) symbolTitle.innerText = symbol;
    
    if (listContent) listContent.innerHTML = '';

    if (!data.news_sources || data.news_sources.length === 0) {
        console.log("No news sources found for", symbol, data);
        listContent.innerHTML = `<div class="text-slate-500 text-center py-4">暫無相關新聞</div>`;
    } else {
        data.news_sources.forEach(news => {
            const item = document.createElement('div');
            item.className = 'bg-slate-800/50 border border-slate-700 p-3 rounded-xl hover:bg-slate-800 transition group';

            const title = news.title || '無標題';
            const source = news.source || '未知來源';
            const url = news.url || '#';
            const linkHtml = url !== '#'
                ? `<a href="${url}" target="_blank" class="text-[10px] text-blue-500 hover:underline">查看原文 <i data-lucide="external-link" class="w-2.5 h-2.5"></i></a>`
                : `<span class="text-[10px] text-slate-500 cursor-not-allowed">無連結</span>`;

            item.innerHTML = `
                <div class="flex justify-between items-start mb-1">
                    <span class="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-400 rounded border border-blue-500/20">${source}</span>
                </div>
                <h4 class="text-sm font-semibold text-slate-200 mb-2 group-hover:text-blue-300 transition line-clamp-2">${title}</h4>
                ${linkHtml}
            `;
            listContent.appendChild(item);
        });
    }
    modal.classList.remove('hidden'); lucide.createIcons();
}

// --- Analysis Progress Polling ---
let isPollingProgress = false;

async function pollAnalysisProgress() {
    if (isPollingProgress) return;
    isPollingProgress = true;

    const container = document.getElementById('analysis-progress-container');
    const bar = document.getElementById('analysis-progress-bar');
    const text = document.getElementById('analysis-progress-text');

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

                // Keep polling
                await new Promise(r => setTimeout(r, 2000));
            } else {
                // Done or not running
                if (!container.classList.contains('hidden')) {
                    // Show 100% briefly then hide
                    bar.style.width = '100%';
                    text.innerText = '完成';
                    await new Promise(r => setTimeout(r, 2000));
                    container.classList.add('hidden');

                    // Refresh grid one last time to show new data
                    checkMarketPulse(false, false);
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

// Hook into existing functions
const originalCheckMarketPulse = checkMarketPulse;
checkMarketPulse = async function(showLoading, forceRefresh) {
    await originalCheckMarketPulse(showLoading, forceRefresh);
    pollAnalysisProgress(); // Start polling if background task is running
};

const originalRefreshMarketPulse = refreshMarketPulse;
refreshMarketPulse = async function() {
    await originalRefreshMarketPulse();
    pollAnalysisProgress();
};

// Initialize pulse when tab becomes active
if (typeof onTabSwitch === 'function') {
    const originalOnTabSwitch = onTabSwitch;
    onTabSwitch = function(tabId) {
        if (originalOnTabSwitch) originalOnTabSwitch(tabId);
        if (tabId === 'pulse') {
            // Check pulse data when pulse tab is activated
            setTimeout(() => checkMarketPulse(false, false), 500);
        }
    };
} else {
    // Define the function if it doesn't exist
    window.onTabSwitch = function(tabId) {
        if (tabId === 'pulse') {
            // Check pulse data when pulse tab is activated
            setTimeout(() => checkMarketPulse(false, false), 500);
        }
    };
}
