/**
 * friends.js - 好友功能前端 API 客戶端
 * v1.0
 */

const FriendsAPI = {
    /**
     * 取得當前用戶 ID
     */
    _getUserId() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            return AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
        }
        return null;
    },

    _getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            const token = AuthManager.currentUser.accessToken || AuthManager.currentUser.piAccessToken;
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return headers;
    },

    /**
     * 搜尋用戶
     * @param {string} query - 搜尋關鍵字
     * @param {number} limit - 結果數量限制
     */
    async searchUsers(query, limit = 20) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/search?q=${encodeURIComponent(query)}&user_id=${userId}&limit=${limit}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '搜尋失敗');
        }
        return await res.json();
    },

    /**
     * 取得用戶資料
     * @param {string} targetUserId - 目標用戶 ID
     */
    async getProfile(targetUserId) {
        const userId = this._getUserId();
        const query = userId ? `?user_id=${userId}` : '';
        const res = await fetch(`/api/friends/profile/${targetUserId}${query}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得用戶資料失敗');
        }
        return await res.json();
    },

    /**
     * 發送好友請求
     * @param {string} targetUserId - 目標用戶 ID
     */
    async sendRequest(targetUserId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/request?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: targetUserId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '發送請求失敗');
        }
        return await res.json();
    },

    /**
     * 接受好友請求
     * @param {string} requesterId - 發送請求的用戶 ID
     */
    async acceptRequest(requesterId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/accept?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: requesterId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '接受請求失敗');
        }
        return await res.json();
    },

    /**
     * 拒絕好友請求
     * @param {string} requesterId - 發送請求的用戶 ID
     */
    async rejectRequest(requesterId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/reject?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: requesterId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '拒絕請求失敗');
        }
        return await res.json();
    },

    /**
     * 取消已發送的好友請求
     * @param {string} targetUserId - 目標用戶 ID
     */
    async cancelRequest(targetUserId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/cancel?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: targetUserId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取消請求失敗');
        }
        return await res.json();
    },

    /**
     * 移除好友
     * @param {string} friendId - 好友的用戶 ID
     */
    async removeFriend(friendId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/remove?user_id=${userId}&target_user_id=${friendId}`, {
            method: 'DELETE',
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '移除好友失敗');
        }
        return await res.json();
    },

    /**
     * 取得好友列表
     * @param {number} limit - 結果數量限制
     * @param {number} offset - 偏移量
     */
    async getFriends(limit = 50, offset = 0) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/list?user_id=${userId}&limit=${limit}&offset=${offset}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得好友列表失敗');
        }
        return await res.json();
    },

    /**
     * 取得收到的好友請求
     */
    async getReceivedRequests() {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/requests/received?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得好友請求失敗');
        }
        return await res.json();
    },

    /**
     * 取得已發送的好友請求
     */
    async getSentRequests() {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/requests/sent?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得已發送請求失敗');
        }
        return await res.json();
    },

    /**
     * 取得與特定用戶的好友狀態
     * @param {string} targetUserId - 目標用戶 ID
     */
    async getStatus(targetUserId) {
        const userId = this._getUserId();
        if (!userId) return { status: null, is_friend: false };

        const res = await fetch(`/api/friends/status/${targetUserId}?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            return { status: null, is_friend: false };
        }
        return await res.json();
    },

    /**
     * 取得好友相關數量
     */
    async getCounts() {
        const userId = this._getUserId();
        if (!userId) return { friends_count: 0, pending_received: 0 };

        const res = await fetch(`/api/friends/counts?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            return { friends_count: 0, pending_received: 0 };
        }
        return await res.json();
    },

    /**
     * 封鎖用戶
     * @param {string} targetUserId - 目標用戶 ID
     */
    async blockUser(targetUserId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/block?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: targetUserId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '封鎖失敗');
        }
        return await res.json();
    },

    /**
     * 解除封鎖
     * @param {string} targetUserId - 目標用戶 ID
     */
    async unblockUser(targetUserId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/unblock?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ target_user_id: targetUserId })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '解除封鎖失敗');
        }
        return await res.json();
    },

    /**
     * 取得封鎖名單
     */
    async getBlockedUsers() {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/blocked?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得封鎖名單失敗');
        }
        return await res.json();
    }
};

// 匯出到全域
window.FriendsAPI = FriendsAPI;

/**
 * 好友功能 UI 工具函數
 */
