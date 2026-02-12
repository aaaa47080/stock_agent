// ========================================
// NotificationBell.js - 通知圖標組件
// ========================================

class NotificationBell {
    constructor(container) {
        this.container = container;
        this.isPanelOpen = false;
        this.init();
    }

    init() {
        this.render();
        this.attachEvents();
        this.updateBadge(NotificationService.getUnreadCount());

        // 监听通知更新
        window.addEventListener('notificationsUpdated', (e) => {
            this.updateBadge(e.detail.unreadCount);
        });
    }

    render() {
        this.container.innerHTML = `
            <div class="notification-bell relative">
                <button id="notification-bell-btn"
                        class="relative p-2 hover:bg-white/5 rounded-full text-textMuted hover:text-primary transition"
                        aria-label="通知">
                    <i data-lucide="bell" class="w-5 h-5"></i>
                    <!-- 未读徽章 -->
                    <span id="notification-badge"
                          class="absolute -top-0.5 -right-0.5 w-4 h-4 bg-danger text-white text-[10px] font-bold rounded-full flex items-center justify-center hidden">
                        0
                    </span>
                </button>
            </div>
        `;

        // 初始化图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    attachEvents() {
        const btn = document.getElementById('notification-bell-btn');
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.togglePanel();
            });
        }

        // 点击外部关闭面板
        document.addEventListener('click', (e) => {
            if (this.isPanelOpen && !e.target.closest('.notification-bell') && !e.target.closest('.notification-panel')) {
                this.closePanel();
            }
        });
    }

    updateBadge(count) {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (count > 0) {
                badge.classList.remove('hidden');
                badge.textContent = count > 99 ? '99+' : count;
            } else {
                badge.classList.add('hidden');
            }
        }
    }

    togglePanel() {
        if (this.isPanelOpen) {
            this.closePanel();
        } else {
            this.openPanel();
        }
    }

    openPanel() {
        this.isPanelOpen = true;

        // 创建或显示面板
        if (!window.notificationPanel) {
            const panelContainer = document.createElement('div');
            panelContainer.className = 'notification-panel-wrapper';
            document.body.appendChild(panelContainer);
            window.notificationPanel = new NotificationPanel(panelContainer);
        }

        window.notificationPanel.show();
    }

    closePanel() {
        this.isPanelOpen = false;
        if (window.notificationPanel) {
            window.notificationPanel.hide();
        }
    }
}

// 暴露全局
window.NotificationBell = NotificationBell;
