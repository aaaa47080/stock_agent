// ========================================
// watchlist.js - 自選清單功能
// ========================================

async function refreshWatchlist() {
    const container = document.getElementById('watchlist-container');
    container.innerHTML = '<div class="bg-surface rounded-2xl p-6 text-center"><div class="animate-pulse">載入中...</div></div>';
    try {
        const res = await fetch(`/api/watchlist/${currentUserId}`);
        const data = await res.json();
        if (!data.symbols || data.symbols.length === 0) {
            container.innerHTML = '<div class="bg-surface rounded-2xl p-6 text-center text-textMuted"><i data-lucide="star" class="w-12 h-12 mx-auto mb-3 opacity-30"></i><p>您還沒有收藏任何幣種</p></div>';
            lucide.createIcons(); return;
        }
        container.innerHTML = '';
        for (const symbol of data.symbols) {
            const card = document.createElement('div');
            card.className = 'bg-surface rounded-2xl p-4 hover:bg-surfaceHighlight transition cursor-pointer border border-white/5';
            card.innerHTML = `<div class="flex items-center justify-between"><div class="flex items-center gap-3"><div class="w-10 h-10 bg-gradient-to-br from-primary to-accent rounded-full flex items-center justify-center font-bold text-secondary">${symbol.substring(0, 2)}</div><div><div class="font-semibold text-secondary">${symbol}</div></div></div><div class="flex gap-2"><button onclick="event.stopPropagation(); showChart('${symbol}')" class="p-2 bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition border border-primary/20"><i data-lucide="trending-up" class="w-4 h-4"></i></button><button onclick="event.stopPropagation(); removeFromWatchlist('${symbol}')" class="p-2 bg-danger/10 text-danger rounded-lg hover:bg-danger/20 transition border border-danger/20"><i data-lucide="trash-2" class="w-4 h-4"></i></button></div></div>`;
            card.onclick = () => showChart(symbol);
            container.appendChild(card);
        }
        lucide.createIcons();
    } catch (err) { console.error(err); }
}

async function addToWatchlist(symbol) {
    try {
        const res = await fetch('/api/watchlist/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: currentUserId, symbol: symbol }) });
        const data = await res.json(); if (data.success) alert(`✅ ${symbol} 已加入自選！`);
    } catch (err) { console.error(err); }
}

async function removeFromWatchlist(symbol) {
    if (!confirm(`確定要移除 ${symbol} 嗎？`)) return;
    try {
        const res = await fetch('/api/watchlist/remove', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: currentUserId, symbol: symbol }) });
        const data = await res.json(); if (data.success) refreshWatchlist();
    } catch (err) { console.error(err); }
}

async function showChart(symbol) {
    const chartSection = document.getElementById('chart-section');
    const chartContainer = document.getElementById('chart-container');
    chartSection.classList.remove('hidden');
    document.getElementById('chart-title').textContent = symbol;
    chartContainer.innerHTML = '<div class="animate-pulse text-textMuted">載入圖表中...</div>';
    try {
        const res = await fetch('/api/klines', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: symbol, interval: '1d', limit: 100 }) });
        const data = await res.json();
        if (!data.klines || data.klines.length === 0) { chartContainer.innerHTML = '<div class="text-danger">無法載入數據</div>'; return; }
        chartContainer.innerHTML = '';
        if (chart) chart.remove();
        chart = LightweightCharts.createChart(chartContainer, { width: chartContainer.clientWidth, height: 380, layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8' }, grid: { vertLines: { color: 'rgba(51, 65, 85, 0.3)' }, horzLines: { color: 'rgba(51, 65, 85, 0.3)' } }, timeScale: { borderColor: '#334155', timeVisible: true } });
        candleSeries = chart.addCandlestickSeries({ upColor: '#22c55e', downColor: '#ef4444' });
        candleSeries.setData(data.klines);
        chart.timeScale().fitContent();
    } catch (err) { console.error(err); }
}
