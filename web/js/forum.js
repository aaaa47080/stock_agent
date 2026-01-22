// ========================================
// forum.js - 論壇功能核心邏輯
// ========================================

// ============================================
// Pi 支付價格配置（從後端動態獲取）
// ============================================
window.PiPrices = {
    create_post: 1.0,  // 預設值，會被後端覆蓋
    tip: 1.0,
    premium: 100.0,    // 高級會員價格更新為 100 Pi
    loaded: false
};

// 從後端載入價格配置
async function loadPiPrices() {
    if (window.PiPrices.loading) return; // Prevent concurrent requests
    window.PiPrices.loading = true;

    try {
        const res = await fetch('/api/config/prices');
        if (res.ok) {
            const data = await res.json();
            window.PiPrices = { ...data.prices, loaded: true, loading: false };
            console.log('[Forum] Pi 價格配置已載入:', window.PiPrices);
            // 更新頁面上的價格顯示
            updatePriceDisplays();
            // 通知其他模組價格已更新
            document.dispatchEvent(new Event('pi-prices-updated'));
        } else {
             window.PiPrices.loading = false;
        }
    } catch (e) {
        console.error('[Forum] 載入價格配置失敗:', e);
        window.PiPrices.loading = false;
    }
}

function updatePriceDisplays() {
    // 價格更新時刷新相關 UI
}

// Helper to format date
function formatTWDate(dateStr, full = false) {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;
        
        // Less than 24 hours
        if (diff < 86400000 && !full) {
            if (diff < 3600000) return Math.max(1, Math.floor(diff / 60000)) + 'm ago';
            return Math.floor(diff / 3600000) + 'h ago';
        }
        
        // Format: MM/DD or YYYY/MM/DD HH:mm
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        
        if (full) return `${year}/${month}/${day} ${hours}:${minutes}`;
        return `${month}/${day}`;
    } catch (e) {
        return dateStr;
    }
}

// ============================================
// Forum API Client
// ============================================
const ForumAPI = {
    _getUserId() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            return AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
        }
        return null;
    },

    // Boards
    async getBoards() {
        const res = await fetch('/api/forum/boards');
        return await res.json();
    },

    // Posts
    async getPosts(filters = {}) {
        const query = new URLSearchParams(filters).toString();
        const res = await fetch(`/api/forum/posts?${query}`);
        return await res.json();
    },
    async getPost(id) {
        const res = await fetch(`/api/forum/posts/${id}`);
        return await res.json();
    },
    async createPost(data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts?user_id=${encodeURIComponent(userId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            let errorMsg = 'Failed to create post';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    // Pydantic validation error
                    errorMsg = err.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                } else {
                    errorMsg = JSON.stringify(err);
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Comments & Reactions
    async getComments(postId) {
        const res = await fetch(`/api/forum/posts/${postId}/comments`);
        return await res.json();
    },
    async createComment(postId, data) {
         const userId = this._getUserId();
         if (!userId) throw new Error('Please login first');

         const query = new URLSearchParams({ user_id: userId }).toString();
         const res = await fetch(`/api/forum/posts/${postId}/comments?${query}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            let errorMsg = 'Failed to create comment';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                } else {
                    errorMsg = JSON.stringify(err);
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },
    async pushPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');
        
        const res = await fetch(`/api/forum/posts/${postId}/push?user_id=${userId}`, { method: 'POST' });
        if (!res.ok) {
            let errorMsg = 'Failed to push';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },
    async booPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}/boo?user_id=${userId}`, { method: 'POST' });
        if (!res.ok) {
             let errorMsg = 'Failed to boo';
             try {
                 const err = await res.json();
                 if (typeof err.detail === 'string') {
                     errorMsg = err.detail;
                 } else if (Array.isArray(err.detail)) {
                     errorMsg = err.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                 } else if (err.message) {
                     errorMsg = err.message;
                 }
             } catch (e) {
                 errorMsg = `Status ${res.status}: ${res.statusText}`;
             }
             throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Tags
    async getTrendingTags() {
        const res = await fetch('/api/forum/tags/trending');
        return await res.json();
    },

    // Tips
    async tipPost(postId, amount, txHash) {
         const userId = this._getUserId();
         if (!userId) throw new Error('Please login first');

         const res = await fetch(`/api/forum/posts/${postId}/tip?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount, tx_hash: txHash })
        });
        if (!res.ok) {
            let errorMsg = 'Failed to tip';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // My Stats (Me)
    async getMyStats() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/stats?user_id=${userId}`);
        return await res.json();
    },
    async getMyPosts() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/posts?user_id=${userId}`);
        return await res.json();
    },
    async getMyTipsSent() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/sent?user_id=${userId}`);
        return await res.json();
    },
    async getMyTipsReceived() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/received?user_id=${userId}`);
        return await res.json();
    },
    async getMyPayments() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/payments?user_id=${userId}`);
        return await res.json();
    },
    async checkLimits() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 5000); // 5s timeout

        try {
            const res = await fetch(`/api/forum/me/limits?user_id=${userId}`, {
                signal: controller.signal
            });
            clearTimeout(id);
            return await res.json();
        } catch (e) {
            clearTimeout(id);
            throw e;
        }
    },
};

