/**
 * US Stock Tab - 美股看板
 * 
 * 提供美股市場看盤和 AI 脈動分析功能
 */

window.USStockTab = {
    currentSubTab: 'market',
    popularStocks: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'AMD', 'INTC'],
    indices: ['^DJI', '^GSPC', '^IXIC'],
    
    /**
     * 初始化美股看板
     */
    init: function() {
        console.log('[USStockTab] Initializing...');
        this.switchSubTab('market');
    },
    
    /**
     * 切換子標籤頁
     */
    switchSubTab: function(tabId) {
        this.currentSubTab = tabId;
        
        // 更新按鈕樣式
        document.querySelectorAll('.usstock-sub-tab').forEach(btn => {
            btn.classList.remove('bg-primary', 'text-background', 'shadow-md');
            btn.classList.add('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
        });
        
        const activeBtn = document.getElementById(`usstock-btn-${tabId}`);
        if (activeBtn) {
            activeBtn.classList.remove('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
            activeBtn.classList.add('bg-primary', 'text-background', 'shadow-md');
        }
        
        // 切換內容區域
        document.getElementById('usstock-market-content').classList.toggle('hidden', tabId !== 'market');
        document.getElementById('usstock-pulse-content').classList.toggle('hidden', tabId !== 'pulse');
        
        // 載入數據
        if (tabId === 'market') {
            this.loadMarketWatch();
        } else if (tabId === 'pulse') {
            this.loadAIPulse();
        }
    },
    
    /**
     * 刷新當前標籤頁
     */
    refreshCurrent: function() {
        console.log('[USStockTab] Refreshing...');
        if (this.currentSubTab === 'market') {
            this.loadMarketWatch();
        } else if (this.currentSubTab === 'pulse') {
            this.loadAIPulse();
        }
    },
    
    /**
     * 載入市場看盤
     */
    loadMarketWatch: async function() {
        console.log('[USStockTab] Loading market watch...');
        
        // 載入熱門美股
        await this.loadPopularStocks();
        
        // 載入大盤指數
        await this.loadMarketIndices();
    },
    
    /**
     * 載入熱門美股
     */
    loadPopularStocks: async function() {
        const container = document.getElementById('usstock-popular-stocks');
        if (!container) return;
        
        container.innerHTML = '<div class="text-center text-textMuted py-8">載入中...</div>';
        
        try {
            // 使用 Yahoo Finance API 獲取數據
            const stocks = [];
            for (const symbol of this.popularStocks) {
                try {
                    const response = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=1d`);
                    if (response.ok) {
                        const data = await response.json();
                        const result = data.chart.result[0];
                        const meta = result.meta;
                        const price = meta.regularMarketPrice;
                        const change = meta.regularMarketChange;
                        const changePercent = meta.regularMarketChangePercent;
                        
                        stocks.push({
                            symbol,
                            name: meta.shortName || symbol,
                            price,
                            change,
                            changePercent
                        });
                    }
                } catch (e) {
                    console.warn(`Failed to load ${symbol}:`, e);
                }
            }
            
            // 渲染股票卡片
            container.innerHTML = stocks.map(stock => `
                <div class="bg-surface border border-white/5 rounded-xl p-4 hover:bg-surfaceHighlight transition cursor-pointer">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <h4 class="font-bold text-secondary">${stock.symbol}</h4>
                            <p class="text-xs text-textMuted truncate">${stock.name}</p>
                        </div>
                        <div class="text-right">
                            <p class="font-bold text-secondary">$${stock.price?.toFixed(2)}</p>
                            <p class="text-xs ${stock.change >= 0 ? 'text-success' : 'text-danger'}">
                                ${stock.change >= 0 ? '+' : ''}${stock.change?.toFixed(2)} (${stock.changePercent?.toFixed(2)}%)
                            </p>
                        </div>
                    </div>
                </div>
            `).join('');
            
        } catch (error) {
            console.error('[USStockTab] Failed to load popular stocks:', error);
            container.innerHTML = '<div class="text-center text-danger py-8">載入失敗</div>';
        }
    },
    
    /**
     * 載入大盤指數
     */
    loadMarketIndices: async function() {
        const container = document.getElementById('usstock-market-indices');
        if (!container) return;
        
        container.innerHTML = '<div class="text-center text-textMuted py-8">載入中...</div>';
        
        try {
            const indices = [
                { symbol: '^DJI', name: '道瓊工業指數' },
                { symbol: '^GSPC', name: 'S&P 500' },
                { symbol: '^IXIC', name: '那斯達克綜合指數' }
            ];
            
            const indexData = [];
            for (const idx of indices) {
                try {
                    const response = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${idx.symbol}?interval=1d&range=1d`);
                    if (response.ok) {
                        const data = await response.json();
                        const meta = data.chart.result[0].meta;
                        indexData.push({
                            ...idx,
                            price: meta.regularMarketPrice,
                            change: meta.regularMarketChange,
                            changePercent: meta.regularMarketChangePercent
                        });
                    }
                } catch (e) {
                    console.warn(`Failed to load ${idx.symbol}:`, e);
                }
            }
            
            container.innerHTML = indexData.map(idx => `
                <div class="bg-surface border border-white/5 rounded-xl p-4">
                    <h4 class="text-xs text-textMuted mb-2">${idx.name}</h4>
                    <p class="font-bold text-secondary text-lg">$${idx.price?.toFixed(2)}</p>
                    <p class="text-xs ${idx.change >= 0 ? 'text-success' : 'text-danger'}">
                        ${idx.change >= 0 ? '↑' : '↓'} ${idx.change?.toFixed(2)} (${idx.changePercent?.toFixed(2)}%)
                    </p>
                </div>
            `).join('');
            
        } catch (error) {
            console.error('[USStockTab] Failed to load market indices:', error);
            container.innerHTML = '<div class="text-center text-danger py-8">載入失敗</div>';
        }
    },
    
    /**
     * 載入 AI 脈動分析
     */
    loadAIPulse: function() {
        const container = document.getElementById('usstock-pulse-content');
        if (!container) return;
        
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-20 text-center">
                <i data-lucide="brain-circuit" class="w-16 h-16 text-primary mb-4"></i>
                <h3 class="font-serif text-xl text-secondary mb-2">AI 脈動分析</h3>
                <p class="text-textMuted text-sm mb-6">使用 AI 分析美股市場趨勢</p>
                <button onclick="document.getElementById('user-input').focus()" class="px-6 py-3 bg-primary text-background font-bold rounded-xl hover:scale-105 transition">
                    開始分析
                </button>
            </div>
        `;
        
        // 重新初始化 Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }
    },
    
    /**
     * 綁定事件
     */
    bindEvents: function() {
        // 可以在這裡添加更多事件監聽器
    }
};

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    window.USStockTab.bindEvents();
});
