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
            const userId = AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
            // 優先使用標準 Token，若無則在測試模式下使用 user_id
            const token = AuthManager.currentUser.accessToken || AuthManager.currentUser.piAccessToken || userId;
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
                <div class="flex gap-2">
                    <button onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleRemoveFriend('${userId}')"
                            class="friend-btn bg-white/5 text-textMuted px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-white/10 hover:bg-danger/10 hover:text-danger hover:border-danger/20 transition group">
                        <i data-lucide="user-check" class="w-4 h-4 group-hover:hidden"></i>
                        <i data-lucide="user-minus" class="w-4 h-4 hidden group-hover:block"></i>
                        <span class="group-hover:hidden">好友</span>
                        <span class="hidden group-hover:inline">移除</span>
                    </button>
                    <button onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleBlock('${userId}')"
                            class="friend-btn bg-danger/5 text-danger/80 px-2 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-danger/10 hover:bg-danger/20 hover:text-danger transition"
                            title="封鎖用戶">
                        <i data-lucide="ban" class="w-4 h-4"></i>
                    </button>
                </div>
            `;
        }
        if (status === 'pending') {
            if (isRequester) {
                return `
                    <button onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleCancelRequest('${userId}')"
                            class="friend-btn bg-white/5 text-textMuted px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-white/10 hover:bg-danger/10 hover:text-danger hover:border-danger/20 transition">
                        <i data-lucide="clock" class="w-4 h-4"></i>
                        <span>等待中</span>
                    </button>
                `;
            }
            return `
                <div class="flex gap-2">
                    <button id="accept-btn-${userId}" onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleAcceptRequest('${userId}')"
                            class="bg-success/10 hover:bg-success/20 text-success px-3 py-1.5 rounded-lg text-sm font-bold transition disabled:opacity-50 disabled:cursor-not-allowed">
                        <i data-lucide="check" class="w-4 h-4"></i>
                    </button>
                    <button id="reject-btn-${userId}" onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleRejectRequest('${userId}')"
                            class="bg-danger/10 hover:bg-danger/20 text-danger px-3 py-1.5 rounded-lg text-sm font-bold transition disabled:opacity-50 disabled:cursor-not-allowed">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
            `;
        }
        if (status === 'blocked') {
            return `
                <button onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleUnblock('${userId}')"
                        class="friend-btn bg-danger/10 text-danger px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-danger/20 hover:bg-danger/20 transition">
                    <i data-lucide="ban" class="w-4 h-4"></i>
                    <span>已封鎖</span>
                </button>
            `;
        }
        // 預設：加好友按鈕
        return `
            <button id="add-friend-btn-${userId}" onclick="event.stopPropagation(); event.preventDefault(); FriendsUI.handleAddFriend('${userId}')"
                    class="friend-btn bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 transition border border-primary/20 disabled:opacity-50 disabled:cursor-not-allowed">
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
        const btn = document.getElementById(`add-friend-btn-${userId}`);

        // 立即顯示加載狀態
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>發送中...</span>';
            if (window.lucide) window.lucide.createIcons();
        }

        try {
            await FriendsAPI.sendRequest(userId);
            if (typeof showToast === 'function') {
                showToast('好友請求已發送', 'success');
            }

            // 更新為「等待中」按鈕
            if (btn) {
                btn.id = `cancel-request-btn-${userId}`;
                btn.disabled = false;
                btn.className = 'friend-btn bg-white/5 text-textMuted px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 border border-white/10 hover:bg-danger/10 hover:text-danger hover:border-danger/20 transition';
                btn.innerHTML = '<i data-lucide="clock" class="w-4 h-4"></i><span>等待中</span>';
                btn.onclick = (e) => { e.stopPropagation(); e.preventDefault(); FriendsUI.handleCancelRequest(userId); };
                if (window.lucide) window.lucide.createIcons();
            }

        } catch (error) {
            // 恢復按鈕狀態
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="user-plus" class="w-4 h-4"></i><span>加好友</span>';
                if (window.lucide) window.lucide.createIcons();
            }

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
        const acceptBtn = document.getElementById(`accept-btn-${userId}`);
        const rejectBtn = document.getElementById(`reject-btn-${userId}`);

        // 禁用按鈕防止重複點擊
        if (acceptBtn) {
            acceptBtn.disabled = true;
            acceptBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i>';
        }
        if (rejectBtn) rejectBtn.disabled = true;

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
            // 恢復按鈕狀態
            if (acceptBtn) {
                acceptBtn.disabled = false;
                acceptBtn.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i>';
                if (window.lucide) window.lucide.createIcons();
            }
            if (rejectBtn) rejectBtn.disabled = false;

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
        const acceptBtn = document.getElementById(`accept-btn-${userId}`);
        const rejectBtn = document.getElementById(`reject-btn-${userId}`);

        // 禁用按鈕防止重複點擊
        if (rejectBtn) {
            rejectBtn.disabled = true;
            rejectBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i>';
        }
        if (acceptBtn) acceptBtn.disabled = true;

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
            // 恢復按鈕狀態
            if (rejectBtn) {
                rejectBtn.disabled = false;
                rejectBtn.innerHTML = '<i data-lucide="x" class="w-4 h-4"></i>';
                if (window.lucide) window.lucide.createIcons();
            }
            if (acceptBtn) acceptBtn.disabled = false;

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
        const btn = document.getElementById(`cancel-request-btn-${userId}`);

        // 立即顯示加載狀態
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>取消中...</span>';
            if (window.lucide) window.lucide.createIcons();
        }

        try {
            await FriendsAPI.cancelRequest(userId);
            if (typeof showToast === 'function') {
                showToast('已取消請求', 'info');
            }

            // 更新為「加好友」按鈕
            if (btn) {
                btn.id = `add-friend-btn-${userId}`;
                btn.disabled = false;
                btn.className = 'friend-btn bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 transition border border-primary/20 disabled:opacity-50 disabled:cursor-not-allowed';
                btn.innerHTML = '<i data-lucide="user-plus" class="w-4 h-4"></i><span>加好友</span>';
                btn.onclick = (e) => { e.stopPropagation(); e.preventDefault(); FriendsUI.handleAddFriend(userId); };
                if (window.lucide) window.lucide.createIcons();
            }

        } catch (error) {
            // 恢復按鈕狀態
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="clock" class="w-4 h-4"></i><span>等待中</span>';
                if (window.lucide) window.lucide.createIcons();
            }

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
            // Refresh in-place without reloading
            await loadFriendsTabData();
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
            // Refresh in-place without reloading
            await loadFriendsTabData();
        } catch (error) {
            if (typeof showToast === 'function') {
                showToast(error.message, 'error');
            } else {
                alert(error.message);
            }
        }
    },

    // Toggle between Friends list and Blocked list view
    toggleBlockedView() {
        const friendsView = document.getElementById('friends-view-container');
        const blockedView = document.getElementById('blocked-view-container');
        const toggleBtnSpan = document.querySelector('button[onclick="FriendsUI.toggleBlockedView()"] span');

        if (!friendsView || !blockedView) return;

        if (friendsView.classList.contains('hidden')) {
            // Switch to Friends View
            friendsView.classList.remove('hidden');
            blockedView.classList.add('hidden');
            if (toggleBtnSpan) toggleBtnSpan.textContent = '管理黑名單';
        } else {
            // Switch to Blocked View
            friendsView.classList.add('hidden');
            blockedView.classList.remove('hidden');
            if (toggleBtnSpan) toggleBtnSpan.textContent = '返回好友列表';
        }
    },

    /**
     * 開啟與用戶的聊天（切換到聊天 tab 並開啟對話）
     */
    openChat(userId, username) {
        const isMobile = window.innerWidth < 768;

        if (isMobile) {
            // 移動端：跳轉到全屏聊天頁面
            sessionStorage.setItem('returnToTab', 'friends');
            const targetUrl = `/static/forum/messages.html?with=${userId}&source=friends`;
            if (typeof smoothNavigate === 'function') {
                smoothNavigate(targetUrl);
            } else {
                window.location.href = targetUrl;
            }
        } else {
            // 桌面端：切換到聊天 tab 並打開對話
            if (typeof SocialHub !== 'undefined') {
                SocialHub.switchSubTab('messages');
                SocialHub.openConversation(userId, username);
            }
        }
    }
};

