// ========================================
// NotificationPanel.js - 通知面板組件
// ========================================

class NotificationPanel {
    constructor(container) {
        this.container = container;
        this.isVisible = false;
        this.init();
    }

    init() {
        this.render();
        this.attachEvents();

        // 监听通知更新
        window.addEventListener('notificationsUpdated', (e) => {
            if (this.isVisible) {
                this.renderNotifications(e.detail.notifications);
            }
        });
    }

    render() {
        this.container.innerHTML = `
            <div id="notification-panel" 
                 class="notification-panel fixed top-14 right-4 w-80 max-h-[70vh] bg-surface border border-white/10 rounded-2xl shadow-2xl z-[60] hidden overflow-hidden">
                <!-- 头部 -->
                <div class="flex items-center justify-between px-4 py-3 border-b border-white/5">
                    <h3 class="font-bold text-secondary">通知中心</h3>
                    <button id="notification-mark-all-read" 
                            class="text-xs text-textMuted hover:text-primary transition">
                        全部已讀
                    </button>
                </div>
                
                <!-- 通知列表 -->
                <div id="notification-list" class="overflow-y-auto max-h-[calc(70vh-50px)]">
                    <!-- 通知项会动态插入 -->
                </div>
                
                <!-- 空状态 -->
                <div id="notification-empty" class="hidden p-8 text-center">
                    <i data-lucide="bell-off" class="w-12 h-12 text-textMuted/30 mx-auto mb-3"></i>
                    <p class="text-textMuted text-sm">暫無通知</p>
                </div>
            </div>
        `;

        // 初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    attachEvents() {
        // 全部已读按钮
        const markAllBtn = document.getElementById('notification-mark-all-read');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', () => {
                NotificationService.markAllAsRead();
            });
        }

        // 阻止面板内点击冒泡
        const panel = document.getElementById('notification-panel');
        if (panel) {
            panel.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
    }

    show() {
        this.isVisible = true;
        const panel = document.getElementById('notification-panel');
        if (panel) {
            panel.classList.remove('hidden');
            this.renderNotifications(NotificationService.getNotifications());
        }
    }

    hide() {
        this.isVisible = false;
        const panel = document.getElementById('notification-panel');
        if (panel) {
            panel.classList.add('hidden');
        }
    }

    renderNotifications(notifications) {
        const listEl = document.getElementById('notification-list');
        const emptyEl = document.getElementById('notification-empty');

        if (!listEl || !emptyEl) return;

        if (notifications.length === 0) {
            listEl.classList.add('hidden');
            emptyEl.classList.remove('hidden');
            return;
        }

        listEl.classList.remove('hidden');
        emptyEl.classList.add('hidden');

        listEl.innerHTML = notifications.map(n => this.renderNotificationItem(n)).join('');

        // 绑定事件
        listEl.querySelectorAll('.notification-item').forEach(item => {
            const id = item.dataset.id;
            
            // 点击标记已读
            item.addEventListener('click', () => {
                NotificationService.markAsRead(id);
                this.handleNotificationClick(JSON.parse(item.dataset.notification));
            });

            // 操作按钮
            item.querySelectorAll('.notification-action').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.handleAction(id, btn.dataset.action, JSON.parse(item.dataset.notification));
                });
            });
        });

        // 重新初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    renderNotificationItem(notification) {
        const icons = {
            friend_request: 'user-plus',
            message: 'message-circle',
            post_interaction: 'heart',
            system_update: 'refresh-cw',
            announcement: 'megaphone'
        };

        const colors = {
            friend_request: 'text-primary',
            message: 'text-accent',
            post_interaction: 'text-danger',
            system_update: 'text-success',
            announcement: 'text-secondary'
        };

        const icon = icons[notification.type] || 'bell';
        const color = colors[notification.type] || 'text-textMuted';
        const unreadClass = notification.is_read ? '' : 'bg-surfaceHighlight/50';
        const dotClass = notification.is_read ? 'invisible' : '';

        // 操作按钮
        let actionsHtml = '';
        if (notification.type === 'friend_request' && !notification.is_read) {
            actionsHtml = `
                <div class="flex gap-2 mt-2">
                    <button class="notification-action text-xs px-2 py-1 bg-success/10 hover:bg-success/20 text-success rounded-lg transition" data-action="accept">
                        接受
                    </button>
                    <button class="notification-action text-xs px-2 py-1 bg-danger/10 hover:bg-danger/20 text-danger rounded-lg transition" data-action="reject">
                        拒絕
                    </button>
                </div>
            `;
        } else if (notification.type === 'system_update') {
            actionsHtml = `
                <button class="notification-action text-xs px-2 py-1 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition mt-2" data-action="update">
                    立即更新
                </button>
            `;
        }

        return `
            <div class="notification-item px-4 py-3 hover:bg-white/5 cursor-pointer transition border-b border-white/5 ${unreadClass}"
                 data-id="${notification.id}"
                 data-notification='${JSON.stringify(notification).replace(/'/g, "&#39;")}'>
                <div class="flex gap-3">
                    <!-- 未读标记 -->
                    <div class="w-2 h-2 rounded-full bg-primary mt-2 shrink-0 ${dotClass}"></div>
                    <!-- 图标 -->
                    <div class="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center shrink-0">
                        <i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
                    </div>
                    <!-- 内容 -->
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-medium text-secondary">${notification.title}</div>
                        <div class="text-xs text-textMuted mt-0.5 line-clamp-2">${notification.body}</div>
                        ${actionsHtml}
                        <div class="text-[10px] text-textMuted/60 mt-1">
                            ${NotificationService.formatTime(notification.created_at)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    handleNotificationClick(notification) {
        // 根据通知类型跳转
        switch (notification.type) {
            case 'friend_request':
                if (typeof switchTab === 'function') {
                    switchTab('friends');
                }
                break;
            case 'message':
                if (typeof switchTab === 'function') {
                    switchTab('friends');
                }
                if (notification.data && notification.data.from_user_id && window.SocialHub) {
                    const fromUsername = notification.data.from_username || '';
                    setTimeout(() => SocialHub.openConversation(notification.data.from_user_id, fromUsername), 300);
                }
                break;
            case 'post_interaction':
                if (typeof switchTab === 'function') {
                    switchTab('forum');
                }
                if (notification.data && notification.data.post_id && window.ForumApp) {
                    setTimeout(() => ForumApp.loadPostDetail(notification.data.post_id), 300);
                }
                break;
        }

        // 关闭面板
        this.hide();
        if (window.notificationBell) {
            window.notificationBell.isPanelOpen = false;
        }
    }

    handleAction(notificationId, action, notification) {
        switch (action) {
            case 'accept':
                if (notification.data.from_user_id && typeof FriendsUI !== 'undefined') {
                    FriendsUI.handleAcceptRequest(notification.data.from_user_id);
                }
                NotificationService.markAsRead(notificationId);
                break;
            case 'reject':
                if (notification.data.from_user_id && typeof FriendsUI !== 'undefined') {
                    FriendsUI.handleRejectRequest(notification.data.from_user_id);
                }
                NotificationService.markAsRead(notificationId);
                break;
            case 'update':
                // 刷新页面以更新
                if (typeof showToast === 'function') {
                    showToast('正在更新...', 'info');
                }
                setTimeout(() => window.location.reload(), 500);
                break;
        }
    }
}

// 暴露全局
window.NotificationPanel = NotificationPanel;
