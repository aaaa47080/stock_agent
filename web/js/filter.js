// ========================================
// filter.js - 過濾器功能
// ========================================

// 預設熱門幣種列表 (當用戶未選擇時顯示)
// 預設熱門幣種列表 (當用戶未選擇時顯示)
var DEFAULT_MARKET_SYMBOLS = [
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'DOGE-USDT', 'XRP-USDT',
    'BNB-USDT', 'ADA-USDT', 'AVAX-USDT', 'DOT-USDT', 'LINK-USDT'
];

// 從 localStorage 載入已保存的選擇
function loadSavedSymbolSelection() {
    try {
        const saved = localStorage.getItem('marketWatchSymbols');
        if (saved) {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed) && parsed.length > 0) {
                window.globalSelectedSymbols = parsed;
                console.log('[Filter] 已載入保存的選擇:', parsed.length, '個幣種');
                return true;
            }
        }
    } catch (e) {
        console.error('[Filter] 載入保存的選擇失敗:', e);
    }

    // 如果沒有保存的選擇，保持為空，讓 market.js 加載後端預設數據 (Auto Mode)
    window.globalSelectedSymbols = [];
    console.log('[Filter] 無保存紀錄，初始化為空 (Auto Mode)');
    return true;
}

// 保存選擇到 localStorage
function saveSymbolSelection() {
    try {
        if (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0) {
            localStorage.setItem('marketWatchSymbols', JSON.stringify(window.globalSelectedSymbols));
            console.log('[Filter] 已保存選擇:', window.globalSelectedSymbols.length, '個幣種');
        } else {
            localStorage.removeItem('marketWatchSymbols');
            console.log('[Filter] 已清除保存的選擇');
        }
    } catch (e) {
        console.error('[Filter] 保存選擇失敗:', e);
    }
}

// 初始化時載入保存的選擇
document.addEventListener('DOMContentLoaded', () => {
    loadSavedSymbolSelection();
});

async function openGlobalFilter() {
    const modal = document.getElementById('global-filter-modal');
    modal.classList.remove('hidden');

    const select = document.getElementById('filter-exchange-select');
    if (select) select.value = window.currentFilterExchange || 'okx';

    if (!window.allMarketSymbols || window.allMarketSymbols.length === 0) {
        await fetchSymbols(window.currentFilterExchange || 'okx');
    } else {
        renderSymbolList(window.allMarketSymbols);
    }
}

async function switchFilterExchange(exchange) {
    if (exchange === window.currentFilterExchange) return;

    if (window.globalSelectedSymbols && window.globalSelectedSymbols.length > 0) {
        const confirmed = await showConfirm({
            title: '切換交易所',
            message: '切換交易所將清除目前的選擇，是否繼續？',
            type: 'warning',
            confirmText: '繼續',
            cancelText: '取消'
        });

        if (!confirmed) {
            const select = document.getElementById('filter-exchange-select');
            if (select) select.value = window.currentFilterExchange || 'okx';
            return;
        }
    }

    window.currentFilterExchange = exchange;
    window.globalSelectedSymbols = [];
    window.allMarketSymbols = [];
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
            window.allMarketSymbols = data.symbols.sort();
            renderSymbolList(window.allMarketSymbols);
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

    const toRender = filtered.sort((a, b) => {
        const aSelected = window.globalSelectedSymbols && window.globalSelectedSymbols.includes(a);
        const bSelected = window.globalSelectedSymbols && window.globalSelectedSymbols.includes(b);
        if (aSelected && !bSelected) return -1;
        if (!aSelected && bSelected) return 1;
        return a.localeCompare(b);
    }).slice(0, 200);

    if (toRender.length === 0) {
        container.innerHTML = '<div class="text-center py-8 text-slate-500">沒有找到符合的幣種</div>';
    } else {
        toRender.forEach(s => {
            const isChecked = window.globalSelectedSymbols && window.globalSelectedSymbols.includes(s);
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

    document.getElementById('selected-count-modal').innerText = (window.globalSelectedSymbols || []).length;
    lucide.createIcons();
}

function toggleSymbolSelection(s) {
    if (window.globalSelectedSymbols && window.globalSelectedSymbols.includes(s)) {
        window.globalSelectedSymbols = window.globalSelectedSymbols.filter(item => item !== s);
    } else {
        if (!window.globalSelectedSymbols) window.globalSelectedSymbols = [];
        window.globalSelectedSymbols.push(s);
    }
    renderSymbolList(window.allMarketSymbols || []);
}

function selectAllMatches() {
    const searchVal = document.getElementById('symbol-search').value.toUpperCase().trim();
    if (!searchVal) return;

    const filtered = (window.allMarketSymbols || []).filter(s => s.includes(searchVal));
    let addedCount = 0;
    filtered.forEach(s => {
        if (!window.globalSelectedSymbols) window.globalSelectedSymbols = [];
        if (!window.globalSelectedSymbols.includes(s)) {
            window.globalSelectedSymbols.push(s);
            addedCount++;
        }
    });
    if (addedCount > 0) renderSymbolList(window.allMarketSymbols || []);
}

function applyGlobalFilter() {
    document.getElementById('global-filter-modal').classList.add('hidden');
    const indicator = document.getElementById('active-filter-indicator');
    const headerBadge = document.getElementById('global-count-badge');

    // 保存選擇到 localStorage
    saveSymbolSelection();

    const count = (window.globalSelectedSymbols || []).length;
    if (headerBadge) {
        headerBadge.innerText = count > 0 ? count : 'Auto';
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
    if (typeof window.refreshScreener === 'function') {
        window.refreshScreener(true);
    } else if (typeof refreshScreener === 'function') {
        refreshScreener(true);
    } else {
        console.error('[Filter] refreshScreener is not defined');
    }

    // Only refresh Pulse if visible (to save tokens), otherwise it will refresh on tab switch
    if (!document.getElementById('pulse-tab').classList.contains('hidden')) {
        checkMarketPulse(true);
    }
}

function clearGlobalFilter() {
    window.globalSelectedSymbols = [...DEFAULT_MARKET_SYMBOLS];
    localStorage.removeItem('marketWatchSymbols');
    console.log('[Filter] 已重置為預設熱門幣種');
    applyGlobalFilter();
}
