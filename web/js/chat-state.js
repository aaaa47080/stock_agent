// ========================================
// chat-state.js - 聊天模組共享狀態與基礎組件
// 職責：共享狀態變量、MessageComponents、基本 UI 操作
// 載入順序：必須是所有 chat-*.js 中第一個載入
// ========================================

window.currentSessionId = null;
AppStore.set('currentSessionId', null);
window.chatInitialized = false; // 防止重複初始化
AppStore.set('chatInitialized', false);

// ✅ 效能優化：預先快取 userKey，避免每次 sendMessage 都打後端 API
let _cachedUserProvider = null;
async function getCachedUserProvider(forceRefresh = false) {
    if (!forceRefresh && _cachedUserProvider) return _cachedUserProvider;
    _cachedUserProvider = (await window.APIKeyManager?.getCurrentProvider()) || null;
    return _cachedUserProvider;
}
window.getCachedUserProvider = getCachedUserProvider;
// 當 APIKeyManager 更新金鑰時，清除快取
window.addEventListener('apiKeyUpdated', () => {
    _cachedUserProvider = null;
});

// ✅ 效能優化：scoped lucide icon 初始化，避免全頁 DOM 掃描
function createIconsIn(el) {
    if (!window.lucide || !el) return;
    window.lucide.createIcons({ nodes: Array.isArray(el) ? el : [el] });
}
window.createIconsIn = createIconsIn;

// 用於跟踪分析過程面板的展開狀態
AppStore.set('lastProcessOpenState', false);

// 編輯模式（批量刪除）
// Must be on window so chat-sessions.js (separate ES module) can access them
let isEditMode = false;
window.isEditMode = isEditMode;
let selectedSessions = new Set();
window.selectedSessions = selectedSessions;

// HITL (Human-in-the-Loop) 上下文 - 使用 Map 以避免多會話並發時的競態條件
// Key: sessionId, Value: HITL context object
const _hitlContextMap = new Map();

