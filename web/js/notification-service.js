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

    // 是否已登录
    isLoggedIn: false,

    // 模拟数据（Phase 1 使用，作为后备）
    mockNotifications: [
        {
            id: 'notif_001',
            type: 'friend_request',
            title: '好友請求',
            body: 'Alice 想加你為好友',
            data: { from_user_id: 'user_123', from_username: 'Alice' },
            is_read: false,
            created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString()
        },
        {
            id: 'notif_002',
            type: 'system_update',
            title: '系統更新',
            body: '有新版本可用，建議更新以獲得最佳體驗',
            data: { version: '2.1.0' },
            is_read: false,
            created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString()
        },
        {
            id: 'notif_003',
            type: 'message',
            title: '新消息',
            body: 'Bob: 你好，最近怎麼樣？',
            data: { from_user_id: 'user_456', from_username: 'Bob', conversation_id: 'conv_001' },
            is_read: true,
            created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
        },
        {
            id: 'notif_004',
            type: 'post_interaction',
            title: '帖子互動',
            body: 'Carol 贊了你的文章「市場分析」',
            data: { post_id: 'post_001', interaction_type: 'like', from_username: 'Carol' },
            is_read: true,
            created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
        }
    ],

    /**
     * 初始化通知服务
     */
    async init() {
        // 检查是否登录
        this.isLoggedIn = window.AuthManager && window.AuthManager.isLoggedIn();

        if (this.isLoggedIn) {
            // 已登录：从 API 获取真实数据
            await this.fetchNotifications();

            // 连接 WebSocket
            this.connectWebSocket();
        } else {
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
     * 从 API 获取通知
     */
    async fetchNotifications() {
        try {
            const { userId, token } = this._getCredentials();

            if (!userId || !token) {
                console.log('[NotificationService] No credentials, empty notifications');
                this.notifications = [];
                this.unreadCount = 0;
                this.notifyUpdate();
                return;
            }

            const response = await fetch(`/api/notifications?user_id=${userId}&limit=50`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.notifications = data.notifications || [];
                this.unreadCount = data.unread_count || 0;
                this.notifyUpdate();
                console.log('[NotificationService] Loaded from API:', this.notifications.length, 'notifications');
            } else {
                console.warn('[NotificationService] API failed, status:', response.status);
                this.notifications = [];
                this.unreadCount = 0;
                this.notifyUpdate();
            }
        } catch (error) {
            console.error('[NotificationService] Fetch error:', error);
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
        this.unreadCount = this.notifications.filter(n => !n.is_read).length;
    },

    /**
     * 标记通知为已读
     */
    async markAsRead(notificationId) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (notification && !notification.is_read) {
            notification.is_read = true;
            this.updateUnreadCount();
            this.notifyUpdate();

            // 同步到服务器
            if (this.isLoggedIn) {
                try {
                    const { userId, token } = this._getCredentials();
                    if (userId && token) {
                        await fetch(`/api/notifications/${notificationId}/read?user_id=${userId}`, {
                            method: 'POST',
                            headers: {
                                'Authorization': `Bearer ${token}`
                            }
                        });
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
        this.notifications.forEach(n => n.is_read = true);
        this.updateUnreadCount();
        this.notifyUpdate();

        // 同步到服务器
        if (this.isLoggedIn) {
            try {
                const { userId, token } = this._getCredentials();
                if (userId && token) {
                    await fetch(`/api/notifications/read-all?user_id=${userId}`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
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
        window.dispatchEvent(new CustomEvent('notificationsUpdated', {
            detail: {
                notifications: this.notifications,
                unreadCount: this.unreadCount
            }
        }));
    },

    /**
     * 连接 WebSocket (Phase 2)
     */
    connectWebSocket() {
        const { userId, token } = this._getCredentials();

        if (!userId || !token) {
            console.log('[NotificationService] No credentials for WebSocket');
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('[NotificationService] WebSocket connected');
                // 发送认证信息
                this.ws.send(JSON.stringify({ type: 'auth', user_id: userId }));
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
     * 安排重连
     */
    scheduleReconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        this.reconnectTimer = setTimeout(() => {
            this.connectWebSocket();
        }, 5000);
    },

    /**
     * 格式化时间
     */
    formatTime(dateString) {
        if (!dateString) return '';
        // PostgreSQL returns "2026-02-28 18:02:54.123" (space) — Android/Pi Browser
        // requires ISO 8601 "2026-02-28T18:02:54" (T) for reliable parsing
        const normalized = typeof dateString === 'string'
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
    }
};

// 自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => NotificationService.init());
} else {
    NotificationService.init();
}

window.NotificationService = NotificationService;
