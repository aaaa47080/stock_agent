// ========================================
// forum.js - 論壇功能核心邏輯
// ========================================

// 格式化為台灣時間
function formatTWDate(dateStr, showTime = false) {
    const date = new Date(dateStr);
    const options = {
        timeZone: 'Asia/Taipei',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    };
    if (showTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
        options.hour12 = false;
    }
    return date.toLocaleString('zh-TW', options);
}

const ForumAPI = {
    baseUrl: '/api/forum',

    async _fetch(endpoint, options = {}) {
        try {
            const res = await fetch(`${this.baseUrl}${endpoint}`, options);
            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.detail || 'API request failed');
            }
            return await res.json();
        } catch (e) {
            console.error(`ForumAPI Error (${endpoint}):`, e);
            throw e;
        }
    },

    // Helper to get user ID safely (handling uid vs user_id mismatch)
    _getUserId() {
        if (!AuthManager.currentUser) return null;
        return AuthManager.currentUser.uid || AuthManager.currentUser.user_id;
    },

    // 看板相關
    async getBoards() {
        return this._fetch('/boards');
    },

    async getBoard(slug) {
        return this._fetch(`/boards/${slug}`);
    },

    // 文章相關
    async getPosts(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this._fetch(`/posts?${query}`);
    },

    async getPost(id) {
        const uid = this._getUserId();
        const query = uid ? `?user_id=${uid}` : '';
        return this._fetch(`/posts/${id}${query}`);
    },

    async createPost(data) {
        // data: { board_slug, category, title, content, tags, payment_tx_hash }
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        // user_id 必須是 Query Parameter
        return this._fetch(`/posts?user_id=${uid}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },

    async updatePost(postId, data) {
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        return this._fetch(`/posts/${postId}?user_id=${uid}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },

    async deletePost(postId) {
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        return this._fetch(`/posts/${postId}?user_id=${uid}`, {
            method: 'DELETE'
        });
    },

    // 回覆相關
    async getComments(postId) {
        return this._fetch(`/posts/${postId}/comments`);
    },

    async createComment(postId, data) {
        // data: { content, parent_id, type }
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        return this._fetch(`/posts/${postId}/comments?user_id=${uid}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },

    async pushPost(postId) {
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        return this._fetch(`/posts/${postId}/push?user_id=${uid}`, {
            method: 'POST'
        });
    },

    async booPost(postId) {
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        return this._fetch(`/posts/${postId}/boo?user_id=${uid}`, {
            method: 'POST'
        });
    },

    // 打賞相關
    async tipPost(postId, amount, txHash) {
        const uid = this._getUserId();
        if (!uid) throw new Error("User not logged in");

        const data = {
            amount: amount,
            tx_hash: txHash
        };
        
        return this._fetch(`/posts/${postId}/tip?user_id=${uid}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },

    // 標籤相關
    async getTrendingTags() {
        return this._fetch('/tags/trending');
    },

    // 個人後台
    async getMyStats() {
        const uid = this._getUserId();
        const query = uid ? `?user_id=${uid}` : '';
        return this._fetch(`/me/stats${query}`);
    },

    async getMyPosts() {
        const uid = this._getUserId();
        if (!uid) return { posts: [] };
        return this._fetch(`/me/posts?user_id=${uid}`);
    },

    async getMyTipsSent() {
        const uid = this._getUserId();
        if (!uid) return { tips: [] };
        return this._fetch(`/me/tips/sent?user_id=${uid}`);
    },

    async getMyTipsReceived() {
        const uid = this._getUserId();
        if (!uid) return { tips: [] };
        return this._fetch(`/me/tips/received?user_id=${uid}`);
    }
};

const ForumApp = {
    init() {
        this.bindEvents();
        // 頁面特定初始化
        const page = document.body.dataset.page;
        if (page === 'index') this.initIndexPage();
        else if (page === 'post') this.initPostPage();
        else if (page === 'create') this.initCreatePage();
        else if (page === 'dashboard') this.initDashboardPage();
        
        this.updateAuthUI();
    },

    bindEvents() {
        // 全域事件監聽
        document.addEventListener('auth:login', () => this.updateAuthUI());
    },

    updateAuthUI() {
        const user = AuthManager.currentUser;
        const authElements = document.querySelectorAll('.auth-only');
        const guestElements = document.querySelectorAll('.guest-only');
        
        if (user) {
            authElements.forEach(el => el.classList.remove('hidden'));
            guestElements.forEach(el => el.classList.add('hidden'));
            
            // 更新用戶顯示名稱
            const nameEls = document.querySelectorAll('.user-display-name');
            nameEls.forEach(el => el.textContent = user.username);
        } else {
            authElements.forEach(el => el.classList.add('hidden'));
            guestElements.forEach(el => el.classList.remove('hidden'));
        }
    },

    // ===========================================
    // Index Page Logic
    // ===========================================
    async initIndexPage() {
        this.loadBoards();
        this.loadPosts();
        this.loadTrendingTags();

        // 搜尋/篩選監聽
        document.getElementById('category-filter')?.addEventListener('change', (e) => {
            this.loadPosts({ category: e.target.value });
        });
    },

    async loadBoards() {
        try {
            const boards = await ForumAPI.getBoards();
            // 渲染看板列表 (如果有的話)
        } catch (e) { console.error('Error loading boards:', e); }
    },

    async loadPosts(filters = {}) {
        const container = document.getElementById('post-list');
        if (!container) return;
        
        container.innerHTML = '<div class="text-center py-10 text-textMuted"><i class="animate-spin" data-lucide="loader-2"></i> Loading...</div>';
        lucide.createIcons();

        try {
            const response = await ForumAPI.getPosts(filters);
            const posts = response.posts || [];
            
            container.innerHTML = '';
            
            if (posts.length === 0) {
                container.innerHTML = '<div class="text-center py-10 text-textMuted">暫無文章</div>';
                return;
            }

            posts.forEach(post => {
                const el = document.createElement('div');
                el.className = 'bg-surface hover:bg-surfaceHighlight border border-white/5 rounded-xl p-4 transition cursor-pointer mb-3';
                el.onclick = () => window.location.href = `/static/forum/post.html?id=${post.id}`;
                
                // 標籤 HTML
                let tagsHtml = '';
                try {
                    if (post.tags) {
                        const tags = JSON.parse(post.tags);
                        tagsHtml = tags.map(tag => 
                            `<span class="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full mr-1">#${tag}</span>`
                        ).join('');
                    }
                } catch (e) {}

                // 日期格式化
                const date = formatTWDate(post.created_at);
                
                // 計算推噓淨值
                const netLikes = (post.push_count || 0) - (post.boo_count || 0);

                el.innerHTML = `
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold text-secondary bg-white/10 px-2 py-0.5 rounded uppercase">${post.category}</span>
                            <span class="text-xs text-textMuted">${post.username || post.user_id}</span>
                            <span class="text-xs text-textMuted">• ${date}</span>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-textMuted">
                            <span class="flex items-center gap-1 ${netLikes > 0 ? 'text-success' : ''}"><i data-lucide="thumbs-up" class="w-3 h-3"></i> ${netLikes}</span>
                            <span class="flex items-center gap-1"><i data-lucide="message-square" class="w-3 h-3"></i> ${post.comment_count}</span>
                            ${post.tips_total > 0 ? `<span class="flex items-center gap-1 text-primary"><i data-lucide="gift" class="w-3 h-3"></i> ${post.tips_total}</span>` : ''}
                        </div>
                    </div>
                    <h3 class="font-bold text-lg text-textMain mb-2 truncate">${post.title}</h3>
                    <div class="flex items-center">
                        ${tagsHtml}
                    </div>
                `;
                container.appendChild(el);
            });
            lucide.createIcons();
        } catch (e) {
            console.error(e);
            container.innerHTML = '<div class="text-center py-10 text-danger">載入失敗</div>';
        }
    },

    async loadTrendingTags() {
        const container = document.getElementById('trending-tags');
        if (!container) return;

        try {
            const response = await ForumAPI.getTrendingTags();
            const tags = response.tags || []; // Adjust based on API response structure
            
            container.innerHTML = tags.map(tag => `
                <a href="#" class="block text-sm text-textMuted hover:text-primary transition py-1">#${tag.name} <span class="text-xs opacity-50">(${tag.post_count})</span></a>
            `).join('');
        } catch (e) {
            console.error('Failed to load tags', e);
        }
    },

    // ===========================================
    // Post Page Logic
    // ===========================================
    async initPostPage() {
        const urlParams = new URLSearchParams(window.location.search);
        const postId = urlParams.get('id');
        
        if (!postId) {
            window.location.href = '/static/forum/index.html';
            return;
        }

        this.currentPostId = postId;
        await this.loadPostDetail(postId);
        await this.loadComments(postId);

        // 綁定按鈕事件
        document.getElementById('btn-push')?.addEventListener('click', () => this.handlePush(postId));
        document.getElementById('btn-boo')?.addEventListener('click', () => this.handleBoo(postId));
        document.getElementById('btn-reply')?.addEventListener('click', () => this.toggleReplyForm());
        document.getElementById('btn-tip')?.addEventListener('click', () => this.handleTip(postId));
        document.getElementById('submit-reply')?.addEventListener('click', () => this.submitReply(postId));
    },

    async loadPostDetail(id) {
        try {
            const response = await ForumAPI.getPost(id);
            const post = response.post;
            
            document.title = `${post.title} - Pi Forum`;
            
            document.getElementById('post-category').textContent = post.category;
            document.getElementById('post-title').textContent = post.title;
            document.getElementById('post-author').textContent = post.username || post.user_id;
            document.getElementById('post-date').textContent = formatTWDate(post.created_at, true);
            
            // 使用 markdown-it 渲染內容
            const md = window.markdownit ? window.markdownit() : { render: t => t };
            document.getElementById('post-content').innerHTML = md.render(post.content);

            // Tags
            const tagsContainer = document.getElementById('post-tags');
            if (post.tags && tagsContainer) {
                try {
                    const tags = JSON.parse(post.tags);
                    tagsContainer.innerHTML = tags.map(tag => 
                        `<span class="text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">#${tag}</span>`
                    ).join('');
                } catch(e) {}
            }
            
            // Stats
            this.updatePostStats(post);
            
            // Re-render icons
            if(window.lucide) window.lucide.createIcons();

        } catch (e) {
            showToast('文章載入失敗', 'error');
            console.error(e);
        }
    },

    updatePostStats(post) {
        const btnPush = document.getElementById('btn-push');
        const btnBoo = document.getElementById('btn-boo');
        const statPush = document.getElementById('stat-push');
        const statBoo = document.getElementById('stat-boo');
        const statTips = document.getElementById('stat-tips');

        if (statPush) statPush.textContent = post.push_count;
        if (statBoo) statBoo.textContent = post.boo_count;
        if (statTips) statTips.textContent = post.tips_total;

        // 重置顏色
        btnPush?.classList.remove('text-success');
        btnPush?.classList.add('text-textMuted');
        btnBoo?.classList.remove('text-danger');
        btnBoo?.classList.add('text-textMuted');

        // 根據投票狀態上色
        if (post.viewer_vote === 'push') {
            btnPush?.classList.remove('text-textMuted');
            btnPush?.classList.add('text-success');
        } else if (post.viewer_vote === 'boo') {
            btnBoo?.classList.remove('text-textMuted');
            btnBoo?.classList.add('text-danger');
        }
    },

    async loadComments(postId) {
        const container = document.getElementById('comments-list');
        try {
            const response = await ForumAPI.getComments(postId);
            const comments = response.comments || [];
            
            container.innerHTML = '';
            
            if (comments.length === 0) {
                 container.innerHTML = '<div class="text-center text-textMuted py-4">暫無回覆</div>';
                 return;
            }
            
            comments.forEach(comment => {
                if (comment.type !== 'comment') return; // 只顯示一般回覆
                
                const el = document.createElement('div');
                el.className = 'border-b border-white/5 py-3';
                el.innerHTML = `
                    <div class="flex justify-between items-start mb-1">
                        <span class="font-bold text-sm text-secondary">${comment.username || comment.user_id}</span>
                        <span class="text-xs text-textMuted">${formatTWDate(comment.created_at, true)}</span>
                    </div>
                    <div class="text-textMain text-sm">${comment.content}</div>
                `;
                container.appendChild(el);
            });
        } catch (e) {
            console.error(e);
        }
    },

    async handlePush(postId) {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        try {
            await ForumAPI.pushPost(postId);
            // 重新載入以更新數字
            this.loadPostDetail(postId);
        } catch (e) {
            showToast(e.message, 'error');
        }
    },
    
    async handleBoo(postId) {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        try {
            await ForumAPI.booPost(postId);
            this.loadPostDetail(postId);
        } catch (e) {
            showToast(e.message, 'error');
        }
    },

    toggleReplyForm() {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        const form = document.getElementById('reply-form');
        form.classList.toggle('hidden');
    },

    async submitReply(postId) {
        const content = document.getElementById('reply-content').value;
        if (!content) return;

        try {
            await ForumAPI.createComment(postId, { type: 'comment', content });
            document.getElementById('reply-content').value = '';
            this.toggleReplyForm();
            this.loadComments(postId);
            // Update stats to show new comment count (if displayed)
        } catch (e) {
            showToast(e.message, 'error');
        }
    },

    async handleTip(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請先登入', 'warning');
        }

        const confirmed = await showConfirm({
            title: '確認打賞',
            message: '確認打賞 1 Pi 給作者？',
            type: 'info',
            confirmText: '確認打賞',
            cancelText: '取消'
        });

        if (!confirmed) return;

        try {
            // 1. 呼叫 Pi SDK 支付 (mock)
            // TODO: Implement actual Pi.createPayment
            const txHash = "mock_tx_" + Date.now();

            // 2. 後端記錄
            await ForumAPI.tipPost(postId, 1, txHash);
            showToast('打賞成功！', 'success');
            this.loadPostDetail(postId);

        } catch (e) {
            console.error(e);
            showToast('打賞失敗: ' + e.message, 'error');
        }
    },

    // ===========================================
    // Create Post Logic
    // ===========================================
    initCreatePage() {
        document.getElementById('post-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!AuthManager.currentUser) return showToast('請先登入', 'warning');

            // 檢查錢包綁定狀態
            if (!canMakePiPayment()) {
                const goToDashboard = await showConfirm({
                    title: '需要綁定 Pi 錢包',
                    message: '發文需要支付 1 Pi，請先綁定您的 Pi 錢包。\n\n是否前往 Dashboard 綁定？',
                    type: 'warning',
                    confirmText: '前往綁定',
                    cancelText: '取消'
                });

                if (goToDashboard) {
                    window.location.href = '/static/forum/dashboard.html';
                }
                return;
            }

            const title = document.getElementById('input-title').value;
            const content = document.getElementById('input-content').value;
            const category = document.getElementById('input-category').value;
            const tagsStr = document.getElementById('input-tags').value;

            // 處理標籤
            const tags = tagsStr.split(' ').map(t => t.replace('#', '').trim()).filter(t => t);

            try {
                // 1. 支付發文費 (如果需要)
                // TODO: Implement actual Pi.createPayment
                const txHash = "mock_payment_" + Date.now();

                // 2. 提交 API
                await ForumAPI.createPost({
                    board_slug: 'crypto', // 目前固定
                    category,
                    title,
                    content,
                    tags,
                    payment_tx_hash: txHash
                });

                showToast('發布成功！', 'success');
                window.location.href = '/static/forum/index.html';

            } catch (e) {
                showToast('發布失敗: ' + e.message, 'error');
            }
        });
    },

    // ===========================================
    // Dashboard Logic
    // ===========================================
    async initDashboardPage() {
        if (!AuthManager.currentUser) {
            window.location.href = '/static/forum/index.html';
            return;
        }

        try {
            // Load Wallet Status
            await this.loadWalletStatus();

            // Load Stats
            const statsRes = await ForumAPI.getMyStats();
            const stats = statsRes.stats || {};
            document.getElementById('dash-post-count').textContent = stats.post_count || 0;
            document.getElementById('dash-tips-sent').textContent = stats.tips_sent || 0;
            document.getElementById('dash-tips-received').textContent = stats.tips_received || 0;

            // Load Posts
            const postsRes = await ForumAPI.getMyPosts();
            const postsList = document.getElementById('dash-posts-list');
            if (postsList && postsRes.posts && postsRes.posts.length > 0) {
                postsList.innerHTML = postsRes.posts.map(p => `
                    <div class="flex items-center justify-between border-b border-white/5 py-2">
                        <a href="/static/forum/post.html?id=${p.id}" class="text-sm hover:text-primary truncate">${p.title}</a>
                        <span class="text-xs text-textMuted">${formatTWDate(p.created_at)}</span>
                    </div>
                `).join('');
            }

            // Load Transactions (Tips Sent)
            const tipsRes = await ForumAPI.getMyTipsSent();
            const txList = document.getElementById('dash-tx-list');
            if (txList && tipsRes.tips && tipsRes.tips.length > 0) {
                txList.innerHTML = tipsRes.tips.map(t => `
                    <div class="flex items-center justify-between border-b border-white/5 py-2">
                        <div class="flex flex-col">
                            <span class="text-sm">Sent 1 Pi to Post #${t.post_id}</span>
                            <span class="text-[10px] text-textMuted font-mono">${t.tx_hash.substring(0, 8)}...</span>
                        </div>
                        <span class="text-xs text-textMuted">${formatTWDate(t.created_at)}</span>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error("Dashboard load error", e);
        }
    },

    async loadWalletStatus() {
        const statusText = document.getElementById('wallet-status-text');
        const usernameEl = document.getElementById('wallet-username');
        const actionArea = document.getElementById('wallet-action-area');
        const iconEl = document.getElementById('wallet-icon');

        if (!statusText || !actionArea) return;

        try {
            const status = await getWalletStatus();

            if (status.has_wallet || status.auth_method === 'pi_network') {
                // 已綁定或 Pi 錢包登入
                statusText.textContent = '已連接';
                statusText.classList.add('text-success');
                iconEl.classList.remove('bg-primary/20');
                iconEl.classList.add('bg-success/20');
                iconEl.innerHTML = '<i data-lucide="check-circle" class="w-7 h-7 text-success"></i>';

                if (status.pi_username) {
                    usernameEl.textContent = `@${status.pi_username}`;
                    usernameEl.classList.remove('hidden');
                }

                actionArea.innerHTML = `
                    <div class="flex items-center gap-2 text-success">
                        <i data-lucide="shield-check" class="w-5 h-5"></i>
                        <span class="text-sm font-bold">Verified</span>
                    </div>
                `;
            } else {
                // 未綁定
                statusText.textContent = '未綁定';
                statusText.classList.add('text-textMuted');

                actionArea.innerHTML = `
                    <button onclick="handleLinkWallet()" class="bg-primary/10 hover:bg-primary/20 text-primary px-4 py-2 rounded-xl flex items-center gap-2 transition text-sm font-bold border border-primary/20">
                        <i data-lucide="link" class="w-4 h-4"></i>
                        綁定 Pi 錢包
                    </button>
                `;
            }

            if (window.lucide) lucide.createIcons();
        } catch (e) {
            console.error('Load wallet status error:', e);
            statusText.textContent = '載入失敗';
        }
    }
};

// 綁定錢包按鈕處理
async function handleLinkWallet() {
    const result = await linkPiWallet();
    if (result.success) {
        // 重新載入錢包狀態
        ForumApp.loadWalletStatus();
    }
}

// 確保在 DOM 載入後執行
document.addEventListener('DOMContentLoaded', () => {
    // 檢查 AuthManager 是否就緒，或者等待它
    if (window.AuthManager) {
        // 嘗試從 localStorage 恢復
        AuthManager.init();
        ForumApp.init();
    } else {
        // 簡單輪詢
        const checkAuth = setInterval(() => {
            if (window.AuthManager) {
                clearInterval(checkAuth);
                AuthManager.init();
                ForumApp.init();
            }
        }, 100);
    }
});