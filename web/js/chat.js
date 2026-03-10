// ========================================
// chat.js - 聊天功能 (多會話版)
// ========================================

let currentSessionId = null;
let chatInitialized = false;  // 防止重複初始化

// ✅ 效能優化：預先快取 userKey，避免每次 sendMessage 都打後端 API
let _cachedUserKey = null;
async function getCachedUserKey(forceRefresh = false) {
    if (!forceRefresh && _cachedUserKey) return _cachedUserKey;
    _cachedUserKey = await window.APIKeyManager?.getCurrentKey() || null;
    return _cachedUserKey;
}
// 當 APIKeyManager 更新金鑰時，清除快取
window.addEventListener('apiKeyUpdated', () => { _cachedUserKey = null; });

// ✅ 效能優化：scoped lucide icon 初始化，避免全頁 DOM 掃描
function createIconsIn(el) {
    if (!window.lucide || !el) return;
    window.lucide.createIcons({ nodes: Array.isArray(el) ? el : [el] });
}

// 用於跟踪分析過程面板的展開狀態
window.lastProcessOpenState = false;

// 編輯模式（批量刪除）
let isEditMode = false;
let selectedSessions = new Set();

// HITL (Human-in-the-Loop) 上下文 - 使用 Map 以避免多會話並發時的競態條件
// Key: sessionId, Value: HITL context object
const _hitlContextMap = new Map();

// Backward compatibility: expose a getter that returns context for current session
Object.defineProperty(window, '_hitlContext', {
    get() {
        return _hitlContextMap.get(currentSessionId);
    },
    set(value) {
        if (value === null) {
            _hitlContextMap.delete(currentSessionId);
        } else {
            _hitlContextMap.set(currentSessionId, value);
        }
    }
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
                ${data.high_24h || data.low_24h ? `
                <div class="flex gap-4 mt-2 text-xs text-textMuted">
                    ${data.high_24h ? `<span>H: $${data.high_24h}</span>` : ''}
                    ${data.low_24h? `<span>L: $${data.low_24h}</span>` : ''}
                    ${data.volume_24h ? `<span>Vol: ${data.volume_24h}</span>` : ''}
                </div>
                ` : ''}
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
        const statusClass = status.includes('貪婪') || status.includes('Greed') ? 'text-success' :
                         status.includes('恐慌') || status.includes('Fear') ? 'text-danger' : 'text-textMain';

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

        let txList = transactions.slice(0, 5).map(tx => `
            <div class="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                <div class="flex items-center gap-2">
                    <span class="text-xs text-textMuted font-mono">${tx.hash || 'N/A'}</span>
                </div>
                <div class="text-right">
                    <div class="text-sm font-medium ${tx.usd >= 1000000 ? 'text-warning' : 'text-secondary'}">$${(tx.usd || 0).toLocaleString()}</div>
                    <div class="text-xs text-textMuted">${tx.amount || ''} ${tx.symbol || ''}</div>
                </div>
            </div>
        `).join('');

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
    }
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
        div.querySelectorAll('table').forEach(table => {
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
                // 使用安全的 DOM 操作而非 innerHTML
                const debateBtn = document.createElement('button');
                debateBtn.className = 'text-xs bg-gradient-to-r from-success/20 to-danger/20 text-secondary px-3 py-1.5 rounded-full hover:from-success/30 hover:to-danger/30 border border-white/10 transition flex items-center gap-1.5';
                debateBtn.innerHTML = '<i data-lucide="swords" class="w-3 h-3"></i> AI War Room';
                debateBtn.onclick = () => startDebateInChat(symbol);
                actionsDiv.appendChild(debateBtn);

                const chartBtn = document.createElement('button');
                chartBtn.className = 'text-xs bg-primary/10 text-primary px-3 py-1.5 rounded-full hover:bg-primary/20 border border-primary/20 transition flex items-center gap-1.5';
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

function toggleOptions() {
    const panel = document.getElementById('analysis-options-panel');
    panel.classList.toggle('hidden');
    createIconsIn(panel);
}

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
                if (currentVisibleTab && !currentVisibleTab.id.includes(currentActiveTab)) {
                    switchTab(currentActiveTab);
                }
            }, 150);
        }
    }
}

// ========================================
// Session Management
// ========================================

// 用於記住收藏區的展開狀態
let starredSectionOpen = true;

async function loadSessions() {
    // 🔒 安全檢查：未登入時不載入 session 列表
    const isLoggedIn = window.AuthManager?.isLoggedIn();
    if (!isLoggedIn) {
        const list = document.getElementById('chat-session-list');
        if (list) {
            list.innerHTML = '<div class="text-center text-xs text-textMuted/40 py-4">Please login first</div>';
        }
        return;
    }

    try {
        // 使用 AuthManager 獲取用戶 ID
        const isLoggedIn = window.AuthManager?.isLoggedIn();
        if (!isLoggedIn) return; // Should be handled by top check, but safe to keep

        const userId = AuthManager.currentUser.user_id;
        const token = AuthManager.currentUser.accessToken;

        const res = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        const data = await res.json();
        const list = document.getElementById('chat-session-list');
        list.innerHTML = '';

        if (data.sessions && data.sessions.length > 0) {
            // 分離收藏和普通對話
            const starredSessions = data.sessions.filter(s => s.is_pinned);
            const regularSessions = data.sessions.filter(s => !s.is_pinned);
            const allSessions = data.sessions;

            // 編輯模式工具栏
            const toolbar = document.createElement('div');
            toolbar.className = 'edit-toolbar flex items-center gap-2 px-3 py-2 mb-2';

            if (isEditMode) {
                const allSelected = allSessions.length > 0 && selectedSessions.size === allSessions.length;
                toolbar.innerHTML = `
                    <button onclick="toggleSelectAll()" class="flex items-center gap-1.5 text-xs ${allSelected ? 'text-primary' : 'text-textMuted hover:text-secondary'} transition">
                        <i data-lucide="${allSelected ? 'check-square' : 'square'}" class="w-3.5 h-3.5"></i>
                        <span>${allSelected ? '取消全選' : '全選'}</span>
                    </button>
                    <div class="flex-1"></div>
                    <span class="text-[10px] text-textMuted/50">${selectedSessions.size} 已選</span>
                    <button onclick="deleteSelectedSessions(this)" class="p-1.5 ${selectedSessions.size > 0 ? 'text-danger hover:bg-danger/10' : 'text-textMuted/30 cursor-not-allowed'} rounded-lg transition" ${selectedSessions.size === 0 ? 'disabled' : ''} title="刪除已選">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                    <button onclick="exitEditMode()" class="p-1.5 text-textMuted hover:text-secondary hover:bg-white/5 rounded-lg transition" title="完成">
                        <i data-lucide="check" class="w-4 h-4"></i>
                    </button>
                `;
            } else {
                toolbar.innerHTML = `
                    <div class="flex-1"></div>
                    <button onclick="enterEditMode()" class="p-1.5 text-textMuted/50 hover:text-textMuted hover:bg-white/5 rounded-lg transition" title="管理對話">
                        <i data-lucide="list-checks" class="w-4 h-4"></i>
                    </button>
                `;
            }
            list.appendChild(toolbar);

            // 渲染收藏區（如果有收藏的對話）
            if (starredSessions.length > 0) {
                const starredSection = document.createElement('div');
                starredSection.className = 'mb-3';
                starredSection.innerHTML = `
                    <details class="starred-section" ${starredSectionOpen ? 'open' : ''}>
                        <summary class="flex items-center gap-2 px-3 py-2 text-xs font-medium text-textMuted/60 hover:text-textMuted cursor-pointer select-none" onclick="toggleStarredSection(this)">
                            <i data-lucide="chevron-right" class="w-3 h-3 transition-transform starred-chevron"></i>
                            <i data-lucide="star" class="w-3 h-3 text-yellow-500"></i>
                            <span>收藏</span>
                            <span class="ml-auto text-[10px] opacity-50">${starredSessions.length}</span>
                        </summary>
                        <div class="starred-list mt-1 ml-2 pl-2 border-l border-white/5"></div>
                    </details>
                `;
                list.appendChild(starredSection);

                const starredList = starredSection.querySelector('.starred-list');
                starredSessions.forEach(session => {
                    starredList.appendChild(createSessionItem(session));
                });
            }

            // 渲染普通對話區
            if (regularSessions.length > 0) {
                // 如果有收藏區，加一個小標題
                if (starredSessions.length > 0) {
                    const recentLabel = document.createElement('div');
                    recentLabel.className = 'flex items-center gap-2 px-3 py-2 text-xs font-medium text-textMuted/60';
                    recentLabel.innerHTML = `
                        <i data-lucide="clock" class="w-3 h-3"></i>
                        <span>最近</span>
                    `;
                    list.appendChild(recentLabel);
                }

                regularSessions.forEach(session => {
                    list.appendChild(createSessionItem(session));
                });
            }

            // 都沒有的話顯示空狀態
            if (starredSessions.length === 0 && regularSessions.length === 0) {
                list.innerHTML = '<div class="text-center text-xs text-textMuted/40 py-4">No history</div>';
            }

            // 儲存所有 session ID 供全選使用
            window._allSessionIds = allSessions.map(s => s.id);
        } else {
            list.innerHTML = '<div class="text-center text-xs text-textMuted/40 py-4">No history</div>';
            // 退出編輯模式（沒有對話了）
            if (isEditMode) exitEditMode();
        }
        createIconsIn(document.getElementById('chat-session-list'));

        // 更新收藏區的 chevron 樣式
        updateStarredChevron();
        return data.sessions || [];
    } catch (e) {
        console.error("Failed to load sessions:", e);
        return [];
    }
}

