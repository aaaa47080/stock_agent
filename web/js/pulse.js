// ========================================
// pulse.js - 市場脈動功能
// ========================================

async function checkMarketPulse(showLoading = false, forceRefresh = false) {
    const grid = document.getElementById('pulse-grid');
    let targets = globalSelectedSymbols.length > 0 ? globalSelectedSymbols : ['BTC', 'ETH', 'SOL', 'PI'];
    if (showLoading) {
        grid.innerHTML = '';
        targets.forEach(symbol => {
            const el = document.createElement('div');
            el.className = 'glass-card rounded-2xl p-6 h-full flex flex-col items-center justify-center min-h-[200px]';
            el.innerHTML = `<div class="animate-pulse text-slate-400">AI 分析中...</div>`;
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

        // 1. Trigger global batch update on server with specific symbols
        const res = await fetch('/api/market-pulse/refresh-all', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbols: targets })
        });
        
        if (!res.ok) throw new Error("Refresh failed");
        
        // 2. Fetch the newly cached data
        await checkMarketPulse(true, false);
        
    } catch (e) {
        console.error("Market Pulse Refresh Error:", e);
        alert("重新整理失敗，請稍後再試");
    } finally {
        setTimeout(() => {
            if (btn) btn.disabled = false;
            if (icon) icon.classList.remove('animate-spin');
            lucide.createIcons();
        }, 1000);
    }
}

