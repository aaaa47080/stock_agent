// ========================================
// chat-history.js - 對話歷史管理
// 職責：loadChatHistory、loadMoreHistory、滾動偵測
// 依賴：chat-state.js
// ========================================

// ── 對話歷史動態載入狀態 ──────────────────────────────────────────────────────
let _historyOldestTimestamp = null; // 目前可見訊息中最舊的時間戳
let _historyHasMore = false; // 是否還有更舊的訊息
let _historyLoading = false; // 防止重複載入
let _historySessionId = null; // 目前載入的 session

/** 將單條歷史訊息渲染為 DOM 節點（不 append，只 create）。 */
function _buildHistoryMsgEl(msg) {
    const role = msg.role === 'assistant' ? 'bot' : 'user';
    const div = document.createElement('div');
    div.className = `message-bubble ${role === 'user' ? 'user-message' : 'bot-bubble prose'}`;

    if (role === 'bot') {
        const savedState = AppStore.get('lastProcessOpenState');
        AppStore.set('lastProcessOpenState', false);
        div.innerHTML = renderStoredBotMessage(msg.content);
        AppStore.set('lastProcessOpenState', savedState);
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
        const url = `/api/chat/history?session_id=${encodeURIComponent(_historySessionId)}&before_timestamp=${encodeURIComponent(_historyOldestTimestamp)}`;
        const data = await AppAPI.get(url);

        loader.remove();

        if (data.history && data.history.length > 0) {
            // 記錄捲動位置，prepend 後還原（避免畫面跳動）
            const oldScrollHeight = container.scrollHeight;

            const frag = document.createDocumentFragment();
            data.history.forEach((msg) => frag.appendChild(_buildHistoryMsgEl(msg)));
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
        if (typeof showToast === 'function') showToast('載入更多歷史記錄失敗', 'error');
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
        const data = await AppAPI.get(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`);

        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        if (data.history && data.history.length > 0) {
            data.history.forEach((msg) => container.appendChild(_buildHistoryMsgEl(msg)));
            createIconsIn(container);

            // 更新動態載入狀態
            _historyOldestTimestamp = data.history[0].timestamp;
            _historyHasMore = data.has_more;

            // 初始捲到底
            setTimeout(() => {
                container.scrollTop = container.scrollHeight;
            }, 100);

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
        console.error('Failed to load history:', e);
    }
}

// 暴露到全域供其他模組使用
window.loadChatHistory = loadChatHistory;
window.loadMoreHistory = loadMoreHistory;

/** 捲動偵測：接近頂部 80px 時觸發 loadMoreHistory。只掛一個 listener。 */
let _scrollListenerAttached = false;
function _attachHistoryScrollListener(container) {
    if (_scrollListenerAttached) return;
    _scrollListenerAttached = true;
    container.addEventListener(
        'scroll',
        () => {
            if (container.scrollTop < 80 && _historyHasMore && !_historyLoading) {
                loadMoreHistory();
            }
        },
        { passive: true }
    );
}

export { loadChatHistory, loadMoreHistory };