// Backward compatibility: expose a getter that returns context for current session
Object.defineProperty(window, '_hitlContext', {
    get() {
        return _hitlContextMap.get(window.currentSessionId);
    },
    set(value) {
        if (value === null) {
            _hitlContextMap.delete(window.currentSessionId);
        } else {
            _hitlContextMap.set(window.currentSessionId, value);
        }
    },
});
// ========================================
// MessageComponents - 結構化消息卡片組件
// ========================================
const MessageComponents = {
    /**
     * 價格卡片 - 用於顯示加密貨幣價格資訊
     */
    priceCard(symbol, data) {
        const price = data.price || data.current_price || 'N/A';
        const change = data.change_24h || data.change || 0;
        const changeClass = change >= 0 ? 'text-success' : 'text-danger';
        const changeIcon = change >= 0 ? '📈' : '📉';

        return `
            <div class="price-card bg-surface border border-white/10 rounded-2xl p-4 my-3 hover:border-primary/30 transition">
                <div class="flex justify-between items-center mb-2">
                    <div class="flex items-center gap-2">
                        <span class="text-2xl font-bold text-secondary">${symbol}</span>
                        ${data.exchange ? `<span class="text-xs text-textMuted">(${data.exchange})</span>` : ''}
                    </div>
                    <span class="${changeClass} text-sm font-medium flex items-center gap-1">
                        <span>${changeIcon}</span> ${change >= 0 ? '+' : ''}${Math.abs(change).toFixed(2)}%
                    </span>
                </div>
                <div class="text-3xl font-mono text-secondary font-bold">
                    ${typeof price === 'number' ? '$' + price.toLocaleString() : price}
                </div>
                ${
                    data.high_24h || data.low_24h
                        ? `
                <div class="flex gap-4 mt-2 text-xs text-textMuted">
                    ${data.high_24h ? `<span>H: $${data.high_24h}</span>` : ''}
                    ${data.low_24h ? `<span>L: $${data.low_24h}</span>` : ''}
                    ${data.volume_24h ? `<span>Vol: ${data.volume_24h}</span>` : ''}
                </div>
                `
                        : ''
                }
            </div>
        `;
    },

    /**
     * Pi 資訊卡片 - 用於顯示 Pi Network 相關資訊
     */
    piInfoCard(data) {
        const title = data.title || 'Pi Network';
        const content = data.content || '';
        const icon = data.icon || '🥧';

        return `
            <div class="pi-info-card border border-purple-500/20 bg-purple-500/5 rounded-2xl p-4 my-3">
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                        <span class="text-2xl">${icon}</span>
                    </div>
                    <div>
                        <div class="text-sm font-medium text-secondary">${title}</div>
                        <div class="text-xs text-textMuted">即時資訊</div>
                    </div>
                </div>
                <div class="text-sm text-textMain">
                    ${content}
                </div>
            </div>
        `;
    },

    /**
     * 市場指標卡片 - 用於顯示恐懼貪婪指數等
     */
    marketIndicatorCard(data) {
        const name = data.name || '指標';
        const value = data.value || 0;
        const status = data.status || '';
        const statusClass =
            status.includes('貪婪') || status.includes('Greed')
                ? 'text-success'
                : status.includes('恐慌') || status.includes('Fear')
                  ? 'text-danger'
                  : 'text-textMain';

        return `
            <div class="market-indicator-card bg-surface border border-white/10 rounded-xl p-4 my-3">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-sm text-textMuted">${name}</span>
                    <span class="text-lg font-bold ${statusClass}">${value}/100</span>
                </div>
                <div class="text-xs ${statusClass}">${status}</div>
            </div>
        `;
    },

    /**
     * Gas 費用卡片 - 用於顯示 Ethereum Gas 費用
     */
    gasFeeCard(data) {
        const low = data.low || data.safe || 'N/A';
        const average = data.average || data.propose || 'N/A';
        const high = data.high || data.fast || 'N/A';

        return `
            <div class="gas-fee-card bg-surface border border-amber-500/20 rounded-xl p-4 my-3">
                <div class="flex items-center gap-2 mb-3">
                    <span class="text-xl">⛽</span>
                    <span class="text-sm font-medium text-secondary">Ethereum Gas 費用 (Gwei)</span>
                </div>
                <div class="grid grid-cols-3 gap-2 text-center">
                    <div class="bg-background/50 rounded-lg p-2">
                        <div class="text-xs text-textMuted">🐢 慢速</div>
                        <div class="text-sm font-mono text-secondary">${low}</div>
                    </div>
                    <div class="bg-background/50 rounded-lg p-2">
                        <div class="text-xs text-textMuted">🚗 標準</div>
                        <div class="text-sm font-mono text-secondary">${average}</div>
                    </div>
                    <div class="bg-background/50 rounded-lg p-2">
                        <div class="text-xs text-textMuted">🚀 快速</div>
                        <div class="text-sm font-mono text-secondary">${high}</div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * 鯨魚交易卡片 - 用於顯示大額交易
     */
    whaleTransactionCard(data) {
        const transactions = data.transactions || [];

        if (transactions.length === 0) {
            return `
                <div class="whale-card bg-surface border border-blue-500/20 rounded-xl p-4 my-3">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-xl">🐋</span>
                        <span class="text-sm font-medium text-secondary">鯨魚監控</span>
                    </div>
                    <div class="text-sm text-textMuted">目前沒有發現大額交易活動</div>
                </div>
            `;
        }

        let txList = transactions
            .slice(0, 5)
            .map(
                (tx) => `
            <div class="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                <div class="flex items-center gap-2">
                    <span class="text-xs text-textMuted font-mono">${tx.hash || 'N/A'}</span>
                </div>
                <div class="text-right">
                    <div class="text-sm font-medium ${tx.usd >= 1000000 ? 'text-warning' : 'text-secondary'}">$${(tx.usd || 0).toLocaleString()}</div>
                    <div class="text-xs text-textMuted">${tx.amount || ''} ${tx.symbol || ''}</div>
                </div>
            </div>
        `
            )
            .join('');

        return `
            <div class="whale-card bg-surface border border-blue-500/20 rounded-xl p-4 my-3">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-xl">🐋</span>
                        <span class="text-sm font-medium text-secondary">鯨魚大額轉帳</span>
                    </div>
                    <span class="text-xs text-textMuted">≥ $${(data.min_value || 500000).toLocaleString()}</span>
                </div>
                <div class="divide-y divide-white/5">
                    ${txList}
                </div>
            </div>
        `;
    },

    /**
     * 資金流向卡片 - 用於顯示交易所資金流
     */
    exchangeFlowCard(data) {
        const symbol = data.symbol || 'BTC';
        const flow = data.flow || '流出';
        const flowClass = flow.includes('流出') ? 'text-success' : 'text-danger';
        const interpretation = data.interpretation || '';

        return `
            <div class="flow-card bg-surface border border-white/10 rounded-xl p-4 my-3">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-xl">🏦</span>
                        <span class="text-sm font-medium text-secondary">${symbol} 交易所資金流向</span>
                    </div>
                    <span class="text-sm font-medium ${flowClass}">${flow}</span>
                </div>
                ${interpretation ? `<div class="text-xs text-textMuted">${interpretation}</div>` : ''}
            </div>
        `;
    },

    /**
     * 通用資訊卡片 - 用於顯示任何類型的摘要資訊
     */
    infoCard(title, content, icon = '📊') {
        return `
            <div class="info-card bg-surface border border-white/10 rounded-xl p-4 my-3">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-xl">${icon}</span>
                    <span class="text-sm font-medium text-secondary">${title}</span>
                </div>
                <div class="text-sm text-textMain">
                    ${content}
                </div>
            </div>
        `;
    },

    /**
     * 檢測內容中的結構化數據並渲染為卡片
     */
    renderStructuredContent(content, data) {
        // 如果有結構化數據，嘗試渲染卡片
        if (data && typeof data === 'object') {
            let cardsHtml = '';

            // 價格數據
            if (data.price_data || data.symbol) {
                cardsHtml += this.priceCard(data.symbol || 'BTC', data.price_data || data);
            }

            // Pi 相關數據
            if (data.pi_data || data.pi_network) {
                cardsHtml += this.piInfoCard(data.pi_data || data.pi_network);
            }

            // Gas 費用數據
            if (data.gas_fees) {
                cardsHtml += this.gasFeeCard(data.gas_fees);
            }

            // 鯨魚交易數據
            if (data.whale_transactions) {
                cardsHtml += this.whaleTransactionCard(data.whale_transactions);
            }

            // 資金流向數據
            if (data.exchange_flow) {
                cardsHtml += this.exchangeFlowCard(data.exchange_flow);
            }

            // 如果有卡片，則在內容前插入
            if (cardsHtml) {
                return cardsHtml + content;
            }
        }

        // 沒有結構化數據，直接返回原始內容
        return content;
    },
};

// 全域暴露 MessageComponents
window.MessageComponents = MessageComponents;
// isAnalyzing is declared globally in app.js
// Note: lastProcessOpenState, isEditMode, selectedSessions are already declared at the top of this file

function appendMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    // 使用 bot-bubble 取代原本的 bot-message 來套用背景框，bot-message 則保持透明
    div.className = `message-bubble ${role === 'user' ? 'user-message' : 'bot-bubble prose'}`;

    if (role === 'bot') {
        // BUG FIX: 檢查 md 對象是否存在且 render 方法可用
        // 防止在 markdown 庫未載入時崩潰
        // 安全修復: 使用 SecurityUtils 清理 HTML 防止 XSS
        if (typeof md !== 'undefined' && md && typeof md.render === 'function') {
            const rendered = md.render(content);
            // 使用 SecurityUtils.sanitizeHTML 清理，如果不存在則降級為 textContent
            if (typeof SecurityUtils !== 'undefined' && SecurityUtils.sanitizeHTML) {
                div.innerHTML = SecurityUtils.sanitizeHTML(rendered);
            } else {
                div.innerHTML = rendered;
                console.warn('[chat] SecurityUtils 未載入，XSS 防護可能不足');
            }
        } else {
            // 降級處理：使用純文本顯示，轉義 HTML 防止 XSS
            div.textContent = content;
            console.warn('[chat] markdown 庫未載入，使用純文本顯示');
        }
        // Wrap tables in overflow-x container for proper horizontal scroll + border styling
        div.querySelectorAll('table').forEach((table) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'table-wrapper';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });
        const match = content.match(/\b([A-Z]{2,5})\b/);
        if (match && !content.includes('載入中') && !content.includes('Error')) {
            // 安全修復: 驗證 symbol 只包含合法的大寫字母
            let symbol = match[1];
            if (!/^[A-Z]{2,5}$/.test(symbol)) {
                console.warn('[chat] 無效的股票代號:', symbol);
                symbol = '';
            }
            if (symbol) {
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'flex gap-2 mt-4 pt-4 border-t border-white/5';
                const chartBtn = document.createElement('button');
                chartBtn.className =
                    'text-xs bg-primary/10 text-primary px-3 py-1.5 rounded-full hover:bg-primary/20 border border-primary/20 transition flex items-center gap-1.5';
                chartBtn.innerHTML = '<i data-lucide="bar-chart" class="w-3 h-3"></i> Chart';
                chartBtn.onclick = () => showChart(symbol);
                actionsDiv.appendChild(chartBtn);

                div.appendChild(actionsDiv);
                setTimeout(() => createIconsIn(div), 0);
            }
        }
    } else {
        div.textContent = content;
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}
window.appendMessage = appendMessage;

function toggleOptions() {
    const panel = document.getElementById('analysis-options-panel');
    panel.classList.toggle('hidden');
    createIconsIn(panel);
}
window.toggleOptions = toggleOptions;

function toggleSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');

    if (sidebar.classList.contains('-translate-x-full')) {
        // 打開側邊欄
        sidebar.classList.remove('-translate-x-full');
        // 顯示背景遮罩（僅在手機上）
        if (backdrop) {
            backdrop.classList.remove('hidden');
        }
    } else {
        // 關閉側邊欄
        sidebar.classList.add('-translate-x-full');
        // 隱藏背景遮罩
        if (backdrop) {
            backdrop.classList.add('hidden');
        }

        // 如果當前頁面不是活動標籤頁，則返回到活動標籤頁
        // 這確保在關閉側邊欄時返回到正確的頁面
        if (typeof currentActiveTab !== 'undefined' && typeof switchTab === 'function') {
            // 延遲執行，確保側邊欄動畫完成
            setTimeout(() => {
                // 檢查當前是否在活動標籤頁上，如果不是則切換回去
                const currentVisibleTab = document.querySelector('.tab-content:not(.hidden)');
                if (currentVisibleTab && !currentVisibleTab.id.includes(AppStore.get('activeTab'))) {
                    switchTab(AppStore.get('activeTab'));
                }
            }, 150);
        }
    }
}
window.toggleSidebar = toggleSidebar;

export {
    getCachedUserProvider,
    createIconsIn,
    MessageComponents,
    appendMessage,
    toggleOptions,
    toggleSidebar,
};