// 創建單個 session 項目
function createSessionItem(session) {
    const isActive = session.id === currentSessionId;
    const isSelected = selectedSessions.has(session.id);
    const div = document.createElement('div');
    div.dataset.sessionId = session.id;
    div.className = `group flex items-center gap-2 p-3 rounded-xl cursor-pointer transition text-sm mb-1 ${isActive ? 'bg-surfaceHighlight text-primary' : 'hover:bg-white/5 text-textMuted hover:text-secondary'} ${isSelected ? 'bg-primary/10 border border-primary/20' : ''}`;

    if (isEditMode) {
        // 編輯模式：點擊切換選中狀態
        div.onclick = () => toggleSessionSelection(session.id);
        div.innerHTML = `
            <div class="w-5 h-5 rounded border ${isSelected ? 'bg-primary border-primary' : 'border-white/20'} flex items-center justify-center transition">
                ${isSelected ? '<i data-lucide="check" class="w-3 h-3 text-white"></i>' : ''}
            </div>
            <i data-lucide="message-square" class="w-4 h-4 opacity-70"></i>
            <div class="flex-1 truncate">${session.title || 'New Chat'}</div>
            ${session.is_pinned ? '<i data-lucide="star" class="w-3 h-3 fill-yellow-500 text-yellow-500"></i>' : ''}
        `;
    } else {
        // 正常模式
        div.onclick = () => switchSession(session.id);
        div.innerHTML = `
            <i data-lucide="message-square" class="w-4 h-4 opacity-70"></i>
            <div class="flex-1 truncate">${session.title || 'New Chat'}</div>
            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                <button onclick="toggleStarSession(event, '${encodeURIComponent(session.id)}', ${!session.is_pinned})" class="p-1 hover:text-yellow-500 transition" title="${session.is_pinned ? '取消收藏' : '收藏'}">
                    <i data-lucide="star" class="w-3.5 h-3.5 ${session.is_pinned ? 'fill-yellow-500 text-yellow-500' : ''}"></i>
                </button>
                <button onclick="deleteSession(event, '${encodeURIComponent(session.id)}')" class="p-1 hover:text-danger transition" title="Delete Chat">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        `;

        // 如果是收藏的，強制顯示星星按鈕
        if (session.is_pinned) {
            const btnGroup = div.querySelector('.opacity-0');
            if (btnGroup) btnGroup.classList.remove('opacity-0');
        }
    }

    // 如果是當前 session，滾動到可見區域
    if (isActive && !isEditMode) {
        setTimeout(() => {
            div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    }

    return div;
}

// 切換收藏區展開/收合狀態
function toggleStarredSection(summaryElement) {
    setTimeout(() => {
        const details = summaryElement.parentElement;
        starredSectionOpen = details.open;
        updateStarredChevron();
    }, 0);
}

// 更新收藏區 chevron 的旋轉狀態
function updateStarredChevron() {
    const chevron = document.querySelector('.starred-chevron');
    if (chevron) {
        if (starredSectionOpen) {
            chevron.style.transform = 'rotate(90deg)';
        } else {
            chevron.style.transform = 'rotate(0deg)';
        }
    }
}

// ========================================
// 編輯模式（批量刪除）
// ========================================

function enterEditMode() {
    isEditMode = true;
    selectedSessions.clear();
    loadSessions();
}

function exitEditMode() {
    isEditMode = false;
    selectedSessions.clear();
    loadSessions();
}

function toggleSessionSelection(sessionId) {
    if (selectedSessions.has(sessionId)) {
        selectedSessions.delete(sessionId);
    } else {
        selectedSessions.add(sessionId);
    }
    loadSessions();
}

function toggleSelectAll() {
    const allIds = window._allSessionIds || [];
    if (selectedSessions.size === allIds.length) {
        // 已全選，取消全選
        selectedSessions.clear();
    } else {
        // 全選
        selectedSessions = new Set(allIds);
    }
    loadSessions();
}

async function deleteSelectedSessions(btnElement) {
    if (selectedSessions.size === 0) return;

    const count = selectedSessions.size;
    const confirmed = await showConfirm({
        title: '批量刪除',
        message: `確定要刪除 ${count} 個對話嗎？此操作無法復原。`,
        confirmText: '刪除',
        cancelText: '取消',
        type: 'danger'
    });

    if (!confirmed) return;

    if (btnElement) {
        btnElement.disabled = true;
        btnElement.classList.add('opacity-50', 'cursor-not-allowed');
    }

    // ── Optimistic UI: remove all selected items + toolbar immediately ───────
    const toDelete = Array.from(selectedSessions);
    toDelete.forEach(sid => {
        const div = document.querySelector(`[data-session-id="${sid}"]`);
        if (div) div.remove();
    });
    // Remove edit toolbar immediately so the count/buttons don't linger
    document.querySelector('#chat-session-list .edit-toolbar')?.remove();

    // 如果當前 session 被刪除了，清空聊天區域
    if (selectedSessions.has(currentSessionId)) {
        currentSessionId = null;
        showWelcomeScreen();
    }

    // Clear any HITL context for deleted sessions
    if (_hitlContext?.sessionId && selectedSessions.has(_hitlContext.sessionId)) {
        _hitlContext = null;
    }

    // 清空選中並退出編輯模式
    selectedSessions.clear();
    isEditMode = false;

    try {
        const token = AuthManager.currentUser.accessToken;
        await Promise.all(toDelete.map(sessionId =>
            fetch(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            })
        ));
        // Rebuild sidebar (clears edit toolbar and syncs with server)
        await loadSessions();
    } catch (e) {
        console.error("Failed to delete sessions:", e);
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        await loadSessions();
    }
}

async function toggleStarSession(event, sessionId, newStatus) {
    event.stopPropagation();
    // Decode sessionId that was encoded for XSS protection
    sessionId = decodeURIComponent(sessionId);
    try {
        const token = AuthManager.currentUser.accessToken;
        await fetch(`/api/chat/sessions/${sessionId}/pin?is_pinned=${newStatus}`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        await loadSessions();
    } catch (e) {
        console.error("Failed to toggle star:", e);
    }
}

async function createNewChat() {
    try {
        // 先切換到 Chat tab（確保用戶能看到效果）
        if (typeof switchTab === 'function') {
            await switchTab('chat');
        }

        // 如果當前已經是新對話狀態 (currentSessionId 為 null)，直接返回
        if (currentSessionId === null) {
            showWelcomeScreen();
            return;
        }

        // ⚠️ 取消正在進行的分析請求，避免 isAnalyzing 阻擋新聊天室的訊息發送
        if (window.currentAnalysisController) {
            window.currentAnalysisController.abort();
            window.currentAnalysisController = null;
        }
        isAnalyzing = false;

        // 切換到"新對話"狀態，不立即建立 session
        currentSessionId = null;

        // 顯示歡迎畫面
        showWelcomeScreen();

        // 重新載入列表（這會移除當前選中的高亮狀態）
        await loadSessions();

        // Close sidebar on mobile
        const sidebar = document.getElementById('chat-sidebar');
        if (!sidebar.classList.contains('-translate-x-full') && window.innerWidth < 768) {
            sidebar.classList.add('-translate-x-full');
        }
    } catch (e) {
        console.error("Failed to prepare new chat:", e);
    }
}

function showWelcomeScreen() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = `
    <div class="bot-message opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; animation-fill-mode: forwards;">
        <div class="flex flex-col items-center justify-center mb-8">
            <h1 class="font-serif text-3xl md:text-4xl leading-tight text-center">
                <span class="text-secondary">Welcome to</span><br>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">CryptoMind</span>
            </h1>
        </div>
        <p class="text-textMuted text-lg font-light leading-relaxed text-center">
            AI-powered crypto analysis. Start a new conversation.
        </p>
        <div class="flex flex-wrap gap-3 mt-8 justify-center">
             <button onclick="quickAsk('Analyze BTC trend')" class="px-5 py-2.5 rounded-full bg-surface hover:bg-surfaceHighlight border border-white/5 text-sm text-textMuted hover:text-primary transition shadow-sm">
                Bitcoin Trend
            </button>
            <button onclick="quickAsk('ETH Funding Rates')" class="px-5 py-2.5 rounded-full bg-surface hover:bg-surfaceHighlight border border-white/5 text-sm text-textMuted hover:text-primary transition shadow-sm">
                ETH Rates
            </button>
        </div>
    </div>`;
    createIconsIn(document.getElementById('chat-session-list'));
}

// 直接更新側邊欄的 active 高亮，不重新拉取 sessions
function updateSessionActiveState(newSessionId) {
    document.querySelectorAll('[data-session-id]').forEach(el => {
        const isActive = el.dataset.sessionId === newSessionId;
        if (isActive) {
            el.classList.add('bg-surfaceHighlight', 'text-primary');
            el.classList.remove('hover:bg-white/5', 'text-textMuted', 'hover:text-secondary');
        } else {
            el.classList.remove('bg-surfaceHighlight', 'text-primary');
            el.classList.add('hover:bg-white/5', 'text-textMuted', 'hover:text-secondary');
        }
    });
}

async function switchSession(sessionId) {
    if (sessionId === currentSessionId) return;

    // ⚠️ 取消正在進行的分析請求，避免 isAnalyzing 阻擋新 session 的訊息發送
    if (window.currentAnalysisController) {
        window.currentAnalysisController.abort();
        window.currentAnalysisController = null;
    }
    isAnalyzing = false;

    currentSessionId = sessionId;

    // 自動切換到 Chat 標籤頁（確保等待完成再載入歷史）
    if (typeof switchTab === 'function') {
        await switchTab('chat');
    }

    // 直接更新 DOM active 狀態，省掉一次 GET /api/chat/sessions
    updateSessionActiveState(sessionId);

    // Load history
    await loadChatHistory(sessionId);

    // Close sidebar on mobile
    const sidebar = document.getElementById('chat-sidebar');
    if (!sidebar.classList.contains('-translate-x-full') && window.innerWidth < 768) {
        sidebar.classList.add('-translate-x-full');
    }
}

async function deleteSession(event, sessionId) {
    event.stopPropagation();
    // Decode sessionId that was encoded for XSS protection
    sessionId = decodeURIComponent(sessionId);
    const btnElement = event.currentTarget;

    const confirmed = await showConfirm({
        title: '刪除對話',
        message: '確定要刪除這個對話嗎？此操作無法復原。',
        confirmText: '刪除',
        cancelText: '取消',
        type: 'danger'
    });

    if (!confirmed) return;

    if (btnElement) {
        btnElement.disabled = true;
        btnElement.classList.add('opacity-50', 'cursor-not-allowed');
    }

    // ── Step 1: Optimistic UI — remove immediately, find next session ──────────
    const sessionDiv = event.target.closest('[data-session-id]');
    let nextSessionId = null;

    if (sessionDiv) {
        const allItems = [...document.querySelectorAll('[data-session-id]')];
        const idx = allItems.indexOf(sessionDiv);
        const sibling = allItems[idx + 1] || allItems[idx - 1];
        if (sibling) nextSessionId = sibling.dataset.sessionId;
        sessionDiv.remove();
    }

    const wasActive = currentSessionId === sessionId;
    if (wasActive) {
        const container = document.getElementById('chat-messages');
        if (container) container.innerHTML = '';
        currentSessionId = nextSessionId || null;
        if (!nextSessionId) showWelcomeScreen();
    }

    // Clear any lingering HITL context for this session to prevent ghost re-creation
    if (_hitlContext?.sessionId === sessionId) _hitlContext = null;

    // ── Step 2: Fire DELETE + load next session history in parallel ───────────
    // No need to call loadSessions() — optimistic UI already removed the item
    try {
        const token = AuthManager.currentUser.accessToken;
        await Promise.all([
            fetch(`/api/chat/sessions/${sessionId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            }),
            (wasActive && nextSessionId) ? loadChatHistory(nextSessionId) : Promise.resolve()
        ]);
    } catch (e) {
        console.error("Failed to delete session:", e);
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        // Restore sidebar on failure
        await loadSessions();
    }
}

// ── HITL Web Mode ─────────────────────────────────────────────────────────────
// Stores context needed to resume the graph after user answers a HITL question

function showHITLModal(interruptData) {
    const modal = document.getElementById('hitl-modal');
    const questionEl = document.getElementById('hitl-question-text');
    const optionsEl = document.getElementById('hitl-options-container');
    const customInput = document.getElementById('hitl-custom-input');

    if (!modal) return;

    questionEl.textContent = interruptData.question || '請確認執行計畫';
    optionsEl.innerHTML = '';
    customInput.value = '';

    const options = interruptData.options || [];
    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.textContent = opt;
        btn.className = 'w-full text-left px-5 py-3 rounded-2xl bg-background border border-white/5 text-secondary text-sm hover:border-primary/50 hover:bg-primary/5 transition';
        btn.onclick = () => window.submitHITLAnswer(opt);
        optionsEl.appendChild(btn);
    });

    modal.classList.remove('hidden');
    if (lucide) createIconsIn(modal);
}

function closeHITLModal() {
    const modal = document.getElementById('hitl-modal');
    if (modal) modal.classList.add('hidden');
}

// ── Pre-Research Card (pre_research HITL) ────────────────────────────────────

function renderPreResearchCard(idata, targetDiv) {
    console.log('[renderPreResearchCard] idata:', idata);
    if (!targetDiv) return;
    const summary = idata.research_summary || '';
    const message = idata.message || '已整理即時資料供您參考：';
    const question = idata.question || '有特別想深入的方向嗎？';

    // 若後端有 Q&A 回答，在主聊天顯示（純問答泡泡，不加 AI War Room 按鈕）
    if (idata.qa_question && idata.qa_answer) {
        const container = document.getElementById('chat-messages');
        if (container) {
            const qaDiv = document.createElement('div');
            qaDiv.className = 'message-bubble bot-bubble prose';
            // XSS Fix: 使用 SecurityUtils 清理 HTML
            const qRaw = window.md ? window.md.renderInline(idata.qa_question) : idata.qa_question;
            const aRaw = window.md ? window.md.render(idata.qa_answer) : idata.qa_answer;
            const qHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(qRaw) : qRaw;
            const aHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(aRaw) : aRaw;
            qaDiv.innerHTML = `<p class="text-xs text-textMuted/60 mb-1">💬 ${qHtml}</p>${aHtml}`;
            container.appendChild(qaDiv);
            container.scrollTop = container.scrollHeight;
        }
    }

    // XSS Fix: 使用 SecurityUtils 清理 HTML
    const summaryRaw = summary && window.md
        ? window.md.render(summary)
        : (summary ? summary.replace(/\n/g, '<br>') : '');
    const summaryHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(summaryRaw) : summaryRaw;
    const messageRaw = window.md
        ? window.md.renderInline(message)
        : message;
    const messageHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(messageRaw) : messageRaw;

    // Use a compact card if no summary is provided (e.g., follow-up Q&A)
    if (!summary) {
        targetDiv.innerHTML = `
            <div class="pre-research-card-compact rounded-2xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
                <div class="px-5 pt-4 pb-2">
                    <p class="text-sm text-secondary mb-2">${messageHtml}</p>
                    <p class="text-xs text-textMuted mb-2">${question}</p>
                </div>
                <div class="flex gap-2 px-5 py-3 border-t border-white/5 bg-background/30">
                    <button onclick="submitPreResearch()"
                        class="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border
                               border-primary/30 rounded-xl py-2 text-sm font-medium transition">
                        確認開始規劃
                    </button>
                    <!-- No cancel button needed in compact mode usually, but can keep -->
                </div>
            </div>`;
    } else {
        // Full card with summary
        targetDiv.innerHTML = `
            <div class="pre-research-card rounded-2xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
                <div class="px-5 pt-5 pb-4">
                    <p class="text-sm text-secondary mb-3">${messageHtml}</p>
                    <div class="prose prose-sm prose-invert max-w-none text-secondary leading-relaxed
                                max-h-72 overflow-y-auto bg-white/5 rounded-xl px-4 py-3 mb-4">
                        ${summaryHtml}
                    </div>
                    <p class="text-sm text-secondary mb-2">${question}</p>
                    <!-- Pre-Research Input Removed: Use main chat input -->
                </div>
                <div class="flex gap-2 px-5 py-4 border-t border-white/5 bg-background/30">
                    <button onclick="submitPreResearch()"
                        class="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border
                               border-primary/30 rounded-xl py-2.5 text-sm font-medium transition">
                        開始規劃
                    </button>
                    <button onclick="window.submitHITLAnswer('取消')"
                        class="px-4 bg-white/5 hover:bg-white/10 text-secondary border
                               border-white/10 rounded-xl py-2.5 text-sm transition">
                        取消
                    </button>
                </div>
            </div>`;
    }

    if (window.lucide) createIconsIn(botMsgDiv);
}

window.submitPreResearch = function () {
    // No specific input from card anymore, just confirm.
    // If user wants to specify, they type in main chat.
    window.submitHITLAnswer('confirm');
};

// ── Removed client-side _isDiscussionQuestion check to rely on backend ──

// ── Plan Card (confirm_plan HITL) ──────────────────────────────────────────────

function renderPlanCard(interruptData, targetDiv) {
    if (!targetDiv) return;
    const plan = interruptData.plan || [];

    // 計畫為空時顯示錯誤訊息，不渲染空計畫卡
    if (plan.length === 0) {
        targetDiv.innerHTML = `
            <div class="rounded-2xl border border-red-500/20 bg-red-500/5 px-5 py-4 text-sm text-textMuted">
                ⚠️ 無法為此查詢建立執行計畫，請換個方式描述您的問題。
            </div>`;
        return;
    }

    const message = interruptData.message || '針對您的問題，我規劃了以下分析步驟：';

    const stepsHtml = plan.map(t => `
        <div class="plan-step flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-white/5 transition"
             data-step="${t.step}" data-selected="true">
            <div class="plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10
                        flex items-center justify-center flex-shrink-0">
                <i data-lucide="check" class="w-3 h-3 text-primary"></i>
            </div>
            <span class="text-base leading-none">${t.icon || '🔧'}</span>
            <span class="text-sm text-secondary flex-1">${t.description || t.agent}</span>
        </div>`).join('');

    // Negotiation Response as a clearer "Chat" element BEFORE the card
    const negotiationResponse = interruptData.negotiation_response
        ? `<div class="mb-4 text-base text-secondary leading-relaxed border-l-2 border-primary/40 pl-3">
             <span class="text-xs font-bold text-primary block mb-1">🤖 說明：</span>
             ${interruptData.negotiation_response}
           </div>`
        : '';

    targetDiv.innerHTML = `
        ${negotiationResponse}
        <div class="plan-card rounded-2xl border border-primary/20 bg-primary/5 overflow-hidden"
             id="active-plan-card">
            <div class="px-5 pt-5 pb-3">
                <div class="flex items-center gap-2 mb-3">
                    <div class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                        <i data-lucide="list-checks" class="w-4 h-4 text-primary"></i>
                    </div>
                    <span class="text-sm font-medium text-primary">AI 執行計畫</span>
                </div>
                
                <p class="text-sm text-textMuted mb-3">${message}</p>
                <div class="plan-steps space-y-0.5">${stepsHtml}</div>
                
                <!-- Negotiation Instructions (Shown in custom mode) -->
                <div id="plan-negotiate-container" class="hidden mt-3 pt-3 border-t border-white/5 animate-fade-in-up">
                    <p class="text-xs text-textMuted bg-white/5 px-3 py-2 rounded-lg border border-white/10">
                        <i data-lucide="info" class="w-3 h-3 inline mr-1"></i>
                        若需調整計畫（例如：「增加基本面分析」），請直接在下方<b>聊天輸入框</b>打字即可。
                    </p>
                </div>
            </div>
            <div class="plan-actions flex gap-2 px-5 py-4 border-t border-white/5 bg-background/30">
                <button id="plan-execute-btn" onclick="window.executePlan('all')"
                    class="flex-1 py-2.5 bg-primary hover:bg-primary/80 text-background font-bold
                           rounded-xl text-sm transition flex items-center justify-center gap-1.5">
                    <i data-lucide="play" class="w-4 h-4"></i>執行全部
                </button>
                <button id="plan-customize-btn" onclick="window.togglePlanCustomize()"
                    class="px-4 py-2.5 bg-white/5 hover:bg-white/10 text-textMuted rounded-xl
                           text-sm transition flex items-center gap-1.5 ${interruptData.negotiation_limit_reached ? 'hidden' : ''}"
                    ${interruptData.negotiation_limit_reached ? 'disabled' : ''}>
                    <i data-lucide="settings-2" class="w-4 h-4"></i>自訂/挑選
                </button>
                <button onclick="window.executePlan('cancel')"
                    class="px-4 py-2.5 bg-white/5 hover:bg-white/10 text-textMuted
                           hover:text-danger rounded-xl text-sm transition">
                    取消
                </button>
            </div>
        </div>`;
    if (lucide) createIconsIn(botMsgDiv);
}

window.togglePlanCustomize = function () {
    const card = document.getElementById('active-plan-card');
    if (!card) return;

    // Toggle class
    const isCustom = card.classList.toggle('plan-custom-mode');

    const executeBtn = document.getElementById('plan-execute-btn');
    const customizeBtn = document.getElementById('plan-customize-btn');
    const negotiateContainer = document.getElementById('plan-negotiate-container');

    if (isCustom) {
        // Show negotiation instruction
        if (negotiateContainer) negotiateContainer.classList.remove('hidden');

        // Enable clicking steps to toggle
        card.querySelectorAll('.plan-step').forEach(step => {
            step.style.cursor = 'pointer';
            step.onclick = () => window.togglePlanStep(step);
        });

        // Update Buttons
        if (customizeBtn) {
            customizeBtn.innerHTML = '<i data-lucide="rotate-ccw" class="w-4 h-4"></i>重置';
            customizeBtn.classList.add('bg-primary/10', 'text-primary');
        }

        // Initial button state update
        window.updateCustomExecuteButton();

    } else {
        // Hide negotiation instruction
        if (negotiateContainer) {
            negotiateContainer.classList.add('hidden');
        }

        // Reset all steps to selected
        card.querySelectorAll('.plan-step').forEach(step => {
            step.dataset.selected = 'true';
            step.style.cursor = '';
            step.onclick = null;
            step.classList.remove('opacity-40');
            const check = step.querySelector('.plan-check');
            if (check) {
                check.className = 'plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10 flex items-center justify-center flex-shrink-0';
                check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
            }
        });

        // Reset Buttons
        if (executeBtn) {
            executeBtn.onclick = () => window.executePlan('all');
            executeBtn.classList.remove('bg-white/10', 'text-white');
            executeBtn.classList.add('bg-primary', 'text-background');
            executeBtn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i>執行全部';
        }
        if (customizeBtn) {
            customizeBtn.innerHTML = '<i data-lucide="settings-2" class="w-4 h-4"></i>自訂/挑選';
            customizeBtn.classList.remove('bg-primary/10', 'text-primary');
        }
    }
    if (lucide) createIconsIn(document.getElementById('chat-messages'));
};

window.updateCustomExecuteButton = function () {
    const executeBtn = document.getElementById('plan-execute-btn');
    if (!executeBtn) return;

    // Main chat input is used for negotiation now, but execute button here is for "selected steps".
    // "execute_custom" action sends { selected_steps: [...] }.

    executeBtn.onclick = () => window.executePlan('custom');

    // Style remains Primary for execution
    executeBtn.classList.remove('bg-white/10', 'text-white');
    executeBtn.classList.add('bg-primary', 'text-background');
    executeBtn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i>執行已選步驟';

    createIconsIn(executeBtn);
};

window.togglePlanStep = function (step) {
    const wasSelected = step.dataset.selected === 'true';
    const nowSelected = !wasSelected;
    step.dataset.selected = String(nowSelected);
    step.classList.toggle('opacity-40', !nowSelected);
    const check = step.querySelector('.plan-check');
    if (!check) return;
    if (nowSelected) {
        check.className = 'plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10 flex items-center justify-center flex-shrink-0';
        check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
        if (lucide) lucide.createIcons({ nodes: [check] });
    } else {
        check.className = 'plan-check w-5 h-5 rounded border border-white/20 flex items-center justify-center flex-shrink-0';
        check.innerHTML = '';
    }
};

window.executePlan = function (mode) {
    if (mode === 'cancel') { window.submitHITLAnswer(JSON.stringify({action: 'cancel'})); return; }
    if (mode === 'all') { window.submitHITLAnswer(JSON.stringify({action: 'execute'})); return; }

    if (mode === 'custom') {
        // Check negotiation text first
        const input = document.getElementById('plan-negotiate-input');
        const text = input ? input.value.trim() : '';

        if (text) {
            window.submitHITLAnswer(JSON.stringify({ action: 'modify_request', text: text }));
            return;
        }

        const card = document.getElementById('active-plan-card');
        if (!card) { window.submitHITLAnswer('執行'); return; }

        const selected = [];
        card.querySelectorAll('.plan-step').forEach(step => {
            if (step.dataset.selected === 'true') selected.push(parseInt(step.dataset.step, 10));
        });

        if (selected.length === 0) {
            // Hint user to select something or cancel
            alert('請至少選擇一個步驟，或點擊「取消」');
            return;
        }

        window.submitHITLAnswer(JSON.stringify({ action: 'execute_custom', selected_steps: selected }));
    }
};

window.submitHITLAnswer = async function (answer) {
    if (!answer || !answer.trim()) return;
    if (!_hitlContext) return;

    closeHITLModal();

    const ctx = _hitlContext;
    _hitlContext = null;

    // ── History Preservation ──
    // Instead of overwriting the old bot message, we mark it as "done" by REMOVING the buttons
    // and create a NEW bot message for the response/next step.
    // ── History Preservation ──
    // Instead of overwriting the old bot message, we mark it as "done" by REMOVING the buttons

    // 1. Clean up specific context message if it exists
    if (ctx.botMsgDiv) {
        const oldBtns = ctx.botMsgDiv.querySelectorAll('button');
        oldBtns.forEach(b => b.remove());
        const btnContainer = ctx.botMsgDiv.querySelector('.flex.gap-2.border-t');
        if (btnContainer) btnContainer.remove();

        const oldCard = ctx.botMsgDiv.querySelector('#active-plan-card');
        if (oldCard) oldCard.removeAttribute('id');
    }

    // 2. Force Clean: Remove ALL persistence buttons from previous HITL cards in the chat
    // This ensures even if context was lost, we don't leave active buttons.
    document.querySelectorAll('.pre-research-card button, .plan-card button, .pre-research-card-compact button').forEach(btn => {
        // If the button is not in the NEW botMsgDiv (which isn't created yet), remove it.
        // Since we haven't created the new div yet, ALL existing buttons are "old".
        const parent = btn.closest('.flex');
        if (parent && parent.className.includes('gap-2') && parent.className.includes('border-t')) {
            parent.remove();
        } else {
            btn.remove();
        }
    });

    // Create NEW bot message for the response logic
    const botMsgDiv = appendMessage('bot', '');
    ctx.botMsgDiv = botMsgDiv; // Update context to point to new div for streaming

    // Initial "Thinking" UI
    botMsgDiv.innerHTML = `
        <div class="process-container" style="border-style: dashed; opacity: 0.7;">
            <div class="flex items-center gap-2 px-4 py-3">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-primary"></i>
                <span class="font-medium text-sm text-textMuted">AI 正在思考調研...</span>
            </div>
        </div>`;
    if (window.lucide) createIconsIn(botMsgDiv);

    const token = AuthManager.currentUser.accessToken;
    let fullContent = '';

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                message: ctx.originalMessage,
                session_id: ctx.sessionId,
                user_api_key: ctx.userKey.key,
                user_provider: ctx.userKey.provider,
                user_model: ctx.userSelectedModel,
                language: window.I18n?.getLanguage() || 'zh-TW',
                // Ensure resume_answer is an object if it's a JSON string
                resume_answer: (() => {
                    const trimmed = answer.trim();
                    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                        try { return JSON.parse(trimmed); } catch (e) { return trimmed; }
                    }
                    return trimmed;
                })()
            })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server Error (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            for (const line of chunk.split('\n')) {
                if (!line.startsWith('data: ')) continue;
                let data;
                try { data = JSON.parse(line.substring(6)); } catch { continue; }

                if (data.type === 'hitl_question') {
                    // Nested HITL — reuse same context, dispatch by type
                    _hitlContext = ctx;
                    const idata = data.data || {};
                    _hitlContext.hitlType = idata.type;
                    if (idata.type === 'pre_research') {
                        renderPreResearchCard(idata, ctx.botMsgDiv);
                    } else if (idata.type === 'confirm_plan') {
                        renderPlanCard(idata, ctx.botMsgDiv);
                    } else {
                        // Inline clarification (no modal, no stale spinner)
                        const question = idata.question || '請問您具體想了解什麼？';
                        ctx.botMsgDiv.innerHTML = `
                            <div class="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                                <div class="px-5 py-4 flex items-start gap-3">
                                    <i data-lucide="help-circle" class="w-4 h-4 text-primary mt-0.5 flex-shrink-0"></i>
                                    <div>
                                        <p class="text-sm text-secondary">${question}</p>
                                        <p class="text-xs text-textMuted mt-1.5">請在下方輸入框回覆</p>
                                    </div>
                                </div>
                            </div>`;
                        if (window.lucide) lucide.createIcons({ nodes: [ctx.botMsgDiv] });
                    }
                    return;
                }
                if (data.waiting) return;

                if (data.content) {
                    fullContent += data.content;
                    if (ctx.botMsgDiv) {
                        ctx.botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, true, null);
                    }
                }
                if (data.done) {
                    if (ctx.botMsgDiv) {
                        const totalTime = ((Date.now() - ctx.startTime) / 1000).toFixed(1);
                        ctx.botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, false, totalTime);
                        const badge = document.createElement('div');
                        badge.className = 'mt-4 text-xs text-textMuted/60 font-mono';
                        badge.textContent = `分析完成，耗時 ${totalTime}s`;
                        ctx.botMsgDiv.appendChild(badge);
                        if (lucide) createIconsIn(ctx.botMsgDiv);
                    }
                    isAnalyzing = false;
                    loadSessions();
                }
                if (data.error) {
                    if (ctx.botMsgDiv) {
                        ctx.botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${escapeHtml(data.error)}</span>`;
                    }
                    isAnalyzing = false;
                }
            }
        }
    } catch (err) {
        console.error('[HITL resume error]', err);
        if (ctx.botMsgDiv) {
            // Fix [object Object] by properly stringifying error detail if it's an object
            // XSS Fix: 使用 escapeHtml 转义错误消息
            const rawError = typeof err.message === 'object' ? JSON.stringify(err.message) : (err.message || String(err));
            const errorMsg = escapeHtml(rawError);
            ctx.botMsgDiv.innerHTML = `<span class="text-red-400">恢復分析失敗：${errorMsg}</span>`;
        }
        isAnalyzing = false;
    } finally {
        const input = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        // 只有在 HITL 完全解決（_hitlContext=null）時才重新啟用輸入
        // 若後端再次 interrupt（Q&A 循環），_hitlContext 已被恢復，保持禁用
        if (_hitlContext === null) {
            isAnalyzing = false;
            if (input) { input.disabled = false; input.classList.remove('opacity-50'); input.focus(); }
            if (sendBtn) { sendBtn.disabled = false; sendBtn.classList.remove('opacity-50', 'cursor-not-allowed'); }
        }
    }
};
// ── End HITL ─────────────────────────────────────────────────────────────────

