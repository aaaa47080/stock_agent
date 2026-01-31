/**
 * messages_page.js - 訊息頁面控制器
 * Logic extracted from messages.html
 */

const MessagesPage = {
    currentConversationId: null,
    currentOtherUserId: null,
    currentOtherUsername: null,
    isPro: false,
    conversations: [],
    isMobile: window.innerWidth < 768,
    maxMessageLength: 500,  // 預設值，會從 API 更新
    hasMoreMessages: false,  // 是否還有更多訊息
    isLoadingMore: false,    // 是否正在載入更多
    oldestMessageId: null,   // 最舊訊息的 ID

    /**
     * 初始化頁面
     */
    async init() {
        // 檢查登入
        if (typeof AuthManager !== 'undefined') {
            await AuthManager.init();
            if (!AuthManager.isLoggedIn()) {
                // 使用平滑過渡跳轉
                if (typeof smoothNavigate === 'function') {
                    smoothNavigate('/static/forum/index.html');
                } else {
                    window.location.href = '/static/forum/index.html';
                }
                return;
            }
        }

        if (typeof MessagesUI !== 'undefined') {
            MessagesUI.init();
        }

        // 載入訊息限制狀態
        await this.loadLimits();

        // 載入對話列表
        await this.loadConversations();

        // 連接 WebSocket
        this.setupWebSocket();

        // 處理 URL 參數
        const params = new URLSearchParams(window.location.search);

        // 設置返回按鈕 - 根據來源返回正確頁面
        const source = params.get('source');
        const backBtn = document.getElementById('back-btn');
        if (backBtn) {
            if (source === 'friends' || source === 'social') {
                // 從好友頁面來的，返回好友頁面
                backBtn.href = '/static/index.html#friends';
                backBtn.onclick = (e) => {
                    e.preventDefault();
                    sessionStorage.setItem('activeTab', 'friends');
                    if (typeof smoothNavigate === 'function') {
                        smoothNavigate('/static/index.html');
                    } else {
                        window.location.href = '/static/index.html';
                    }
                };
            }
        }

        // 直接開啟與某人的對話
        const withUserId = params.get('with');
        if (withUserId) {
            await this.openConversationWith(withUserId);
        }

        // 響應式處理
        window.addEventListener('resize', () => {
            this.isMobile = window.innerWidth < 768;
        });

        if (window.lucide) lucide.createIcons();
    },

    /**
     * 載入訊息限制狀態
     */
    async loadLimits() {
        const limits = await MessagesAPI.getLimits();
        if (limits) {
            this.isPro = limits.is_pro;

            // 更新訊息長度限制（從 API 取得）
            if (limits.max_length) {
                this.maxMessageLength = limits.max_length;
                // 更新 textarea 的 maxlength 屬性
                const input = document.getElementById('message-input');
                if (input) {
                    input.maxLength = this.maxMessageLength;
                }
                // 更新字數統計顯示
                const charCount = document.getElementById('char-count');
                if (charCount) {
                    charCount.textContent = `0/${this.maxMessageLength}`;
                }
            }

            // 顯示/隱藏 Pro 功能
            if (this.isPro) {
                const searchBtn = document.getElementById('search-btn');
                if (searchBtn) searchBtn.classList.remove('hidden');
                const limitInfo = document.getElementById('message-limit-info');
                if (limitInfo) limitInfo.classList.add('hidden');
            } else {
                const limitInfo = document.getElementById('message-limit-info');
                if (limitInfo) limitInfo.classList.remove('hidden');
                const limitUsed = document.getElementById('limit-used');
                if (limitUsed) limitUsed.textContent = limits.message_limit.used || 0;
                const limitTotal = document.getElementById('limit-total');
                if (limitTotal) limitTotal.textContent = limits.message_limit.limit || 20;
            }
        }
    },

    /**
     * 載入對話列表
     */
    async loadConversations() {
        const listEl = document.getElementById('conversation-list');
        if (!listEl) return;

        try {
            const result = await MessagesAPI.getConversations();
            this.conversations = result.conversations || [];

            if (this.conversations.length === 0) {
                listEl.innerHTML = MessagesUI.renderEmptyState('尚無對話', 'message-square');
                if (window.lucide) lucide.createIcons();
                return;
            }

            listEl.innerHTML = this.conversations.map(conv =>
                MessagesUI.renderConversationItem(conv, conv.id === this.currentConversationId)
            ).join('');

            if (window.lucide) lucide.createIcons();

            // Loop: Auto-select first conversation on desktop if none selected
            if (!this.isMobile && this.conversations.length > 0 && !this.currentConversationId) {
                const first = this.conversations[0];
                this.selectConversation(first.id, first.other_user_id, first.other_username);
            }
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

        // 載入訊息 (主要操作)
        await this.loadMessages();

        // 標記已讀 (後台執行，不阻塞 UI)
        MessagesAPI.markAsRead(conversationId).catch(e => console.error('標記已讀失敗:', e));

        // 更新對話列表中的未讀狀態 (本地更新)
        this.updateConversationUnread(conversationId, 0);

        // Focus input
        const input = document.getElementById('message-input');
        if (input) input.focus();
    },

    /**
     * 透過用戶 ID 開啟對話
     */
    async openConversationWith(userId) {
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) messagesContainer.innerHTML = MessagesUI.renderLoadingState();

        try {
            const result = await MessagesAPI.getConversationWith(userId);
            this.currentConversationId = result.conversation.id;
            this.currentOtherUserId = userId;

            // 取得用戶名
            const conv = this.conversations.find(c => c.other_user_id === userId);
            this.currentOtherUsername = conv?.other_username || result.conversation.other_username || userId;

            this.showChatSection();
            this.updateChatHeader(this.currentOtherUsername);
            this.renderMessages(result.messages || []);

            // 標記已讀 (後台執行)
            if (result.conversation.id) {
                MessagesAPI.markAsRead(result.conversation.id).catch(e => console.error('標記已讀失敗:', e));
            }

            // 延遲更新對話列表 (不阻塞主要操作)
            setTimeout(() => this.loadConversations(), 500);

        } catch (e) {
            console.error('開啟對話失敗:', e);
            if (messagesContainer) messagesContainer.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
        }
    },

    /**
     * 載入訊息
     */
    async loadMessages() {
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) messagesContainer.innerHTML = MessagesUI.renderLoadingState();

        try {
            const result = await MessagesAPI.getMessages(this.currentConversationId, 10);  // 初始只載入 10 條

            this.hasMoreMessages = result.has_more || false;
            this.oldestMessageId = result.messages && result.messages.length > 0
                ? result.messages[0].id
                : null;

            this.renderMessages(result.messages || []);
            this.setupScrollListener();  // 設置滾動監聽
        } catch (e) {
            console.error('載入訊息失敗:', e);
            if (messagesContainer) messagesContainer.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
        }
    },

    /**
     * 載入更多舊訊息
     */
    async loadMoreMessages() {
        if (this.isLoadingMore || !this.hasMoreMessages || !this.oldestMessageId) {
            return;
        }

        this.isLoadingMore = true;
        const container = document.getElementById('messages-container');
        const oldScrollHeight = container.scrollHeight;

        try {
            // 在頂部顯示載入提示
            const loadingIndicator = document.createElement('div');
            loadingIndicator.className = 'text-center py-2 text-textMuted text-sm';
            loadingIndicator.textContent = '載入中...';
            container.insertBefore(loadingIndicator, container.firstChild);

            const result = await MessagesAPI.getMessages(
                this.currentConversationId,
                20,  // 每次載入 20 條舊訊息
                this.oldestMessageId
            );

            // 移除載入提示
            loadingIndicator.remove();

            if (result.messages && result.messages.length > 0) {
                // 更新狀態
                this.hasMoreMessages = result.has_more || false;
                this.oldestMessageId = result.messages[0].id;

                // 在頂部插入訊息
                const messagesHTML = result.messages.reverse().map(msg =>
                    MessagesUI.renderMessageBubble(msg, this.isPro)
                ).join('');
                container.insertAdjacentHTML('afterbegin', messagesHTML);

                // 保持滾動位置
                container.scrollTop = container.scrollHeight - oldScrollHeight;
            } else {
                this.hasMoreMessages = false;
            }
        } catch (e) {
            console.error('載入更多訊息失敗:', e);
        } finally {
            this.isLoadingMore = false;
        }
    },

    /**
     * 設置滾動監聽（無限滾動）
     */
    setupScrollListener() {
        const container = document.getElementById('messages-container');
        if (!container) return;

        // 移除舊的監聽器
        container.removeEventListener('scroll', this.scrollHandler);

        // 創建新的監聽器
        this.scrollHandler = () => {
            // 當滾動到頂部 100px 內時，載入更多
            if (container.scrollTop < 100 && this.hasMoreMessages && !this.isLoadingMore) {
                this.loadMoreMessages();
            }
        };

        container.addEventListener('scroll', this.scrollHandler);
    },

    /**
     * 渲染訊息列表
     * 會在已讀和未讀訊息之間插入「新訊息」分隔線
     */
    renderMessages(messages, unreadCount = 0) {
        const container = document.getElementById('messages-container');
        if (!container) return;

        if (messages.length === 0) {
            container.innerHTML = MessagesUI.renderEmptyState('開始對話吧', 'message-circle');
            if (window.lucide) lucide.createIcons();
            return;
        }

        // API 返回的是正序（舊 -> 新），不需要反轉
        const sortedMessages = [...messages];

        // 找到第一條未讀訊息的位置（對方發給我的、且尚未讀取的）
        // 未讀訊息 = to_user_id 是我 且 is_read = false
        const currentUserId = MessagesUI.currentUserId;
        let firstUnreadIndex = -1;

        for (let i = 0; i < sortedMessages.length; i++) {
            const msg = sortedMessages[i];
            // 對方發給我的訊息，且未讀
            if (msg.to_user_id === currentUserId && !msg.is_read) {
                firstUnreadIndex = i;
                break;
            }
        }

        // 渲染訊息，在適當位置插入分隔線
        let html = '';
        for (let i = 0; i < sortedMessages.length; i++) {
            // 在第一條未讀訊息前插入分隔線
            if (i === firstUnreadIndex && firstUnreadIndex > 0) {
                html += MessagesUI.renderNewMessagesSeparator();
            }
            html += MessagesUI.renderMessageBubble(sortedMessages[i], this.isPro);
        }

        container.innerHTML = html;

        // 渲染圖示
        if (window.lucide) lucide.createIcons();

        // 確保 DOM 完全更新後再滾動
        // 如果有未讀訊息，滾動到分隔線位置；否則滾動到底部
        if (firstUnreadIndex > 0) {
            this.scrollToNewMessages(container);
        } else {
            this.scrollToBottom(container);
        }
    },

    /**
     * 滾動到新訊息分隔線位置
     */
    scrollToNewMessages(container) {
        if (!container) {
            container = document.getElementById('messages-container');
        }
        if (!container) return;

        requestAnimationFrame(() => {
            const separator = container.querySelector('.new-messages-separator');
            if (separator) {
                // 滾動到分隔線位置，讓用戶看到分隔線上方的一些舊訊息
                separator.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                this.scrollToBottom(container);
            }
        });
    },

    /**
     * 滾動到底部並確保輸入框可見 - 改進版
     */
    scrollToBottom(container) {
        if (!container) {
            container = document.getElementById('messages-container');
        }
        if (!container) return;

        // Force scroll to very bottom
        const scroll = () => {
            container.scrollTop = container.scrollHeight;

            // Also try to scroll the very last element into view
            const lastMessage = container.lastElementChild;
            if (lastMessage) {
                lastMessage.scrollIntoView({ block: 'end', behavior: 'auto' });
            }
        };

        // Execute immediately
        scroll();

        // Execute after next repaint
        requestAnimationFrame(() => {
            scroll();
            // Additional attempts to handle dynamic content/images loading
            setTimeout(scroll, 50);
            setTimeout(scroll, 150);
            setTimeout(scroll, 300);
        });

        // 確保輸入框可見 - 在手機端特別重要
        this.scrollToInputBox();
    },

    /**
     * 滾動到輸入框位置 - 確保輸入框在可視區域內
     */
    scrollToInputBox() {
        requestAnimationFrame(() => {
            const inputContainer = document.getElementById('message-input-container');
            const messageInput = document.getElementById('message-input');

            if (inputContainer) {
                // 使用 setTimeout 確保 DOM 完全更新
                setTimeout(() => {
                    // 滾動輸入框容器到可視區域
                    inputContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });

                    // 在手機端，確保軟鍵盤不會遮擋輸入框
                    if (this.isMobile && messageInput) {
                        // 延遲 focus 以確保滾動完成
                        setTimeout(() => {
                            messageInput.focus();
                            // 再次確保輸入框可見（處理軟鍵盤彈出的情況）
                            setTimeout(() => {
                                inputContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
                            }, 300);
                        }, 100);
                    }
                }, 100);
            }
        });
    },

    /**
     * 發送訊息
     */
    async sendMessage(event) {
        if (event) event.preventDefault();

        const input = document.getElementById('message-input');
        const content = input.value.trim();

        if (!content || !this.currentOtherUserId) return;

        const sendBtn = document.getElementById('send-btn');
        // Lock button visually and functionally
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }

        try {
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
                        const limitUsed = document.getElementById('limit-used');
                        if (limitUsed) limitUsed.textContent = limits.message_limit.used || 0;
                    }
                }
            }
        } catch (e) {
            console.error('發送訊息失敗:', e);
            if (typeof showToast === 'function') {
                showToast(e.message, 'error');
            } else {
                alert(e.message || '發送失敗');
            }
        } finally {
            // Restore button state - ensure button is re-enabled
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
            this.updateCharCount();

            // Focus back to input
            if (input) input.focus();
        }
    },

    /**
     * 添加新訊息到畫面
     */
    appendMessage(msg) {
        const container = document.getElementById('messages-container');
        if (!container) return;

        // 移除空狀態
        const emptyState = container.querySelector('.flex.flex-col.items-center');
        if (emptyState) {
            container.innerHTML = '';
        }

        container.insertAdjacentHTML('beforeend', MessagesUI.renderMessageBubble(msg, this.isPro));
        if (window.lucide) lucide.createIcons();
        this.scrollToBottom(container);
    },

    /**
     * 收回訊息
     */
    async recallMessage(messageId) {
        if (!confirm('確定要收回這條訊息嗎？對方會看到「對方已收回訊息」')) return;

        try {
            const userId = MessagesAPI._getUserId();
            if (!userId) return;

            const res = await fetch(`/api/messages/${messageId}?user_id=${userId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${MessagesAPI._getToken()}`
                }
            });

            const data = await res.json();

            if (res.ok && data.success) {
                // 更新 DOM：將訊息替換為「已收回」樣式
                const msgEl = document.getElementById(`msg-${messageId}`);
                if (msgEl) {
                    const timeStr = msgEl.querySelector('.text-xs.text-textMuted')?.textContent || '';
                    msgEl.outerHTML = `
                        <div id="msg-${messageId}" class="flex justify-end mb-4">
                            <div class="flex flex-col items-end">
                                <div class="px-4 py-2 rounded-2xl bg-white/5 border border-white/10">
                                    <span class="text-textMuted/60 text-sm italic">你已收回訊息</span>
                                </div>
                                <div class="text-xs text-textMuted/50 mt-1 px-1">${timeStr}</div>
                            </div>
                        </div>
                    `;
                }
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
     * 處理輸入框按鍵
     */
    handleInputKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage(event);
        }
    },

    /**
     * 自動調整輸入框高度
     */
    autoResizeInput(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        this.updateCharCount();
    },

    /**
     * 更新發送按鈕狀態
     */
    /**
     * updateSendButton - Deprecated, logic moved to updateCharCount
     * Kept for compatibility if called from elsewhere, but redirects to updateCharCount
     */
    updateSendButton() {
        this.updateCharCount();
    },

    /**
     * 更新字數統計
     */
    updateCharCount() {
        const input = document.getElementById('message-input');
        const charCount = document.getElementById('char-count');
        const warning = document.getElementById('input-limit-warning');
        const sendBtn = document.getElementById('send-btn');

        if (!input) return;

        const currentLength = input.value.length;
        const hasContent = input.value.trim().length > 0;
        const maxLength = this.maxMessageLength;

        // 1. Update Button State (Robust Logic from friends.js)
        if (sendBtn) {
            if (hasContent) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            } else {
                sendBtn.disabled = true;
                sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
            }
        }

        // 2. Update Char Count Text
        if (charCount) charCount.textContent = `${currentLength}/${maxLength}`;

        // 3. Update Warning / Colors
        if (charCount && warning) {
            if (currentLength >= maxLength) {
                charCount.classList.remove('text-textMuted/50');
                charCount.classList.add('text-danger');
                warning.textContent = '已達字數上限';
                warning.classList.remove('hidden');
            } else if (currentLength >= maxLength * 0.9) {
                charCount.classList.remove('text-textMuted/50');
                charCount.classList.add('text-yellow-500');
                warning.classList.add('hidden');
            } else {
                charCount.classList.remove('text-danger', 'text-yellow-500');
                charCount.classList.add('text-textMuted/50');
                warning.classList.add('hidden');
            }
        }
    },

    /**
     * 顯示聊天區域
     */
    showChatSection() {
        const sidebar = document.getElementById('conversation-sidebar');
        const chatSection = document.getElementById('chat-section');
        const chatHeader = document.getElementById('chat-header');
        const inputContainer = document.getElementById('message-input-container');

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

        // 安全檢查：chat-header 已移除
        if (chatHeader) chatHeader.classList.remove('hidden');
        if (inputContainer) inputContainer.classList.remove('hidden');

        // 延遲確保 DOM 更新完成後滾動到輸入框
        setTimeout(() => {
            this.scrollToInputBox();
        }, 200);
    },

    /**
     * 返回對話列表（手機版）
     */
    backToList() {
        const sidebar = document.getElementById('conversation-sidebar');
        const chatSection = document.getElementById('chat-section');

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
        // 安全檢查：這些元素已被移除，不需要更新
        const avatar = document.getElementById('chat-user-avatar');
        const usernameEl = document.getElementById('chat-username');
        const profileLink = document.getElementById('chat-profile-link');
        const badge = document.getElementById('chat-user-badge');

        if (avatar) avatar.textContent = MessagesUI.getInitial(username);
        if (usernameEl) usernameEl.textContent = username;
        if (profileLink) profileLink.href = `/static/forum/profile.html?id=${this.currentOtherUserId}`;

        // 找到對話資訊更新徽章
        if (badge) {
            const conv = this.conversations.find(c => c.other_user_id === this.currentOtherUserId);
            if (conv && conv.other_membership_tier === 'pro') {
                badge.innerHTML = MessagesUI.getMembershipBadge('pro');
            } else {
                badge.innerHTML = '';
            }
        }
    },

    /**
     * 更新對話的未讀數
     */
    updateConversationUnread(conversationId, count) {
        const item = document.querySelector(`.conversation-item[data-conversation-id="${conversationId}"]`);
        if (item) {
            const badge = item.querySelector('.bg-primary.rounded-full');
            if (badge) {
                if (count > 0) {
                    badge.textContent = count > 99 ? '99+' : count;
                } else {
                    badge.remove();
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
            console.log('WebSocket 連接成功');
        });

        MessagesWebSocket.onMessage((message, isSent) => {
            // 如果是自己發送的訊息（message_sent），跳過，因為 API 回應已經添加過了
            if (isSent) {
                return;
            }

            // 如果是當前對話的訊息，添加到畫面
            if (message.conversation_id === this.currentConversationId) {
                this.appendMessage(message);
                // 標記已讀
                MessagesAPI.markAsRead(this.currentConversationId);
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
            // 更新已讀狀態（僅 Pro 可見）
            if (this.isPro && conversationId === this.currentConversationId) {
                // 將所有自己發送的訊息標記為已讀
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

    /**
     * 切換搜尋面板
     */
    toggleSearch() {
        const panel = document.getElementById('search-panel');
        if (!panel) return;

        panel.classList.toggle('hidden');

        if (!panel.classList.contains('hidden')) {
            const searchInput = document.getElementById('search-input');
            if (searchInput) searchInput.focus();
        }
    },

    /**
     * 處理搜尋
     */
    async handleSearch(query) {
        const resultsEl = document.getElementById('search-results');
        if (!resultsEl) return;

        if (!query || query.length < 2) {
            resultsEl.innerHTML = '<div class="text-center text-textMuted py-8">輸入至少 2 個字元</div>';
            return;
        }

        resultsEl.innerHTML = MessagesUI.renderLoadingState();

        try {
            const result = await MessagesAPI.searchMessages(query);

            if (!result.results || result.results.length === 0) {
                resultsEl.innerHTML = '<div class="text-center text-textMuted py-8">找不到符合的訊息</div>';
                return;
            }

            resultsEl.innerHTML = result.results.map(msg => `
                <div class="p-3 border-b border-white/5 hover:bg-white/5 cursor-pointer transition"
                     onclick="MessagesPage.openConversationWith('${msg.other_user_id}'); MessagesPage.toggleSearch();">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="font-bold text-textMain">${msg.other_username || msg.other_user_id}</span>
                        <span class="text-xs text-textMuted">${MessagesUI.formatTime(msg.created_at)}</span>
                    </div>
                    <p class="text-sm text-textMuted">${msg.content}</p>
                </div>
            `).join('');

        } catch (e) {
            resultsEl.innerHTML = `<div class="p-4 text-center text-danger">${e.message}</div>`;
        }
    },

    /**
     * 切換側邊欄
     */
    toggleSidebar() {
        const sidebar = document.getElementById('conversation-sidebar');
        if (!sidebar) return;

        // Toggle visibility with animation classes if possible, but basic hidden is safer for now
        if (sidebar.classList.contains('hidden')) {
            sidebar.classList.remove('hidden');
            // Ensure width classes are present
            sidebar.classList.add('md:w-80', 'lg:w-96');
        } else {
            sidebar.classList.add('hidden');
            sidebar.classList.remove('md:w-80', 'lg:w-96');
        }

        // Force layout update if needed
        window.dispatchEvent(new Event('resize'));
    }
};

// Toast 函數
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');

    const colors = {
        success: 'bg-success/20 border-success/30 text-success',
        error: 'bg-danger/20 border-danger/30 text-danger',
        warning: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
        info: 'bg-primary/20 border-primary/30 text-primary'
    };

    const icons = {
        success: 'check-circle',
        error: 'x-circle',
        warning: 'alert-triangle',
        info: 'info'
    };

    toast.className = `pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-2xl border backdrop-blur-xl shadow-xl animate-fade-in-up ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <i data-lucide="${icons[type] || icons.info}" class="w-5 h-5 flex-shrink-0 mt-0.5"></i>
        <p class="text-sm font-medium flex-1">${message}</p>
        <button onclick="this.parentElement.remove()" class="text-current opacity-60 hover:opacity-100 transition">
            <i data-lucide="x" class="w-4 h-4"></i>
        </button>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    if (duration > 0) {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// 智能返回邏輯
function setupBackButton() {
    const backBtn = document.getElementById('back-btn');
    if (!backBtn) return;

    // 從 URL 參數或 sessionStorage 獲取來源
    const params = new URLSearchParams(window.location.search);
    const source = params.get('source') || sessionStorage.getItem('messages_source');

    // 保存來源到 sessionStorage（供後續使用）
    if (params.get('source')) {
        sessionStorage.setItem('messages_source', params.get('source'));
    }

    // 根據來源決定返回目標
    if (source === 'friends' || source === 'main') {
        // 從主應用的 Friends tab 來的
        backBtn.href = '/static/index.html#friends';
    } else if (source === 'forum') {
        // 從論壇來的
        backBtn.href = '/static/forum/index.html';
    } else {
        // 使用 referrer 作為後備方案，但不完全依賴它
        const referrer = document.referrer;
        if (referrer && referrer.includes('/static/forum/')) {
            backBtn.href = '/static/forum/index.html';
        } else {
            // 默認返回主應用的 Friends tab
            backBtn.href = '/static/index.html#friends';
        }
    }

    // 添加平滑過渡效果
    backBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const targetUrl = backBtn.href;

        // 淡出效果
        document.body.style.opacity = '0';
        document.body.style.transition = 'opacity 0.2s ease-out';

        // 清除 sessionStorage
        sessionStorage.removeItem('messages_source');

        setTimeout(() => {
            window.location.href = targetUrl;
        }, 200);
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) lucide.createIcons();
    setupBackButton();
    if (window.MessagesPage) MessagesPage.init();
});

// Export to window
window.MessagesPage = MessagesPage;
window.showToast = showToast;