window.FriendsUI = FriendsUI;

// 定義 refreshFriendsUI 函數，讓所有好友操作都能正常更新
function refreshFriendsUI() {
    // 如果在好友 Tab 中，重新載入好友數據
    if (typeof loadFriendsTabData === 'function') {
        loadFriendsTabData();
    }
    // 如果 SocialHub 存在，刷新
    if (typeof SocialHub !== 'undefined' && SocialHub.refresh) {
        SocialHub.refresh();
    }
}
window.refreshFriendsUI = refreshFriendsUI;

// ========================================
// Helper Functions
// ========================================

/**
 * Update badge count and visibility
 */
function updateBadge(elementId, count, hideIfZero = false) {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.textContent = count > 99 ? '99+' : count;

    if (hideIfZero && count === 0) {
        el.classList.add('hidden');
    } else {
        el.classList.remove('hidden');
    }
}

/**
 * Render empty state HTML
 */
function renderEmptyState(message) {
    return `
        <div class="text-center py-6 opacity-50">
            <p class="text-sm text-textMuted">${message}</p>
        </div>
    `;
}

/**
 * Render error state HTML
 */
function renderErrorState(message) {
    return `
        <div class="text-center py-6 text-danger opacity-80">
            <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
            <p class="text-sm">${message}</p>
        </div>
    `;
}

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
    const blockedListEl = document.getElementById('blocked-users-list');

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
                // updateBadge('blocked-count-badge', blockedRes.blocked_users.length); // Tab badge removed
                updateBadge('blocked-count-badge-content', blockedRes.blocked_users.length, true); // Content header badge (if kept) or could be reused
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

            // 重新初始化 Lucide 圖標
            if (window.lucide) lucide.createIcons();

        } catch (e) {
            resultsEl.innerHTML = `<div class="text-center text-danger py-4">${e.message}</div>`;
        }
    }, 500);
}

