// ========================================
// chat.js - 聊天功能 (多會話版)
// ========================================

let currentSessionId = null;
let chatInitialized = false;  // 防止重複初始化
// isAnalyzing is declared globally in app.js
// 用於跟踪分析過程面板的展開狀態
window.lastProcessOpenState = false;

// 編輯模式（批量刪除）
let isEditMode = false;
let selectedSessions = new Set();

function appendMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    // 使用 bot-bubble 取代原本的 bot-message 來套用背景框，bot-message 則保持透明
    div.className = `message-bubble ${role === 'user' ? 'user-message' : 'bot-bubble prose'}`;

    if (role === 'bot') {
        div.innerHTML = md.render(content);
        const match = content.match(/\b([A-Z]{2,5})\b/);
        if (match && !content.includes('載入中') && !content.includes('Error')) {
            const symbol = match[1];
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'flex gap-2 mt-4 pt-4 border-t border-white/5';
            actionsDiv.innerHTML = `
                <button onclick="startDebateInChat('${symbol}')" class="text-xs bg-gradient-to-r from-success/20 to-danger/20 text-secondary px-3 py-1.5 rounded-full hover:from-success/30 hover:to-danger/30 border border-white/10 transition flex items-center gap-1.5">
                    <i data-lucide="swords" class="w-3 h-3"></i> AI War Room
                </button>
                <button onclick="showChart('${symbol}');" class="text-xs bg-primary/10 text-primary px-3 py-1.5 rounded-full hover:bg-primary/20 border border-primary/20 transition flex items-center gap-1.5">
                    <i data-lucide="bar-chart" class="w-3 h-3"></i> Chart
                </button>
            `;
            div.appendChild(actionsDiv);
            setTimeout(() => lucide.createIcons(), 0);
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
    lucide.createIcons();
}

function toggleSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
    if (sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.remove('-translate-x-full');
    } else {
        sidebar.classList.add('-translate-x-full');
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
        // 使用 user_id 來過濾該用戶的 sessions
        const userId = window.currentUserId || 'local_user';
        const res = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
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
                    <button onclick="deleteSelectedSessions()" class="p-1.5 ${selectedSessions.size > 0 ? 'text-danger hover:bg-danger/10' : 'text-textMuted/30 cursor-not-allowed'} rounded-lg transition" ${selectedSessions.size === 0 ? 'disabled' : ''} title="刪除已選">
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
        lucide.createIcons();

        // 更新收藏區的 chevron 樣式
        updateStarredChevron();
    } catch (e) {
        console.error("Failed to load sessions:", e);
    }
}

