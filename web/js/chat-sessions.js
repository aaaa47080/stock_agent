// ========================================
// chat-sessions.js - Session 管理
// 職責：Session 列表載入、創建、刪除、收藏、編輯模式
// 依賴：chat-state.js
// ========================================


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
            list.innerHTML =
                '<div class="text-center text-xs text-textMuted/40 py-4">Please login first</div>';
        }
        return;
    }

    try {
        // 使用 AuthManager 獲取用戶 ID
        const isLoggedIn = window.AuthManager?.isLoggedIn();
        if (!isLoggedIn) return; // Should be handled by top check, but safe to keep

        const userId = AuthManager.currentUser.user_id;

        const data = await AppAPI.get(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
        const list = document.getElementById('chat-session-list');
        list.innerHTML = '';

        if (data.sessions && data.sessions.length > 0) {
            // 分離收藏和普通對話
            const starredSessions = data.sessions.filter((s) => s.is_pinned);
            const regularSessions = data.sessions.filter((s) => !s.is_pinned);
            const allSessions = data.sessions;

            // 編輯模式工具栏
            const toolbar = document.createElement('div');
            toolbar.className = 'edit-toolbar flex items-center gap-2 px-3 py-2 mb-2';

            if (window.isEditMode) {
                const allSelected =
                    allSessions.length > 0 && window.selectedSessions.size === allSessions.length;
                toolbar.innerHTML = `
                    <button onclick="toggleSelectAll()" class="flex items-center gap-1.5 text-xs ${allSelected ? 'text-primary' : 'text-textMuted hover:text-secondary'} transition">
                        <i data-lucide="${allSelected ? 'check-square' : 'square'}" class="w-3.5 h-3.5"></i>
                        <span>${allSelected ? '取消全選' : '全選'}</span>
                    </button>
                    <div class="flex-1"></div>
                    <span class="text-[10px] text-textMuted/50">${window.selectedSessions.size} 已選</span>
                    <button onclick="deleteSelectedSessions(this)" class="p-1.5 ${window.selectedSessions.size > 0 ? 'text-danger hover:bg-danger/10' : 'text-textMuted/30 cursor-not-allowed'} rounded-lg transition" ${window.selectedSessions.size === 0 ? 'disabled' : ''} title="刪除已選">
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
                starredSessions.forEach((session) => {
                    starredList.appendChild(createSessionItem(session));
                });
            }

            // 渲染普通對話區
            if (regularSessions.length > 0) {
                // 如果有收藏區，加一個小標題
                if (starredSessions.length > 0) {
                    const recentLabel = document.createElement('div');
                    recentLabel.className =
                        'flex items-center gap-2 px-3 py-2 text-xs font-medium text-textMuted/60';
                    recentLabel.innerHTML = `
                        <i data-lucide="clock" class="w-3 h-3"></i>
                        <span>最近</span>
                    `;
                    list.appendChild(recentLabel);
                }

                regularSessions.forEach((session) => {
                    list.appendChild(createSessionItem(session));
                });
            }

            // 都沒有的話顯示空狀態
            if (starredSessions.length === 0 && regularSessions.length === 0) {
                list.innerHTML =
                    '<div class="text-center text-xs text-textMuted/40 py-4">No history</div>';
            }

            // 儲存所有 session ID 供全選使用
            AppStore.set('allSessionIds', allSessions.map((s) => s.id));
            window._allSessionIds = AppStore.get('allSessionIds');
        } else {
            list.innerHTML =
                '<div class="text-center text-xs text-textMuted/40 py-4">No history</div>';
            // 退出編輯模式（沒有對話了）
            if (window.isEditMode) exitEditMode();
        }
        createIconsIn(document.getElementById('chat-session-list'));

        // 更新收藏區的 chevron 樣式
        updateStarredChevron();
        return data.sessions || [];
    } catch (e) {
        console.error('Failed to load sessions:', e);
        return [];
    }
}
window.loadSessions = loadSessions;

// 創建單個 session 項目
function createSessionItem(session) {
    const isActive = session.id === window.currentSessionId;
    const isSelected = window.selectedSessions.has(session.id);
    const div = document.createElement('div');
    div.dataset.sessionId = session.id;
    div.className = `group flex items-center gap-2 p-3 rounded-xl cursor-pointer transition text-sm mb-1 ${isActive ? 'bg-surfaceHighlight text-primary' : 'hover:bg-white/5 text-textMuted hover:text-secondary'} ${isSelected ? 'bg-primary/10 border border-primary/20' : ''}`;

    if (window.isEditMode) {
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
    if (isActive && !window.isEditMode) {
        setTimeout(() => {
            div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    }

    return div;
}
window.createSessionItem = createSessionItem;

// 切換收藏區展開/收合狀態
function toggleStarredSection(summaryElement) {
    setTimeout(() => {
        const details = summaryElement.parentElement;
        starredSectionOpen = details.open;
        updateStarredChevron();
    }, 0);
}
window.toggleStarredSection = toggleStarredSection;

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
window.updateStarredChevron = updateStarredChevron;

// ========================================
// 編輯模式（批量刪除）
// ========================================

function enterEditMode() {
    window.isEditMode = true;
    window.selectedSessions.clear();
    loadSessions();
}
window.enterEditMode = enterEditMode;

function exitEditMode() {
    window.isEditMode = false;
    window.selectedSessions.clear();
    loadSessions();
}
window.exitEditMode = exitEditMode;

function toggleSessionSelection(sessionId) {
    if (window.selectedSessions.has(sessionId)) {
        window.selectedSessions.delete(sessionId);
    } else {
        window.selectedSessions.add(sessionId);
    }
    loadSessions();
}
window.toggleSessionSelection = toggleSessionSelection;

function toggleSelectAll() {
    const allIds = AppStore.get('allSessionIds') || [];
    if (window.selectedSessions.size === allIds.length) {
        // 已全選，取消全選
        window.selectedSessions.clear();
    } else {
        // 全選
        window.selectedSessions = new Set(allIds);
    }
    loadSessions();
}
window.toggleSelectAll = toggleSelectAll;

async function deleteSelectedSessions(btnElement) {
    if (window.selectedSessions.size === 0) return;

    const count = window.selectedSessions.size;
    const confirmed = await showConfirm({
        title: '批量刪除',
        message: `確定要刪除 ${count} 個對話嗎？此操作無法復原。`,
        confirmText: '刪除',
        cancelText: '取消',
        type: 'danger',
    });

    if (!confirmed) return;

    if (btnElement) {
        btnElement.disabled = true;
        btnElement.classList.add('opacity-50', 'cursor-not-allowed');
    }

    // ── Optimistic UI: remove all selected items + toolbar immediately ───────
    const toDelete = Array.from(window.selectedSessions);
    toDelete.forEach((sid) => {
        const div = document.querySelector(`[data-session-id="${sid}"]`);
        if (div) div.remove();
    });
    // Remove edit toolbar immediately so the count/buttons don't linger
    document.querySelector('#chat-session-list .edit-toolbar')?.remove();

    // 如果當前 session 被刪除了，清空聊天區域
    if (window.selectedSessions.has(window.currentSessionId)) {
        window.currentSessionId = null;
        AppStore.set('currentSessionId', null);
        showWelcomeScreen();
    }

    // Clear any HITL context for deleted sessions
    if (_hitlContext?.sessionId && window.selectedSessions.has(_hitlContext.sessionId)) {
        _hitlContext = null;
    }

    // 清空選中並退出編輯模式
    window.selectedSessions.clear();
    window.isEditMode = false;

    try {
        await Promise.all(
            toDelete.map((sessionId) =>
                AppAPI.delete(`/api/chat/sessions/${sessionId}`)
            )
        );
        // Rebuild sidebar (clears edit toolbar and syncs with server)
        await loadSessions();
    } catch (e) {
        console.error('Failed to delete sessions:', e);
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }
}
window.deleteSelectedSessions = deleteSelectedSessions;

async function toggleStarSession(event, sessionId, newStatus) {
    event.stopPropagation();
    // Decode sessionId that was encoded for XSS protection
    sessionId = decodeURIComponent(sessionId);
    try {
        await AppAPI.put(`/api/chat/sessions/${sessionId}/pin?is_pinned=${newStatus}`);
        await loadSessions();
    } catch (e) {
        console.error('Failed to toggle star:', e);
        if (typeof showToast === 'function') showToast('收藏操作失敗，請稍後再試', 'error');
    }
}
window.toggleStarSession = toggleStarSession;

async function createNewChat() {
    try {
        // 先切換到 Chat tab（確保用戶能看到效果）
        if (typeof switchTab === 'function') {
            await switchTab('chat');
        }

        // 如果當前已經是新對話狀態 (currentSessionId 為 null)，直接返回
        if (window.currentSessionId === null) {
            showWelcomeScreen();
            return;
        }

        // ⚠️ 取消正在進行的分析請求，避免 isAnalyzing 阻擋新聊天室的訊息發送
        if (AppStore.get('currentAnalysisController')) {
            AppStore.get('currentAnalysisController').abort();
            AppStore.set('currentAnalysisController', null);
            window.currentAnalysisController = null;
        }
        isAnalyzing = false;

        // 切換到"新對話"狀態，不立即建立 session
        window.currentSessionId = null;
        AppStore.set('currentSessionId', null);

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
        console.error('Failed to prepare new chat:', e);
    }
}
window.createNewChat = createNewChat;

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
window.showWelcomeScreen = showWelcomeScreen;

// 直接更新側邊欄的 active 高亮，不重新拉取 sessions
function updateSessionActiveState(newSessionId) {
    document.querySelectorAll('[data-session-id]').forEach((el) => {
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
window.updateSessionActiveState = updateSessionActiveState;

async function switchSession(sessionId) {
    if (sessionId === window.currentSessionId) return;

    // ⚠️ 取消正在進行的分析請求，避免 isAnalyzing 阻擋新 session 的訊息發送
    if (AppStore.get('currentAnalysisController')) {
        AppStore.get('currentAnalysisController').abort();
        AppStore.set('currentAnalysisController', null);
        window.currentAnalysisController = null;
    }
    isAnalyzing = false;

    window.currentSessionId = sessionId;
    AppStore.set('currentSessionId', sessionId);

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
window.switchSession = switchSession;

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
        type: 'danger',
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

    const wasActive = window.currentSessionId === sessionId;
    if (wasActive) {
        const container = document.getElementById('chat-messages');
        if (container) container.innerHTML = '';
        window.currentSessionId = nextSessionId || null;
        AppStore.set('currentSessionId', window.currentSessionId);
        if (!nextSessionId) showWelcomeScreen();
    }

    // Clear any lingering HITL context for this session to prevent ghost re-creation
    if (_hitlContext?.sessionId === sessionId) _hitlContext = null;

    // ── Step 2: Fire DELETE + load next session history in parallel ───────────
    // No need to call loadSessions() — optimistic UI already removed the item
    try {
        await Promise.all([
            AppAPI.delete(`/api/chat/sessions/${sessionId}`),
            wasActive && nextSessionId ? loadChatHistory(nextSessionId) : Promise.resolve(),
        ]);
    } catch (e) {
        console.error('Failed to delete session:', e);
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        // Restore sidebar on failure
        await loadSessions();
    }
}
window.deleteSession = deleteSession;

export {
    loadSessions,
    createSessionItem,
    toggleStarredSection,
    updateStarredChevron,
    enterEditMode,
    exitEditMode,
    toggleSessionSelection,
    toggleSelectAll,
    deleteSelectedSessions,
    toggleStarSession,
    createNewChat,
    showWelcomeScreen,
    updateSessionActiveState,
    switchSession,
    deleteSession,
};
