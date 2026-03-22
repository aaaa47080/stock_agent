// ========================================
// chat-init.js - 聊天初始化與反饋
// 職責：initChat、resetChatInit、submitFeedback
// 依賴：所有其他 chat-*.js 模組
// ========================================

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
            list.innerHTML =
                '<div class="text-center text-xs text-textMuted/40 py-4">Please login first</div>';
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
                    cleanupPromises.push(
                        AppAPI.delete(`/api/chat/sessions/${s.id}`)
                    );
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
window.resetChatInit = resetChatInit;

// 暴露到全域供其他模組使用
window.initChat = initChat;

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

// 反饋提交
async function submitFeedback(codebookId, score, btn) {
    if (!codebookId) return;

    // Disable buttons to prevent spam
    const parent = btn.parentElement;
    const buttons = parent.querySelectorAll('button');
    buttons.forEach((b) => (b.disabled = true));

    try {
        await AppAPI.post('/api/chat/feedback', {
            codebook_entry_id: codebookId,
            score: score,
        });

        // UI Feedback
        if (score > 0) {
            btn.innerHTML =
                '<i data-lucide="check-circle" class="w-3.5 h-3.5 text-success fill-success/20"></i>';
            btn.classList.add('text-success');
        } else {
            btn.innerHTML =
                '<i data-lucide="x-circle" class="w-3.5 h-3.5 text-danger fill-danger/20"></i>';
            btn.classList.add('text-danger');
        }
        createIconsIn(btn);
    } catch (e) {
        console.error('Feedback failed:', e);
        // Re-enable on error
        buttons.forEach((b) => (b.disabled = false));
        if (typeof showToast === 'function') showToast('反饋提交失敗，請稍後再試', 'error');
    }
};
window.submitFeedback = submitFeedback;

export {
    initChat,
    resetChatInit,
    submitFeedback,
};
