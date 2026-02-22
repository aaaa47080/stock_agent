// ========================================
// forum.js - 論壇功能核心邏輯
// ========================================

// ============================================
// Pi 支付價格配置（從後端動態獲取）
// ============================================
window.PiPrices = {
    create_post: null,  // 完全依賴後端配置
    tip: null,
    premium: null,
    loaded: false
};

// ============================================
// 論壇限制配置（從後端動態獲取）
// ============================================
window.ForumLimits = {
    daily_post_free: null,
    daily_post_premium: null,
    daily_comment_free: null,
    daily_comment_premium: null,
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
    // 更新所有帶有 data-price 屬性的元素
    if (!window.PiPrices || !window.PiPrices.loaded) {
        console.log('[Forum] 價格尚未載入，跳過更新');
        return;
    }

    const priceElements = document.querySelectorAll('[data-price]');
    priceElements.forEach(el => {
        const priceKey = el.getAttribute('data-price');
        const price = window.PiPrices[priceKey];

        if (price !== undefined && price !== null) {
            el.textContent = `${price} Pi`;
        }
    });

    console.log('[Forum] 價格顯示已更新:', window.PiPrices);
}

// 從後端載入論壇限制配置
async function loadForumLimits() {
    if (window.ForumLimits.loading) return;
    window.ForumLimits.loading = true;

    try {
        const res = await fetch('/api/config/limits');
        if (res.ok) {
            const data = await res.json();
            window.ForumLimits = { ...data.limits, loaded: true, loading: false };
            console.log('[Forum] 論壇限制配置已載入:', window.ForumLimits);
            // 通知其他模組限制已更新
            document.dispatchEvent(new Event('forum-limits-updated'));
        } else {
            window.ForumLimits.loading = false;
        }
    } catch (e) {
        console.error('[Forum] 載入論壇限制配置失敗:', e);
        window.ForumLimits.loading = false;
    }
}

// 取得價格的輔助函數（確保有值）
function getPrice(key) {
    if (window.PiPrices?.loaded && window.PiPrices[key] !== null) {
        return window.PiPrices[key];
    }
    console.warn(`[Forum] 價格 ${key} 尚未載入，請確認 API 連線`);
    return null;
}

// 取得限制的輔助函數（確保有值）
function getLimit(key) {
    if (window.ForumLimits?.loaded && window.ForumLimits[key] !== undefined) {
        return window.ForumLimits[key];
    }
    console.warn(`[Forum] 限制 ${key} 尚未載入，請確認 API 連線`);
    return null;
}