// Expose globally
window.ForumAPI = ForumAPI;

// ============================================
// Forum App Logic
// ============================================
const ForumApp = {
    init() {
        console.log('ForumApp: init starting...');
        
        // Ensure prices are loaded
        if (!window.PiPrices.loaded) {
            loadPiPrices();
        }

        try {
            // 確保 AuthManager 已初始化（從 localStorage 載入用戶資訊）
            if (typeof AuthManager !== 'undefined' && typeof AuthManager.init === 'function') {
                AuthManager.init();
                console.log('ForumApp: AuthManager initialized, currentUser:', AuthManager.currentUser);
            }

            this.bindEvents();
            // 頁面特定初始化
            const page = document.body.dataset.page;
            console.log('ForumApp: page detected', page);

            if (page === 'index') this.initIndexPage();
            else if (page === 'post') this.initPostPage();
            else if (page === 'create') this.initCreatePage();
            else if (page === 'dashboard') this.initDashboardPage();
            
            this.updateAuthUI();
        } catch (err) {
            console.error('ForumApp: Init failed', err);
        }
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
        if (window.lucide) lucide.createIcons();

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
            if (window.lucide) lucide.createIcons();
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
            const tags = response.tags || []; 
            
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
        } catch (e) {
            showToast(e.message, 'error');
        }
    },

    async handleTip(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請先登入', 'warning');
        }

        // 檢查是否在 Pi Browser 環境
        const isPi = typeof isPiBrowser === 'function' ? isPiBrowser() : false;

        // 獲取打賞價格
        const tipAmount = window.PiPrices?.tip || null;

        // 確認打賞
        const confirmed = await showConfirm({
            title: '確認打賞',
            message: isPi
                ? `確認打賞 ${tipAmount} Pi 給作者？\n將會開啟 Pi 支付流程。`
                : `確認打賞 ${tipAmount} Pi 給作者？\n（測試模式：非 Pi Browser 環境）`,
            type: 'info',
            confirmText: '確認打賞',
            cancelText: '取消'
        });

        if (!confirmed) return;

        try {
            let txHash = "";

            if (isPi && window.Pi) {
                // === Pi 真實支付流程 ===
                console.log('[Tip] 開始 Pi 支付流程');

                if (typeof AuthManager.verifyPiBrowserEnvironment === 'function') {
                    const envCheck = await AuthManager.verifyPiBrowserEnvironment();
                    if (!envCheck.valid) {
                        showToast('Pi Browser 環境異常，請確認已登入 Pi 帳號', 'warning');
                        return;
                    }
                }

                try {
                    await Pi.authenticate(['payments'], () => {});
                } catch (authErr) {
                    showToast('支付權限不足，請重新登入', 'error');
                    return;
                }

                let paymentComplete = false;
                let paymentError = null;

                showToast('正在處理支付...', 'info', 0);

                await Pi.createPayment({
                    amount: tipAmount,
                    memo: `打賞文章 #${postId}`,
                    metadata: { type: "tip", post_id: postId }
                }, {
                    onReadyForServerApproval: async (paymentId) => {
                        try {
                            await fetch('/api/user/payment/approve', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId })
                            });
                        } catch (e) { console.error(e); }
                    },
                    onReadyForServerCompletion: async (paymentId, txid) => {
                        txHash = txid;
                        paymentComplete = true;
                        try {
                            await fetch('/api/user/payment/complete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId, txid })
                            });
                        } catch (e) { console.error(e); }
                    },
                    onCancel: (paymentId) => {
                        paymentError = 'CANCELLED';
                    },
                    onError: (error) => {
                        paymentError = error?.message || 'PAYMENT_ERROR';
                    }
                });

                const startTime = Date.now();
                while (!paymentComplete && !paymentError && (Date.now() - startTime) < 120000) {
                    await new Promise(r => setTimeout(r, 300));
                }

                const toastContainer = document.getElementById('toast-container');
                if (toastContainer) toastContainer.innerHTML = '';

                if (paymentError) {
                    showToast(paymentError === 'CANCELLED' ? '支付已取消' : '支付失敗', 'warning');
                    return;
                }

                if (!txHash) {
                    showToast('支付超時，請重試', 'warning');
                    return;
                }

            } else {
                txHash = "mock_tip_" + Date.now();
            }

            await ForumAPI.tipPost(postId, tipAmount, txHash);
            showToast('打賞成功！感謝您的支持', 'success');
            this.loadPostDetail(postId);

        } catch (e) {
            showToast('打賞失敗: ' + e.message, 'error');
        }
    },

    // ===========================================
    // Create Post Logic
    // ===========================================
    initCreatePage() {
        const log = (msg, data = {}) => {
            console.log('[CreatePost]', msg, data);
        };

        const updateUIForMembership = async () => {
            const userId = AuthManager.currentUser?.user_id || AuthManager.currentUser?.uid;
            if (!userId) {
                console.warn('[CreatePost] No user ID found for UI update');
                return;
            }

            const limitDisplay = document.getElementById('daily-limit-display');

            try {
                const limitsData = await ForumAPI.checkLimits();
                console.log('[CreatePost] UI Update limits data:', limitsData);

                if (limitsData.success) {
                    const isPro = limitsData.membership?.is_pro || false;
                    const postLimit = limitsData.limits?.post || { count: 0, limit: 3, remaining: 3 };

                    // Update Daily Limit Display
                    if (limitDisplay) {
                        if (isPro) {
                            limitDisplay.innerHTML = `
                                <div class="bg-primary/10 text-primary px-3 py-1 rounded-full border border-primary/20 flex items-center gap-1.5 font-bold">
                                    <i data-lucide="crown" class="w-3 h-3"></i>
                                    Daily Limit: Unlimited
                                </div>
                            `;
                        } else {
                            const total = postLimit.limit || 3;
                            const used = postLimit.count || 0;
                            // Ensure remaining logic is consistent
                            const remaining = (postLimit.remaining !== undefined) ? postLimit.remaining : (total - used);
                            const isLow = remaining <= 0;
                            
                            limitDisplay.innerHTML = `
                                <div class="bg-white/5 px-3 py-1 rounded-full border border-white/10 flex items-center gap-1.5">
                                    <span class="opacity-60">Daily Posts:</span>
                                    <span class="font-bold ${isLow ? 'text-danger' : 'text-success'}">${used}/${total}</span>
                                </div>
                            `;
                        }
                        if (window.lucide) lucide.createIcons();
                    }

                    // Update Submit Button and Cost Info
                    const submitButton = document.querySelector('button[type="submit"]');
                    const paySpan = submitButton?.querySelector('span');
                    if (paySpan) {
                        if (isPro) {
                            paySpan.textContent = 'Post for Free (PRO)';
                        } else {
                            const postAmount = window.PiPrices?.create_post || 1.0;
                            paySpan.innerHTML = `Pay <span class="font-bold text-white">${postAmount}</span> Pi & Post`;
                        }
                    }
                    
                    const costElements = document.querySelectorAll('.text-sm.text-textMuted');
                    costElements.forEach(el => {
                        if (el.textContent.includes('Cost to post:')) {
                            if (isPro) {
                                el.innerHTML = 'Cost to post: <span class="text-success font-bold">FREE</span> <br><span class="text-xs opacity-60">(For PRO members)</span>';
                            } else {
                                // Reset to default if needed or keep existing
                            }
                        }
                    });
                }
            } catch (error) {
                console.warn('[CreatePost] Failed to update UI status:', error);
                if (limitDisplay) limitDisplay.innerHTML = '<span class="text-danger text-xs">Connection Error</span>';
            }
        };
                    
                    if (AuthManager.currentUser) {
                        updateUIForMembership();
                    }
                    
                    document.getElementById('post-form')?.addEventListener('submit', async (e) => {
                        e.preventDefault();
                        console.log('[CreatePost] Form submitted');
                    
                        // Disable button to prevent double submit
                        const submitBtn = document.querySelector('button[type="submit"]');
                        let originalBtnContent = '';
                        
                        if (submitBtn) {
                            if (submitBtn.disabled) return; // Already processing
                            submitBtn.disabled = true;
                            originalBtnContent = submitBtn.innerHTML;
                            submitBtn.innerHTML = '<i class="animate-spin" data-lucide="loader-2"></i> Processing...';
                            if (window.lucide) lucide.createIcons();
                        }
                    
                        // Function to reset button state
                        const resetButton = () => {
                            console.log('[CreatePost] Resetting button state');
                            if (submitBtn) {
                                submitBtn.disabled = false;
                                submitBtn.innerHTML = originalBtnContent;
                                if (window.lucide) lucide.createIcons();
                            }
                        };
                    
                        if (!AuthManager?.currentUser) {
                            showToast('請先登入', 'warning');
                            resetButton();
                            return;
                        }
                    
                        const title = document.getElementById('input-title').value;
                        const content = document.getElementById('input-content').value;
                        const category = document.getElementById('input-category').value;
                        const tagsStr = document.getElementById('input-tags').value;
                        const tags = tagsStr.split(' ').map(t => t.replace('#', '').trim()).filter(t => t);
                    
                        const postAmount = window.PiPrices?.create_post || 1.0;
                        const isPi = AuthManager.isPiBrowser();
                        let txHash = "";
                    
                        const userId = AuthManager.currentUser?.user_id || AuthManager.currentUser?.uid;
                        let isProMember = false;
                    
                        if (userId) {
                            try {
                                // First, check limits and membership status
                                console.log('[CreatePost] Checking limits and membership...');
                                const limitsData = await ForumAPI.checkLimits();
                                
                                if (limitsData.success) {
                                    const postLimit = limitsData.limits.post;
                                    isProMember = limitsData.membership?.is_pro || false;

                                    // Check if limit reached
                                    // limit === null means unlimited (Pro)
                                    if (postLimit.limit !== null && postLimit.remaining <= 0) {
                                        console.warn('[CreatePost] Daily limit reached:', postLimit);
                                        
                                        // Custom Styled Modal
                                        const modal = document.createElement('div');
                                        modal.className = 'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                                        modal.innerHTML = `
                                            <div class="bg-surface w-full max-w-sm p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in text-center">
                                                <div class="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-warning/20">
                                                    <i data-lucide="lock" class="w-8 h-8 text-warning"></i>
                                                </div>
                                                <h3 class="text-xl font-bold text-secondary mb-2">發文額度已滿</h3>
                                                <div class="text-textMuted text-sm mb-6 leading-relaxed">
                                                    今日已發布 <span class="text-textMain font-bold text-base">${postLimit.count}</span> / <span class="text-textMain font-bold text-base">${postLimit.limit}</span> 篇文章<br>
                                                    <span class="opacity-70">升級 PRO 會員即可無限發文！</span>
                                                </div>
                                                <div class="flex flex-col gap-3">
                                                    <button onclick="window.location.href='/static/forum/premium.html'" class="w-full py-3.5 bg-gradient-to-r from-primary to-primary/80 hover:to-primary text-background font-bold rounded-2xl transition shadow-lg flex items-center justify-center gap-2 transform active:scale-95">
                                                        <i data-lucide="crown" class="w-4 h-4"></i>
                                                        <span>升級 PRO 會員</span>
                                                    </button>
                                                    <button onclick="this.closest('.fixed').remove()" class="w-full py-3.5 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5 hover:text-white">
                                                        知道了
                                                    </button>
                                                </div>
                                            </div>
                                        `;
                                        document.body.appendChild(modal);
                                        if (window.lucide) lucide.createIcons();

                                        resetButton();
                                        return; // STOP HERE - Do not proceed to payment
                                    }
                                }
                            } catch (error) {
                                console.warn('[CreatePost] Failed to check limits:', error);
                                // Optional: Decide whether to block or proceed if check fails. 
                                // Ideally we should probably warn but maybe let them try? 
                                // For safety, let's proceed but log the error.
                            }
                        }
                        
                        console.log(`[CreatePost] User: ${userId}, IsPro: ${isProMember}, Amount: ${postAmount}`);
                    
                        if (isProMember) {
                            txHash = "pro_member_free"; 
                            console.log('[CreatePost] Pro member, skipping payment');
                        } else {
                            try {
                                if (isPi && window.Pi) {
                                    console.log('[CreatePost] Starting Pi Payment flow...');
                                    try {
                                        await Pi.authenticate(['payments'], () => {});
                                    } catch (authErr) {
                                        console.error('[CreatePost] Pi Auth failed:', authErr);
                                        showToast('支付權限不足，請重新登入', 'error');
                                        resetButton();
                                        return;
                                    }
                    
                                    let paymentComplete = false;
                                    let paymentError = null;
                                    let serverCompletionCalled = false;
                    
                                    await Pi.createPayment({
                                        amount: postAmount,
                                        memo: `發文: ${title.substring(0, 20)}`,
                                        metadata: { type: "create_post" }
                                    }, {
                                        onReadyForServerApproval: async (paymentId) => {
                                            console.log('[CreatePost] onReadyForServerApproval', paymentId);
                                            try {
                                                await fetch('/api/user/payment/approve', {
                                                    method: 'POST',
                                                    headers: { 'Content-Type': 'application/json' },
                                                    body: JSON.stringify({ paymentId })
                                                });
                                            } catch (e) {
                                                console.error('[CreatePost] Approve failed:', e);
                                                // Don't throw here, let Pi SDK handle timeout if needed
                                            }
                                        },
                                        onReadyForServerCompletion: async (paymentId, txid) => {
                                            console.log('[CreatePost] onReadyForServerCompletion', paymentId, txid);
                                            txHash = txid; // CRITICAL: Capture txid immediately
                                            serverCompletionCalled = true;
                                            
                                            // Non-blocking call to server completion
                                            fetch('/api/user/payment/complete', {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ paymentId, txid })
                                            }).then(res => {
                                                console.log('[CreatePost] Server completion notified:', res.status);
                                            }).catch(err => {
                                                console.error('[CreatePost] Server completion notification failed (ignoring):', err);
                                            }).finally(() => {
                                                paymentComplete = true; // Mark done regardless of backend success
                                            });
                                        },
                                        onCancel: (paymentId) => {
                                            console.log('[CreatePost] Payment cancelled', paymentId);
                                            paymentError = 'CANCELLED';
                                        },
                                        onError: (error) => {
                                            console.error('[CreatePost] Payment error', error);
                                            paymentError = error?.message || 'ERROR';
                                        }
                                    });
                    
                                    // Wait for txHash (preferred) or paymentComplete flag
                                    console.log('[CreatePost] Waiting for payment result...');
                                    const startTime = Date.now();
                                    
                                    while (!txHash && !paymentError && (Date.now() - startTime) < 120000) {
                                        if (serverCompletionCalled && txHash) break; // We have what we need
                                        await new Promise(r => setTimeout(r, 500));
                                    }
                    
                                    if (paymentError) {
                                        showToast(paymentError === 'CANCELLED' ? '支付已取消' : '支付失敗', 'warning');
                                        resetButton();
                                        return;
                                    }

                                    if (!txHash) {
                                        console.error('[CreatePost] Payment timed out (no txHash)');
                                        showToast('支付超時或狀態異常，請聯繫管理員', 'warning');
                                        resetButton();
                                        return;
                                    }
                                    
                                    console.log('[CreatePost] Payment successful, txHash:', txHash);

                                } else {
                                    console.log('[CreatePost] Mock payment (Non-Pi Env)');
                                    txHash = "mock_" + Date.now();
                                }
                            } catch (paymentError) {
                                console.error('[CreatePost] Exception during payment setup:', paymentError);
                                showToast('支付過程中發生錯誤', 'error');
                                resetButton();
                                return;
                            }
                        }
                    
                        try {
                            const postData = {
                                board_slug: 'crypto',
                                category,
                                title,
                                content,
                                tags,
                                payment_tx_hash: txHash
                            };

                            console.log('[Forum] Sending post data:', postData);
                            const result = await ForumAPI.createPost(postData);
                            console.log('[Forum] Post created successfully:', result);

                            const container = document.getElementById('toast-container');
                            if (container) container.innerHTML = '';

                            // Success Modal
                            const successModal = document.createElement('div');
                            successModal.className = 'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                            successModal.innerHTML = `
                                <div class="bg-surface w-full max-w-sm p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in text-center">
                                    <div class="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-success/20">
                                        <i data-lucide="check-circle-2" class="w-8 h-8 text-success"></i>
                                    </div>
                                    <h3 class="text-xl font-bold text-secondary mb-2">發布成功！</h3>
                                    <div class="text-textMuted text-sm mb-6">
                                        您的文章已成功上鏈儲存。<br>
                                        <span class="text-primary animate-pulse">正在前往文章詳情頁...</span>
                                    </div>
                                    <button id="btn-go-now" class="w-full py-3.5 bg-gradient-to-r from-success/80 to-success text-background font-bold rounded-2xl transition shadow-lg transform active:scale-95">
                                        立即前往
                                    </button>
                                </div>
                            `;
                            document.body.appendChild(successModal);
                            if (window.lucide) lucide.createIcons();

                            // Determine redirect URL
                            const targetUrl = result.post_id 
                                ? `/static/forum/post.html?id=${result.post_id}` 
                                : '/static/forum/index.html';

                            // Redirect Action
                            const doRedirect = () => {
                                console.log('[Forum] Redirecting to:', targetUrl);
                                try {
                                    window.location.assign(targetUrl);
                                } catch (e) {
                                    window.location.href = targetUrl;
                                }
                            };

                            // Bind button
                            document.getElementById('btn-go-now').onclick = doRedirect;

                            // Auto redirect
                            setTimeout(doRedirect, 2000);

                            // Update button state (just in case)
                            if (submitBtn) {
                                submitBtn.disabled = true;
                                submitBtn.innerHTML = '<i class="w-4 h-4 animate-spin" data-lucide="loader-2"></i> Redirecting...';
                                if (window.lucide) lucide.createIcons();
                            }

                        } catch (err) {
                            console.error('[Forum] CreatePost API failed:', err);
                            // If payment was made but post failed, we should alert the user to copy their content
                            if (txHash && txHash !== "pro_member_free" && !txHash.startsWith("mock_")) {
                                alert(`發文失敗但支付可能已成功。\n請保存您的交易 ID: ${txHash}\n並聯繫管理員處理。\n\n錯誤: ${err.message}`);
                            } else {
                                showToast('發布失敗: ' + err.message, 'error');
                            }
                            resetButton();
                        }
                    });    },

    // ===========================================
    // Dashboard Logic
    // ===========================================
    async initDashboardPage() {
        console.log('initDashboardPage: Starting initialization');

        if (!AuthManager.currentUser) {
            window.location.href = '/static/forum/index.html';
            return;
        }

        const user = AuthManager.currentUser;
        
        const usernameEl = document.getElementById('nav-username');
        const avatarEl = document.getElementById('nav-avatar');
        
        if (usernameEl) {
            usernameEl.textContent = user.username || user.pi_username || 'User';
        }
        if (avatarEl && user.username) {
            avatarEl.innerHTML = `<span class="text-primary font-bold">${user.username[0].toUpperCase()}</span>`;
        }

        const loaders = [
            this.loadWalletStatus().catch(err => console.error('Wallet Status Load Failed:', err)),
            this.loadStats().catch(err => console.error('Stats Load Failed:', err)),
            this.loadMyPosts().catch(err => console.error('Posts Load Failed:', err)),
            this.loadTransactions().catch(err => console.error('Tx Load Failed:', err))
        ];

        await Promise.allSettled(loaders);
    },

    async loadWalletStatus() {
        const statusText = document.getElementById('wallet-status-text');
        const usernameEl = document.getElementById('wallet-username');
        const actionArea = document.getElementById('wallet-action-area');
        const iconEl = document.getElementById('wallet-icon');

        if (!statusText || !actionArea) return;

        if (typeof window.getWalletStatus !== 'function') {
            statusText.textContent = 'System Error (Auth)';
            statusText.classList.add('text-danger');
            return;
        }

        try {
            const status = await getWalletStatus();

            if (status.has_wallet || status.auth_method === 'pi_network') {
                statusText.textContent = '已連接';
                statusText.classList.remove('text-textMuted', 'text-danger');
                statusText.classList.add('text-success');
                
                if (iconEl) {
                    iconEl.classList.remove('bg-primary/20');
                    iconEl.classList.add('bg-success/20');
                    iconEl.innerHTML = '<i data-lucide="check-circle" class="w-7 h-7 text-success"></i>';
                }

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
                statusText.textContent = '未綁定';
                statusText.classList.remove('text-success', 'text-danger');
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
            statusText.textContent = '載入失敗';
            statusText.classList.add('text-danger');

            actionArea.innerHTML = `
                <button onclick="location.reload()" class="text-xs text-textMuted hover:text-white underline">
                    Retry
                </button>
            `;
        }
    },

    async loadStats() {
        try {
            const data = await ForumAPI.getMyStats();
            if (data.success && data.stats) {
                const s = data.stats;
                const postCountEl = document.getElementById('dash-post-count');
                const tipsRecEl = document.getElementById('dash-tips-received');
                
                if (postCountEl) postCountEl.textContent = s.post_count || 0;
                if (tipsRecEl) tipsRecEl.textContent = s.tips_received || 0; 
            }

            const sentData = await ForumAPI.getMyTipsSent();
            const tipsSentEl = document.getElementById('dash-tips-sent');
            if (tipsSentEl) {
                if (sentData.success && sentData.tips) {
                    const totalSent = sentData.tips.reduce((acc, tip) => acc + (tip.amount || 0), 0);
                    tipsSentEl.textContent = totalSent.toFixed(1); 
                } else {
                    tipsSentEl.textContent = "0";
                }
            }
        } catch (e) {
            console.error('loadStats error', e);
        }
    },

    async loadMyPosts() {
        const container = document.getElementById('dash-posts-list');
        if (!container) return;

        try {
            const data = await ForumAPI.getMyPosts();
            const posts = data.posts || [];

            container.innerHTML = '';
            if (posts.length === 0) {
                container.innerHTML = '<div class="text-center text-textMuted py-4">No posts yet</div>';
                return;
            }

            posts.forEach(post => {
                const el = document.createElement('div');
                el.className = 'flex items-center justify-between border-b border-white/5 pb-3 last:border-0 last:pb-0';
                
                const netVotes = (post.push_count || 0) - (post.boo_count || 0);
                
                el.innerHTML = `
                    <div class="overflow-hidden mr-4">
                         <a href="/static/forum/post.html?id=${post.id}" class="font-bold text-textMain hover:text-primary transition truncate block">${post.title}</a>
                         <div class="text-xs text-textMuted mt-1 flex items-center gap-2">
                            <span>${formatTWDate(post.created_at)}</span>
                            <span class="bg-white/10 px-1.5 rounded text-[10px] uppercase">${post.category}</span>
                         </div>
                    </div>
                    <div class="flex items-center gap-3 text-xs text-textMuted shrink-0">
                        <span class="flex items-center gap-1"><i data-lucide="message-square" class="w-3 h-3"></i> ${post.comment_count}</span>
                        <span class="flex items-center gap-1 ${netVotes > 0 ? 'text-success' : ''}"><i data-lucide="thumbs-up" class="w-3 h-3"></i> ${netVotes}</span>
                    </div>
                `;
                container.appendChild(el);
            });
            if (window.lucide) lucide.createIcons();
        } catch (e) {
            console.error('loadMyPosts error', e);
            container.innerHTML = '<div class="text-center text-danger py-4">Failed to load</div>';
        }
    },

    async loadTransactions() {
         const container = document.getElementById('dash-tx-list');
         if (!container) return;
         
         try {
             const [paymentsData, tipsSentData] = await Promise.all([
                 ForumAPI.getMyPayments(),
                 ForumAPI.getMyTipsSent()
             ]);

             const payments = (paymentsData.payments || [])
                 .filter(p => p.tx_hash !== 'pro_member_free')
                 .map(p => ({...p, type: 'post_payment', amount: -1.0})); 
             const tips = (tipsSentData.tips || []).map(t => ({...t, type: 'tip_sent', amount: -t.amount, title: `Tip: ${t.post_title || 'Post'}`}));
             
             const allTx = [...payments, ...tips].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
             
             container.innerHTML = '';
             if (allTx.length === 0) {
                 container.innerHTML = '<div class="text-center text-textMuted py-4">No transactions</div>';
                 return;
             }
             
             allTx.slice(0, 20).forEach((tx, idx) => { 
                 const el = document.createElement('div');
                 el.className = 'flex items-center justify-between border-b border-white/5 py-4 hover:bg-white/5 px-2 rounded-xl transition cursor-pointer last:border-0';
                 
                 el.dataset.txData = JSON.stringify(tx);
                 el.onclick = function() {
                     ForumApp.showTransactionDetail(tx);
                 };

                 let icon = 'credit-card';
                 let title = 'Payment';
                 
                 if (tx.type === 'post_payment') {
                     title = 'Post Fee';
                     icon = 'file-text';
                 } else if (tx.type === 'tip_sent') {
                     title = 'Tip Sent';
                     icon = 'gift';
                 }

                 el.innerHTML = `
                    <div class="flex items-center gap-3 overflow-hidden">
                         <div class="w-10 h-10 rounded-full bg-surfaceHighlight flex items-center justify-center shrink-0">
                            <i data-lucide="${icon}" class="w-5 h-5 text-textMuted"></i>
                         </div>
                         <div class="overflow-hidden">
                             <div class="font-bold text-textMain truncate">${title}</div>
                             <div class="text-xs text-textMuted mt-0.5">${formatTWDate(tx.created_at)}</div>
                         </div>
                    </div>
                    <div class="text-right shrink-0">
                        <div class="font-bold ${tx.amount < 0 ? 'text-danger' : 'text-success'}">${tx.amount.toFixed(1)} Pi</div>
                        <div class="text-[10px] text-textMuted font-mono opacity-50">${(tx.tx_hash || tx.payment_tx_hash || '').substring(0,8)}...</div>
                    </div>
                 `;
                 container.appendChild(el);
             });
             
             if (window.lucide) lucide.createIcons();
         } catch (e) {
             console.error('loadTransactions error', e);
             container.innerHTML = '<div class="text-center text-danger py-4">Failed to load</div>';
         }
    },

    showTransactionDetail(tx) {
        const txId = tx.tx_hash || tx.payment_tx_hash || 'N/A';
        const typeLabel = tx.type === 'post_payment' ? 'Post Publication Fee' : 'Article Tip Support';
        const status = 'Completed'; 
        const memo = tx.title || (tx.type === 'post_payment' ? 'Forum Posting Fee' : 'Tip to Author');

        const modal = document.createElement('div');
        modal.id = 'tx-detail-modal';
        modal.className = 'fixed inset-0 bg-background/90 backdrop-blur-md z-[110] flex items-center justify-center p-4 animate-fade-in';
        modal.innerHTML = `
            <div class="bg-surface w-full max-w-md p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="text-xl font-bold text-secondary">Transaction Detail</h3>
                    <button onclick="document.getElementById('tx-detail-modal').remove()" class="text-textMuted hover:text-white transition">
                        <i data-lucide="x" class="w-6 h-6"></i>
                    </button>
                </div>

                <div class="space-y-4">
                    <div class="text-center py-6 bg-background/50 rounded-2xl border border-white/5 mb-4">
                        <div class="text-textMuted text-xs uppercase font-bold tracking-widest mb-1">Amount</div>
                        <div class="text-3xl font-bold text-primary">${Math.abs(tx.amount).toFixed(1)} <span class="text-sm">Pi</span></div>
                    </div>

                    <div class="grid grid-cols-1 gap-4 text-sm">
                        <div class="flex justify-between border-b border-white/5 pb-2">
                            <span class="text-textMuted">Type</span>
                            <span class="text-secondary font-medium">${typeLabel}</span>
                        </div>
                        <div class="flex justify-between border-b border-white/5 pb-2">
                            <span class="text-textMuted">Status</span>
                            <span class="text-success font-bold flex items-center gap-1">
                                <i data-lucide="check-circle" class="w-3 h-3"></i> ${status}
                            </span>
                        </div>
                        <div class="flex justify-between border-b border-white/5 pb-2">
                            <span class="text-textMuted">Date</span>
                            <span class="text-secondary">${formatTWDate(tx.created_at, true)}</span>
                        </div>
                        <div class="flex flex-col gap-1 border-b border-white/5 pb-2">
                            <span class="text-textMuted">Transaction ID</span>
                            <span class="text-primary font-mono text-[10px] break-all bg-white/5 p-2 rounded-lg mt-1">${txId}</span>
                        </div>
                        <div class="flex flex-col gap-1">
                            <span class="text-textMuted">Memo / Note</span>
                            <span class="text-secondary italic text-xs bg-white/5 p-3 rounded-lg mt-1">"${memo}"</span>
                        </div>
                    </div>
                </div>

                <button onclick="document.getElementById('tx-detail-modal').remove()" 
                    class="w-full mt-8 py-4 bg-surfaceHighlight hover:bg-white/10 text-textMain font-bold rounded-2xl transition border border-white/5">
                    Close
                </button>
            </div>
        `;

        document.body.appendChild(modal);
        if (window.lucide) lucide.createIcons();
    }
};

// 暴露到全局
window.ForumApp = ForumApp;

// 確保在 DOM 載入後執行
document.addEventListener('DOMContentLoaded', () => {
    if (window.ForumApp) {
        ForumApp.init();
    } else {
        const checkApp = setInterval(() => {
            if (window.ForumApp) {
                clearInterval(checkApp);
                ForumApp.init();
            }
        }, 100);
    }
});