// ── Global Helper for Button Cleanup ─────────────────────────────────────────
// ── Global Helper for Button Cleanup ─────────────────────────────────────────
function cleanupStaleButtons() {
    // Target ALL buttons within the chat container to ensure thorough cleanup
    const chatBtns = document.querySelectorAll('#chat-messages button');
    chatBtns.forEach(btn => {
        // If the button is inside a bordered action bar (common in our cards), remove the bar.
        // Otherwise just remove the button.
        const parent = btn.closest('.flex');
        if (parent && parent.className.includes('border-t')) {
            parent.remove();
        } else {
            btn.remove();
        }
    });
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const text = input.value.trim();
    if (!text && !isAnalyzing) return; // Allow empty text if we are just stopping? No, stop is a separate click.

    // ── Global Cleanup ──
    // Force remove old buttons on any new interaction
    cleanupStaleButtons();

    // ── Input State Management for "Stop" capability ─────────────────────
    if (isAnalyzing) {
        // If we are in HITL pause (waiting for input), allow typing
        // But isAnalyzing is technically false during HITL pause (set in finally block)
        // Wait, in my previous edit, I set isAnalyzing = false in finally if hitlPaused.
        // So this block only runs if isAnalyzing is TRUE (streaming).
        // So clicking button here means STOP.

        // However, if the user hits ENTER in the input box...
        // If input is enabled (which it shouldn't be during streaming, but IS during HITL pause),
        // we need to check if we are actually in HITL mode.

        // Wait, if isAnalyzing is true, input SHOULD be disabled. 
        // If isAnalyzing is false (HITL pause), we fall through to Start Analysis logic below.

        stopAnalysis();
        return;
    }

    // ── HITL Input Routing ───────────────────────────────────────────────
    // If we have a pending HITL context, this input is an answer/negotiation
    if (_hitlContext && _hitlContext.sessionId === currentSessionId) {
        const hitlType = _hitlContext.hitlType;

        // Clear input immediately
        input.value = '';

        // If it's a plan confirmation or pre_research, send the user's raw text 
        // and let the backend's LLM determine if it's a question, modification, or confirmation.
        if (hitlType === 'confirm_plan' || hitlType === 'pre_research') {
            appendMessage('user', text);
            window.submitHITLAnswer(text);
            return;
        }

        // For other HITL types (e.g. simple clarification), send raw text
        appendMessage('user', text);
        window.submitHITLAnswer(text);
        return;
    }

    if (!text) return;

    // ── Start Analysis ───────────────────────────────────────────────────
    isAnalyzing = true;

    // Change Send button to Stop button
    sendBtn.classList.remove('bg-primary', 'hover:brightness-110');
    sendBtn.classList.add('bg-red-500', 'hover:bg-red-600', 'text-white');
    sendBtn.innerHTML = '<i data-lucide="square" class="w-4 h-4 fill-current"></i>'; // Stop icon
    if (window.lucide) lucide.createIcons({ nodes: [sendBtn] });

    // Disable Input but keep Button enabled (as Stop)
    input.disabled = true;
    input.classList.add('opacity-50');
    // sendBtn.disabled = true; // Don't disable, we need it for Stop

    // 檢查用戶是否有設置 API key（使用快取，避免每次發送都打後端）
    const userKey = await getCachedUserKey();

    if (!userKey) {
        resetChatUI(); // Helper to reset UI state
        showAlert({
            title: '未設置 API Key',
            message: '請先在系統設定中輸入您的 API Key 才能使用分析功能。\n\n您需要 OpenAI、Google Gemini 或 OpenRouter API Key。',
            type: 'warning',
            confirmText: '前往設定'
        }).then(() => {
            if (typeof switchTab === 'function') switchTab('settings');
        });
        return;
    }

    // Enable UI for sending (transition to analysis state)
    sendBtn.disabled = false;
    input.classList.remove('opacity-50');
    sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');

    const _sendIcon = sendBtn.querySelector('i[data-lucide]');
    // Note: We changed icon to Stop square earlier, so we don't want to reset it to arrow-up yet!
    // The previous code block was copy-pasted wrong.
    // We already set it to square icon at the top of function.

    // Remove the redundant error check block that was here.

    // Lazy Creation: 如果沒有 currentSessionId，先建立新的 Session
    if (!currentSessionId) {
        try {
            const userId = AuthManager.currentUser.user_id;
            const token = AuthManager.currentUser.accessToken;

            // 這裡可以傳遞 title (e.g., text.substring(0, 20)) 但後端通常會預設為 New Chat 或由第一條訊息生成
            const createRes = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const createData = await createRes.json();
            currentSessionId = createData.session_id;

            // 刷新列表以顯示新對話
            // loadSessions();
        } catch (e) {
            console.error("Failed to create lazy session:", e);
            appendMessage('bot', '❌ 無法建立對話 Session，請稍後再試。');
            return;
        }
    }

    const userSelectedModel = window.APIKeyManager.getModelForProvider(userKey.provider);
    const checkboxes = document.querySelectorAll('.analysis-checkbox:checked');
    const selection = Array.from(checkboxes).map(cb => cb.value);
    const marketType = 'spot';
    const autoExecute = false;

    input.value = '';
    appendMessage('user', text);

    const botMsgDiv = appendMessage('bot', '');
    const startTime = Date.now();
    let timerInterval;

    // 重置分析過程面板的展開狀態
    window.lastProcessOpenState = false;

    // Initial "Proto-Process" UI to match the final analysis UI for seamless transition
    botMsgDiv.innerHTML = `
        <div class="process-container" style="border-style: dashed; opacity: 0.7;">
            <div class="flex items-center gap-2 px-4 py-3">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-primary"></i>
                <span class="font-medium text-sm text-textMuted">正在思考...</span>
                <span id="loading-timer" class="ml-auto text-xs font-mono text-textMuted/50">0.0s</span>
            </div>
        </div>
    `;

    const timerSpan = botMsgDiv.querySelector('#loading-timer');
    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        const display = document.getElementById('loading-timer');
        if (display) {
            display.textContent = `${elapsed}s`;
        }
    }, 100);

    window.currentAnalysisController = new AbortController();

    // Pre-build HITL resume context (used if server sends hitl_question)
    const _hitlResumeContext = {
        originalMessage: text,
        sessionId: currentSessionId,
        userKey,
        userSelectedModel,
        botMsgDiv,
        startTime,
    };

    // Declared OUTSIDE try so finally can read it
    let hitlPaused = false;

    try {
        const token = AuthManager.currentUser.accessToken;
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                message: text,
                manual_selection: selection,
                market_type: marketType,
                auto_execute: autoExecute,
                user_api_key: userKey.key,
                user_provider: userKey.provider,
                user_model: userSelectedModel,
                session_id: currentSessionId,
                language: window.I18n?.getLanguage() || 'zh-TW'
            }),
            signal: window.currentAnalysisController.signal
        });

        if (!response.ok) {
            let errorMsg = `Server Error (${response.status})`;
            try {
                const errorData = await response.json();
                if (errorData.detail) errorMsg = errorData.detail;
            } catch (e) {
                // If not JSON, try text
                const text = await response.text();
                if (text) errorMsg = text.substring(0, 100);
            }
            throw new Error(errorMsg);
        }

        // Backend 已經保存了用戶訊息並更新了標題，立即刷新列表以顯示新標題
        loadSessions();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done || hitlPaused) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            const currentElapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    let data;
                    try { data = JSON.parse(line.substring(6)); } catch { continue; }

                    // ── HITL: server needs user input ──────────────────────
                    if (data.type === 'hitl_question') {
                        clearInterval(timerInterval);
                        _hitlContext = _hitlResumeContext;
                        const idata = data.data || {};
                        // Store HITL type for sendMessage routing
                        _hitlContext.hitlType = idata.type;

                        if (idata.type === 'pre_research') {
                            renderPreResearchCard(idata, botMsgDiv);
                        } else if (idata.type === 'confirm_plan') {
                            renderPlanCard(idata, botMsgDiv);
                        } else {
                            // Render clarification question inline (clear spinner, show question)
                            const question = idata.question || '請問您具體想了解什麼？';
                            botMsgDiv.innerHTML = `
                                <div class="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                                    <div class="px-5 py-4 flex items-start gap-3">
                                        <i data-lucide="help-circle" class="w-4 h-4 text-primary mt-0.5 flex-shrink-0"></i>
                                        <div>
                                            <p class="text-sm text-secondary">${question}</p>
                                            <p class="text-xs text-textMuted mt-1.5">請在下方輸入框回覆</p>
                                        </div>
                                    </div>
                                </div>`;
                            if (window.lucide) lucide.createIcons({ nodes: [botMsgDiv] });
                        }
                    }
                    if (data.waiting) {
                        hitlPaused = true;
                        break;
                    }

                    // ── Meta Update (Codebook ID) ───────────────────────────
                    if (data.type === 'meta') {
                        if (data.codebook_id) {
                            botMsgDiv.dataset.codebookId = data.codebook_id;
                        }
                    }

                    // ── Progress Update (Parallel Execution) ────────────────
                    if (data.type === 'progress') {
                        const pData = data.data || {};
                        const stepNum = pData.step;
                        const stepEl = document.querySelector(`.plan-step[data-step="${stepNum}"]`);
                        if (stepEl) {
                            const check = stepEl.querySelector('.plan-check');
                            if (pData.type === 'agent_start') {
                                if (check) check.innerHTML = '<i data-lucide="loader-2" class="w-3 h-3 text-primary animate-spin"></i>';
                                stepEl.classList.add('bg-primary/5', 'border-primary/20');
                            } else if (pData.type === 'agent_finish') {
                                if (check) {
                                    if (pData.success) {
                                        check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
                                    } else {
                                        check.innerHTML = '<i data-lucide="alert-circle" class="w-3 h-3 text-danger"></i>';
                                        stepEl.classList.add('border-danger/20');
                                    }
                                }
                                stepEl.classList.remove('bg-primary/5', 'animate-pulse');
                            }
                            if (lucide) createIconsIn(botMsgDiv);
                        }
                    }

                    if (data.content) {
                        fullContent += data.content;
                        // 實時更新內容，傳入 isStreaming=true 和當前耗時
                        botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, true, currentElapsed);
                    }

                    if (data.done) {
                        clearInterval(timerInterval);
                        isAnalyzing = false;
                        const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);

                        // Final render，傳入 isStreaming=false
                        botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, false, totalTime);

                        const timeBadge = document.createElement('div');
                        timeBadge.className = 'mt-4 flex items-center justify-between text-xs text-textMuted/60 font-mono';

                        let feedbackHtml = '';
                        const codebookId = botMsgDiv.dataset.codebookId;
                        if (codebookId) {
                            feedbackHtml = `
                                <div class="flex items-center gap-2">
                                    <span class="opacity-50">分析品質回饋：</span>
                                    <button onclick="submitFeedback('${codebookId}', 1, this)" class="p-1 hover:text-success transition" title="有幫助">
                                        <i data-lucide="thumbs-up" class="w-3.5 h-3.5"></i>
                                    </button>
                                    <button onclick="submitFeedback('${codebookId}', -1, this)" class="p-1 hover:text-danger transition" title="需改進">
                                        <i data-lucide="thumbs-down" class="w-3.5 h-3.5"></i>
                                    </button>
                                </div>
                            `;
                        }

                        timeBadge.innerHTML = `<span>分析完成，耗時 ${totalTime}s</span>${feedbackHtml}`;
                        botMsgDiv.appendChild(timeBadge);
                        lucide.createIcons({ nodes: [botMsgDiv] });

                        // Refresh sessions list (to update title if it was new)
                        loadSessions();
                    }

                    if (data.error) {
                        clearInterval(timerInterval);
                        botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${escapeHtml(data.error)}</span>`;
                        isAnalyzing = false;
                    }
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            console.log('Analysis aborted by user');
            botMsgDiv.innerHTML = '<span class="text-orange-400">已取消分析。</span>';
        } else {
            console.error(err);
            botMsgDiv.innerHTML = '<span class="text-red-400">連線失敗，請檢查後端伺服器。</span>';
        }
        clearInterval(timerInterval);
        isAnalyzing = false;
    } finally {
        clearInterval(timerInterval);

        if (hitlPaused) {
            // HITL paused: Unlock input so user can type negotiation/answer
            // But keep "Stop" button hidden or converted back to Send?
            // If we unlock input, user can type and hit Send. 
            // sendMessage needs to handle this state.

            isAnalyzing = false; // Logically not "analyzing" (streaming), but waiting.
            const input = document.getElementById('user-input');
            const sendBtn = document.getElementById('send-btn');

            if (input) {
                input.disabled = false;
                input.classList.remove('opacity-50');
                input.focus();
                input.placeholder = "輸入回應或是調整計畫...";
            }
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-red-500', 'hover:bg-red-600', 'text-white');
                sendBtn.classList.add('bg-primary', 'hover:brightness-110');
                sendBtn.innerHTML = '<i data-lucide="arrow-up" class="w-5 h-5"></i>'; // use Send icon
                if (window.lucide) lucide.createIcons({ nodes: [sendBtn] });
            }

        } else {
            // Normal finish or Abort
            resetChatUI();
        }
    }
}

function stopAnalysis() {
    if (window.currentAnalysisController) {
        window.currentAnalysisController.abort();
        window.currentAnalysisController = null;
    }

    // IMPORTANT: Clear HITL context so subsequent messages are treated as new queries
    window._hitlContext = null;

    // Append "Stopped" message
    const chatContainer = document.getElementById('chat-messages');
    if (chatContainer) {
        const stopMsg = document.createElement('div');
        stopMsg.className = 'flex justify-center my-4 opacity-0 animate-fade-in-up';
        stopMsg.style.animationFillMode = 'forwards';
        stopMsg.innerHTML = '<span class="px-3 py-1 rounded-full bg-red-500/10 text-red-500 text-xs font-mono border border-red-500/20">⛔ 分析已終止</span>';
        chatContainer.appendChild(stopMsg);
        setTimeout(() => chatContainer.scrollTop = chatContainer.scrollHeight, 100);
    }

    resetChatUI();
}

function resetChatUI() {
    isAnalyzing = false;
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    if (window.currentAnalysisController) {
        // If called directly (not via stopAnalysis), ensure we nullify
        // But usually stopAnalysis does the aborting.
    }

    if (input) {
        input.disabled = false;
        input.classList.remove('opacity-50');
        input.focus();
    }
    if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-red-500', 'hover:bg-red-600', 'text-white');
        sendBtn.classList.add('bg-primary', 'hover:brightness-110');
        sendBtn.innerHTML = '<i data-lucide="arrow-up" class="w-5 h-5"></i>';
    }
    if (window.lucide) createIconsIn(sendBtn);
}

// Reuse the renderStoredBotMessage function from previous step
function renderStoredBotMessage(fullContent, isStreaming = false, elapsedTime = null) {
    let processContent = '';
    let resultContent = '';
    let hasProcessContent = false;

    const contentLines = fullContent.split('\n');
    let currentMode = 'normal';

    for (const cLine of contentLines) {
        if (cLine.includes('[PROCESS_START]')) { currentMode = 'process'; hasProcessContent = true; continue; }
        if (cLine.includes('[PROCESS_END]')) { currentMode = 'normal'; continue; }
        if (cLine.includes('[RESULT]')) { currentMode = 'result'; continue; }
        if (cLine.startsWith('[PROCESS]')) { processContent += cLine.substring(9) + '\n'; hasProcessContent = true; }
        else if (currentMode === 'process') { processContent += cLine + '\n'; }
        else if (currentMode === 'result') { resultContent += cLine + '\n'; }
        else { resultContent += cLine + '\n'; }
    }

    let html = '';
    if (hasProcessContent && processContent.trim()) {
        const stepCount = (processContent.match(/✅|📊|⚔️|👨‍⚖️|⚖️|🛡️|💰|🚀|🔍|⏳/g) || []).length;
        const processLines = processContent.trim().split('\n').filter(l => l.trim());
        let stepsHtml = '';
        let hasTimeInfo = false;

        processLines.forEach((line, index) => {
            const trimmed = line.trim();
            const isLastLine = index === processLines.length - 1;

            // Determine content
            let lineContent = '';
            if (trimmed.startsWith('---') || trimmed.startsWith('###')) {
                lineContent = `<div class="mt-3 mb-2 text-accent font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
            } else if (trimmed.startsWith('**🐂') || trimmed.startsWith('**🐻') || trimmed.startsWith('**⚖️')) {
                lineContent = `<div class="mt-2 font-medium text-secondary">${md.renderInline(trimmed)}</div>`;
            } else if (trimmed.startsWith('>')) {
                lineContent = `<div class="pl-3 border-l-2 border-white/10 text-textMuted text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
            } else if (trimmed.startsWith('→')) {
                lineContent = `<div class="pl-4 text-textMuted/60 text-xs">${trimmed}</div>`;
            } else if (trimmed.includes('⏱️ **分析完成**: 總耗時')) {
                hasTimeInfo = true;
                const timeMatch = trimmed.match(/⏱️ \*\*分析完成\*\*: 總耗時 ([\d.]+) 秒/);
                if (timeMatch) {
                    lineContent = `<div class="mt-2 p-3 rounded-xl bg-surface border border-white/10 flex items-center gap-2">
                                    <span class="text-primary">⏱️</span>
                                    <span class="text-textMuted">總耗時: <span class="text-secondary font-mono">${timeMatch[1]} 秒</span></span>
                                  </div>`;
                }
            } else {
                lineContent = `<div class="process-step-item py-1">${md.renderInline(trimmed)}</div>`;
            }

            // Append Loading Spinner to the last line if streaming
            if (isStreaming && isLastLine && !trimmed.includes('分析完成')) {
                const spinnerSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-loader-2 animate-spin inline-block ml-2 text-primary"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;

                // Check if it's a div wrapper (standard lines) or just text
                if (lineContent.includes('<div')) {
                    // Insert before the closing div
                    lineContent = lineContent.replace('</div>', ` ${spinnerSvg}</div>`);
                } else {
                    lineContent += ` ${spinnerSvg}`;
                }
            }
            stepsHtml += lineContent;
        });

        // 使用全局變量來跟蹤展開狀態
        const isCurrentlyOpen = window.lastProcessOpenState !== undefined ? window.lastProcessOpenState : true; // Default to open during analysis

        // 如果在步驟中沒有找到時間信息，則檢查完整內容
        let timeInfo = '';
        let timerHeader = '';

        if (!hasTimeInfo) {
            const timeMatch = fullContent.match(/\[PROCESS\]⏱️ \*\*分析完成\*\*: 總耗時 ([\d.]+) 秒/);
            if (timeMatch) {
                timeInfo = `<div class="mt-2 p-3 rounded-xl bg-surface border border-white/10 flex items-center gap-2">
                              <span class="text-primary">⏱️</span>
                              <span class="text-textMuted">總耗時: <span class="text-secondary font-mono">${timeMatch[1]} 秒</span></span>
                            </div>`;
            } else if (isStreaming && elapsedTime) {
                // Live Timer in Header - Reuses the ID so the interval keeps updating it
                timerHeader = `<span class="ml-2 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-mono flex items-center gap-1">
                                <i data-lucide="clock" class="w-3 h-3"></i> 
                                <span id="loading-timer">${elapsedTime}s</span>
                               </span>`;
            }
        }

        html += `
            <details class="process-container" ${isCurrentlyOpen ? 'open' : ''}>
                <summary onclick="toggleProcessState(this)">
                    <div class="flex items-center gap-2">
                        <i data-lucide="chevron-right" class="w-4 h-4 chevron"></i>
                        ${isStreaming ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-loader animate-spin text-primary"><path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/><path d="m16.2 16.2 2.9 2.9"/><path d="M12 18v4"/><path d="m4.9 19.1 2.9-2.9"/><path d="M2 12h4"/><path d="m4.9 4.9 2.9 2.9"/></svg>' : '<i data-lucide="check-circle" class="w-4 h-4 text-green-500"></i>'}
                        <span class="font-medium">分析過程</span>
                        ${timerHeader}
                    </div>
                    <span class="ml-auto text-xs text-textMuted/50">${stepCount} 個步驟</span>
                </summary>
                <div class="process-content custom-scrollbar pl-6 border-l border-white/5 ml-2 mt-2 space-y-1">
                    ${stepsHtml}
                </div>
                ${timeInfo}
            </details>
        `;
    }

    const renderMd = (text) => md ? md.render(text) : `<pre>${text.replace(/</g, '&lt;')}</pre>`;

    if (resultContent.trim()) {
        html += `<div class="result-container prose mt-4">${renderMd(resultContent)}</div>`;
    } else if (!hasProcessContent) {
        let timerHtml = '';
        if (isStreaming && elapsedTime) {
            timerHtml = `<div class="flex items-center gap-2 mb-2 text-xs text-textMuted/50 font-mono">
                            <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>
                            <span id="loading-timer">${elapsedTime}s</span>
                          </div>`;
        }
        html = timerHtml + renderMd(fullContent);
    }

    const proposalMatch = fullContent.match(/<!-- TRADE_PROPOSAL_START (.*?) TRADE_PROPOSAL_END -->/);
    if (proposalMatch) {
        try {
            const proposalJson = proposalMatch[1];
            const pData = JSON.parse(proposalJson);
            html = html.replace(proposalMatch[0], '');
            const btnHtml = `
                <div class="mt-6 p-5 bg-surface rounded-2xl border border-primary/20 flex items-center justify-between">
                    <div>
                        <h4 class="text-sm font-bold text-primary">交易機會</h4>
                        <p class="text-xs text-textMuted mt-1">AI 建議: <span class="text-secondary font-mono">${pData.side.toUpperCase()} ${pData.symbol}</span></p>
                    </div>
                    <button onclick='showProposalModal(${proposalJson})' class="px-4 py-2.5 bg-primary hover:brightness-110 text-background text-sm font-bold rounded-xl shadow-lg shadow-primary/20 transition flex items-center gap-2">
                        <i data-lucide="zap" class="w-4 h-4"></i> 執行交易
                    </button>
                </div>
            `;
            html += btnHtml;
        } catch (e) { console.error("Error parsing proposal", e); }
    }

    // Wrap <table> elements for proper overflow + border styling
    if (html.includes('<table')) {
        const temp = document.createElement('div');
        temp.innerHTML = html;
        temp.querySelectorAll('table').forEach(table => {
            if (!table.parentElement.classList.contains('table-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-wrapper';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
        html = temp.innerHTML;
    }

    return html;
}

// 保存展開狀態的函數
function toggleProcessState(summaryElement) {
    // 獲取對應的 details 元素
    const detailsElement = summaryElement.parentElement;
    // 延遲執行以確保狀態已更新
    setTimeout(() => {
        // 更新狀態標記
        window.lastProcessOpenState = detailsElement.open;
    }, 0);
}

// ── 對話歷史動態載入狀態 ──────────────────────────────────────────────────────
let _historyOldestTimestamp = null;  // 目前可見訊息中最舊的時間戳
let _historyHasMore = false;         // 是否還有更舊的訊息
let _historyLoading = false;         // 防止重複載入
let _historySessionId = null;        // 目前載入的 session

/** 將單條歷史訊息渲染為 DOM 節點（不 append，只 create）。 */
function _buildHistoryMsgEl(msg) {
    const role = msg.role === 'assistant' ? 'bot' : 'user';
    const div = document.createElement('div');
    div.className = `message-bubble ${role === 'user' ? 'user-message' : 'bot-bubble prose'}`;

    if (role === 'bot') {
        const savedState = window.lastProcessOpenState;
        window.lastProcessOpenState = false;
        div.innerHTML = renderStoredBotMessage(msg.content);
        window.lastProcessOpenState = savedState;
    } else {
        div.textContent = msg.content;
    }

    if (msg.timestamp) {
        const footer = document.createElement('div');
        footer.className = 'mt-2 text-[10px] text-textMuted/30 font-mono';
        const date = new Date(msg.timestamp + 'Z');
        footer.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        div.appendChild(footer);
    }
    return div;
}

/** 載入更舊的訊息（向上捲動觸發）。 */
async function loadMoreHistory() {
    if (_historyLoading || !_historyHasMore || !_historyOldestTimestamp) return;
    _historyLoading = true;

    const container = document.getElementById('chat-messages');

    // 顯示頂部 loading 指示器
    const loader = document.createElement('div');
    loader.id = 'history-loader';
    loader.className = 'text-center text-xs text-textMuted/40 py-2';
    loader.textContent = '載入更多訊息…';
    container.prepend(loader);

    try {
        const token = AuthManager.currentUser.accessToken;
        const url = `/api/chat/history?session_id=${encodeURIComponent(_historySessionId)}&before_timestamp=${encodeURIComponent(_historyOldestTimestamp)}`;
        const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
        const data = await res.json();

        loader.remove();

        if (data.history && data.history.length > 0) {
            // 記錄捲動位置，prepend 後還原（避免畫面跳動）
            const oldScrollHeight = container.scrollHeight;

            const frag = document.createDocumentFragment();
            data.history.forEach(msg => frag.appendChild(_buildHistoryMsgEl(msg)));
            container.prepend(frag);
            createIconsIn(container);

            // 還原捲動位置
            container.scrollTop = container.scrollHeight - oldScrollHeight;

            // 更新狀態
            _historyOldestTimestamp = data.history[0].timestamp;
            _historyHasMore = data.has_more;
        } else {
            _historyHasMore = false;
        }
    } catch (e) {
        loader.remove();
        console.error('[history] loadMoreHistory error:', e);
    } finally {
        _historyLoading = false;
    }
}

async function loadChatHistory(sessionId = 'default') {
    // 🔒 安全檢查：未登入時不載入聊天歷史
    const isLoggedIn = window.AuthManager?.isLoggedIn();
    if (!isLoggedIn) {
        showWelcomeScreen();
        return;
    }

    // 重置動態載入狀態
    _historyOldestTimestamp = null;
    _historyHasMore = false;
    _historyLoading = false;
    _historySessionId = sessionId;

    try {
        const token = AuthManager.currentUser.accessToken;
        const res = await fetch(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();

        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        if (data.history && data.history.length > 0) {
            data.history.forEach(msg => container.appendChild(_buildHistoryMsgEl(msg)));
            createIconsIn(container);

            // 更新動態載入狀態
            _historyOldestTimestamp = data.history[0].timestamp;
            _historyHasMore = data.has_more;

            // 初始捲到底
            setTimeout(() => { container.scrollTop = container.scrollHeight; }, 100);

            // 掛載捲動偵測（只掛一次）
            _attachHistoryScrollListener(container);
        } else {
            // Welcome message for empty session
            container.innerHTML = `
                <div class="bot-message opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; animation-fill-mode: forwards;">
                    <div class="flex flex-col items-center justify-center mb-8">
                        <h1 class="font-serif text-3xl md:text-4xl leading-tight text-center">
                            <span class="text-secondary">Welcome to</span><br>
                            <span class="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">CryptoMind</span>
                        </h1>
                    </div>
                    <p class="text-textMuted text-lg font-light leading-relaxed text-center">
                        AI-powered crypto analysis. Start a new conversation.
                    </p>
                    <div class="flex flex-wrap gap-3 mt-8 justify-center">
                         <button onclick="quickAsk('Analyze BTC trend')" class="px-5 py-2.5 rounded-full bg-surface hover:bg-surfaceHighlight border border-white/5 text-sm text-textMuted hover:text-primary transition shadow-sm">
                            Bitcoin Trend
                        </button>
                    </div>
                </div>`;
            createIconsIn(container);
        }
    } catch (e) {
        console.error("Failed to load history:", e);
    }
}

/** 捲動偵測：接近頂部 80px 時觸發 loadMoreHistory。只掛一個 listener。 */
let _scrollListenerAttached = false;
function _attachHistoryScrollListener(container) {
    if (_scrollListenerAttached) return;
    _scrollListenerAttached = true;
    container.addEventListener('scroll', () => {
        if (container.scrollTop < 80 && _historyHasMore && !_historyLoading) {
            loadMoreHistory();
        }
    }, { passive: true });
}

async function initChat() {
    // 防止重複初始化
    if (chatInitialized) {
        console.log('initChat: already initialized, skipping');
        return;
    }

    // 🔒 安全檢查：必須先登入（用戶認證）才能載入聊天記錄
    // 這防止未授權的用戶看到歷史對話
    const isLoggedIn = window.AuthManager?.isLoggedIn();

    if (!isLoggedIn) {
        // 未登入，只顯示歡迎畫面，不載入任何歷史記錄
        showWelcomeScreen();
        // 清空側邊欄
        const list = document.getElementById('chat-session-list');
        if (list) {
            list.innerHTML = '<div class="text-center text-xs text-textMuted/40 py-4">Please login first</div>';
        }
        return;
    }

    chatInitialized = true;
    console.log('initChat: initializing chat...');

    // 2. 檢查是否有現有的 session，如果沒有才創建新的
    const userId = window.currentUserId || AuthManager.currentUser?.user_id || 'local_user';
    const token = AuthManager.currentUser?.accessToken;

    // Safety check
    if (!token) {
        console.error('initChat: No token found');
        return;
    }

    // 1. 載入 sessions（同時渲染側邊欄並取得資料，不重複 fetch）
    let sessions = await loadSessions();

    // Auto-cleanup: Remove older "New Chat" sessions to prevent accumulation
    // Keep the most recent "New Chat" (if any) and delete the rest
    if (sessions.length > 0) {
        const cleanupPromises = [];
        let newChatCount = 0;

        // sessions is sorted by updated_at DESC (newest first)
        for (let i = 0; i < sessions.length; i++) {
            const s = sessions[i];
            if (s.title === 'New Chat') {
                newChatCount++;
                // If we already found one "New Chat" (the newest one), delete this one
                if (newChatCount > 1) {
                    cleanupPromises.push(fetch(`/api/chat/sessions/${s.id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                    }));
                }
            }
        }

        if (cleanupPromises.length > 0) {
            console.log(`Cleaning up ${cleanupPromises.length} redundant sessions...`);
            await Promise.allSettled(cleanupPromises);
            // 清理後重新整理側邊欄（合併原本的兩次 fetch+loadSessions 為一次）
            sessions = await loadSessions();
        }
    }

    if (sessions && sessions.length > 0) {
        // 有現有 sessions，但顯示歡迎畫面而不是自動載入最近的對話
        currentSessionId = null; // Don't auto-load the previous session
        console.log('initChat: showing clean chat room, not auto-loading previous session');
        // 顯示歡迎畫面，讓用戶選擇是否要載入之前的對話
        showWelcomeScreen();
    } else {
        // 沒有 session，設定為 null (Lazy Creation)
        currentSessionId = null;
        console.log('initChat: no existing sessions, showing welcome screen');
        // 不需要創建新的 session，只顯示歡迎畫面
        showWelcomeScreen();
    }

    // 3. 顯示歡迎畫面（如果載入了歷史，loadChatHistory 會覆蓋它）
    // 如果沒有載入歷史 (currentSessionId is null), showWelcomeScreen 已被呼叫
}