// Helper to format date
function formatTWDate(dateStr, full = false) {
    if (!dateStr) return '';
    try {
        // Server stores UTC — append 'Z' if no timezone info so JS parses as UTC
        let normalized = dateStr;
        if (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+') && !/\d{2}:\d{2}:\d{2}-/.test(dateStr)) {
            normalized = dateStr.replace(' ', 'T') + 'Z';
        }
        const date = new Date(normalized);
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

    _getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            // 修正：使用 accessToken 而不是 token
            const token = AuthManager.currentUser.accessToken || AuthManager.currentUser.token || localStorage.getItem('auth_token');
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return headers;
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
        const userId = this._getUserId();
        const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
        const res = await fetch(`/api/forum/posts/${id}${query}`);
        return await res.json();
    },
    async createPost(data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts?user_id=${encodeURIComponent(userId)}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
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
            headers: this._getAuthHeaders(),
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

        const res = await fetch(`/api/forum/posts/${postId}/push?user_id=${userId}`, { method: 'POST', headers: this._getAuthHeaders() });
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

        const res = await fetch(`/api/forum/posts/${postId}/boo?user_id=${userId}`, { method: 'POST', headers: this._getAuthHeaders() });
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
            headers: this._getAuthHeaders(),
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

    // Delete Post
    async deletePost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`, {
            method: 'DELETE',
            headers: this._getAuthHeaders()
        });
        if (!res.ok) {
            let errorMsg = 'Failed to delete post';
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

    // Update Post
    async updatePost(postId, data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`, {
            method: 'PUT',
            headers: this._getAuthHeaders(),
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            let errorMsg = 'Failed to update post';
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
        const res = await fetch(`/api/forum/me/stats?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        return await res.json();
    },
    async getMyPosts() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/posts?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        return await res.json();
    },
    async getMyTipsSent() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/sent?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        return await res.json();
    },
    async getMyTipsReceived() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/received?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        return await res.json();
    },
    async getMyPayments() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/payments?user_id=${userId}`, {
            headers: this._getAuthHeaders()
        });
        return await res.json();
    },
    async checkLimits() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');

        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 5000); // 5s timeout

        try {
            const res = await fetch(`/api/forum/me/limits?user_id=${userId}`, {
                headers: this._getAuthHeaders(),
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

        // Ensure prices and limits are loaded
        if (!window.PiPrices.loaded) {
            loadPiPrices();
        }
        if (!window.ForumLimits.loaded) {
            loadForumLimits();
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
            else if (!page) {
                // SPA 模式：沒有 data-page 屬性，預設載入首頁
                console.log('ForumApp: SPA mode detected, loading index page');
                this.initIndexPage();
            }

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

        container.innerHTML = `<div class="flex flex-col items-center justify-center py-10 text-textMuted gap-2">
            <i class="animate-spin" data-lucide="loader-2"></i>
            <span>Loading...</span>
        </div>`;
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
                el.onclick = () => {
                    if (typeof smoothNavigate === 'function') {
                        smoothNavigate(`/static/forum/post.html?id=${post.id}`);
                    } else {
                        window.location.href = `/static/forum/post.html?id=${post.id}`;
                    }
                };

                // 標籤 HTML
                let tagsHtml = '';
                try {
                    if (post.tags) {
                        const tags = JSON.parse(post.tags);
                        tagsHtml = tags.map(tag =>
                            `<span class="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full mr-1">#${tag}</span>`
                        ).join('');
                    }
                } catch (e) { }

                // 日期格式化
                const date = formatTWDate(post.created_at);

                // 推噓數
                const pushCount = Math.max(0, post.push_count || 0);
                const booCount = Math.max(0, post.boo_count || 0);

                el.innerHTML = `
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold text-secondary bg-white/10 px-2 py-0.5 rounded uppercase">${post.category}</span>
                            <a href="/static/forum/profile.html?id=${post.user_id}" class="text-xs text-textMuted hover:text-primary transition" onclick="event.stopPropagation()">${post.username || post.user_id}</a>
                            <span class="text-xs text-textMuted">• ${date}</span>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-textMuted">
                            <span class="flex items-center gap-1 ${pushCount > 0 ? 'text-success' : ''}"><i data-lucide="thumbs-up" class="w-3 h-3"></i> ${pushCount}</span>
                            <span class="flex items-center gap-1 ${booCount > 0 ? 'text-danger' : ''}"><i data-lucide="thumbs-down" class="w-3 h-3"></i> ${booCount}</span>
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
            if (typeof smoothNavigate === 'function') {
                smoothNavigate('/static/forum/index.html');
            } else {
                window.location.href = '/static/forum/index.html';
            }
            return;
        }

        this.currentPostId = postId;
        await this.loadPostDetail(postId);
        await this.loadComments(postId);

        // 綁定按鈕事件 - 使用克隆替換法防止重複綁定
        const bindButton = (id, handler) => {
            const btn = document.getElementById(id);
            if (btn) {
                const newBtn = btn.cloneNode(true);
                btn.parentNode.replaceChild(newBtn, btn);
                newBtn.addEventListener('click', handler);
            }
        };

        bindButton('btn-push', () => this.handlePush(postId));
        bindButton('btn-boo', () => this.handleBoo(postId));
        bindButton('btn-reply', () => this.toggleReplyForm());
        bindButton('btn-tip', () => this.handleTip(postId));
        bindButton('submit-reply', () => this.submitReply(postId));
        bindButton('btn-delete', () => this.handleDelete(postId));
        bindButton('btn-edit', () => this.handleEdit(postId));
    },

    async loadPostDetail(id) {
        try {
            const response = await ForumAPI.getPost(id);
            const post = response.post;

            // 保存當前文章對象，用於後續檢查（如打賞時檢查作者）
            this.currentPost = post;

            document.title = `${post.title} - Pi Forum`;

            document.getElementById('post-category').textContent = post.category;
            document.getElementById('post-title').textContent = post.title;

            // 安全地創建作者鏈接（防止 XSS）
            const authorContainer = document.getElementById('post-author');
            authorContainer.innerHTML = '';
            if (typeof SecurityUtils !== 'undefined') {
                const authorLink = SecurityUtils.createSafeLink(
                    `/static/forum/profile.html?id=${SecurityUtils.encodeURL(post.user_id)}`,
                    post.username || post.user_id,
                    { className: 'hover:text-primary transition' }
                );
                authorContainer.appendChild(authorLink);
            } else {
                // Fallback: 使用 textContent
                const authorLink = document.createElement('a');
                authorLink.href = `/static/forum/profile.html?id=${encodeURIComponent(post.user_id)}`;
                authorLink.textContent = post.username || post.user_id;
                authorLink.className = 'hover:text-primary transition';
                authorContainer.appendChild(authorLink);
            }

            document.getElementById('post-date').textContent = formatTWDate(post.created_at, true);

            // 安全地渲染 Markdown 內容（防止 XSS）
            const contentContainer = document.getElementById('post-content');
            if (typeof SecurityUtils !== 'undefined') {
                // 使用 SecurityUtils 安全渲染
                contentContainer.innerHTML = SecurityUtils.renderMarkdownSafely(post.content);
            } else {
                // Fallback: 基本的 markdown 渲染
                const md = window.markdownit ? window.markdownit({ html: false }) : { render: t => t };
                contentContainer.innerHTML = md.render(post.content);
            }

            // Tags
            const tagsContainer = document.getElementById('post-tags');
            if (post.tags && tagsContainer) {
                try {
                    const tags = JSON.parse(post.tags);
                    tagsContainer.innerHTML = tags.map(tag =>
                        `<span class="text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">#${tag}</span>`
                    ).join('');
                } catch (e) { }
            }

            // 顯示作者操作按鈕（編輯/刪除）
            this.updateAuthorActions(post);

            // Stats
            this.updatePostStats(post);

            // Re-render icons
            if (window.lucide) window.lucide.createIcons();

        } catch (e) {
            showToast('文章載入失敗', 'error');
            console.error(e);
        }
    },

    updateAuthorActions(post) {
        const currentUserId = AuthManager.currentUser?.user_id || AuthManager.currentUser?.uid;
        const isAuthor = currentUserId && post.user_id && currentUserId === post.user_id;

        // 尋找或創建作者操作按鈕容器
        let actionsContainer = document.getElementById('author-actions');
        if (!actionsContainer) {
            // 在標題下方插入操作按鈕容器
            const titleEl = document.getElementById('post-title');
            if (titleEl) {
                actionsContainer = document.createElement('div');
                actionsContainer.id = 'author-actions';
                actionsContainer.className = 'flex gap-2 mt-4 mb-4';
                titleEl.parentNode.insertBefore(actionsContainer, titleEl.nextSibling);
            }
        }

        if (actionsContainer) {
            if (isAuthor) {
                actionsContainer.innerHTML = `
                    <button id="btn-edit"
                        class="bg-white/5 hover:bg-white/10 text-secondary px-3 py-1.5 rounded-lg flex items-center gap-2 transition text-sm border border-white/10">
                        <i data-lucide="edit-2" class="w-3.5 h-3.5"></i>
                        <span>編輯</span>
                    </button>
                    <button id="btn-delete"
                        class="bg-danger/10 hover:bg-danger/20 text-danger px-3 py-1.5 rounded-lg flex items-center gap-2 transition text-sm border border-danger/20">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        <span>刪除</span>
                    </button>
                `;
            } else {
                actionsContainer.innerHTML = '';
            }
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
                        <a href="/static/forum/profile.html?id=${comment.user_id}" class="font-bold text-sm text-secondary hover:text-primary transition">${comment.username || comment.user_id}</a>
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-textMuted">${formatTWDate(comment.created_at, true)}</span>
                            <button onclick="ForumApp.openReportModal('comment', ${comment.id})" class="text-textMuted hover:text-danger p-1 rounded transition" title="Report">
                                <i data-lucide="flag" class="w-3 h-3"></i>
                            </button>
                        </div>
                    </div>
                    <div class="text-textMain text-sm">${comment.content}</div>
                `;
                container.appendChild(el);
            });
            if (window.lucide) lucide.createIcons();
        } catch (e) {
            console.error(e);
        }
    },

    async handlePush(postId) {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        const post = this.currentPost;
        if (!post) return;

        // Optimistic UI update
        const wasPush = post.viewer_vote === 'push';
        const wasBoo = post.viewer_vote === 'boo';
        if (wasPush) {
            post.push_count = Math.max(0, (post.push_count || 0) - 1);
            post.viewer_vote = null;
        } else {
            post.push_count = (post.push_count || 0) + 1;
            if (wasBoo) post.boo_count = Math.max(0, (post.boo_count || 0) - 1);
            post.viewer_vote = 'push';
        }
        this.updatePostStats(post);

        try {
            await ForumAPI.pushPost(postId);
        } catch (e) {
            // Revert on failure
            if (wasPush) {
                post.push_count = (post.push_count || 0) + 1;
                post.viewer_vote = 'push';
            } else {
                post.push_count = Math.max(0, (post.push_count || 0) - 1);
                if (wasBoo) post.boo_count = (post.boo_count || 0) + 1;
                post.viewer_vote = wasBoo ? 'boo' : null;
            }
            this.updatePostStats(post);
            showToast(e.message, 'error');
        }
    },

    async handleBoo(postId) {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        const post = this.currentPost;
        if (!post) return;

        // Optimistic UI update
        const wasBoo = post.viewer_vote === 'boo';
        const wasPush = post.viewer_vote === 'push';
        if (wasBoo) {
            post.boo_count = Math.max(0, (post.boo_count || 0) - 1);
            post.viewer_vote = null;
        } else {
            post.boo_count = (post.boo_count || 0) + 1;
            if (wasPush) post.push_count = Math.max(0, (post.push_count || 0) - 1);
            post.viewer_vote = 'boo';
        }
        this.updatePostStats(post);

        try {
            await ForumAPI.booPost(postId);
        } catch (e) {
            // Revert on failure
            if (wasBoo) {
                post.boo_count = (post.boo_count || 0) + 1;
                post.viewer_vote = 'boo';
            } else {
                post.boo_count = Math.max(0, (post.boo_count || 0) - 1);
                if (wasPush) post.push_count = (post.push_count || 0) + 1;
                post.viewer_vote = wasPush ? 'push' : null;
            }
            this.updatePostStats(post);
            showToast(e.message, 'error');
        }
    },

    toggleReplyForm() {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');
        const form = document.getElementById('reply-form');
        form.classList.toggle('hidden');
    },

    async submitReply(postId) {
        // 防連點保護：如果正在提交中，直接返回
        if (this.isSubmittingReply) {
            console.log('[submitReply] 🚫 Already submitting, ignoring duplicate click');
            return;
        }

        const content = document.getElementById('reply-content').value;
        if (!content) return;

        const submitBtn = document.getElementById('submit-reply');

        try {
            // 設置提交中標誌
            this.isSubmittingReply = true;

            // 禁用按鈕並顯示載入狀態
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<div class="flex items-center gap-2 justify-center"><svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>發送中</span></div>';
            }

            await ForumAPI.createComment(postId, { type: 'comment', content });

            // 清空輸入框並關閉回覆表單
            document.getElementById('reply-content').value = '';
            this.toggleReplyForm();

            // 重新載入評論列表
            this.loadComments(postId);

            showToast('評論發送成功', 'success');
        } catch (e) {
            showToast(e.message, 'error');
        } finally {
            // 恢復按鈕狀態並清除提交中標誌
            this.isSubmittingReply = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<div class="flex items-center gap-2 justify-center"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg><span>送出評論</span></div>';
            }
        }
    },

    async handleDelete(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請先登入', 'warning');
        }

        // 確認刪除
        const confirmed = await showConfirm({
            title: '確認刪除',
            message: '確定要刪除這篇文章嗎？\n刪除後將無法恢復。',
            type: 'warning',
            confirmText: '確認刪除',
            cancelText: '取消'
        });

        if (!confirmed) return;

        const btnElement = document.getElementById('btn-delete');
        if (btnElement) {
            btnElement.disabled = true;
            btnElement.classList.add('opacity-50', 'cursor-not-allowed');
        }

        try {
            await ForumAPI.deletePost(postId);
            showToast('文章已刪除', 'success');

            // 延遲後導航回首頁
            setTimeout(() => {
                if (typeof smoothNavigate === 'function') {
                    smoothNavigate('/static/forum/index.html');
                } else {
                    window.location.href = '/static/forum/index.html';
                }
            }, 1000);
        } catch (e) {
            if (btnElement) {
                btnElement.disabled = false;
                btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
            }
            showToast('刪除失敗: ' + e.message, 'error');
        }
    },

    async handleEdit(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請先登入', 'warning');
        }

        // TODO: 實現編輯功能 - 可以創建一個編輯模態框或導航到編輯頁面
        showToast('編輯功能開發中', 'info');
    },

    async handleTip(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請先登入', 'warning');
        }

        // 檢查是否在打賞自己的文章
        const currentUserId = AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
        const postAuthorId = this.currentPost?.user_id;

        if (currentUserId && postAuthorId && currentUserId === postAuthorId) {
            return showToast('不能打賞自己的文章', 'warning');
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
                    await Pi.authenticate(['payments'], () => { });
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
                    // 使用後端返回的限制，fallback 使用動態載入的配置
                    const defaultLimit = getLimit('daily_post_free');
                    const postLimit = limitsData.limits?.post || { count: 0, limit: defaultLimit, remaining: defaultLimit };

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
                            const total = postLimit.limit !== null ? postLimit.limit : (getLimit('daily_post_free') || 0);
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
                            const postAmount = getPrice('create_post');
                            if (postAmount !== null) {
                                paySpan.innerHTML = `Pay <span class="font-bold text-white">${postAmount}</span> Pi & Post`;
                            }
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

        // 初始化字數統計功能
        const initCharCounters = () => {
            const titleInput = document.getElementById('input-title');
            const contentInput = document.getElementById('input-content');
            const titleCurrent = document.getElementById('title-current');
            const contentCurrent = document.getElementById('content-current');
            const titleMax = document.getElementById('title-max');
            const contentMax = document.getElementById('content-max');

            // 從後端配置獲取限制（與後端保持一致）
            const MAX_TITLE = 200;
            const MAX_CONTENT = 10000;

            // 更新顯示的最大值
            if (titleMax) titleMax.textContent = MAX_TITLE;
            if (contentMax) contentMax.textContent = MAX_CONTENT;

            // 標題字數統計
            if (titleInput && titleCurrent) {
                const updateTitleCount = () => {
                    const count = titleInput.value.length;
                    titleCurrent.textContent = count;

                    // 顏色變化提示
                    const titleCounter = document.getElementById('title-counter');
                    if (count > MAX_TITLE * 0.9) {
                        titleCurrent.className = 'text-danger font-bold';
                        titleCounter?.classList.add('border-danger/30');
                    } else if (count > MAX_TITLE * 0.7) {
                        titleCurrent.className = 'text-warning font-bold';
                        titleCounter?.classList.remove('border-danger/30');
                    } else {
                        titleCurrent.className = 'text-primary font-bold';
                        titleCounter?.classList.remove('border-danger/30');
                    }
                };

                titleInput.addEventListener('input', updateTitleCount);
                titleInput.addEventListener('paste', () => setTimeout(updateTitleCount, 10));
                updateTitleCount(); // 初始化
            }

            // 內容字數統計
            if (contentInput && contentCurrent) {
                const updateContentCount = () => {
                    const count = contentInput.value.length;
                    contentCurrent.textContent = count;

                    // 顏色變化提示
                    const contentCounter = document.getElementById('content-counter');
                    if (count > MAX_CONTENT * 0.9) {
                        contentCurrent.className = 'text-danger font-bold';
                        contentCounter?.classList.add('border-danger/30');
                    } else if (count > MAX_CONTENT * 0.7) {
                        contentCurrent.className = 'text-warning font-bold';
                        contentCounter?.classList.remove('border-danger/30');
                    } else {
                        contentCurrent.className = 'text-primary font-bold';
                        contentCounter?.classList.remove('border-danger/30');
                    }
                };

                contentInput.addEventListener('input', updateContentCount);
                contentInput.addEventListener('paste', () => setTimeout(updateContentCount, 10));
                updateContentCount(); // 初始化
            }

            console.log('[CharCounter] Character counters initialized');
        };

        // 執行初始化
        initCharCounters();

        document.getElementById('post-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            console.log('[CreatePost] V38 Handler Active');
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

            const postAmount = getPrice('create_post');
            if (postAmount === null) {
                showToast('價格配置載入失敗，請重新整理頁面', 'error');
                resetButton();
                return;
            }
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
                                                    <button onclick="smoothNavigate('/static/forum/premium.html')" class="w-full py-3.5 bg-gradient-to-r from-primary to-primary/80 hover:to-primary text-background font-bold rounded-2xl transition shadow-lg flex items-center justify-center gap-2 transform active:scale-95">
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
                // 關鍵修復：檢查真實的 Pi Browser UA，而非僅檢查 SDK 存在
                const userAgent = navigator.userAgent || '';
                const isRealPiBrowser = userAgent.includes('PiBrowser');

                console.log('[CreatePost] 🔍 Environment:', {
                    ua: userAgent.substring(0, 60),
                    hasPiUA: isRealPiBrowser,
                    hasSDK: typeof window.Pi !== 'undefined'
                });

                try {
                    if (isRealPiBrowser && window.Pi) {
                        console.log('[CreatePost] 💳 Real Pi Browser - Starting payment...');
                        try {
                            await Pi.authenticate(['payments'], () => { });
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

                // Redirect Action (with smooth transition)
                const doRedirect = () => {
                    console.log('[Forum] Redirecting to:', targetUrl);
                    if (typeof smoothNavigate === 'function') {
                        smoothNavigate(targetUrl);
                    } else {
                        try {
                            window.location.assign(targetUrl);
                        } catch (e) {
                            window.location.href = targetUrl;
                        }
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
                    // 顯示友好的錯誤 Modal 而非 alert
                    const errorModal = document.createElement('div');
                    errorModal.className = 'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                    errorModal.innerHTML = `
                        <div class="bg-surface w-full max-w-md p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in">
                            <div class="w-16 h-16 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-danger/20">
                                <i data-lucide="alert-triangle" class="w-8 h-8 text-danger"></i>
                            </div>
                            <h3 class="text-xl font-bold text-secondary mb-3 text-center">發文失敗但支付已完成</h3>
                            <div class="text-textMuted text-sm mb-4 leading-relaxed">
                                <p class="mb-2">您的支付已成功，但文章發布失敗。請保存以下交易 ID 並聯繫客服處理：</p>
                                <div class="bg-background/50 p-3 rounded-xl border border-white/10 mb-3">
                                    <div class="text-xs text-textMuted mb-1">交易 ID</div>
                                    <div class="text-textMain font-mono text-xs break-all" id="error-txhash">${txHash}</div>
                                </div>
                                <p class="text-xs opacity-60">錯誤訊息：${err.message}</p>
                            </div>
                            <div class="flex flex-col gap-2">
                                <button id="copy-txhash-btn" class="w-full py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg flex items-center justify-center gap-2">
                                    <i data-lucide="copy" class="w-4 h-4"></i>
                                    <span>複製交易 ID</span>
                                </button>
                                <button onclick="this.closest('.fixed').remove()" class="w-full py-3 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5">
                                    關閉
                                </button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(errorModal);
                    if (window.lucide) lucide.createIcons();

                    // 複製功能
                    document.getElementById('copy-txhash-btn').onclick = () => {
                        navigator.clipboard.writeText(txHash).then(() => {
                            showToast('交易 ID 已複製', 'success');
                        }).catch(() => {
                            // Fallback for older browsers
                            const textArea = document.createElement('textarea');
                            textArea.value = txHash;
                            document.body.appendChild(textArea);
                            textArea.select();
                            document.execCommand('copy');
                            document.body.removeChild(textArea);
                            showToast('交易 ID 已複製', 'success');
                        });
                    };
                } else {
                    showToast('發布失敗: ' + err.message, 'error');
                }
                resetButton();
            }
        });
    },

    // ===========================================
    // Dashboard Logic
    // ===========================================
    async initDashboardPage() {
        console.log('initDashboardPage: Starting initialization');

        if (!AuthManager.currentUser) {
            if (typeof smoothNavigate === 'function') {
                smoothNavigate('/static/forum/index.html');
            } else {
                window.location.href = '/static/forum/index.html';
            }
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

                const pushCount = Math.max(0, post.push_count || 0);

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
                        <span class="flex items-center gap-1 ${pushCount > 0 ? 'text-success' : ''}"><i data-lucide="thumbs-up" class="w-3 h-3"></i> ${pushCount}</span>
                        <span class="flex items-center gap-1 ${post.boo_count > 0 ? 'text-danger' : ''}"><i data-lucide="thumbs-down" class="w-3 h-3"></i> ${post.boo_count || 0}</span>
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
            // 使用 Promise.allSettled 確保部分 API 失敗時仍能顯示可用數據
            const results = await Promise.allSettled([
                ForumAPI.getMyPayments(),
                ForumAPI.getMyTipsSent()
            ]);

            // 記錄失敗的 API
            results.forEach((result, index) => {
                if (result.status === 'rejected') {
                    const apiNames = ['getMyPayments', 'getMyTipsSent'];
                    console.warn(`[Dashboard] ${apiNames[index]} failed:`, result.reason);
                }
            });

            // 提取數據，失敗時使用空數組
            const paymentsData = results[0].status === 'fulfilled' ? results[0].value : { payments: [] };
            const tipsSentData = results[1].status === 'fulfilled' ? results[1].value : { tips: [] };

            const payments = (paymentsData.payments || [])
                // 保留 PRO 會員免費發文記錄但標記為免費
                .map(p => {
                    const isFree = p.tx_hash === 'pro_member_free';
                    return {
                        ...p,
                        type: isFree ? 'post_payment_free' : 'post_payment',
                        amount: isFree ? 0 : -(p.amount || getPrice('create_post') || 0),
                        isFree: isFree
                    };
                });
            const tips = (tipsSentData.tips || []).map(t => ({ ...t, type: 'tip_sent', amount: -t.amount, title: `Tip: ${t.post_title || 'Post'}` }));

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
                el.onclick = function () {
                    ForumApp.showTransactionDetail(tx);
                };

                let icon = 'credit-card';
                let title = 'Payment';

                if (tx.type === 'post_payment') {
                    icon = 'file-text';
                    title = 'Post Fee';
                } else if (tx.type === 'post_payment_free') {
                    icon = 'file-text';
                    title = 'Post (FREE)';
                } else if (tx.type === 'tip_sent') {
                    icon = 'gift';
                    title = tx.title || 'Tip Sent';
                }

                const amountClass = tx.isFree ? 'text-success' : (tx.amount < 0 ? 'text-danger' : 'text-success');
                const amountText = tx.isFree ? 'FREE' : `${tx.amount > 0 ? '+' : ''}${Math.abs(tx.amount).toFixed(1)} Pi`;

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
                         <div class="font-bold ${amountClass}">${amountText}</div>
                         <div class="text-[10px] text-textMuted opacity-60 mt-0.5">${formatTWDate(tx.created_at)}</div>
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
    },

    // ===========================================
    // Reporting Logic
    // ===========================================
    openReportModal(type, id) {
        if (!AuthManager.currentUser) return showToast('請先登入', 'warning');

        const modal = document.getElementById('report-modal');
        if (!modal) return;

        document.getElementById('report-content-type').value = type;
        document.getElementById('report-content-id').value = id;
        document.getElementById('report-type').value = '';
        document.getElementById('report-description').value = '';

        // Clear previous errors
        const errorDiv = document.getElementById('report-error');
        if (errorDiv) errorDiv.classList.add('hidden');

        modal.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
    },

    closeReportModal() {
        const modal = document.getElementById('report-modal');
        if (modal) modal.classList.add('hidden');
    },

    async submitReport() {
        const contentType = document.getElementById('report-content-type').value;
        const contentId = document.getElementById('report-content-id').value;
        const reportType = document.getElementById('report-type').value;
        const description = document.getElementById('report-description').value;

        const errorDiv = document.getElementById('report-error');
        const errorMsg = document.getElementById('report-error-msg');

        const showError = (msg) => {
            if (errorDiv && errorMsg) {
                errorMsg.textContent = msg;
                errorDiv.classList.remove('hidden');
            } else {
                showToast(msg, 'error');
            }
        };

        if (!reportType) {
            return showError('請選擇違規類型');
        }

        const btn = document.getElementById('btn-submit-report');
        if (!btn) return;

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="animate-spin" data-lucide="loader-2"></i> Submitting...';
        if (window.lucide) lucide.createIcons();

        // Clear previous error
        if (errorDiv) errorDiv.classList.add('hidden');

        try {
            const res = await fetch('/api/governance/reports', {
                method: 'POST',
                headers: ForumAPI._getAuthHeaders(),
                body: JSON.stringify({
                    content_type: contentType,
                    content_id: parseInt(contentId),
                    report_type: reportType,
                    description: description
                })
            });

            if (res.ok) {
                showToast('舉報提交成功，我們會盡快審核', 'success');
                this.closeReportModal();
            } else {
                const err = await res.json();
                showError(err.detail || '提交失敗');
            }
        } catch (e) {
            showError('提交失敗: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
            if (window.lucide) lucide.createIcons();
        }
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