const FriendsUI = {
    /**
     * 格式化時間
     */
    formatTime(dateString) {
        if (!dateString) return '';
        // Fix: If date string has no timezone (e.g. from SQLite/MySQL datetime), treat as UTC
        if (!dateString.includes('Z') && !dateString.includes('+')) {
            dateString += 'Z';
        }
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return '剛剛';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分鐘前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小時前`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;
        return date.toLocaleDateString('zh-TW');
    },

    /**
     * 取得會員等級徽章
     */
    getMembershipBadge(tier) {
        if (tier === 'pro') {
            return '<span class="px-1.5 py-0.5 text-xs font-bold bg-gradient-to-r from-yellow-500 to-orange-500 text-black rounded">PRO</span>';
        }
        return '';
    },

    /**
     * 取得好友狀態按鈕 HTML
     */
    getFriendButton(userId, status, isRequester) {
        if (status === 'accepted') {
            return `
                <button onclick="FriendsUI.handleRemoveFriend('${userId}')"
                        class="friend-btn bg-success/10 text-success px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-success/20 hover:bg-danger/10 hover:text-danger hover:border-danger/20 transition group">
                    <i data-lucide="user-check" class="w-4 h-4 group-hover:hidden"></i>
                    <i data-lucide="user-minus" class="w-4 h-4 hidden group-hover:block"></i>
                    <span class="group-hover:hidden">好友</span>
                    <span class="hidden group-hover:inline">移除</span>
                </button>
            `;
        }
        if (status === 'pending') {
            if (isRequester) {
                return `
                    <button onclick="FriendsUI.handleCancelRequest('${userId}')"
                            class="friend-btn bg-white/5 text-textMuted px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-white/10 hover:bg-danger/10 hover:text-danger hover:border-danger/20 transition">
                        <i data-lucide="clock" class="w-4 h-4"></i>
                        <span>等待中</span>
                    </button>
                `;
            }
            return `
                <div class="flex gap-2">
                    <button onclick="FriendsUI.handleAcceptRequest('${userId}')"
                            class="bg-success/10 hover:bg-success/20 text-success px-3 py-1.5 rounded-lg text-sm font-bold transition">
                        <i data-lucide="check" class="w-4 h-4"></i>
                    </button>
                    <button onclick="FriendsUI.handleRejectRequest('${userId}')"
                            class="bg-danger/10 hover:bg-danger/20 text-danger px-3 py-1.5 rounded-lg text-sm font-bold transition">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
            `;
        }
        if (status === 'blocked') {
            return `
                <button onclick="FriendsUI.handleUnblock('${userId}')"
                        class="friend-btn bg-danger/10 text-danger px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-danger/20 hover:bg-danger/20 transition">
                    <i data-lucide="ban" class="w-4 h-4"></i>
                    <span>已封鎖</span>
                </button>
            `;
        }
        // 預設：加好友按鈕
        return `
            <button onclick="FriendsUI.handleAddFriend('${userId}')"
                    class="friend-btn bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 transition border border-primary/20">
                <i data-lucide="user-plus" class="w-4 h-4"></i>
                <span>加好友</span>
            </button>
        `;
    },

    /**
     * 渲染用戶卡片
     */
    renderUserCard(user, showActions = true) {
        const badge = this.getMembershipBadge(user.membership_tier);
        const actionBtn = showActions ? this.getFriendButton(user.user_id, user.friend_status, user.is_requester) : '';
        const initial = (user.username || 'U')[0].toUpperCase();

        // 如果是好友，顯示發訊息按鈕
        const messageBtn = (user.friend_status === 'accepted') ? `
            <button onclick="event.stopPropagation(); FriendsUI.openChat('${user.user_id}', '${user.username || user.user_id}')"
               class="p-2 hover:bg-white/5 rounded-lg transition text-textMuted hover:text-primary"
               title="發訊息">
                <i data-lucide="message-circle" class="w-4 h-4"></i>
            </button>
        ` : '';

        return `
            <div class="user-card bg-surface border border-white/5 rounded-xl p-4 flex items-center justify-between hover:border-white/10 transition">
                <a href="/static/forum/profile.html?id=${user.user_id}" onclick="sessionStorage.setItem('returnToTab', 'friends')" class="flex items-center gap-3 flex-1 min-w-0">
                    <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold flex-shrink-0">
                        ${initial}
                    </div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-textMain truncate">${user.username || user.user_id}</span>
                            ${badge}
                        </div>
                        <div class="text-xs text-textMuted">
                            ${user.last_active_at ? '上線 ' + this.formatTime(user.last_active_at) : (user.friends_since ? '成為好友 ' + this.formatTime(user.friends_since) : '')}
                            ${user.requested_at ? '收到請求 ' + this.formatTime(user.requested_at) : ''}
                            ${user.sent_at ? '已發送請求 ' + this.formatTime(user.sent_at) : ''}
                        </div>
                    </div>
                </a>
                <div class="flex-shrink-0 ml-2 flex items-center gap-2">
                    ${messageBtn}
                    ${actionBtn}
                </div>
            </div>
        `;
    },

    /**
     * 處理加好友
     */
    async handleAddFriend(userId) {
        try {
            await FriendsAPI.sendRequest(userId);
            if (typeof showToast === 'function') {
                showToast('好友請求已發送', 'success');
            }
            // 重新載入頁面或更新 UI
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理接受請求
     */
    async handleAcceptRequest(userId) {
        try {
            await FriendsAPI.acceptRequest(userId);
            if (typeof showToast === 'function') {
                showToast('已成為好友', 'success');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理拒絕請求
     */
    async handleRejectRequest(userId) {
        try {
            await FriendsAPI.rejectRequest(userId);
            if (typeof showToast === 'function') {
                showToast('已拒絕請求', 'info');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理取消請求
     */
    async handleCancelRequest(userId) {
        try {
            await FriendsAPI.cancelRequest(userId);
            if (typeof showToast === 'function') {
                showToast('已取消請求', 'info');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理移除好友
     */
    async handleRemoveFriend(userId) {
        if (typeof showConfirm === 'function') {
            const confirmed = await showConfirm({
                title: '移除好友',
                message: '確定要移除此好友嗎？',
                type: 'warning',
                confirmText: '確定移除',
                cancelText: '取消'
            });
            if (!confirmed) return;
        } else if (!confirm('確定要移除此好友嗎？')) {
            return;
        }

        try {
            await FriendsAPI.removeFriend(userId);
            if (typeof showToast === 'function') {
                showToast('已移除好友', 'info');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理封鎖
     */
    async handleBlock(userId) {
        if (typeof showConfirm === 'function') {
            const confirmed = await showConfirm({
                title: '封鎖用戶',
                message: '封鎖後，對方將無法發送好友請求給你。確定要封鎖嗎？',
                type: 'danger',
                confirmText: '確定封鎖',
                cancelText: '取消'
            });
            if (!confirmed) return;
        } else if (!confirm('確定要封鎖此用戶嗎？')) {
            return;
        }

        try {
            await FriendsAPI.blockUser(userId);
            if (typeof showToast === 'function') {
                showToast('已封鎖用戶', 'info');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 處理解除封鎖
     */
    async handleUnblock(userId) {
        try {
            await FriendsAPI.unblockUser(userId);
            if (typeof showToast === 'function') {
                showToast('已解除封鎖', 'success');
            }
            if (typeof refreshFriendsUI === 'function') {
                refreshFriendsUI();
            } else {
                location.reload();
            }
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    /**
     * 開啟與用戶的聊天（切換到聊天 tab 並開啟對話）
     */
    openChat(userId, username) {
        // 保存當前 tab 以便返回
        sessionStorage.setItem('returnToTab', 'friends');
        // 統一跳轉到全屏聊天頁面，帶上來源參數（平滑過渡）
        const targetUrl = `/static/forum/messages.html?with=${userId}&source=friends`;
        if (typeof smoothNavigate === 'function') {
            smoothNavigate(targetUrl);
        } else {
            window.location.href = targetUrl;
        }
    }
};

window.FriendsUI = FriendsUI;

// ========================================
// Friends Logic Controller (UI Orchestration)
// ========================================

/**
 * 載入好友分頁的所有數據
 */
async function loadFriendsTabData() {
    console.log('loadFriendsTabData called');

    // Check if AuthManager exists
    if (typeof AuthManager === 'undefined') {
        console.error('AuthManager not found');
        return;
    }

    const isLoggedIn = AuthManager.isLoggedIn();
    const pendingListEl = document.getElementById('pending-requests-list');
    const friendsListEl = document.getElementById('friends-list');
    const blockedListEl = document.getElementById('blocked-users-container');

    // Reset badges
    updateBadge('friends-badge-total', 0);
    updateBadge('pending-count-badge', 0, true);
    updateBadge('friends-count-badge', 0, true);
    updateBadge('blocked-count-badge', 0, true);

    if (!isLoggedIn) {
        const loginMsg = `<div class="text-center py-6"><p class="text-textMuted mb-3">請先登入以使用好友功能</p><button onclick="handleLinkWallet()" class="px-4 py-2 bg-primary/10 text-primary rounded-lg text-sm font-bold">登入 / 綁定錢包</button></div>`;
        if (pendingListEl) pendingListEl.innerHTML = loginMsg;
        if (friendsListEl) friendsListEl.innerHTML = loginMsg;
        if (blockedListEl) blockedListEl.innerHTML = renderEmptyState('請先登入');
        return;
    }

    // Load Data in Parallel
    try {
        const [requestsRes, friendsRes, blockedRes] = await Promise.all([
            FriendsAPI.getReceivedRequests().catch(e => ({ error: e })),
            FriendsAPI.getFriends().catch(e => ({ error: e })),
            FriendsAPI.getBlockedUsers().catch(e => ({ error: e }))
        ]);

        // Render Requests
        if (pendingListEl) {
            if (requestsRes.error) {
                pendingListEl.innerHTML = renderErrorState(requestsRes.error.message);
            } else if (!requestsRes.requests || requestsRes.requests.length === 0) {
                pendingListEl.innerHTML = renderEmptyState('沒有待處理的好友請求');
            } else {
                pendingListEl.innerHTML = requestsRes.requests.map(req => {
                    // Normalize data structure if needed
                    const user = {
                        ...req,
                        friend_status: 'pending',
                        is_requester: false // We are receiving, so we are NOT the requester
                    };
                    return FriendsUI.renderUserCard(user);
                }).join('');

                // Update badge
                updateBadge('pending-count-badge', requestsRes.requests.length);

                // Update total badge if needed
                updateBadge('friends-badge-total', requestsRes.requests.length);
            }
        }

        // Render Friends
        if (friendsListEl) {
            if (friendsRes.error) {
                friendsListEl.innerHTML = renderErrorState(friendsRes.error.message);
            } else if (!friendsRes.friends || friendsRes.friends.length === 0) {
                friendsListEl.innerHTML = renderEmptyState('尚未添加任何好友');
            } else {
                friendsListEl.innerHTML = friendsRes.friends.map(friend => {
                    const user = {
                        ...friend,
                        friend_status: 'accepted'
                    };
                    return FriendsUI.renderUserCard(user);
                }).join('');
                updateBadge('friends-count-badge', friendsRes.friends.length);
            }
        }

        // Render Blocked
        if (blockedListEl) {
            if (blockedRes.error) {
                blockedListEl.innerHTML = renderErrorState(blockedRes.error.message);
            } else if (!blockedRes.blocked_users || blockedRes.blocked_users.length === 0) {
                blockedListEl.innerHTML = renderEmptyState('黑名單為空');
            } else {
                blockedListEl.innerHTML = blockedRes.blocked_users.map(user => {
                    const u = {
                        ...user,
                        friend_status: 'blocked'
                    };
                    return FriendsUI.renderUserCard(u);
                }).join('');
                updateBadge('blocked-count-badge', blockedRes.blocked_users.length);
            }
        }

        // Re-initialize icons after rendering dynamic content
        if (window.lucide) lucide.createIcons();

    } catch (e) {
        console.error('Failed to load friend data:', e);
        if (typeof showToast === 'function') showToast('載入好友數據失敗', 'error');
    }
}

/**
 * 處理好友搜尋
 */
let searchTimeout = null;
async function handleFriendSearch(query) {
    const resultsEl = document.getElementById('search-results');
    if (!resultsEl) return;

    if (!query || query.trim().length === 0) {
        resultsEl.classList.add('hidden');
        resultsEl.innerHTML = '';
        return;
    }

    resultsEl.classList.remove('hidden');
    resultsEl.innerHTML = `
        <div class="text-center py-4 text-textMuted">
            <i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>
            搜尋中...
        </div>
    `;
    if (window.lucide) lucide.createIcons();

    // Debounce
    if (searchTimeout) clearTimeout(searchTimeout);

    searchTimeout = setTimeout(async () => {
        try {
            const res = await FriendsAPI.searchUsers(query);

            if (res.users && res.users.length > 0) {
                resultsEl.innerHTML = res.users.map(user =>
                    FriendsUI.renderUserCard(user)
                ).join('');
            } else {
                resultsEl.innerHTML = renderEmptyState('找不到符合的用戶');
            }

            if (window.lucide) lucide.createIcons();

        } catch (e) {
            resultsEl.innerHTML = renderErrorState(e.message);
        }
    }, 500);
}

// Helpers
function renderEmptyState(msg) {
    return `<div class="text-center text-textMuted py-4 opacity-60 text-sm">${msg}</div>`;
}

function renderErrorState(msg) {
    return `<div class="text-center text-danger py-4 text-sm"><i data-lucide="alert-circle" class="w-4 h-4 inline-block mr-1"></i> ${msg}</div>`;
}

function updateBadge(id, count, hideIfZero = false) {
    const el = document.getElementById(id);
    if (!el) return;

    el.textContent = count;
    if (hideIfZero && count === 0) {
        el.classList.add('hidden');
    } else {
        el.classList.remove('hidden');
    }
}

// Expose functions globally
window.loadFriendsTabData = loadFriendsTabData;
window.handleFriendSearch = handleFriendSearch;
window.refreshFriendsUI = loadFriendsTabData; // Alias for internal refreshes


// ============================================================================
// SocialHub - 整合社交中心控制器（好友 + 聊天）
// ============================================================================

const SocialHub = {
    currentSubTab: 'messages',
    currentConversationId: null,
    currentOtherUserId: null,
    currentOtherUsername: null,
    isPro: false,
    conversations: [],
    isMobile: window.innerWidth < 768,
    maxMessageLength: 500,
    initialized: false,

    /**
     * 初始化社交中心
     */
    async init() {
        if (this.initialized) {
            console.log('SocialHub: 已初始化，跳過');
            return;
        }

        // 只在主應用中運行（檢查是否有 friends-tab 容器）
        const friendsTab = document.getElementById('friends-tab');
        if (!friendsTab || !document.getElementById('social-content-messages')) {
            console.log('SocialHub: 不在主應用中，跳過初始化');
            return;
        }

        console.log('SocialHub: 初始化中...');

        // 檢查登入狀態
        if (typeof AuthManager === 'undefined' || !AuthManager.isLoggedIn()) {
            console.log('SocialHub: 未登入');
            return;
        }

        // 初始化 MessagesUI
        if (typeof MessagesUI !== 'undefined') {
            MessagesUI.init();
        }

        // 載入訊息限制狀態
        await this.loadLimits();

        // 載入對話列表
        await this.loadConversations();

        // 載入好友數據
        if (typeof loadFriendsTabData === 'function') {
            loadFriendsTabData();
        }

        // 連接 WebSocket
        this.setupWebSocket();

        // 響應式處理
        window.addEventListener('resize', () => {
            this.isMobile = window.innerWidth < 768;
        });

        this.initialized = true;
        console.log('SocialHub: 初始化完成');

        // 重新初始化圖標
        if (window.lucide) lucide.createIcons();
    },

    /**
     * 導航到消息頁面（平滑過渡）
     */
    navigateToMessages(userId) {
        // 保存當前 tab 以便返回
        sessionStorage.setItem('returnToTab', 'friends');
        const targetUrl = `/static/forum/messages.html?with=${userId}&source=friends`;
        if (typeof smoothNavigate === 'function') {
            smoothNavigate(targetUrl);
        } else {
            window.location.href = targetUrl;
        }
    },

    /**
     * 刷新數據
     */
    async refresh() {
        if (this.currentSubTab === 'messages') {
            await this.loadConversations();
            if (this.currentConversationId) {
                await this.loadMessages();
            }
        } else {
            if (typeof loadFriendsTabData === 'function') {
                loadFriendsTabData();
            }
        }
        if (window.lucide) lucide.createIcons();
    },

    /**
     * 切換子標籤
     */
    switchSubTab(tab) {
        this.currentSubTab = tab;

        // 更新 tab 按鈕樣式
        document.querySelectorAll('.social-sub-tab').forEach(btn => {
            btn.classList.remove('bg-primary', 'text-background');
            btn.classList.add('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
        });

        const activeBtn = document.getElementById(`social-tab-${tab}`);
        if (activeBtn) {
            activeBtn.classList.remove('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
            activeBtn.classList.add('bg-primary', 'text-background');
        }

        // 切換內容
        document.getElementById('social-content-messages').classList.toggle('hidden', tab !== 'messages');
        document.getElementById('social-content-friends').classList.toggle('hidden', tab !== 'friends');

        // 初始化數據
        if (tab === 'messages' && this.conversations.length === 0) {
            this.loadConversations();
        } else if (tab === 'friends') {
            if (typeof loadFriendsTabData === 'function') {
                loadFriendsTabData();
            }
        }

        if (window.lucide) lucide.createIcons();
    },

    /**
     * 載入訊息限制狀態
     */
    async loadLimits() {
        if (typeof MessagesAPI === 'undefined') return;

        const limits = await MessagesAPI.getLimits();
        if (limits) {
            this.isPro = limits.is_pro;

            // 更新訊息長度限制
            if (limits.max_length) {
                this.maxMessageLength = limits.max_length;
                const input = document.getElementById('social-msg-input');
                if (input) {
                    input.maxLength = this.maxMessageLength;
                }
                const charCount = document.getElementById('social-char-count');
                if (charCount) {
                    charCount.textContent = `0/${this.maxMessageLength}`;
                }
            }

            // 顯示/隱藏限制信息
            const limitInfo = document.getElementById('social-msg-limit');
            if (limitInfo) {
                if (this.isPro) {
                    limitInfo.classList.add('hidden');
                } else {
                    limitInfo.classList.remove('hidden');
                    document.getElementById('social-limit-used').textContent = limits.message_limit?.used || 0;
                    document.getElementById('social-limit-total').textContent = limits.message_limit?.limit || 20;
                }
            }
        }
    },

    /**
     * 載入對話列表
     */
    async loadConversations() {
        const listEl = document.getElementById('social-conv-list');
        if (!listEl) return;

        try {
            if (typeof MessagesAPI === 'undefined') {
                listEl.innerHTML = '<div class="p-4 text-center text-textMuted">訊息功能未載入</div>';
                return;
            }

            const result = await MessagesAPI.getConversations();
            this.conversations = result.conversations || [];

            // 更新未讀徽章
            let totalUnread = 0;
            this.conversations.forEach(c => totalUnread += c.unread_count || 0);
            const unreadBadge = document.getElementById('messages-unread-badge');
            if (unreadBadge) {
                if (totalUnread > 0) {
                    unreadBadge.textContent = totalUnread > 99 ? '99+' : totalUnread;
                    unreadBadge.classList.remove('hidden');
                } else {
                    unreadBadge.classList.add('hidden');
                }
            }

            if (this.conversations.length === 0) {
                listEl.innerHTML = this._renderEmptyState('尚無對話', 'message-square');
                if (window.lucide) lucide.createIcons();
                return;
            }

            listEl.innerHTML = this.conversations.map(conv =>
                this._renderConversationItem(conv, conv.id === this.currentConversationId)
            ).join('');

            if (window.lucide) lucide.createIcons();
        } catch (e) {
            console.error('載入對話列表失敗:', e);
            listEl.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
        }
    },

    /**
     * 選擇對話
     */
    async selectConversation(conversationId, otherUserId, otherUsername) {
        this.currentConversationId = conversationId;
        this.currentOtherUserId = otherUserId;
        this.currentOtherUsername = otherUsername;

        // 更新 UI
        this.showChatSection();
        this.updateChatHeader(otherUsername);
        await this.loadMessages();

        // 標記已讀
        if (typeof MessagesAPI !== 'undefined') {
            await MessagesAPI.markAsRead(conversationId);
        }

        // 更新對話列表中的未讀狀態
        this.updateConversationUnread(conversationId, 0);
    },

    /**
     * 透過用戶 ID 開啟對話
     */
    async openConversationWith(userId, username) {
        const messagesContainer = document.getElementById('social-messages-container');
        if (messagesContainer) {
            messagesContainer.innerHTML = this._renderLoadingState();
        }

        try {
            if (typeof MessagesAPI === 'undefined') return;

            const result = await MessagesAPI.getConversationWith(userId);
            this.currentConversationId = result.conversation.id;
            this.currentOtherUserId = userId;

            // 取得用戶名
            const conv = this.conversations.find(c => c.other_user_id === userId);
            this.currentOtherUsername = username || conv?.other_username || userId;

            this.showChatSection();
            this.updateChatHeader(this.currentOtherUsername);
            this.renderMessages(result.messages || []);

            // 標記已讀
            if (result.conversation.id) {
                await MessagesAPI.markAsRead(result.conversation.id);
            }

            // 重新載入對話列表以更新順序
            await this.loadConversations();

        } catch (e) {
            console.error('開啟對話失敗:', e);
            if (messagesContainer) {
                messagesContainer.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
            }
        }
    },

    /**
     * 載入訊息
     */
    async loadMessages() {
        const messagesContainer = document.getElementById('social-messages-container');
        if (!messagesContainer) return;

        messagesContainer.innerHTML = this._renderLoadingState();

        try {
            if (typeof MessagesAPI === 'undefined') return;

            const result = await MessagesAPI.getMessages(this.currentConversationId);
            this.renderMessages(result.messages || []);
        } catch (e) {
            console.error('載入訊息失敗:', e);
            messagesContainer.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
        }
    },

    /**
     * 渲染訊息列表
     */
    renderMessages(messages) {
        const container = document.getElementById('social-messages-container');
        if (!container) return;

        if (messages.length === 0) {
            container.innerHTML = this._renderEmptyState('開始對話吧', 'message-circle');
            if (window.lucide) lucide.createIcons();
            return;
        }

        if (typeof MessagesUI !== 'undefined') {
            container.innerHTML = messages.map(msg =>
                MessagesUI.renderMessageBubble(msg, this.isPro)
            ).join('');
        }

        // 滾動到底部
        container.scrollTop = container.scrollHeight;
    },

    /**
     * 發送訊息
     */
    async sendMessage(event) {
        event.preventDefault();

        const input = document.getElementById('social-msg-input');
        const content = input.value.trim();

        if (!content || !this.currentOtherUserId) return;

        const sendBtn = document.getElementById('social-send-btn');
        sendBtn.disabled = true;

        try {
            if (typeof MessagesAPI === 'undefined') return;

            const result = await MessagesAPI.sendMessage(this.currentOtherUserId, content);

            if (result.success) {
                input.value = '';
                this.autoResizeInput(input);

                // 添加訊息到畫面
                this.appendMessage(result.message);

                // 更新限制顯示
                if (!this.isPro) {
                    const limits = await MessagesAPI.getLimits();
                    if (limits) {
                        document.getElementById('social-limit-used').textContent = limits.message_limit?.used || 0;
                    }
                }
            }
        } catch (e) {
            console.error('發送訊息失敗:', e);
            if (typeof showToast === 'function') {
                showToast(e.message, 'error');
            }
        } finally {
            sendBtn.disabled = false;
            this.updateSendButton();
        }
    },

    /**
     * 添加新訊息到畫面
     */
    appendMessage(msg) {
        const container = document.getElementById('social-messages-container');
        if (!container) return;

        // 移除空狀態
        const emptyState = container.querySelector('.flex.flex-col.items-center');
        if (emptyState) {
            container.innerHTML = '';
        }

        if (typeof MessagesUI !== 'undefined') {
            container.insertAdjacentHTML('beforeend', MessagesUI.renderMessageBubble(msg, this.isPro));
        }
        container.scrollTop = container.scrollHeight;
    },

    /**
     * 處理輸入框按鍵
     */
    handleInputKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            document.getElementById('social-msg-form').requestSubmit();
        }
    },

    /**
     * 自動調整輸入框高度
     */
    autoResizeInput(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        this.updateSendButton();
    },

    /**
     * 更新發送按鈕狀態
     */
    updateSendButton() {
        const input = document.getElementById('social-msg-input');
        const sendBtn = document.getElementById('social-send-btn');
        if (input && sendBtn) {
            sendBtn.disabled = !input.value.trim();
        }
    },

    /**
     * 更新字數統計
     */
    updateCharCount() {
        const input = document.getElementById('social-msg-input');
        const charCount = document.getElementById('social-char-count');
        if (!input || !charCount) return;

        const currentLength = input.value.length;
        const maxLength = this.maxMessageLength;

        charCount.textContent = `${currentLength}/${maxLength}`;

        // 根據字數改變顏色
        charCount.classList.remove('text-danger', 'text-yellow-500', 'text-textMuted/50');
        if (currentLength >= maxLength) {
            charCount.classList.add('text-danger');
        } else if (currentLength >= maxLength * 0.9) {
            charCount.classList.add('text-yellow-500');
        } else {
            charCount.classList.add('text-textMuted/50');
        }
    },

    /**
     * 顯示聊天區域
     */
    showChatSection() {
        const sidebar = document.getElementById('social-conv-sidebar');
        const chatSection = document.getElementById('social-chat-section');
        const chatHeader = document.getElementById('social-chat-header');
        const inputContainer = document.getElementById('social-msg-input-container');

        if (this.isMobile) {
            if (sidebar) sidebar.classList.add('hidden');
            if (chatSection) {
                chatSection.classList.remove('hidden');
                chatSection.classList.add('flex');
            }
        } else {
            if (chatSection) {
                chatSection.classList.remove('hidden');
                chatSection.classList.add('flex');
            }
        }

        if (chatHeader) chatHeader.classList.remove('hidden');
        if (inputContainer) inputContainer.classList.remove('hidden');
    },

    /**
     * 返回對話列表（手機版）
     */
    backToConvList() {
        const sidebar = document.getElementById('social-conv-sidebar');
        const chatSection = document.getElementById('social-chat-section');

        if (sidebar) sidebar.classList.remove('hidden');
        if (chatSection) {
            chatSection.classList.add('hidden');
            chatSection.classList.remove('flex');
        }

        this.currentConversationId = null;
        this.currentOtherUserId = null;
    },

    /**
     * 更新聊天標題
     */
    updateChatHeader(username) {
        const avatar = document.getElementById('social-chat-avatar');
        const usernameEl = document.getElementById('social-chat-username');
        const profileLink = document.getElementById('social-chat-profile-link');
        const badgeEl = document.getElementById('social-chat-badge');

        if (avatar) avatar.textContent = (username || 'U')[0].toUpperCase();
        if (usernameEl) usernameEl.textContent = username;
        if (profileLink) profileLink.href = `/static/forum/profile.html?id=${this.currentOtherUserId}`;

        // 找到對話資訊更新徽章
        const conv = this.conversations.find(c => c.other_user_id === this.currentOtherUserId);
        if (badgeEl) {
            if (conv && conv.other_membership_tier === 'pro' && typeof MessagesUI !== 'undefined') {
                badgeEl.innerHTML = MessagesUI.getMembershipBadge('pro');
            } else {
                badgeEl.innerHTML = '';
            }
        }
    },

    /**
     * 更新對話的未讀數
     */
    updateConversationUnread(conversationId, count) {
        const item = document.querySelector(`.social-conv-item[data-conversation-id="${conversationId}"]`);
        if (item) {
            const badge = item.querySelector('.unread-badge');
            if (badge) {
                if (count > 0) {
                    badge.textContent = count > 99 ? '99+' : count;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
    },

    /**
     * 設置 WebSocket
     */
    setupWebSocket() {
        if (typeof MessagesWebSocket === 'undefined') return;

        MessagesWebSocket.onConnect((data) => {
            console.log('SocialHub: WebSocket 連接成功');
        });

        MessagesWebSocket.onMessage((message, isSent) => {
            // 如果是自己發送的訊息，跳過
            if (isSent) return;

            // 如果是當前對話的訊息，添加到畫面
            if (message.conversation_id === this.currentConversationId) {
                this.appendMessage(message);
                // 標記已讀
                if (typeof MessagesAPI !== 'undefined') {
                    MessagesAPI.markAsRead(this.currentConversationId);
                }
            } else {
                // 其他對話的新訊息，更新對話列表
                this.loadConversations();
                const senderName = message.from_username || message.from_user_id;
                const preview = message.content.length > 30 ? message.content.substring(0, 30) + '...' : message.content;
                if (typeof showToast === 'function') {
                    showToast(`${senderName}: ${preview}`, 'info');
                }
            }
        });

        MessagesWebSocket.onReadReceipt((conversationId, readBy) => {
            // 更新已讀狀態
            if (this.isPro && conversationId === this.currentConversationId) {
                const bubbles = document.querySelectorAll('.message-bubble');
                bubbles.forEach(bubble => {
                    const status = bubble.querySelector('.text-textMuted:last-child');
                    if (status && status.textContent.includes('已送達')) {
                        status.innerHTML = '<span class="text-xs text-success">已讀</span>';
                    }
                });
            }
        });

        MessagesWebSocket.connect();
    },

    // ========================
    // 內部渲染方法
    // ========================

    _renderConversationItem(conv, isActive = false) {
        const initial = (conv.other_username || 'U')[0].toUpperCase();
        const badge = conv.other_membership_tier === 'pro'
            ? '<span class="px-1.5 py-0.5 text-xs font-bold bg-gradient-to-r from-yellow-500 to-orange-500 text-black rounded">PRO</span>'
            : '';
        const unreadClass = conv.unread_count > 0 ? 'font-bold text-textMain' : 'text-textMuted';
        const activeClass = isActive ? 'bg-primary/10 border-primary/30' : 'hover:bg-white/5';

        let preview = conv.last_message || '開始對話';
        if (preview.length > 30) {
            preview = preview.substring(0, 30) + '...';
        }

        const timeStr = this._formatTime(conv.last_message_at);

        return `
            <div class="social-conv-item cursor-pointer p-3 border-b border-white/5 ${activeClass} transition"
                 data-conversation-id="${conv.id}"
                 data-other-user-id="${conv.other_user_id}"
                 onclick="SocialHub.navigateToMessages('${conv.other_user_id}')">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold flex-shrink-0">
                        ${initial}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between gap-2">
                            <div class="flex items-center gap-2 min-w-0">
                                <span class="font-bold text-textMain truncate">${conv.other_username}</span>
                                ${badge}
                            </div>
                            <span class="text-xs text-textMuted flex-shrink-0">${timeStr}</span>
                        </div>
                        <div class="flex items-center justify-between gap-2 mt-0.5">
                            <p class="text-sm ${unreadClass} truncate">${preview}</p>
                            ${conv.unread_count > 0 ? `
                                <span class="unread-badge flex-shrink-0 w-5 h-5 rounded-full bg-primary text-background text-xs font-bold flex items-center justify-center">
                                    ${conv.unread_count > 99 ? '99+' : conv.unread_count}
                                </span>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    _renderEmptyState(message, icon = 'message-square') {
        return `
            <div class="flex flex-col items-center justify-center h-full text-textMuted p-8">
                <i data-lucide="${icon}" class="w-16 h-16 opacity-30 mb-4"></i>
                <p class="text-center">${message}</p>
            </div>
        `;
    },

    _renderLoadingState() {
        return `
            <div class="flex items-center justify-center h-full">
                <div class="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full"></div>
            </div>
        `;
    },

    _formatTime(dateString) {
        if (!dateString) return '';
        if (!dateString.includes('Z') && !dateString.includes('+')) {
            dateString += 'Z';
        }
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return '剛剛';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}分鐘前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}小時前`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;
        return date.toLocaleDateString('zh-TW');
    }
};

window.SocialHub = SocialHub;