// 重置初始化狀態（登出時調用）
function resetChatInit() {
    chatInitialized = false;
    currentSessionId = null;
}

// 不再自動執行 initChat，由 auth.js 在登入成功後調用
// document.addEventListener('DOMContentLoaded', initChat);

// 等待 AuthManager 初始化後，如果已登入則執行 initChat
document.addEventListener('DOMContentLoaded', () => {
    // 延遲一點時間確保 AuthManager 已初始化
    setTimeout(() => {
        if (window.AuthManager && window.AuthManager.isLoggedIn()) {
            initChat();
        }
    }, 100);
});

window.submitFeedback = async function (codebookId, score, btn) {
    if (!codebookId) return;

    // Disable buttons to prevent spam
    const parent = btn.parentElement;
    const buttons = parent.querySelectorAll('button');
    buttons.forEach(b => b.disabled = true);

    try {
        const token = AuthManager.currentUser.accessToken;
        await fetch('/api/chat/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                codebook_entry_id: codebookId,
                score: score
            })
        });

        // UI Feedback
        if (score > 0) {
            btn.innerHTML = '<i data-lucide="check-circle" class="w-3.5 h-3.5 text-success fill-success/20"></i>';
            btn.classList.add('text-success');
        } else {
            btn.innerHTML = '<i data-lucide="x-circle" class="w-3.5 h-3.5 text-danger fill-danger/20"></i>';
            btn.classList.add('text-danger');
        }
        createIconsIn(btn);

    } catch (e) {
        console.error("Feedback failed:", e);
        // Re-enable on error
        buttons.forEach(b => b.disabled = false);
    }
};