async function fetchPulseForSymbol(symbol, forceRefresh = false) {
    const cardId = `pulse-card-${symbol}`;
    let card = document.getElementById(cardId); if (!card) return;
    try {
        const sourcesQuery = selectedNewsSources.join(',');
        const refreshParam = forceRefresh ? '&refresh=true' : '';
        // Add cache buster
        const tParam = `&_t=${new Date().getTime()}`;
        
        const res = await fetch(`/api/market-pulse/${symbol}?sources=${sourcesQuery}${refreshParam}${tParam}`);
        const data = await res.json();

        const report = data.report || {
            summary: data.explanation,
            key_points: [],
            highlights: [],
            risks: []
        };

        if (report.summary) {
            currentPulseData[symbol] = data;
            const isPositive = data.change_24h > 0;

            const updatedTime = new Date(data.timestamp);
            const timeString = updatedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const uniqueSources = data.news_sources ? [...new Set(data.news_sources.map(n => n.source.split(' ')[0]))].join(', ') : '';

            card.className = "glass-card rounded-2xl p-0 h-full flex flex-col hover:border-blue-500/30 transition duration-300 overflow-hidden";

            // 1. Header Section (Price & Summary)
            let html = `
                <div class="p-5 border-b border-slate-700/50 bg-slate-800/20">
                    <div class="flex justify-between items-start mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 ${isPositive ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'} rounded-xl flex items-center justify-center">
                                <i data-lucide="${isPositive ? 'trending-up' : 'trending-down'}" class="w-5 h-5"></i>
                            </div>
                            <div>
                                <h3 class="font-bold text-lg flex items-center gap-2">
                                    ${data.symbol}
                                    <span class="text-xs font-normal text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">${timeString}</span>
                                </h3>
                                <div class="text-xs text-slate-400">
                                    $${data.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    <span class="ml-1 ${isPositive ? 'text-green-400' : 'text-red-400'}">
                                        ${data.change_24h > 0 ? '+' : ''}${data.change_24h.toFixed(2)}%
                                    </span>
                                </div>
                            </div>
                        </div>
                        <span class="px-2 py-1 rounded bg-slate-800 text-[10px] text-slate-400 border border-slate-700">1H: ${data.change_1h > 0 ? '+' : ''}${data.change_1h.toFixed(2)}%</span>
                    </div>
                    <p class="text-slate-200 text-sm font-medium leading-relaxed">${report.summary}</p>
                </div>
            `;

            // 2. Body Section (Scrollable)
            html += `<div class="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-5">`;

            // Key Points
            if (report.key_points && report.key_points.length > 0) {
                html += `
                    <div>
                        <h4 class="text-xs font-bold text-blue-400 mb-2 flex items-center gap-1 uppercase tracking-wider">
                            <i data-lucide="sparkles" class="w-3 h-3"></i> 要點
                        </h4>
                        <ul class="space-y-2">
                            ${report.key_points.map((point, idx) => `
                                <li class="flex gap-2 text-xs text-slate-300">
                                    <span class="text-blue-500/50 font-mono">${idx + 1}.</span>
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
                        <h4 class="text-xs font-bold text-purple-400 mb-2 flex items-center gap-1 uppercase tracking-wider">
                            <i data-lucide="zap" class="w-3 h-3"></i> 亮點
                        </h4>
                        <div class="space-y-2">
                            ${report.highlights.map(item => `
                                <div class="bg-slate-800/40 rounded-lg p-3 border border-slate-700/50">
                                    <div class="text-xs font-semibold text-slate-200 mb-1">${item.title}</div>
                                    <div class="text-[11px] text-slate-400 leading-normal">${item.content}</div>
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
                        <h4 class="text-xs font-bold text-orange-400 mb-2 flex items-center gap-1 uppercase tracking-wider">
                            <i data-lucide="alert-triangle" class="w-3 h-3"></i> 風險
                        </h4>
                        <ul class="space-y-1">
                            ${report.risks.map(risk => `
                                <li class="flex gap-2 text-xs text-slate-400">
                                    <i data-lucide="alert-circle" class="w-3 h-3 text-orange-500/50 mt-0.5 shrink-0"></i>
                                    <span>${risk}</span>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                `;
            }

            html += `</div>`; // End Body

            // 3. Footer Section
            html += `
                <div class="p-4 border-t border-slate-700/50 bg-slate-800/30 flex justify-between items-center text-[10px] text-slate-500">
                    <div class="flex items-center gap-2">
                        <span title="${uniqueSources}">Refs: ${data.news_sources ? data.news_sources.length : 0}</span>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="showNewsList('${symbol}')" class="px-2 py-1.5 hover:bg-slate-700/50 rounded transition text-blue-400 flex items-center gap-1">
                            <i data-lucide="newspaper" class="w-3 h-3"></i> 新聞
                        </button>
                        <button onclick="switchTab('chat'); quickAsk('${data.symbol} 詳細分析')" class="px-2 py-1.5 bg-purple-600/20 text-purple-300 hover:bg-purple-600/30 rounded transition flex items-center gap-1 border border-purple-500/20">
                            <i data-lucide="bot" class="w-3 h-3"></i> 詳情
                        </button>
                    </div>
                </div>
            `;

            card.innerHTML = html;
            lucide.createIcons();
        }
    } catch (e) { console.error(e); }
}

function showNewsList(symbol) {
    const data = currentPulseData[symbol]; if (!data || !data.news_sources) return;
    const modal = document.getElementById('news-modal');
    const listContent = document.getElementById('news-list-content');
    document.getElementById('news-modal-symbol').innerText = symbol;
    listContent.innerHTML = '';
    data.news_sources.forEach(news => {
        const item = document.createElement('div');
        item.className = 'bg-slate-800/50 border border-slate-700 p-3 rounded-xl hover:bg-slate-800 transition group';
        item.innerHTML = `<div class="flex justify-between items-start mb-1"><span class="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-400 rounded border border-blue-500/20">${news.source}</span></div><h4 class="text-sm font-semibold text-slate-200 mb-2 group-hover:text-blue-300 transition line-clamp-2">${news.title}</h4><a href="${news.url}" target="_blank" class="text-[10px] text-blue-500 hover:underline">查看原文 <i data-lucide="external-link" class="w-2.5 h-2.5"></i></a>`;
        listContent.appendChild(item);
    });
    modal.classList.remove('hidden'); lucide.createIcons();
}
