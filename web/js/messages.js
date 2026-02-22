/**
 * messages.js - 私訊功能前端模組
 * v1.0
 */

// ============================================================================
// MessagesAPI - API 客戶端
// ============================================================================

const MessagesAPI = {
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
     * 取得 Access Token
     */
    _getToken() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            const user = AuthManager.currentUser;
            const userId = user.user_id || user.uid;
            return user.accessToken || user.piAccessToken || userId;
        }
        return null;
    },

    /**
     * 取得對話列表
     */
    async getConversations(limit = 50, offset = 0) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const token = this._getToken();
        const res = await fetch(`/api/messages/conversations?user_id=${userId}&limit=${limit}&offset=${offset}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得對話列表失敗');
        }
        return await res.json();
    },

    /**
     * 取得對話訊息
     */
    async getMessages(conversationId, limit = 50, beforeId = null) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        let url = `/api/messages/conversation/${conversationId}?user_id=${userId}&limit=${limit}`;
        if (beforeId) url += `&before_id=${beforeId}`;

        const token = this._getToken();
        const res = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得訊息失敗');
        }
        return await res.json();
    },

    /**
     * 取得與特定用戶的對話
     */
    async getConversationWith(otherUserId, limit = 50) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const token = this._getToken();
        const res = await fetch(`/api/messages/with/${otherUserId}?user_id=${userId}&limit=${limit}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '取得對話失敗');
        }
        return await res.json();
    },

    /**
     * 發送訊息
     */
    async sendMessage(toUserId, content) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/messages/send?user_id=${userId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._getToken()}`
            },
            body: JSON.stringify({ to_user_id: toUserId, content })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '發送訊息失敗');
        }
        return await res.json();
    },

    /**
     * 標記對話為已讀
     */
    async markAsRead(conversationId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/messages/read?user_id=${userId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._getToken()}`
            },
            body: JSON.stringify({ conversation_id: conversationId })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '標記已讀失敗');
        }
        return await res.json();
    },

    /**
     * 發送打招呼（Pro 專屬）
     */
    async sendGreeting(toUserId, content) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const res = await fetch(`/api/messages/greeting?user_id=${userId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._getToken()}`
            },
            body: JSON.stringify({ to_user_id: toUserId, content })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '發送打招呼失敗');
        }
        return await res.json();
    },

    /**
     * 搜尋訊息（Pro 專屬）
     */
    async searchMessages(query, limit = 50) {
        const userId = this._getUserId();
        if (!userId) throw new Error('請先登入');

        const token = this._getToken();
        const res = await fetch(`/api/messages/search?user_id=${userId}&q=${encodeURIComponent(query)}&limit=${limit}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || '搜尋訊息失敗');
        }
        return await res.json();
    },

    /**
     * 取得未讀數量
     */
    async getUnreadCount() {
        const userId = this._getUserId();
        if (!userId) return { unread_count: 0 };

        try {
            const token = this._getToken();
            const res = await fetch(`/api/messages/unread-count?user_id=${userId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) return { unread_count: 0 };
            return await res.json();
        } catch {
            return { unread_count: 0 };
        }
    },

    /**
     * 取得訊息限制狀態
     */
    async getLimits() {
        const userId = this._getUserId();
        if (!userId) return null;

        try {
            const token = this._getToken();
            const res = await fetch(`/api/messages/limits?user_id=${userId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) return null;
            return await res.json();
        } catch {
            return null;
        }
    }
};

window.MessagesAPI = MessagesAPI;


// ============================================================================
// MessagesWebSocket - WebSocket 連接管理
// ============================================================================

const MessagesWebSocket = {
    ws: null,
    connected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 3000,
    heartbeatInterval: null,
    onMessageCallback: null,
    onReadReceiptCallback: null,
    onConnectCallback: null,
    onDisconnectCallback: null,

    /**
     * 連接 WebSocket
     */
    connect() {
        const userId = MessagesAPI._getUserId();
        if (!userId) {
            console.log('MessagesWebSocket: 未登入，不連接');
            return;
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('MessagesWebSocket: 已連接');
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/messages`;

        console.log('MessagesWebSocket: 連接中...', wsUrl);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('MessagesWebSocket: 連接成功，發送認證...');
            // 發送認證
            this.ws.send(JSON.stringify({
                action: 'auth',
                user_id: userId,
                token: MessagesAPI._getToken()
            }));
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._handleMessage(data);
            } catch (e) {
                console.error('MessagesWebSocket: 解析訊息失敗', e);
            }
        };

        this.ws.onclose = () => {
            console.log('MessagesWebSocket: 連接關閉');
            this.connected = false;
            this._stopHeartbeat();

            if (this.onDisconnectCallback) {
                this.onDisconnectCallback();
            }

            // 自動重連
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`MessagesWebSocket: ${this.reconnectDelay}ms 後重連 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                setTimeout(() => this.connect(), this.reconnectDelay);
            }
        };

        this.ws.onerror = (error) => {
            console.error('MessagesWebSocket: 錯誤', error);
        };
    },

    /**
     * 斷開連接
     */
    disconnect() {
        this._stopHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
        this.reconnectAttempts = this.maxReconnectAttempts; // 防止自動重連
    },

    /**
     * 處理收到的訊息
     */
    _handleMessage(data) {
        switch (data.type) {
            case 'authenticated':
                console.log('MessagesWebSocket: 認證成功', data);
                this.connected = true;
                this.reconnectAttempts = 0;
                this._startHeartbeat();

                if (this.onConnectCallback) {
                    this.onConnectCallback(data);
                }
                break;

            case 'new_message':
            case 'message_sent':
                console.log('MessagesWebSocket: 新訊息', data.message);
                if (this.onMessageCallback) {
                    this.onMessageCallback(data.message, data.type === 'message_sent');
                }
                break;

            case 'read_receipt':
                console.log('MessagesWebSocket: 已讀回執', data);
                if (this.onReadReceiptCallback) {
                    this.onReadReceiptCallback(data.conversation_id, data.read_by);
                }
                break;

            case 'pong':
                // 心跳回應
                break;

            case 'error':
                console.error('MessagesWebSocket: 伺服器錯誤', data.message);
                break;

            default:
                console.log('MessagesWebSocket: 未知訊息類型', data);
        }
    },

    /**
     * 開始心跳
     */
    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ action: 'ping' }));
            }
        }, 30000);
    },

    /**
     * 停止心跳
     */
    _stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    },

    /**
     * 設置新訊息回調
     */
    onMessage(callback) {
        this.onMessageCallback = callback;
    },

    /**
     * 設置已讀回執回調
     */
    onReadReceipt(callback) {
        this.onReadReceiptCallback = callback;
    },

    /**
     * 設置連接成功回調
     */
    onConnect(callback) {
        this.onConnectCallback = callback;
    },

    /**
     * 設置斷開連接回調
     */
    onDisconnect(callback) {
        this.onDisconnectCallback = callback;
    }
};

window.MessagesWebSocket = MessagesWebSocket;


// ============================================================================
// MessagesUI - UI 渲染工具
// ============================================================================

const MessagesUI = {
    currentUserId: null,

    /**
     * 初始化
     */
    init() {
        this.currentUserId = MessagesAPI._getUserId();
    },

    /**
     * 格式化時間（訊息氣泡用 - 顯示明確日期時間）
     */
    formatTime(dateString) {
        if (!dateString) return '';
        // 處理沒有時區的日期字串
        if (!dateString.includes('Z') && !dateString.includes('+')) {
            dateString += 'Z';
        }
        const date = new Date(dateString);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const messageDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

        // 同一天：只顯示時間
        if (messageDay.getTime() === today.getTime()) {
            return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
        }

        // 同一年：顯示 MM/DD HH:mm
        if (date.getFullYear() === now.getFullYear()) {
            return `${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}`;
        }

        // 不同年：顯示 YYYY/MM/DD HH:mm
        return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}`;
    },

    /**
     * 格式化完整時間
     */
    formatFullTime(dateString) {
        if (!dateString) return '';
        if (!dateString.includes('Z') && !dateString.includes('+')) {
            dateString += 'Z';
        }
        const date = new Date(dateString);
        return date.toLocaleString('zh-TW', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    /**
     * 取得會員徽章
     */
    getMembershipBadge(tier) {
        if (tier === 'pro') {
            return '<span class="px-1.5 py-0.5 text-xs font-bold bg-gradient-to-r from-yellow-500 to-orange-500 text-black rounded">PRO</span>';
        }
        return '';
    },

    /**
     * 取得用戶首字母
     */
    getInitial(username) {
        return (username || 'U')[0].toUpperCase();
    },

    /**
     * 渲染對話列表項目
     */
    renderConversationItem(conv, isActive = false) {
        const initial = this.getInitial(conv.other_username);
        const badge = this.getMembershipBadge(conv.other_membership_tier);
        const hasUnread = conv.unread_count > 0;

        // 未讀狀態樣式
        const unreadTextClass = hasUnread ? 'font-bold text-textMain' : 'text-textMuted';
        const unreadBgClass = hasUnread ? 'bg-primary/5' : '';
        const unreadAvatarClass = hasUnread ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : '';
        const unreadIndicator = hasUnread ? '<div class="absolute left-0 top-0 bottom-0 w-1 bg-primary rounded-r"></div>' : '';

        // 活動狀態樣式
        const activeClass = isActive ? 'bg-primary/10 border-primary/30' : 'hover:bg-white/5';
        const timeStr = this.formatTime(conv.last_message_at);

        // 截斷訊息預覽
        let preview = conv.last_message || '開始對話';
        if (preview.length > 30) {
            preview = preview.substring(0, 30) + '...';
        }

        return `
            <div class="conversation-item cursor-pointer p-3 border-b border-white/5 ${activeClass} ${unreadBgClass} transition relative"
                 data-conversation-id="${conv.id}"
                 data-other-user-id="${conv.other_user_id}"
                 onclick="MessagesPage.selectConversation(${conv.id}, '${conv.other_user_id}', '${conv.other_username}')">
                ${unreadIndicator}
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold flex-shrink-0 ${unreadAvatarClass}">
                        ${initial}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between gap-2">
                            <div class="flex items-center gap-2 min-w-0">
                                <span class="${hasUnread ? 'font-extrabold' : 'font-bold'} text-textMain truncate">${conv.other_username}</span>
                                ${badge}
                            </div>
                            <span class="text-xs ${hasUnread ? 'text-primary font-bold' : 'text-textMuted'} flex-shrink-0">${timeStr}</span>
                        </div>
                        <div class="flex items-center justify-between gap-2 mt-0.5">
                            <p class="text-sm ${unreadTextClass} truncate">${preview}</p>
                            ${hasUnread ? `
                                <span class="flex-shrink-0 min-w-5 h-5 px-1.5 rounded-full bg-primary text-background text-xs font-bold flex items-center justify-center animate-pulse">
                                    ${conv.unread_count > 99 ? '99+' : conv.unread_count}
                                </span>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * 渲染訊息氣泡
     */
    renderMessageBubble(msg, isPro = false) {
        const isMine = msg.from_user_id === this.currentUserId;
        const timeStr = this.formatTime(msg.created_at);
        const isRecalled = msg.message_type === 'recalled';

        // 如果是已收回的訊息
        if (isRecalled) {
            const recalledText = isMine ? '你已收回訊息' : '對方已收回訊息';
            return `
                <div id="msg-${msg.id}" class="flex ${isMine ? 'justify-end' : 'justify-start'} mb-4" data-message-id="${msg.id}">
                    <div class="flex flex-col ${isMine ? 'items-end' : 'items-start'}">
                        <div class="px-4 py-2 rounded-2xl bg-white/5 border border-white/10">
                            <span class="text-textMuted/60 text-sm italic">${recalledText}</span>
                        </div>
                        <div class="text-xs text-textMuted/50 mt-1 px-1">${timeStr}</div>
                    </div>
                </div>
            `;
        }

        // 已讀狀態（僅 Pro 可見）
        let readStatus = '';
        if (isMine && isPro) {
            readStatus = msg.is_read
                ? `<span class="text-xs text-success">已讀</span>`
                : `<span class="text-xs text-textMuted">已送達</span>`;
        }

        // 打招呼訊息的標記
        const greetingBadge = msg.message_type === 'greeting'
            ? '<span class="text-xs text-accent mr-1">👋</span>'
            : '';

        // 收回按鈕（只有自己的訊息可以收回）
        const recallBtn = isMine ? `
            <button onclick="event.stopPropagation(); MessagesPage.recallMessage(${msg.id}, this)"
                    class="p-1 text-textMuted/30 hover:text-warning opacity-0 group-hover:opacity-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    title="收回訊息">
                <i data-lucide="undo-2" class="w-3.5 h-3.5"></i>
            </button>
        ` : '';

        if (isMine) {
            // 自己的訊息 - 靠右對齊
            return `
                <div id="msg-${msg.id}" class="flex justify-end mb-4 group" data-message-id="${msg.id}">
                    <div class="flex items-start gap-1">
                        ${recallBtn}
                        <div class="flex flex-col items-end" style="max-width: 70%;">
                            <div class="bg-primary text-background px-4 py-2.5 rounded-2xl rounded-br-md">
                                ${greetingBadge}<span class="whitespace-pre-wrap break-words">${this._escapeHtml(msg.content)}</span>
                            </div>
                            <div class="flex items-center gap-2 mt-1 px-1">
                                ${readStatus}
                                <span class="text-xs text-textMuted">${timeStr}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            // 對方的訊息 - 靠左對齊
            return `
                <div id="msg-${msg.id}" class="flex justify-start mb-4" data-message-id="${msg.id}">
                    <div class="flex flex-col items-start" style="max-width: 70%;">
                        <div class="bg-surface border border-white/10 text-textMain px-4 py-2.5 rounded-2xl rounded-bl-md">
                            ${greetingBadge}<span class="whitespace-pre-wrap break-words">${this._escapeHtml(msg.content)}</span>
                        </div>
                        <div class="text-xs text-textMuted mt-1 px-1">${timeStr}</div>
                    </div>
                </div>
            `;
        }
    },

    /**
     * 渲染空狀態
     */
    renderEmptyState(message, icon = 'message-square') {
        return `
            <div class="flex flex-col items-center justify-center h-full text-textMuted p-8">
                <i data-lucide="${icon}" class="w-16 h-16 opacity-30 mb-4"></i>
                <p class="text-center">${message}</p>
            </div>
        `;
    },

    /**
     * 渲染載入狀態
     */
    renderLoadingState() {
        return `
            <div class="flex items-center justify-center h-full">
                <div class="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full"></div>
            </div>
        `;
    },

    /**
     * 渲染新訊息分隔線
     */
    renderNewMessagesSeparator() {
        return `
            <div class="new-messages-separator flex items-center gap-4 my-4 px-4">
                <div class="flex-1 h-px bg-primary/30"></div>
                <span class="text-xs font-bold text-primary uppercase tracking-wider flex items-center gap-1">
                    <i data-lucide="arrow-down" class="w-3 h-3"></i>
                    新訊息
                </span>
                <div class="flex-1 h-px bg-primary/30"></div>
            </div>
        `;
    },

    /**
     * HTML 轉義
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

window.MessagesUI = MessagesUI;


// ============================================================================
// 全局未讀數量更新
// ============================================================================

/**
 * 更新未讀訊息紅點
 */
async function updateUnreadBadge() {
    try {
        const result = await MessagesAPI.getUnreadCount();
        const count = result.unread_count || 0;

        // 更新所有未讀徽章
        const badges = document.querySelectorAll('.messages-unread-badge');
        badges.forEach(badge => {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        });

        // 更新標題
        if (count > 0) {
            document.title = `(${count}) Pi Crypto Forum`;
        }
    } catch (e) {
        console.error('更新未讀數量失敗:', e);
    }
}

window.updateUnreadBadge = updateUnreadBadge;

// 移除定期輪詢 - 未讀數量應該透過 WebSocket 即時更新
// WebSocket 收到 new_message 時會觸發 updateUnreadBadge()
