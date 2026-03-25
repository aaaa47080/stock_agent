// ========================================
// notification-service.js - 通知服務
// ========================================

const NotificationService = {
    // 通知列表
    notifications: [],

    // 未读计数
    unreadCount: 0,

    // WebSocket 连接
    ws: null,

    // 重连定时器
    reconnectTimer: null,

    // 重连尝试次数（防止无限重连）
    reconnectAttempts: 0,
    MAX_RECONNECT_ATTEMPTS: 5,

    // 是否已登录
    isLoggedIn: false,

    // 避免重複初始化 / 重複 WebSocket
    _initializedUserId: null,

    // 模拟数据（Phase 1 使用，作为后备）
    mockNotifications: [
        {
            id: 'notif_001',
            type: 'friend_request',
            title: '好友請求',
            body: 'Alice 想加你為好友',
            data: { from_user_id: 'user_123', from_username: 'Alice' },
            is_read: false,
            created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
        },
        {
            id: 'notif_002',
            type: 'system_update',
            title: '系統更新',
            body: '有新版本可用，建議更新以獲得最佳體驗',
            data: { version: '2.1.0' },
            is_read: false,
            created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        },
        {
            id: 'notif_003',
            type: 'message',
            title: '新消息',
            body: 'Bob: 你好，最近怎麼樣？',
            data: { from_user_id: 'user_456', from_username: 'Bob', conversation_id: 'conv_001' },
            is_read: true,
            created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        },
        {
            id: 'notif_004',
            type: 'post_interaction',
            title: '帖子互動',
            body: 'Carol 贊了你的文章「市場分析」',
            data: { post_id: 'post_001', interaction_type: 'like', from_username: 'Carol' },
            is_read: true,
            created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        },
    ],

    /**
     * 初始化通知服务
     */
    async init() {
        const { userId } = this._getCredentials();

        // Same logged-in user with an active socket does not need full re-init.
        if (
            this.isLoggedIn &&
            userId &&
            this._initializedUserId === userId &&
            this.ws &&
            (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }

        // 檢查是否登录
        this.isLoggedIn = window.AuthManager && window.AuthManager.isLoggedIn();

        if (this.isLoggedIn) {
            this._initializedUserId = userId;
            // 已登录：从 API 获取真实数据
            await this.fetchNotifications();

            // 连接 WebSocket
            this.connectWebSocket();
        } else {
            this._initializedUserId = null;
            this.disconnectWebSocket();
            // 未登录：顯示空列表
            this.notifications = [];
            this.unreadCount = 0;
            this.notifyUpdate();
            console.log('[NotificationService] Not logged in, empty notifications');
        }
    },

    /**
     * 獲取用戶憑證
     */
    _getCredentials() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            const userId = AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
            const token = AuthManager.currentUser.accessToken || AuthManager.currentUser.token;

            return { userId, token };
        }
        return { userId: null, token: null };
    },

    /**
     * 檢查 token 是否過期，     */
    _isTokenExpired() {
        if (typeof AuthManager !== 'undefined' && AuthManager.shouldDeferExpiredSessionCleanup?.()) {
            return false;
        }

        const { userId, token } = this._getCredentials();

        if (!userId || !token) {
            return true;
        }

        // 檢查 AuthManager 是否有過期檢查方法
        if (typeof AuthManager.isTokenExpired === 'function') {
            return AuthManager.isTokenExpired();
        }

        // 備用檢查：檢查 accessTokenExpiry
        const expiry = AuthManager.currentUser?.accessTokenExpiry;
        if (!expiry) {
            return true; // 沒有過期時間，假設已過期
        }

        return Date.now() > expiry;
    },

    /**
     * 从 API 获取通知
     */
    async fetchNotifications() {
        try {
            if (typeof AuthManager !== 'undefined' && AuthManager.shouldDeferExpiredSessionCleanup?.()) {
                return;
            }

            // 檢查 token 是否過期
            if (this._isTokenExpired()) {
                console.warn('[NotificationService] Token expired, clearing...');
                if (
                    typeof AuthManager !== 'undefined' &&
                    typeof AuthManager.clearExpiredToken === 'function'
                ) {
                    AuthManager.clearExpiredToken();
                }
                return;
            }

            const { userId, token } = this._getCredentials();

            if (!userId || !token) {
                if (window.DEBUG_MODE)
                    console.log('[NotificationService] No credentials, empty notifications');
                this.notifications = [];
                this.unreadCount = 0;
                this.notifyUpdate();
                return;
            }

            const data = await AppAPI.get(`/api/notifications?user_id=${userId}&limit=50`);
            this.notifications = data.notifications || [];
            this.unreadCount = data.unread_count || 0;
            this.notifyUpdate();
            console.log(
                '[NotificationService] Loaded from API:',
                this.notifications.length,
                'notifications'
            );
        } catch (error) {
            // 401: token may be expired — clear it
            if (error.status === 401) {
                console.warn('[NotificationService] 401 Unauthorized, token may be expired');
                if (
                    typeof AuthManager !== 'undefined' &&
                    typeof AuthManager.clearExpiredToken === 'function'
                ) {
                    AuthManager.clearExpiredToken();
                }
            } else {
                console.error('[NotificationService] Fetch error:', error);
            }
            this.notifications = [];
            this.unreadCount = 0;
            this.notifyUpdate();
        }
    },

    /**
     * 获取所有通知
     */
    getNotifications() {
        return this.notifications;
    },

    /**
     * 获取未读数量
     */
    getUnreadCount() {
        return this.unreadCount;
    },

    /**
     * 更新未读计数
     */
    updateUnreadCount() {
        this.unreadCount = this.notifications.filter((n) => !n.is_read).length;
    },

    /**
     * 标记通知为已读
     */
    async markAsRead(notificationId) {
        const notification = this.notifications.find((n) => n.id === notificationId);
        if (notification && !notification.is_read) {
            notification.is_read = true;
            this.updateUnreadCount();
            this.notifyUpdate();

            // 同步到服务器
            if (this.isLoggedIn) {
                try {
                    const { userId } = this._getCredentials();
                    if (userId) {
                        await AppAPI.post(
                            `/api/notifications/${notificationId}/read?user_id=${userId}`,
                        );
                    }
                } catch (error) {
                    console.error('[NotificationService] Mark as read error:', error);
                }
            }
        }
    },

    /**
     * 标记所有通知为已读
     */
    async markAllAsRead() {
        this.notifications.forEach((n) => (n.is_read = true));
        this.updateUnreadCount();
        this.notifyUpdate();

        // 同步到服务器
        if (this.isLoggedIn) {
            try {
                const { userId } = this._getCredentials();
                if (userId) {
                    await AppAPI.post(`/api/notifications/read-all?user_id=${userId}`);
                }
            } catch (error) {
                console.error('[NotificationService] Mark all read error:', error);
            }
        }
    },

    /**
     * 添加新通知
     */
    addNotification(notification) {
        this.notifications.unshift(notification);
        this.updateUnreadCount();
        this.notifyUpdate();

        // 显示 toast
        if (typeof showToast === 'function') {
            showToast(notification.body, 'info');
        }
    },

    /**
     * 通知 UI 更新
     */
    notifyUpdate() {
        window.dispatchEvent(
            new CustomEvent('notificationsUpdated', {
                detail: {
                    notifications: this.notifications,
                    unreadCount: this.unreadCount,
                },
            }),
        );
    },

    /**
     * 连接 WebSocket (Phase 2)
     * NOTE: WebSocket connections are NOT converted to AppAPI (different protocol)
     */
    connectWebSocket() {
        const { userId, token } = this._getCredentials();

        if (!userId || !token) {
            if (window.DEBUG_MODE)
                console.log('[NotificationService] No credentials for WebSocket');
            return;
        }

        if (
            this.ws &&
            (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
        ) {
            return;
        }

        this.disconnectWebSocket(false);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('[NotificationService] WebSocket connected');
                // 重置重连计数器
                this.reconnectAttempts = 0;
                // 发送认证信息 (backend requires token for auth)
                this.ws.send(JSON.stringify({ type: 'auth', user_id: userId, token }));
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'notification') {
                    this.addNotification(data.data);
                }
            };

            this.ws.onclose = () => {
                console.log('[NotificationService] WebSocket disconnected');
                this.scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[NotificationService] WebSocket error:', error);
            };
        } catch (error) {
            console.error('[NotificationService] Failed to connect WebSocket:', error);
        }
    },

    /**
     * 安排重连（带最大重试次数和指数退避）
     */
    scheduleReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }

        // 检查是否超过最大重试次数
        if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
            console.warn('[NotificationService] Max reconnect attempts reached, stopping');
            return;
        }

        // 指数退避：5s, 10s, 20s, 40s, 80s
        const delay = Math.min(5000 * Math.pow(2, this.reconnectAttempts), 60000);
        this.reconnectAttempts++;

        console.log(
            `[NotificationService] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`,
        );

        this.reconnectTimer = setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    },

    disconnectWebSocket(resetReconnect = true) {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.ws) {
            try {
                this.ws.onopen = null;
                this.ws.onmessage = null;
                this.ws.onclose = null;
                this.ws.onerror = null;
                if (
                    this.ws.readyState === WebSocket.OPEN ||
                    this.ws.readyState === WebSocket.CONNECTING
                ) {
                    this.ws.close();
                }
            } catch (error) {
                console.warn('[NotificationService] Failed to close WebSocket cleanly', error);
            }
            this.ws = null;
        }

        if (resetReconnect) {
            this.reconnectAttempts = 0;
        }
    },

    /**
     * 格式化时间
     */
    formatTime(dateString) {
        if (!dateString) return '';
        // PostgreSQL returns "2026-02-28 18:02:54.123" (space) — Android/Pi Browser
        // requires ISO 8601 "2026-02-28T18:02:54" (T) for reliable parsing
        const normalized =
            typeof dateString === 'string'
                ? dateString.replace(' ', 'T').replace(/(\.\d+)$/, '') // strip microseconds
                : dateString;
        const date = new Date(normalized);
        if (isNaN(date.getTime())) return '';

        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return '剛剛';
        if (minutes < 60) return `${minutes} 分鐘前`;
        if (hours < 24) return `${hours} 小時前`;
        if (days < 7) return `${days} 天前`;

        return date.toLocaleDateString('zh-TW');
    },
};

// 自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => NotificationService.init(), { once: true });
} else {
    NotificationService.init();
}

window.NotificationService = NotificationService;
export { NotificationService };
