// ========================================
// NotificationBell.js - 通知圖標組件（支援多實例）
// ========================================

let _bellInstanceCount = 0;

class NotificationBell {
    constructor(container) {
        this.container = container;
        this.isPanelOpen = false;
        this.instanceId = ++_bellInstanceCount;
        this.btnId = `notification-bell-btn-${this.instanceId}`;
        this.badgeId = `notification-badge-${this.instanceId}`;
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
                <button id="${this.btnId}"
                        class="relative p-2 hover:bg-white/5 rounded-full text-textMuted hover:text-primary transition"
                        aria-label="通知">
                    <i data-lucide="bell" class="w-5 h-5"></i>
                    <!-- 未读徽章 -->
                    <span id="${this.badgeId}"
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
        const btn = document.getElementById(this.btnId);
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.togglePanel();
            });
        }

        // 点击外部关闭面板（只綁定一次，由第一個實例處理）
        if (this.instanceId === 1) {
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.notification-bell') && !e.target.closest('.notification-panel')) {
                    // 關閉所有實例的面板狀態
                    if (window.notificationBell) window.notificationBell.isPanelOpen = false;
                    if (window.notificationBellDesktop) window.notificationBellDesktop.isPanelOpen = false;
                    if (window.notificationPanel) window.notificationPanel.hide();
                }
            });
        }
    }

    updateBadge(count) {
        const badge = document.getElementById(this.badgeId);
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
        // 同步所有實例的狀態
        const isOpen = window.notificationPanel && window.notificationPanel.isVisible;
        if (isOpen) {
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