// 創建單個 session 項目
function createSessionItem(session) {
    const isActive = session.id === currentSessionId;
    const isSelected = selectedSessions.has(session.id);
    const div = document.createElement('div');
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
                <button onclick="toggleStarSession(event, '${session.id}', ${!session.is_pinned})" class="p-1 hover:text-yellow-500 transition" title="${session.is_pinned ? '取消收藏' : '收藏'}">
                    <i data-lucide="star" class="w-3.5 h-3.5 ${session.is_pinned ? 'fill-yellow-500 text-yellow-500' : ''}"></i>
                </button>
                <button onclick="deleteSession(event, '${session.id}')" class="p-1 hover:text-danger transition" title="Delete Chat">
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

async function deleteSelectedSessions() {
    if (selectedSessions.size === 0) return;

    const count = selectedSessions.size;
    const confirmed = await showConfirmDialog({
        title: '批量刪除',
        message: `確定要刪除 ${count} 個對話嗎？此操作無法復原。`,
        confirmText: '刪除',
        cancelText: '取消',
        type: 'danger'
    });

    if (!confirmed) return;

    try {
        // 批量刪除
        const deletePromises = Array.from(selectedSessions).map(sessionId =>
            fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' })
        );
        await Promise.all(deletePromises);

        // 如果當前 session 被刪除了，清空聊天區域
        if (selectedSessions.has(currentSessionId)) {
            currentSessionId = null;
            showWelcomeScreen();
        }

        // 清空選中並退出編輯模式
        selectedSessions.clear();
        isEditMode = false;
        await loadSessions();
    } catch (e) {
        console.error("Failed to delete sessions:", e);
    }
}

async function toggleStarSession(event, sessionId, newStatus) {
    event.stopPropagation();
    try {
        await fetch(`/api/chat/sessions/${sessionId}/pin?is_pinned=${newStatus}`, { method: 'PUT' });
        await loadSessions();
    } catch (e) {
        console.error("Failed to toggle star:", e);
    }
}

async function createNewChat() {
    try {
        // 先切換到 Chat tab（確保用戶能看到效果）
        if (typeof switchTab === 'function') {
            switchTab('chat');
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
    lucide.createIcons();
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

    // 自動切換到 Chat 標籤頁
    if (typeof switchTab === 'function') {
        switchTab('chat');
    }

    // Update sidebar active state
    await loadSessions();

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

    const confirmed = await showConfirmDialog({
        title: '刪除對話',
        message: '確定要刪除這個對話嗎？此操作無法復原。',
        confirmText: '刪除',
        cancelText: '取消',
        type: 'danger'
    });

    if (!confirmed) return;

    try {
        await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });

        // 重新獲取 sessions 列表（需要傳入 user_id）
        const userId = window.currentUserId || 'local_user';
        const res = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
        const sessions = await res.json();

        if (currentSessionId === sessionId) {
            // 如果刪除的是當前 session，先清空聊天區域
            const container = document.getElementById('chat-messages');
            if (container) {
                container.innerHTML = '';
            }

            if (sessions && sessions.length > 0) {
                // 切換到第一個現有 session
                currentSessionId = sessions[0].session_id;
                await loadSessions();
                await loadChatHistory(currentSessionId);
            } else {
                // 沒有其他 session 了，顯示歡迎畫面
                currentSessionId = null;
                await loadSessions();
                showWelcomeScreen();
            }
        } else {
            // 刪除的不是當前 session，只需刷新列表
            await loadSessions();
        }
    } catch (e) {
        console.error("Failed to delete session:", e);
    }
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const text = input.value.trim();
    if (!text || isAnalyzing) return;

    // 檢查用戶是否有設置 API key（從 localStorage）
    const userKey = window.APIKeyManager?.getCurrentKey();

    if (!userKey) {
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

    // Lazy Creation: 如果沒有 currentSessionId，先建立新的 Session
    if (!currentSessionId) {
        try {
            const userId = window.currentUserId || 'local_user';
            // 這裡可以傳遞 title (e.g., text.substring(0, 20)) 但後端通常會預設為 New Chat 或由第一條訊息生成
            const createRes = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`, { method: 'POST' });
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
    isAnalyzing = true;

    input.disabled = true;
    sendBtn.disabled = true;
    input.classList.add('opacity-50');
    sendBtn.classList.add('opacity-50', 'cursor-not-allowed');

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

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                manual_selection: selection,
                market_type: marketType,
                auto_execute: autoExecute,
                user_api_key: userKey.key,
                user_provider: userKey.provider,
                user_model: userSelectedModel,
                session_id: currentSessionId // Pass current session ID
            }),
            signal: window.currentAnalysisController.signal
        });

        // Backend 已經保存了用戶訊息並更新了標題，立即刷新列表以顯示新標題
        loadSessions();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            const currentElapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));
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
                        timeBadge.className = 'mt-4 text-xs text-textMuted/60 font-mono';
                        timeBadge.innerHTML = `分析完成，耗時 ${totalTime}s`;
                        botMsgDiv.appendChild(timeBadge);
                        lucide.createIcons();

                        // Refresh sessions list (to update title if it was new)
                        loadSessions();
                    }
                    if (data.error) {
                        clearInterval(timerInterval);
                        botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${data.error}</span>`;
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
        window.currentAnalysisController = null;
        clearInterval(timerInterval);
        input.disabled = false;
        sendBtn.disabled = false;
        input.classList.remove('opacity-50');
        sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        input.focus();
    }
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

    if (resultContent.trim()) {
        html += `<div class="result-container prose mt-4">${md.render(resultContent)}</div>`;
    } else if (!hasProcessContent) {
        let timerHtml = '';
        if (isStreaming && elapsedTime) {
             timerHtml = `<div class="flex items-center gap-2 mb-2 text-xs text-textMuted/50 font-mono">
                            <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>
                            <span id="loading-timer">${elapsedTime}s</span>
                          </div>`;
        }
        html = timerHtml + md.render(fullContent);
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

async function loadChatHistory(sessionId = 'default') {
    // 🔒 安全檢查：未登入時不載入聊天歷史
    const isLoggedIn = window.AuthManager?.isLoggedIn();
    if (!isLoggedIn) {
        showWelcomeScreen();
        return;
    }

    try {
        const res = await fetch(`/api/chat/history?session_id=${sessionId}`);
        const data = await res.json();

        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        if (data.history && data.history.length > 0) {
            data.history.forEach(msg => {
                const role = msg.role === 'assistant' ? 'bot' : 'user';
                const div = appendMessage(role, msg.content);

                if (role === 'bot') {
                    // 在渲染歷史消息時，暫時重置狀態以避免影響當前活動的分析
                    const savedState = window.lastProcessOpenState;
                    window.lastProcessOpenState = false;
                    div.innerHTML = renderStoredBotMessage(msg.content);
                    // 恢復原來的狀態
                    window.lastProcessOpenState = savedState;
                    const footer = document.createElement('div');
                    footer.className = 'mt-2 text-[10px] text-textMuted/30 font-mono';
                    const date = new Date(msg.timestamp + 'Z');
                    footer.textContent = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    div.appendChild(footer);
                }
            });
            lucide.createIcons();
            setTimeout(() => { container.scrollTop = container.scrollHeight; }, 100);
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
             lucide.createIcons();
        }
    } catch (e) {
        console.error("Failed to load history:", e);
    }
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

    // 1. 先載入現有 sessions
    await loadSessions();

    // 2. 檢查是否有現有的 session，如果沒有才創建新的
    const userId = window.currentUserId || 'local_user';
    const sessionsRes = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
    const sessionsData = await sessionsRes.json();
    let sessions = sessionsData.sessions || [];

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
                    cleanupPromises.push(fetch(`/api/chat/sessions/${s.id}`, { method: 'DELETE' }));
                }
            }
        }

        if (cleanupPromises.length > 0) {
            console.log(`Cleaning up ${cleanupPromises.length} redundant sessions...`);
            await Promise.allSettled(cleanupPromises);
            // Reload list to reflect changes
            const refreshedRes = await fetch(`/api/chat/sessions?user_id=${encodeURIComponent(userId)}`);
            const refreshedData = await refreshedRes.json();
            sessions = refreshedData.sessions || [];
            await loadSessions();
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

// ========================================
// 自訂確認對話框
// ========================================

/**
 * 顯示自訂確認對話框
 * @param {Object} options - 配置選項
 * @param {string} options.title - 標題
 * @param {string} options.message - 訊息內容
 * @param {string} options.confirmText - 確認按鈕文字 (預設: "確認")
 * @param {string} options.cancelText - 取消按鈕文字 (預設: "取消")
 * @param {string} options.type - 類型: "danger" | "warning" | "info" (預設: "danger")
 * @returns {Promise<boolean>} - 用戶確認返回 true，取消返回 false
 */
function showConfirmDialog(options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const iconContainer = document.getElementById('confirm-modal-icon');
        const title = document.getElementById('confirm-modal-title');
        const message = document.getElementById('confirm-modal-message');
        const confirmBtn = document.getElementById('confirm-modal-confirm');
        const cancelBtn = document.getElementById('confirm-modal-cancel');

        // 設置內容
        title.textContent = options.title || '確認操作';
        message.textContent = options.message || '確定要執行此操作嗎？';
        confirmBtn.textContent = options.confirmText || '確認';
        cancelBtn.textContent = options.cancelText || '取消';

        // 設置圖示和顏色
        const type = options.type || 'danger';
        const iconConfig = {
            danger: { icon: 'trash-2', bgClass: 'bg-danger/10', textClass: 'text-danger', btnClass: 'bg-danger' },
            warning: { icon: 'alert-triangle', bgClass: 'bg-yellow-500/10', textClass: 'text-yellow-500', btnClass: 'bg-yellow-500' },
            info: { icon: 'info', bgClass: 'bg-primary/10', textClass: 'text-primary', btnClass: 'bg-primary' }
        };
        const config = iconConfig[type] || iconConfig.danger;

        // 更新圖示容器
        iconContainer.className = `w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${config.bgClass}`;
        iconContainer.innerHTML = `<i data-lucide="${config.icon}" class="w-8 h-8 ${config.textClass}"></i>`;

        // 更新確認按鈕顏色
        confirmBtn.className = `flex-1 py-3 ${config.btnClass} hover:brightness-110 text-white font-bold rounded-2xl transition shadow-lg`;

        // 重新渲染圖示
        lucide.createIcons();

        // 顯示 modal
        modal.classList.remove('hidden');

        // 清除之前的事件監聽器
        const newConfirmBtn = confirmBtn.cloneNode(true);
        const newCancelBtn = cancelBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

        // 綁定事件
        newConfirmBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
            resolve(true);
        });

        newCancelBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
            resolve(false);
        });

        // 點擊背景關閉
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
                resolve(false);
            }
        }, { once: true });
    });
}

// 暴露到全局
window.showConfirmDialog = showConfirmDialog;
