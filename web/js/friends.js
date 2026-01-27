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

    /**
     * 搜尋用戶
     * @param {string} query - 搜尋關鍵字
     * @param {number} limit - 結果數量限制
     */
    async searchUsers(query, limit = 20) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/friends/search?q=${encodeURIComponent(query)}&user_id=${userId}&limit=${limit}`);
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
        const res = await fetch(`/api/friends/profile/${targetUserId}${query}`);
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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
            method: 'DELETE'
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

        const res = await fetch(`/api/friends/list?user_id=${userId}&limit=${limit}&offset=${offset}`);
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

        const res = await fetch(`/api/friends/requests/received?user_id=${userId}`);
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

        const res = await fetch(`/api/friends/requests/sent?user_id=${userId}`);
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

        const res = await fetch(`/api/friends/status/${targetUserId}?user_id=${userId}`);
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

        const res = await fetch(`/api/friends/counts?user_id=${userId}`);
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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

        const res = await fetch(`/api/friends/blocked?user_id=${userId}`);
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

        return `
            <div class="user-card bg-surface border border-white/5 rounded-xl p-4 flex items-center justify-between hover:border-white/10 transition">
                <a href="/static/forum/profile.html?id=${user.user_id}" class="flex items-center gap-3 flex-1 min-w-0">
                    <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold flex-shrink-0">
                        ${initial}
                    </div>
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-textMain truncate">${user.username || user.user_id}</span>
                            ${badge}
                        </div>
                        <div class="text-xs text-textMuted">
                            ${user.friends_since ? '好友 · ' + this.formatTime(user.friends_since) : ''}
                            ${user.requested_at ? '請求於 ' + this.formatTime(user.requested_at) : ''}
                            ${user.sent_at ? '發送於 ' + this.formatTime(user.sent_at) : ''}
                        </div>
                    </div>
                </a>
                <div class="flex-shrink-0 ml-2">
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
