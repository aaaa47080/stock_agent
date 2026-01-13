// ========================================
// filter.js - 過濾器功能
// ========================================

async function openGlobalFilter() {
    const modal = document.getElementById('global-filter-modal');
    modal.classList.remove('hidden');

    const select = document.getElementById('filter-exchange-select');
    if (select) select.value = currentFilterExchange;

    if (allMarketSymbols.length === 0) {
        await fetchSymbols(currentFilterExchange);
    } else {
        renderSymbolList(allMarketSymbols);
    }
}

async function switchFilterExchange(exchange) {
    if (exchange === currentFilterExchange) return;

    if (globalSelectedSymbols.length > 0) {
        const confirmed = await showConfirm({
            title: '切換交易所',
            message: '切換交易所將清除目前的選擇，是否繼續？',
            type: 'warning',
            confirmText: '繼續',
            cancelText: '取消'
        });

        if (!confirmed) {
            const select = document.getElementById('filter-exchange-select');
            if (select) select.value = currentFilterExchange;
            return;
        }
    }

    currentFilterExchange = exchange;
    globalSelectedSymbols = [];
    allMarketSymbols = [];
    await fetchSymbols(exchange);
}

async function fetchSymbols(exchange) {
    const container = document.getElementById('symbol-list-container');
    container.innerHTML = '<div class="text-center py-8 text-slate-500 animate-pulse">正在從交易所獲取幣種列表...</div>';

    try {
        const res = await fetch(`/api/market/symbols?exchange=${exchange}`);
        
        if (!res.ok) {
            throw new Error(`HTTP Error ${res.status}`);
        }

        const data = await res.json();
        if (data.symbols) {
            allMarketSymbols = data.symbols.sort();
            renderSymbolList(allMarketSymbols);
        } else {
            container.innerHTML = '<div class="text-center py-8 text-red-400">無法獲取幣種列表 (格式錯誤)</div>';
        }
    } catch (e) {
        console.error("Failed to fetch symbols", e);
        
        let errorMessage = '連線錯誤';
        let detail = e.message;

        if (e.message.includes('429')) {
            errorMessage = 'API 請求過於頻繁';
        } else if (e.message.includes('500')) {
            errorMessage = '伺服器內部錯誤';
        } else if (e.message.includes('timeout') || e.message.includes('NetworkError') || e.message.includes('Failed to fetch')) {
            errorMessage = '網路連線失敗';
        }

        container.innerHTML = `
            <div class="text-center py-8 text-red-400 flex flex-col items-center gap-2">
                <i data-lucide="wifi-off" class="w-8 h-8 opacity-50"></i>
                <span class="font-bold">${errorMessage}</span>
                <span class="text-xs opacity-70 mb-2">${detail}</span>
                <button onclick="fetchSymbols('${exchange}')" class="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm transition border border-red-500/20">
                    重試
                </button>
            </div>`;
        lucide.createIcons();
    }
}

function renderSymbolList(symbols) {
    const container = document.getElementById('symbol-list-container');
    container.innerHTML = '';

    const searchVal = document.getElementById('symbol-search').value.toUpperCase().trim();
    const filtered = symbols.filter(s => s.includes(searchVal));

    const toRender = filtered.slice(0, 200);

    if (toRender.length === 0) {
        container.innerHTML = '<div class="text-center py-8 text-slate-500">沒有找到符合的幣種</div>';
    } else {
        toRender.forEach(s => {
            const isChecked = globalSelectedSymbols.includes(s);
            const div = document.createElement('div');
            div.className = `flex items-center justify-between p-3 rounded-lg cursor-pointer transition select-none ${isChecked ? 'bg-blue-900/30 border border-blue-500/50' : 'hover:bg-slate-800 border border-transparent'}`;
            div.onclick = () => toggleSymbolSelection(s);
            div.innerHTML = `
                <span class="text-sm font-mono ${isChecked ? 'text-blue-300 font-bold' : 'text-slate-300'}">${s}</span>
                <div class="w-5 h-5 rounded border ${isChecked ? 'bg-blue-600 border-blue-600' : 'border-slate-600 bg-slate-800'} flex items-center justify-center transition">
                    ${isChecked ? '<i data-lucide="check" class="w-3.5 h-3.5 text-white"></i>' : ''}
                </div>
            `;
            container.appendChild(div);
        });
    }

    document.getElementById('selected-count-modal').innerText = globalSelectedSymbols.length;
    lucide.createIcons();
}

function toggleSymbolSelection(s) {
    if (globalSelectedSymbols.includes(s)) {
        globalSelectedSymbols = globalSelectedSymbols.filter(item => item !== s);
    } else {
        globalSelectedSymbols.push(s);
    }
    renderSymbolList(allMarketSymbols);
}

function selectAllMatches() {
    const searchVal = document.getElementById('symbol-search').value.toUpperCase().trim();
    if (!searchVal) return;

    const filtered = allMarketSymbols.filter(s => s.includes(searchVal));
    let addedCount = 0;
    filtered.forEach(s => {
        if (!globalSelectedSymbols.includes(s)) {
            globalSelectedSymbols.push(s);
            addedCount++;
        }
    });
    if (addedCount > 0) renderSymbolList(allMarketSymbols);
}

function applyGlobalFilter() {
    document.getElementById('global-filter-modal').classList.add('hidden');
    const indicator = document.getElementById('active-filter-indicator');
    const headerBadge = document.getElementById('global-count-badge');

    // 新聞來源固定使用所有來源（不需要用戶選擇）
    // selectedNewsSources 在 app.js 中已經預設為所有來源

    const count = globalSelectedSymbols.length;
    if (headerBadge) {
        headerBadge.innerText = count > 0 ? count : '自動';
    }

    if (count > 0) {
        if (indicator) {
            indicator.classList.remove('hidden');
            document.getElementById('filter-count').innerText = count;
        }
    } else {
        if (indicator) indicator.classList.add('hidden');
    }

    // Refresh both main components
    refreshScreener(true);

    // Only refresh Pulse if visible (to save tokens), otherwise it will refresh on tab switch
    if (!document.getElementById('pulse-tab').classList.contains('hidden')) {
        checkMarketPulse(true);
    }
}

function clearGlobalFilter() {
    globalSelectedSymbols = [];
    applyGlobalFilter();
}
