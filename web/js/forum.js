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
    defaultTimeout: 15000, // 15 秒超時

    async _fetch(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.defaultTimeout);

        try {
            const res = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.detail || 'API request failed');
            }
            return await res.json();
        } catch (e) {
            clearTimeout(timeoutId);
            if (e.name === 'AbortError') {
                console.error(`ForumAPI Timeout (${endpoint}): Request exceeded ${this.defaultTimeout}ms`);
                throw new Error('請求超時，請檢查網路連線');
            }
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
        console.log('ForumApp: init starting...');
        try {
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

        // 檢查是否在 Pi Browser 環境
        const isPi = typeof isPiBrowser === 'function' ? isPiBrowser() : false;

        // 確認打賞
        const confirmed = await showConfirm({
            title: '確認打賞',
            message: isPi
                ? '確認打賞 1 Pi 給作者？\n將會開啟 Pi 支付流程。'
                : '確認打賞 1 Pi 給作者？\n（測試模式：非 Pi Browser 環境）',
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

                // 快速環境驗證
                if (typeof AuthManager.verifyPiBrowserEnvironment === 'function') {
                    const envCheck = await AuthManager.verifyPiBrowserEnvironment();
                    if (!envCheck.valid) {
                        showToast('Pi Browser 環境異常，請確認已登入 Pi 帳號', 'warning');
                        return;
                    }
                }

                // 認證 payments scope
                try {
                    await Pi.authenticate(['payments'], () => {});
                    console.log('[Tip] payments scope 認證成功');
                } catch (authErr) {
                    console.error('[Tip] payments scope 認證失敗', authErr);
                    showToast('支付權限不足，請重新登入', 'error');
                    return;
                }

                // 建立支付
                let paymentComplete = false;
                let paymentError = null;

                showToast('正在處理支付...', 'info', 0);

                await Pi.createPayment({
                    amount: 1.0,
                    memo: `打賞文章 #${postId}`,
                    metadata: { type: "tip", post_id: postId }
                }, {
                    onReadyForServerApproval: async (paymentId) => {
                        console.log('[Tip] onReadyForServerApproval', paymentId);
                        try {
                            await fetch('/api/user/payment/approve', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId })
                            });
                        } catch (e) {
                            console.error('[Tip] approve error', e);
                        }
                    },
                    onReadyForServerCompletion: async (paymentId, txid) => {
                        console.log('[Tip] onReadyForServerCompletion', paymentId, txid);
                        txHash = txid;
                        paymentComplete = true;
                        try {
                            await fetch('/api/user/payment/complete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId, txid })
                            });
                        } catch (e) {
                            console.error('[Tip] complete error', e);
                        }
                    },
                    onCancel: (paymentId) => {
                        console.log('[Tip] onCancel', paymentId);
                        paymentError = 'CANCELLED';
                    },
                    onError: (error) => {
                        console.error('[Tip] onError', error);
                        paymentError = error?.message || 'PAYMENT_ERROR';
                    }
                });

                // 等待支付完成（最多 120 秒）
                const startTime = Date.now();
                while (!paymentComplete && !paymentError && (Date.now() - startTime) < 120000) {
                    await new Promise(r => setTimeout(r, 300));
                }

                // 清除 loading toast
                const toastContainer = document.getElementById('toast-container');
                if (toastContainer) toastContainer.innerHTML = '';

                console.log('[Tip] 支付結果', { paymentComplete, paymentError, txHash });

                if (paymentError) {
                    showToast(paymentError === 'CANCELLED' ? '支付已取消' : '支付失敗', 'warning');
                    return;
                }

                if (!txHash) {
                    showToast('支付超時，請重試', 'warning');
                    return;
                }

            } else {
                // === 模擬支付（非 Pi Browser）===
                console.log('[Tip] 使用模擬支付');
                txHash = "mock_tip_" + Date.now();
            }

            // 後端記錄打賞
            await ForumAPI.tipPost(postId, 1, txHash);
            showToast('打賞成功！感謝您的支持', 'success');
            this.loadPostDetail(postId);

        } catch (e) {
            console.error('[Tip] 錯誤', e);
            showToast('打賞失敗: ' + e.message, 'error');
        }
    },

    // ===========================================
    // Create Post Logic (精簡版)
    // ===========================================
    initCreatePage() {
        const log = (msg, data = {}) => {
            const entry = `[${new Date().toISOString()}] ${msg} ${JSON.stringify(data)}`;
            console.log('[CreatePost]', msg, data);
            // 寫入後端日誌
            fetch('/api/debug/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: 'info', message: msg, data })
            }).catch(() => {});
        };

        log('Create Post Page Initialized');

        document.getElementById('post-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            log('=== 表單提交開始 ===');

            // 1. 檢查登入狀態
            if (!AuthManager?.currentUser) {
                log('未登入');
                showToast('請先登入', 'warning');
                return;
            }

            // 2. 取得表單數據
            const title = document.getElementById('input-title').value;
            const content = document.getElementById('input-content').value;
            const category = document.getElementById('input-category').value;
            const tagsStr = document.getElementById('input-tags').value;
            const tags = tagsStr.split(' ').map(t => t.replace('#', '').trim()).filter(t => t);

            log('表單數據', { title, category, tagsLength: tags.length });

            // 3. 支付流程
            const isPi = AuthManager.isPiBrowser();
            let txHash = "";

            try {
                if (isPi && window.Pi) {
                    // === Pi 真實支付 ===
                    log('開始 Pi 支付流程');

                    // 認證 payments scope
                    try {
                        await Pi.authenticate(['payments'], () => {});
                        log('payments scope 認證成功');
                    } catch (authErr) {
                        log('payments scope 認證失敗', { error: authErr.message });
                        showToast('支付權限不足，請重新登入', 'error');
                        return;
                    }

                    // 建立支付
                    let paymentComplete = false;
                    let paymentError = null;

                    await Pi.createPayment({
                        amount: 1.0,
                        memo: `發文: ${title.substring(0, 20)}`,
                        metadata: { type: "create_post" }
                    }, {
                        onReadyForServerApproval: async (paymentId) => {
                            log('onReadyForServerApproval', { paymentId });
                            await fetch('/api/user/payment/approve', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId })
                            });
                        },
                        onReadyForServerCompletion: async (paymentId, txid) => {
                            log('onReadyForServerCompletion', { paymentId, txid });
                            txHash = txid;
                            paymentComplete = true;
                            await fetch('/api/user/payment/complete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ paymentId, txid })
                            });
                        },
                        onCancel: (paymentId) => {
                            log('onCancel', { paymentId });
                            paymentError = 'CANCELLED';
                        },
                        onError: (error) => {
                            log('onError', { error: error?.message || error });
                            paymentError = error?.message || 'ERROR';
                        }
                    });

                    // 等待支付完成
                    const startTime = Date.now();
                    while (!paymentComplete && !paymentError && (Date.now() - startTime) < 120000) {
                        await new Promise(r => setTimeout(r, 300));
                    }

                    log('支付等待結束', { paymentComplete, paymentError, txHash });

                    if (paymentError || !txHash) {
                        showToast(paymentError === 'CANCELLED' ? '支付已取消' : '支付失敗', 'warning');
                        return;
                    }
                } else {
                    // === 模擬支付 ===
                    log('使用模擬支付（非 Pi Browser）');
                    txHash = "mock_" + Date.now();
                }

                // 4. 提交文章
                log('開始提交文章', { txHash });

                const postData = {
                    board_slug: 'crypto',
                    category,
                    title,
                    content,
                    tags,
                    payment_tx_hash: txHash
                };

                const result = await ForumAPI.createPost(postData);
                log('✅ 文章提交成功', { result });

                // 5. 顯示成功訊息
                log('準備顯示成功 Toast');

                // 清空舊 Toast
                const container = document.getElementById('toast-container');
                log('toast-container 存在?', { exists: !!container });
                if (container) container.innerHTML = '';

                // 顯示成功
                log('呼叫 showToast', { showToastExists: typeof showToast === 'function' });

                if (typeof showToast === 'function') {
                    showToast('🎉 發布成功！', 'success', 5000);
                    log('showToast 已執行');
                } else {
                    log('showToast 不存在，使用 alert');
                    alert('🎉 發布成功！');
                }

                // 6. 延遲跳轉
                log('設定 3 秒後跳轉');
                setTimeout(() => {
                    log('執行跳轉');
                    window.location.href = '/static/forum/index.html';
                }, 3000);

            } catch (err) {
                log('❌ 發生錯誤', { error: err.message, stack: err.stack });
                showToast('發布失敗: ' + err.message, 'error');
            }
        });
    },

    // ===========================================
    // Dashboard Logic
    // ===========================================
    async initDashboardPage() {
        DebugLog.info('initDashboardPage 被呼叫', {
            hasCurrentUser: !!AuthManager.currentUser,
            currentUser: AuthManager.currentUser
        });

        if (!AuthManager.currentUser) {
            DebugLog.warn('Dashboard: 用戶未登入，重定向到首頁');
            window.location.href = '/static/forum/index.html';
            return;
        }

        const uid = ForumAPI._getUserId();
        DebugLog.info('Dashboard 載入開始', {
            uid: uid,
            currentUser: AuthManager.currentUser
        });

        // Load Wallet Status (獨立錯誤處理)
        try {
            await this.loadWalletStatus();
            DebugLog.info('Dashboard Wallet 狀態載入完成');
        } catch (e) {
            DebugLog.error('Dashboard Wallet 狀態載入失敗', { error: e.message });
        }

        // Load Stats (獨立錯誤處理)
        try {
            DebugLog.info('Dashboard 獲取統計數據中...');
            const statsRes = await ForumAPI.getMyStats();
            DebugLog.info('Dashboard 統計數據回應', statsRes);
            const stats = statsRes.stats || {};
            document.getElementById('dash-post-count').textContent = stats.post_count || 0;
            document.getElementById('dash-tips-sent').textContent = stats.tips_sent || 0;
            document.getElementById('dash-tips-received').textContent = stats.tips_received || 0;
        } catch (e) {
            DebugLog.error('Dashboard 統計數據載入失敗', { error: e.message });
            document.getElementById('dash-post-count').textContent = 'Error';
        }

        // Load Posts (獨立錯誤處理)
        try {
            DebugLog.info('Dashboard 獲取文章列表中...');
            const postsRes = await ForumAPI.getMyPosts();
            DebugLog.info('Dashboard 文章列表回應', { count: postsRes.posts?.length || 0, posts: postsRes.posts });
            const postsList = document.getElementById('dash-posts-list');
            if (postsList && postsRes.posts && postsRes.posts.length > 0) {
                postsList.innerHTML = postsRes.posts.map(p => `
                    <div class="flex items-center justify-between border-b border-white/5 py-2">
                        <a href="/static/forum/post.html?id=${p.id}" class="text-sm hover:text-primary truncate">${p.title}</a>
                        <span class="text-xs text-textMuted">${formatTWDate(p.created_at)}</span>
                    </div>
                `).join('');
            } else if (postsList) {
                postsList.innerHTML = '<p class="text-textMuted text-sm">尚無文章</p>';
            }
        } catch (e) {
            DebugLog.error('Dashboard 文章列表載入失敗', { error: e.message });
        }

        // Load Transactions (Tips Sent) (獨立錯誤處理)
        try {
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
        DebugLog.info('loadWalletStatus 開始');

        const statusText = document.getElementById('wallet-status-text');
        const usernameEl = document.getElementById('wallet-username');
        const actionArea = document.getElementById('wallet-action-area');
        const iconEl = document.getElementById('wallet-icon');

        if (!statusText || !actionArea) {
            DebugLog.warn('loadWalletStatus: DOM 元素不存在');
            return;
        }

        // Safety check
        if (typeof window.getWalletStatus !== 'function') {
            DebugLog.error('getWalletStatus function missing');
            statusText.textContent = 'System Error (Auth)';
            statusText.classList.add('text-danger');
            return;
        }

        try {
            DebugLog.info('呼叫 getWalletStatus...');
            const status = await getWalletStatus();
            DebugLog.info('getWalletStatus 回應', status);

            if (status.has_wallet || status.auth_method === 'pi_network') {
                // 已綁定或 Pi 錢包登入
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
                // 未綁定
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
            DebugLog.info('loadWalletStatus 完成');
        } catch (e) {
            DebugLog.error('loadWalletStatus 錯誤', { error: e.message, stack: e.stack });
            statusText.textContent = '載入失敗';
            statusText.classList.add('text-danger');

            // Allow retry
            actionArea.innerHTML = `
                <button onclick="location.reload()" class="text-xs text-textMuted hover:text-white underline">
                    Retry
                </button>
            `;
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

// 顯示 Scope 錯誤的詳細彈窗
function showScopeErrorModal() {
    // 創建模態框
    const modal = document.createElement('div');
    modal.id = 'scope-error-modal';
    modal.className = 'fixed inset-0 bg-background/95 backdrop-blur-xl z-[100] flex items-center justify-center p-4';
    modal.innerHTML = `
        <div class="bg-surface w-full max-w-md p-6 rounded-3xl border border-danger/30 shadow-2xl">
            <div class="w-16 h-16 rounded-full bg-danger/20 flex items-center justify-center mx-auto mb-4">
                <i data-lucide="alert-triangle" class="w-8 h-8 text-danger"></i>
            </div>
            <h3 class="text-xl font-bold text-center text-secondary mb-2">支付權限不足</h3>
            <p class="text-textMuted text-center text-sm mb-4">
                您的帳號缺少「支付 (payments)」權限。這是因為您首次登入時沒有授權支付功能。
            </p>
            <div class="bg-surfaceHighlight rounded-xl p-4 mb-4 text-sm">
                <p class="font-bold text-primary mb-2">請按照以下步驟操作：</p>
                <ol class="list-decimal list-inside space-y-2 text-textMuted">
                    <li>打開 <span class="text-secondary">Pi Browser</span> 應用</li>
                    <li>點擊右下角的 <span class="text-secondary">選單 (三條線)</span></li>
                    <li>前往 <span class="text-secondary">Settings (設定)</span></li>
                    <li>找到 <span class="text-secondary">Connected Apps (已連接的應用)</span></li>
                    <li>找到本應用並點擊 <span class="text-danger">Revoke (撤銷)</span></li>
                    <li>回到本應用，重新登入</li>
                </ol>
            </div>
            <p class="text-xs text-textMuted text-center mb-4">
                重新登入時，請確認授權視窗中包含 <span class="text-primary">payments</span> 權限
            </p>
            <div class="flex gap-3">
                <button onclick="document.getElementById('scope-error-modal').remove()"
                    class="flex-1 py-3 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5">
                    稍後處理
                </button>
                <button onclick="localStorage.removeItem('pi_user');window.location.href=window.location.pathname+'?logout=1'"
                    class="flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg">
                    登出並重試
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    if (window.lucide) lucide.createIcons();
}

// 確保在 DOM 載入後執行
document.addEventListener('DOMContentLoaded', () => {
    // 檢查 ForumApp 是否就緒
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