// ========================================
// SocialHub (Friends Tab Logic)
// ========================================

const SocialHub = {
    container: null,
    pollInterval: null,
    activeSubTab: 'messages', // 'messages' or 'friends'

    /**
     * 初始化 Friends Tab (SocialHub)
     */
    init: async function () {
        console.log('SocialHub initializing...');
        this.container = document.getElementById('friends-tab');

        await this.render();
        this.setupEventListeners();
        this.startPolling();
    },

    // cleanup when leaving tab
    destroy: function () {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.currentChatUserId = null;
        this.currentChatUsername = null;
    },

    /**
     * 渲染完整佈局 (從 Components 獲取模板)
     */
    render: async function () {
        if (!Components.isInjected('friends')) {
            await Components.inject('friends');
        }

        // 確保 Lucide 圖標渲染
        if (window.lucide) lucide.createIcons();

        // 根據 activeSubTab 顯示正確的內容
        this.switchSubTab(this.activeSubTab);

        // 載入初始數據
        if (this.activeSubTab === 'friends') {
            loadFriendsTabData();
        } else {
            this.loadConversations();
        }
    },

    /**
     * 切換子分頁 (聊天 / 好友)
     */
    switchSubTab: function (tabName) {
        this.activeSubTab = tabName;

        // Update Buttons
        document.querySelectorAll('.social-sub-tab').forEach(btn => {
            btn.classList.remove('bg-primary', 'text-background');
            btn.classList.add('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
        });
        const activeBtn = document.getElementById(`social-tab-${tabName}`);
        if (activeBtn) {
            activeBtn.classList.remove('text-textMuted', 'hover:text-textMain', 'hover:bg-white/5');
            activeBtn.classList.add('bg-primary', 'text-background');
        }

        // Show/Hide Content
        document.getElementById('social-content-messages').classList.add('hidden');
        document.getElementById('social-content-friends').classList.add('hidden');
        // document.getElementById('social-content-blocked').classList.add('hidden'); // Tab removed

        const contentEl = document.getElementById(`social-content-${tabName}`);
        if (contentEl) contentEl.classList.remove('hidden');

        // If switching to friends load data if needed
        if (tabName === 'friends') {
            loadFriendsTabData();
        } else {
            // If switching to messages, ensure content is loaded
            if (document.getElementById('social-conv-list').innerHTML.includes('animate-spin')) {
                this.loadConversations();
            }
        }
    },

    /**
     * 加載對話列表
     */
    loadConversations: async function () {
        const listEl = document.getElementById('social-conv-list');
        if (!listEl) return;

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) {
                console.error('[SocialHub] User ID not found (not logged in)');
                listEl.innerHTML = renderEmptyState('請先登入');
                return;
            }

            console.log(`[SocialHub] Loading conversations for user ${myId}...`);
            const res = await fetch(`/api/messages/conversations?limit=20&user_id=${myId}`, {
                headers: FriendsAPI._getAuthHeaders()
            });
            const data = await res.json();
            console.log('[SocialHub] Conversations loaded:', data);

            if (!data.conversations || data.conversations.length === 0) {
                listEl.innerHTML = `
                    <div class="h-full flex flex-col items-center justify-center text-textMuted opacity-50 p-4 text-center">
                        <i data-lucide="message-square-off" class="w-8 h-8 mb-2"></i>
                        <p class="text-sm">尚無對話</p>
                        <button onclick="SocialHub.switchSubTab('friends')" class="mt-4 text-primary text-xs hover:underline">
                            去找朋友聊天
                        </button>
                    </div>
                `;
            } else {
                listEl.innerHTML = data.conversations.map(conv => this.renderConversationItem(conv)).join('');
            }
            if (window.lucide) lucide.createIcons();

        } catch (e) {
            console.error('Failed to load conversations:', e);
            listEl.innerHTML = `<div class="p-4 text-center text-danger text-sm">載入失敗</div>`;
        }
    },

    renderConversationItem: function (conv) {
        const isActive = false; // TODO: Track active conversation
        const activeClass = isActive ? 'bg-white/5 border-l-2 border-primary' : 'hover:bg-white/5 border-l-2 border-transparent';
        const unreadBadge = conv.unread_count > 0 ?
            `<span class="w-5 h-5 rounded-full bg-primary text-background text-[10px] font-bold flex items-center justify-center">${conv.unread_count}</span>` : '';

        // 使用正確的字段名 (API 返回 other_username)
        const username = conv.other_username || conv.username || 'Unknown';
        const lastMessage = conv.last_message || '按此開始聊天';

        return `
            <div id="conv-${conv.id}" class="relative group">
                <div onclick="SocialHub.openConversation('${conv.other_user_id}', '${username}')"
                     class="p-4 border-b border-white/5 cursor-pointer transition ${activeClass}">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-surfaceHighlight flex items-center justify-center text-textMuted font-bold flex-shrink-0 relative">
                            ${username[0].toUpperCase()}
                            ${conv.unread_count > 0 ? '<span class="absolute top-0 right-0 w-2.5 h-2.5 bg-primary rounded-full border-2 border-surface"></span>' : ''}
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex justify-between items-baseline mb-0.5">
                                <h4 class="font-bold text-sm text-textMain truncate pr-2">${username}</h4>
                                <span class="text-[10px] text-textMuted flex-shrink-0">${FriendsUI.formatTime(conv.last_message_at)}</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <p class="text-xs text-textMuted truncate pr-2 opacity-80">${lastMessage}</p>
                                ${unreadBadge}
                            </div>
                        </div>
                    </div>
                </div>
                <!-- 刪除對話按鈕（hover 時顯示，右下位置避免與時間重疊） -->
                <button onclick="event.stopPropagation(); SocialHub.deleteConversation(${conv.id})"
                        class="absolute right-3 bottom-3 p-1.5 text-textMuted/40 hover:text-danger opacity-0 group-hover:opacity-100 transition-all duration-200"
                        title="刪除對話">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        `;
    },

    /**
     * 開啟對話 - 桌面端內嵌，移動端跳轉
     */
    currentChatUserId: null,
    currentChatUsername: null,

    openConversation: function (userId, username) {
        const isMobile = window.innerWidth < 768;

        if (isMobile) {
            // 移動端：跳轉到全屏訊息頁面
            sessionStorage.setItem('returnToTab', 'messages');
            const targetUrl = `/static/forum/messages.html?with=${userId}&source=social`;
            if (typeof smoothNavigate === 'function') {
                smoothNavigate(targetUrl);
            } else {
                window.location.href = targetUrl;
            }
        } else {
            // 桌面端：內嵌顯示
            this.currentChatUserId = userId;
            this.currentChatUsername = username;
            this.showChatContent(userId, username);
            this.loadMessages(userId);
        }
    },

    /**
     * 顯示聊天內容區域
     */
    showChatContent: function (userId, username) {
        // 隱藏空狀態，顯示聊天內容
        const emptyState = document.getElementById('social-chat-empty');
        const chatContent = document.getElementById('social-chat-content');
        if (emptyState) emptyState.classList.add('hidden');
        if (chatContent) chatContent.classList.remove('hidden');

        // 更新頭部
        const avatar = document.getElementById('social-chat-avatar');
        const usernameEl = document.getElementById('social-chat-username');
        const profileLink = document.getElementById('social-chat-profile-link');

        if (avatar) avatar.textContent = (username || 'U')[0].toUpperCase();
        if (usernameEl) usernameEl.textContent = username || userId;
        if (profileLink) profileLink.href = `/static/forum/profile.html?id=${userId}`;

        // 更新對話列表的選中狀態
        document.querySelectorAll('#social-conv-list > div').forEach(item => {
            item.classList.remove('bg-primary/10', 'border-l-2', 'border-primary');
        });

        if (window.lucide) lucide.createIcons();
    },

    /**
     * 載入訊息
     */
    loadMessages: async function (userId) {
        const container = document.getElementById('social-messages-container');
        if (!container) return;

        container.innerHTML = `<div class="flex justify-center py-8"><i data-lucide="loader-2" class="w-6 h-6 animate-spin text-primary"></i></div>`;
        if (window.lucide) lucide.createIcons();

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) return;

            const res = await fetch(`/api/messages/with/${userId}?user_id=${myId}&limit=50`, {
                headers: FriendsAPI._getAuthHeaders()
            });
            const data = await res.json();

            if (!data.success) throw new Error(data.error || '載入失敗');

            // Set current conversation ID for deletion checks
            if (data.conversation?.id) {
                this.currentConversationId = data.conversation.id;
            }

            if (!data.messages || data.messages.length === 0) {
                container.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-full text-textMuted opacity-50">
                        <i data-lucide="message-circle" class="w-10 h-10 mb-3"></i>
                        <p class="text-sm">尚無訊息，打個招呼吧！</p>
                    </div>
                `;
            } else {
                container.innerHTML = data.messages.map(msg => this.renderMessageBubble(msg)).join('');
                container.scrollTop = container.scrollHeight;
            }

            // 標記已讀（後台執行）
            if (data.conversation?.id) {
                fetch(`/api/messages/read?user_id=${myId}`, {
                    method: 'POST',
                    headers: FriendsAPI._getAuthHeaders(),
                    body: JSON.stringify({ conversation_id: data.conversation.id })
                }).catch(() => { });
            }

        } catch (e) {
            console.error('載入訊息失敗:', e);
            container.innerHTML = `<div class="text-center text-danger py-4 text-sm">${e.message || '載入失敗'}</div>`;
        }

        if (window.lucide) lucide.createIcons();
    },

    /**
     * 渲染訊息氣泡
     */
    renderMessageBubble: function (msg) {
        const myId = FriendsAPI._getUserId();
        const isMe = msg.from_user_id === myId;
        const isRecalled = msg.message_type === 'recalled';
        const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // 如果是已收回的訊息
        if (isRecalled) {
            const recalledText = isMe ? '你已收回訊息' : '對方已收回訊息';
            return `
                <div id="social-msg-${msg.id}" class="flex ${isMe ? 'justify-end' : 'justify-start'} mb-3">
                    <div class="max-w-[80%]">
                        <div class="p-2 rounded-2xl bg-white/5 border border-white/10">
                            <span class="text-textMuted/60 text-sm italic">${recalledText}</span>
                        </div>
                        <div class="text-[10px] text-textMuted/40 mt-0.5 ${isMe ? 'text-right' : 'text-left'} px-1">${time}</div>
                    </div>
                </div>
            `;
        }

        const alignClass = isMe ? 'justify-end' : 'justify-start';
        const bubbleClass = isMe
            ? 'bg-primary text-background rounded-br-sm'
            : 'bg-surfaceHighlight text-textMain rounded-bl-sm border border-white/5';

        // 訊息選項按鈕（hover 時顯示）
        // 自己的訊息：收回（對方也看不到）+ 刪除（只對自己隱藏）
        // 對方的訊息：只有刪除（只對自己隱藏）
        const msgActions = isMe ? `
            <div class="absolute ${isMe ? '-left-16' : '-right-16'} top-1/2 -translate-y-1/2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                <button onclick="event.stopPropagation(); SocialHub.recallMessage(${msg.id})"
                        class="p-1 text-textMuted/50 hover:text-warning transition" title="收回訊息">
                    <i data-lucide="undo-2" class="w-3.5 h-3.5"></i>
                </button>
                <button onclick="event.stopPropagation(); SocialHub.hideMessage(${msg.id})"
                        class="p-1 text-textMuted/50 hover:text-danger transition" title="刪除（只對自己）">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        ` : `
            <div class="absolute ${isMe ? '-left-8' : '-right-8'} top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition">
                <button onclick="event.stopPropagation(); SocialHub.hideMessage(${msg.id})"
                        class="p-1 text-textMuted/50 hover:text-danger transition" title="刪除（只對自己）">
                    <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        `;

        return `
            <div id="social-msg-${msg.id}" class="flex ${alignClass} mb-3 group">
                <div class="max-w-[80%] relative">
                    ${msgActions}
                    <div class="p-2.5 rounded-2xl ${bubbleClass} shadow-sm">
                        <p class="text-sm leading-relaxed whitespace-pre-wrap break-words">${this.escapeHtml(msg.content)}</p>
                    </div>
                    <div class="text-[10px] text-textMuted/50 mt-0.5 ${isMe ? 'text-right' : 'text-left'} px-1">${time}</div>
                </div>
            </div>
        `;
    },

    /**
     * 收回訊息
     */
    recallMessage: async function (messageId) {
        if (!confirm('確定要收回這條訊息嗎？對方會看到「對方已收回訊息」')) return;

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) return;

            const res = await fetch(`/api/messages/${messageId}?user_id=${myId}`, {
                method: 'DELETE',
                headers: FriendsAPI._getAuthHeaders()
            });

            const data = await res.json();

            if (res.ok && data.success) {
                // 更新 DOM：將訊息替換為「已收回」樣式
                const msgEl = document.getElementById(`social-msg-${messageId}`);
                if (msgEl) {
                    const time = msgEl.querySelector('.text-\\[10px\\]')?.textContent || '';
                    msgEl.outerHTML = `
                        <div id="social-msg-${messageId}" class="flex justify-end mb-3">
                            <div class="max-w-[80%]">
                                <div class="p-2 rounded-2xl bg-white/5 border border-white/10">
                                    <span class="text-textMuted/60 text-sm italic">你已收回訊息</span>
                                </div>
                                <div class="text-[10px] text-textMuted/40 mt-0.5 text-right px-1">${time}</div>
                            </div>
                        </div>
                    `;
                }
                // 更新對話列表
                this.loadConversations();
            } else {
                throw new Error(data.error || data.detail || '收回失敗');
            }
        } catch (e) {
            console.error('收回訊息失敗:', e);
            if (typeof showToast === 'function') {
                showToast(e.message, 'error');
            } else {
                alert(e.message || '收回失敗');
            }
        }
    },

    /**
     * 隱藏訊息（只對自己隱藏）
     */
    hideMessage: async function (messageId) {
        if (!confirm('確定要刪除這條訊息嗎？（只對你隱藏，對方仍可見）')) return;

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) return;

            const res = await fetch(`/api/messages/${messageId}/hide?user_id=${myId}`, {
                method: 'POST',
                headers: FriendsAPI._getAuthHeaders()
            });

            const data = await res.json();

            if (res.ok && data.success) {
                // 從 DOM 中移除訊息
                const msgEl = document.getElementById(`social-msg-${messageId}`);
                if (msgEl) {
                    msgEl.remove();
                }
                // 更新對話列表
                this.loadConversations();
            } else {
                throw new Error(data.error || data.detail || '刪除失敗');
            }
        } catch (e) {
            console.error('隱藏訊息失敗:', e);
            if (typeof showToast === 'function') {
                showToast(e.message, 'error');
            } else {
                alert(e.message || '刪除失敗');
            }
        }
    },

    /**
     * 刪除對話（隱藏整段對話）
     */
    deleteConversation: async function (conversationId) {
        // 使用平台風格的確認對話框
        const confirmed = typeof showConfirm === 'function'
            ? await showConfirm({
                title: '刪除對話',
                message: '確定要刪除這段對話嗎？所有訊息將從列表中移除。\n\n之後如需再聊，會是乾淨的聊天室。',
                type: 'warning',
                confirmText: '刪除',
                cancelText: '取消'
            })
            : confirm('確定要刪除這段對話嗎？所有訊息將從列表中移除。\n（之後如需再聊，會是乾淨的聊天室）');

        if (!confirmed) return;

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) return;

            const res = await fetch(`/api/conversations/${conversationId}?user_id=${myId}`, {
                method: 'DELETE',
                headers: FriendsAPI._getAuthHeaders()
            });

            const data = await res.json();

            if (res.ok && data.success) {
                // 從 DOM 中移除對話
                const convEl = document.getElementById(`conv-${conversationId}`);
                if (convEl) {
                    convEl.remove();
                }

                // 如果刪除的是當前打開的對話，清空聊天區域和訊息內容
                if (this.currentChatUserId) {
                    const currentConvId = this.currentConversationId;
                    if (currentConvId === conversationId) {
                        // 隱藏聊天區域
                        const chatContent = document.getElementById('social-chat-content');
                        const emptyState = document.getElementById('social-chat-empty');
                        if (chatContent) chatContent.classList.add('hidden');
                        if (emptyState) emptyState.classList.remove('hidden');

                        // 清空訊息容器內容（重要！避免用戶誤以為訊息還在）
                        const messagesContainer = document.getElementById('social-messages-container');
                        if (messagesContainer) {
                            messagesContainer.innerHTML = '';
                        }

                        // 重置狀態
                        this.currentChatUserId = null;
                        this.currentChatUsername = null;
                        this.currentConversationId = null;

                        // Force refresh icons in empty state
                        if (window.lucide) lucide.createIcons();
                    }
                }

                // 檢查列表是否為空
                const listEl = document.getElementById('social-conv-list');
                if (listEl && listEl.children.length === 0) {
                    listEl.innerHTML = `
                        <div class="h-full flex flex-col items-center justify-center text-textMuted opacity-50 p-4 text-center">
                            <i data-lucide="message-square-off" class="w-8 h-8 mb-2"></i>
                            <p class="text-sm">尚無對話</p>
                            <button onclick="SocialHub.switchSubTab('friends')" class="mt-4 text-primary text-xs hover:underline">
                                去找朋友聊天
                            </button>
                        </div>
                    `;
                    if (window.lucide) lucide.createIcons();
                }

                if (typeof showToast === 'function') {
                    showToast('對話已刪除', 'success');
                }
            } else {
                throw new Error(data.error || data.detail || '刪除失敗');
            }
        } catch (e) {
            console.error('刪除對話失敗:', e);
            if (typeof showToast === 'function') {
                showToast(e.message, 'error');
            } else {
                alert(e.message || '刪除失敗');
            }
        }
    },

    /**
     * HTML 轉義
     */
    escapeHtml: function (text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 發送訊息
     */
    sendMessage: async function (e) {
        if (e) e.preventDefault();
        if (!this.currentChatUserId) return;

        const input = document.getElementById('social-msg-input');
        const content = input?.value?.trim();
        if (!content) return;

        const btn = document.getElementById('social-send-btn');
        if (btn) {
            btn.disabled = true;
            btn.classList.add('opacity-50');
        }

        try {
            const myId = FriendsAPI._getUserId();
            if (!myId) throw new Error('請先登入');

            const res = await fetch(`/api/messages/send?user_id=${myId}`, {
                method: 'POST',
                headers: FriendsAPI._getAuthHeaders(),
                body: JSON.stringify({
                    to_user_id: this.currentChatUserId,
                    content: content
                })
            });

            const data = await res.json();

            if (res.ok && data.success) {
                input.value = '';
                this.autoResizeInput(input);
                this.updateCharCount();

                // 添加訊息到畫面
                const container = document.getElementById('social-messages-container');
                if (container && data.message) {
                    // 移除空狀態
                    const emptyState = container.querySelector('.flex.flex-col.items-center');
                    if (emptyState) container.innerHTML = '';

                    container.insertAdjacentHTML('beforeend', this.renderMessageBubble(data.message));
                    container.scrollTop = container.scrollHeight;
                }

                // 異步更新對話列表（不等待，避免阻塞 UI）
                // 訊息已經立即顯示，列表在背景更新
                this.loadConversations().catch(err => {
                    console.warn('Background conversation list update failed:', err);
                });
            } else {
                throw new Error(data.detail || '發送失敗');
            }
        } catch (err) {
            console.error('發送失敗:', err);
            if (typeof showToast === 'function') {
                showToast(err.message, 'error');
            } else {
                alert(err.message || '發送失敗');
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('opacity-50');
            }
            this.updateCharCount();
            input?.focus();
        }
    },

    /**
     * 輸入框按鍵處理
     */
    handleInputKeydown: function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage(e);
        }
    },

    /**
     * 自動調整輸入框高度
     */
    autoResizeInput: function (textarea) {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    },

    /**
     * 更新字數統計和按鈕狀態
     */
    updateCharCount: function () {
        const input = document.getElementById('social-msg-input');
        const countSpan = document.getElementById('social-char-count');
        const btn = document.getElementById('social-send-btn');

        if (!input) return;

        const len = input.value.length;
        const hasContent = input.value.trim().length > 0;

        if (countSpan) countSpan.textContent = `${len}/500`;

        if (btn) {
            btn.disabled = !hasContent;
            if (hasContent) {
                btn.classList.remove('opacity-50');
            } else {
                btn.classList.add('opacity-50');
            }
        }
    },

    setupEventListeners: function () {
        // 視窗大小變化時檢查
        window.addEventListener('resize', () => {
            // 如果切換到移動端且有打開的對話，可以考慮跳轉
        });
    },

    refresh: function () {
        if (this.activeSubTab === 'friends') {
            loadFriendsTabData();
        } else {
            this.loadConversations();
            // 如果有打開的對話，也刷新訊息
            if (this.currentChatUserId) {
                this.loadMessages(this.currentChatUserId);
            }
        }
    },

    startPolling: function () {
        // 移除自動輪詢 - 不需要定時刷新，訊息會在發送時即時更新
        // 如果未來需要即時通知，應該使用 WebSocket 而非輪詢
    }
};

window.SocialHub = SocialHub;
