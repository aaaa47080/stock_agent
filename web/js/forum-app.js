// ============================================
// Forum App Logic
// ============================================
import { loadPiPrices, loadForumLimits, getPrice, getLimit, formatTWDate } from './forum-config.js';

function normalizePostTags(rawTags) {
    if (!rawTags) return [];
    if (Array.isArray(rawTags)) return rawTags.filter(Boolean);
    if (typeof rawTags === 'string') {
        try {
            const parsed = JSON.parse(rawTags);
            return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
        } catch {
            return [];
        }
    }
    return [];
}

const ForumApp = {
    rememberForumReturnTarget() {
        const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        try {
            if (current.includes('/static/forum/post.html')) return;

            if (current.includes('/static/forum/index.html')) {
                sessionStorage.setItem('forumBackHref', '/static/forum/index.html');
                return;
            }

            if (current.includes('/static/index.html')) {
                sessionStorage.setItem('forumBackHref', '/static/index.html#forum');
                return;
            }

            sessionStorage.setItem('forumBackHref', current || '/static/forum/index.html');
        } catch (e) {
            console.warn('[Forum] Failed to remember return target:', e);
        }
    },

    navigateToPost(postId) {
        this.rememberForumReturnTarget();
        const target = `/static/forum/post.html?id=${postId}`;
        if (typeof smoothNavigate === 'function') {
            smoothNavigate(target);
        } else {
            window.location.href = target;
        }
    },

    init() {
        // Ensure prices and limits are loaded
        if (!window.PiPrices?.loaded) {
            loadPiPrices();
        }
        if (!window.ForumLimits?.loaded) {
            loadForumLimits();
        }

        try {
            this.bindEvents();
            // ?�面?��??��???
            const page = document.body.dataset.page;
            window.APP_CONFIG?.DEBUG_MODE && console.log('ForumApp: page detected', page);

            if (page === 'index') this.initIndexPage();
            else if (page === 'post') this.initPostPage();
            else if (page === 'create') this.initCreatePage();
            else if (page === 'dashboard') this.initDashboardPage();
            // SPA mode (no data-page attribute): load forum content when switching tabs
            else this.initIndexPage();

            this.updateAuthUI();
        } catch (err) {
            console.error('ForumApp: Init failed', err);
        }
    },

    bindEvents() {
        // ?��?事件??��
        document.addEventListener('auth:login', () => this.updateAuthUI());
    },

    updateAuthUI() {
        const user = AuthManager.currentUser;
        const authElements = document.querySelectorAll('.auth-only');
        const guestElements = document.querySelectorAll('.guest-only');

        if (user) {
            authElements.forEach((el) => el.classList.remove('hidden'));
            guestElements.forEach((el) => el.classList.add('hidden'));

            // ?�新?�戶顯示?�稱
            const nameEls = document.querySelectorAll('.user-display-name');
            nameEls.forEach((el) => (el.textContent = user.username));
        } else {
            authElements.forEach((el) => el.classList.add('hidden'));
            guestElements.forEach((el) => el.classList.remove('hidden'));
        }
    },

    // ===========================================
    // Index Page Logic
    // ===========================================
    async initIndexPage() {
        this.currentTagFilter = '';
        this.loadBoards();
        this.loadPosts();
        this.loadTrendingTags();
        this.updatePostFiltersUI();

        // ?��?/篩選??��
        document.getElementById('category-filter')?.addEventListener('change', (e) => {
            this.loadPosts({
                category: e.target.value,
                tag: this.currentTagFilter || undefined,
            });
            this.updatePostFiltersUI();
        });
        document.getElementById('clear-post-filters')?.addEventListener('click', () => {
            this.currentTagFilter = '';
            const categoryFilter = document.getElementById('category-filter');
            if (categoryFilter) categoryFilter.value = '';
            this.loadPosts();
            this.loadTrendingTags();
            this.updatePostFiltersUI();
        });
    },

    updatePostFiltersUI() {
        const activeFilters = document.getElementById('active-post-filters');
        const activeFiltersText = document.getElementById('active-post-filters-text');
        if (!activeFilters || !activeFiltersText) return;

        const category = document.getElementById('category-filter')?.value || '';
        const parts = [];
        if (category) parts.push(`Category: ${category}`);
        if (this.currentTagFilter) parts.push(`#${this.currentTagFilter}`);

        if (parts.length === 0) {
            activeFilters.classList.add('hidden');
            activeFiltersText.textContent = '';
            return;
        }

        activeFilters.classList.remove('hidden');
        activeFiltersText.textContent = parts.join(' · ');
    },

    getFilteredEmptyStateMessage() {
        const category = document.getElementById('category-filter')?.value || '';
        if (this.currentTagFilter && category) {
            return `No posts found for #${this.currentTagFilter} in ${category}.`;
        }
        if (this.currentTagFilter) {
            return `No posts found for #${this.currentTagFilter}.`;
        }
        if (category) {
            return `No posts found in ${category}.`;
        }
        return 'No posts yet.';
    },

    async loadBoards() {
        try {
            const boards = await ForumAPI.getBoards();
            // 渲�??�板?�表 (如�??��?�?
        } catch (e) {
            console.error('Error loading boards:', e);
            if (typeof showToast === 'function') showToast('?�板載入失�?，�?稍�??�試', 'error');
        }
    },

    async loadPosts(filters = {}) {
        const container = document.getElementById('post-list');
        if (!container) return;

        container.innerHTML = `<div class="py-12 text-center text-textMuted/50">
            <i class="animate-spin inline-block" data-lucide="loader-2"></i>
        </div>`;
        AppUtils.refreshIcons();

        try {
            const response = await ForumAPI.getPosts(filters);
            const posts = response.posts || [];
            this.updatePostFiltersUI();

            container.innerHTML = '';

            if (posts.length === 0) {
                container.innerHTML =
                    `<div class="py-16 text-center text-textMuted/50 text-sm">${this.getFilteredEmptyStateMessage()}</div>`;
                return;
            }

            // Category color config for post cards
            const CATEGORY_COLORS = {
                analysis: { rail: 'bg-amber-400',   avatar: 'bg-amber-400/20 text-amber-400',   tag: 'bg-amber-400/10 text-amber-400/80',   badge: 'text-amber-400/90' },
                question: { rail: 'bg-blue-400',    avatar: 'bg-blue-400/20 text-blue-400',     tag: 'bg-blue-400/10 text-blue-400/80',     badge: 'text-blue-400/90' },
                tutorial: { rail: 'bg-emerald-400', avatar: 'bg-emerald-400/20 text-emerald-400',tag: 'bg-emerald-400/10 text-emerald-400/80',badge: 'text-emerald-400/90' },
                news:     { rail: 'bg-violet-400',  avatar: 'bg-violet-400/20 text-violet-400', tag: 'bg-violet-400/10 text-violet-400/80', badge: 'text-violet-400/90' },
                chat:     { rail: 'bg-rose-400',    avatar: 'bg-rose-400/20 text-rose-400',     tag: 'bg-rose-400/10 text-rose-400/80',     badge: 'text-rose-400/90' },
                insight:  { rail: 'bg-cyan-400',    avatar: 'bg-cyan-400/20 text-cyan-400',     tag: 'bg-cyan-400/10 text-cyan-400/80',     badge: 'text-cyan-400/90' },
            };
            const DEFAULT_COLORS = { rail: 'bg-[#d4b693]', avatar: 'bg-[#d4b693]/20 text-[#d4b693]', tag: 'bg-[#d4b693]/10 text-[#d4b693]/80', badge: 'text-[#d4b693]/90' };

            posts.forEach((post) => {
                const el = document.createElement('div');
                el.className = 'overflow-hidden rounded-2xl border border-white/6 bg-[rgba(28,26,36,0.92)] flex cursor-pointer transition hover:brightness-[1.07] hover:border-white/10 active:scale-[0.99]';
                el.onclick = () => this.navigateToPost(post.id);

                const colors = CATEGORY_COLORS[(post.category || '').toLowerCase()] || DEFAULT_COLORS;

                // 標籤 HTML
                let tagsHtml = '';
                try {
                    if (post.tags) {
                        const tags = normalizePostTags(post.tags);
                        tagsHtml = tags
                            .map((tag) => {
                                const safe = typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(tag) : tag.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                                return `<span class="text-[10px] font-medium px-2 py-0.5 rounded-full ${colors.tag}">#${safe}</span>`;
                            })
                            .join('');
                    }
                } catch (e) {
                    console.warn('[Forum] Tags parsing failed for post', post.id, e);
                }

                const date = formatTWDate(post.created_at);
                const pushCount = Math.max(0, post.push_count || 0);
                const booCount = Math.max(0, post.boo_count || 0);
                const safeUsername = typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(post.username || post.user_id) : post.username || post.user_id;
                const safeTitle = typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(post.title || '') : post.title || '';
                const avatarLetter = (safeUsername[0] || '?').toUpperCase();
                const categoryLabel = (post.category || 'discussion').toUpperCase();
                const totalEngagement = pushCount + booCount + (post.comment_count || 0);

                el.innerHTML = `
                    <div class="w-[4px] shrink-0 ${colors.rail}"></div>
                    <div class="flex-1 min-w-0 px-4 py-4 sm:px-5">
                        <div class="flex items-start gap-3">
                            <span class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${colors.avatar} text-xs font-bold">${avatarLetter}</span>
                            <div class="min-w-0 flex-1">
                                <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                                    <a href="/static/forum/profile.html?id=${post.user_id}" class="text-sm font-semibold text-secondary hover:text-primary transition truncate" onclick="event.stopPropagation()">${safeUsername}</a>
                                    <span class="text-[10px] font-semibold tracking-[0.16em] ${colors.badge}">${categoryLabel}</span>
                                    <span class="text-[11px] text-textMuted/45">·</span>
                                    <span class="text-[11px] text-textMuted/55">${date}</span>
                                </div>
                                <h3 class="mt-2 text-[1rem] font-bold leading-7 text-textMain sm:text-[1.03rem]">${safeTitle}</h3>
                                ${tagsHtml ? `<div class="mt-3 flex flex-wrap gap-1.5">${tagsHtml}</div>` : ''}
                                <div class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-textMuted/55">
                                    <span class="inline-flex items-center gap-1.5 ${pushCount > 0 ? 'text-success/80' : ''}">
                                <i data-lucide="thumbs-up" class="h-3 w-3"></i>${pushCount}
                            </span>
                                    <span class="inline-flex items-center gap-1.5 ${booCount > 0 ? 'text-danger/80' : ''}">
                                <i data-lucide="thumbs-down" class="h-3 w-3"></i>${booCount}
                            </span>
                                    <span class="inline-flex items-center gap-1.5">
                                <i data-lucide="message-square" class="h-3 w-3"></i>${post.comment_count}
                            </span>
                                    ${post.tips_total > 0 ? `<span class="inline-flex items-center gap-1.5 text-[#d4b693]/80"><i data-lucide="gift" class="h-3 w-3"></i>${post.tips_total} Pi</span>` : ''}
                                    <span class="ml-auto inline-flex items-center rounded-full border border-white/6 bg-white/[0.03] px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-textMuted/60">
                                        ${totalEngagement} interactions
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(el);
            });
            AppUtils.refreshIcons();
        } catch (e) {
            console.error(e);
            container.innerHTML = '<div class="text-center py-10 text-danger">載入失�?</div>';
        }
    },

    async loadTrendingTags() {
        const container = document.getElementById('trending-tags');
        if (!container) return;

        try {
            const response = await ForumAPI.getTrendingTags();
            const tags = response.tags || [];

            if (tags.length === 0) {
                container.innerHTML = '<div class="text-xs text-textMuted">No trending tags yet</div>';
                return;
            }

            const TAG_COLORS = [
                'text-[#d4b693] bg-[#d4b693]/10 border-[#d4b693]/25',
                'text-violet-400 bg-violet-400/10 border-violet-400/25',
                'text-cyan-400 bg-cyan-400/10 border-cyan-400/25',
                'text-rose-400 bg-rose-400/10 border-rose-400/25',
            ];

            container.innerHTML = tags
                .map((tag, index) => {
                    const safeName =
                        typeof SecurityUtils !== 'undefined'
                            ? SecurityUtils.escapeHTML(tag.name)
                            : tag.name;
                    const isActive = this.currentTagFilter === tag.name;
                    const colorClass = TAG_COLORS[index % 4];

                    return `<button type="button" data-tag="${safeName}"
                        class="trending-tag shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-[11px] font-semibold whitespace-nowrap transition ${colorClass} ${isActive ? 'brightness-125 scale-105' : 'opacity-75 hover:opacity-100 hover:scale-105'}">
                        <span>#${safeName}</span><span class="opacity-60 text-[10px]">${tag.post_count}</span>
                    </button>`;
                })
                .join('');

            container.querySelectorAll('.trending-tag').forEach((button) => {
                button.addEventListener('click', () => {
                    const nextTag = button.dataset.tag || '';
                    this.currentTagFilter =
                        this.currentTagFilter === nextTag ? '' : nextTag;
                    const category = document.getElementById('category-filter')?.value || '';

                    this.loadPosts({
                        category: category || undefined,
                        tag: this.currentTagFilter || undefined,
                    });
                    this.loadTrendingTags();
                    this.updatePostFiltersUI();
                });
            });
        } catch (e) {
            console.error('Failed to load tags', e);
            if (container) {
                container.innerHTML = '<div class="text-sm text-danger py-1">標籤載入失�?</div>';
            }
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

        // 綁�??��?事件 - 使用?��??��?法防止�?複�?�?
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

            // 保�??��??��?對象，用?��?續檢?��?如�?賞�?檢查作者�?
            this.currentPost = post;

            document.title = `${post.title} - Pi Forum`;

            document.getElementById('post-category').textContent = post.category;
            document.getElementById('post-title').textContent = post.title;

            // 安全?�創建�??��??��??�止 XSS�?
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

            // 安全?�渲??Markdown ?�容（防�?XSS�?
            const contentContainer = document.getElementById('post-content');
            if (typeof SecurityUtils !== 'undefined') {
                // 使用 SecurityUtils 安全渲�?
                contentContainer.innerHTML = SecurityUtils.renderMarkdownSafely(post.content);
            } else {
                contentContainer.textContent = post.content;
            }

            // Tags
            const tagsContainer = document.getElementById('post-tags');
            if (post.tags && tagsContainer) {
                try {
                    const tags = normalizePostTags(post.tags);
                    tagsContainer.innerHTML = tags
                        .map(
                            (tag) =>
                                `<span class="text-sm bg-primary/10 text-primary px-3 py-1 rounded-full">#${typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(tag) : tag}</span>`
                        )
                        .join('');
                } catch (e) {
                    console.warn('[Forum] Post tags parsing failed for post', id, e);
                }
            }

            // 顯示作者�?作�??��?編輯/?�除�?
            this.updateAuthorActions(post);

            // Stats
            this.updatePostStats(post);

            // Re-render icons
            AppUtils.refreshIcons();
        } catch (e) {
            showToast('?��?載入失�?', 'error');
            console.error(e);
        }
    },

    updateAuthorActions(post) {
        const currentUserId = AuthManager.currentUser?.user_id || AuthManager.currentUser?.uid;
        const isAuthor = currentUserId && post.user_id && currentUserId === post.user_id;

        // 尋找?�創建�??��?作�??�容??
        let actionsContainer = document.getElementById('author-actions');
        if (!actionsContainer) {
            // ?��?題�??��??��?作�??�容??
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
                        <span>?�除</span>
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

        // ?�置顏色
        btnPush?.classList.remove('text-success');
        btnPush?.classList.add('text-textMuted');
        btnBoo?.classList.remove('text-danger');
        btnBoo?.classList.add('text-textMuted');

        // ?��??�票?�?��???
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
                container.innerHTML = '<div class="text-center text-textMuted py-4">?�無?��?</div>';
                return;
            }

            comments.forEach((comment) => {
                if (comment.type !== 'comment') return; // ?�顯示�??��?�?

                const el = document.createElement('div');
                el.className = 'rounded-2xl border border-white/6 bg-white/[0.025] px-4 py-3.5';
                el.innerHTML = `
                    <div class="flex justify-between items-start gap-3 mb-2">
                        <div class="min-w-0">
                            <a href="/static/forum/profile.html?id=${comment.user_id}" class="font-semibold text-sm text-secondary hover:text-primary transition">${typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(comment.username || comment.user_id) : comment.username || comment.user_id}</a>
                            <div class="text-[11px] text-textMuted/60 mt-1">${formatTWDate(comment.created_at, true)}</div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button data-report-type="comment" data-report-id="${comment.id}" class="text-textMuted hover:text-danger p-1 rounded transition report-trigger" title="Report">
                                <i data-lucide="flag" class="w-3 h-3"></i>
                            </button>
                        </div>
                    </div>
                    <div class="text-textMain text-sm leading-7">${escapeHtml(comment.content)}</div>
                `;
                container.appendChild(el);
            });
            AppUtils.refreshIcons();
        } catch (e) {
            console.error('[Forum] loadComments failed:', e);
            if (container) {
                container.innerHTML =
                    '<div class="text-center py-4 text-danger">評�?載入失�?，�?稍�??�試</div>';
            }
        }
    },

    async handlePush(postId) {
        if (!AuthManager.currentUser) return showToast('請�??�入', 'warning');
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
        if (!AuthManager.currentUser) return showToast('請�??�入', 'warning');
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
        if (!AuthManager.currentUser) return showToast('請�??�入', 'warning');
        const form = document.getElementById('reply-form');
        form.classList.toggle('hidden');
    },

    async submitReply(postId) {
        // ?��??保護：�??�正?��?交中，直?��???
        if (this.isSubmittingReply) {
            window.APP_CONFIG?.DEBUG_MODE &&
                console.log('[submitReply] ?�� Already submitting, ignoring duplicate click');
            return;
        }

        const content = document.getElementById('reply-content').value;
        if (!content) return;

        const submitBtn = document.getElementById('submit-reply');

        try {
            // 設置?�交中�?�?
            this.isSubmittingReply = true;

            // 禁用?��?並顯示�??��???
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML =
                    '<div class="flex items-center gap-2 justify-center"><svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>?�送中</span></div>';
            }

            await ForumAPI.createComment(postId, { type: 'comment', content });

            // 清空輸入框並?��??��?表單
            document.getElementById('reply-content').value = '';
            this.toggleReplyForm();

            // ?�新載入評�??�表
            this.loadComments(postId);

            showToast('Reply posted successfully.', 'success');
        } catch (e) {
            showToast(e.message, 'error');
        } finally {
            // ?�復?��??�?�並清除?�交中�?�?
            this.isSubmittingReply = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML =
                    '<div class="flex items-center gap-2 justify-center"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg><span>?�出評�?</span></div>';
            }
        }
    },

    async handleDelete(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請�??�入', 'warning');
        }

        // 確�??�除
        const confirmed = await showConfirm({
            title: '確�??�除',
            message: 'Delete this post? This action cannot be undone.',
            type: 'warning',
            confirmText: '確�??�除',
            cancelText: '?��?',
        });

        if (!confirmed) return;

        const btnElement = document.getElementById('btn-delete');
        if (btnElement) {
            btnElement.disabled = true;
            btnElement.classList.add('opacity-50', 'cursor-not-allowed');
        }

        try {
            await ForumAPI.deletePost(postId);
            showToast('Post deleted successfully.', 'success');

            // 延遲後�??��?首�?
            setTimeout(() => {
                if (typeof smoothNavigate === 'function') {
                    smoothNavigate('/static/forum/index.html');
                } else {
                    window.location.href = '/static/forum/index.html';
                }
            }, 1000);
        } catch (e) {
            showToast('?�除失�?: ' + e.message, 'error');
            if (btnElement) {
                btnElement.disabled = false;
                btnElement.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
    },

    async handleEdit(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請�??�入', 'warning');
        }

        // TODO: 實現編輯?�能 - ?�以?�建一?�編輯模?��??��??�到編輯?�面
        showToast('Edit feature is not available yet.', 'info');
    },

    async handleTip(postId) {
        if (!AuthManager.currentUser) {
            return showToast('請�??�入', 'warning');
        }

        // 檢查?�否?��?賞自己�??��?
        const currentUserId = AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
        const postAuthorId = this.currentPost?.user_id;

        if (currentUserId && postAuthorId && currentUserId === postAuthorId) {
            return showToast('You cannot tip your own post.', 'warning');
        }

        // 檢查?�否??Pi Browser ?��?
        const isPi = typeof isPiBrowser === 'function' ? isPiBrowser() : false;

        // ?��??��??�格
        const tipAmount = getPrice('tip');

        // 確�??��?
        const confirmed = await showConfirm({
            title: '確�??��?',
            message: isPi
                ? ('Tip this post with ' + tipAmount + ' Pi?\nPayment will open in Pi Browser.')
                : ('Tip this post with ' + tipAmount + ' Pi?\nTest mode will simulate Pi Browser payment flow.'),
            type: 'info',
            confirmText: '確�??��?',
            cancelText: '?��?',
        });

        if (!confirmed) return;

        try {
            let txHash = '';

            if (isPi && window.Pi) {
                // === Pi ?�實?��?流�? ===
                window.APP_CONFIG?.DEBUG_MODE && console.log('[Tip] ?��? Pi ?��?流�?');

                if (typeof AuthManager.verifyPiBrowserEnvironment === 'function') {
                    const envCheck = await AuthManager.verifyPiBrowserEnvironment();
                    if (!envCheck.valid) {
                        showToast('Pi Browser ?��??�常，�?確�?已登??Pi 帳�?', 'warning');
                        return;
                    }
                }

                try {
                    await Pi.authenticate(['username', 'payments', 'wallet_address'], () => {});
                } catch (authErr) {
                    showToast('?��?權�?不足，�??�新?�入', 'error');
                    return;
                }

                let paymentComplete = false;
                let paymentError = null;
                let tipPaymentId = null;
                const loadingToast = showToast('�?��?��??��?...', 'info', 0);

                await Pi.createPayment(
                    {
                        amount: tipAmount,
                        memo: `?��??��? #${postId}`,
                        metadata: { type: 'tip', post_id: postId },
                    },
                    {
                        onReadyForServerApproval: async (paymentId) => {
                            try {
                                await AppAPI.post('/api/user/payment/approve', { paymentId });
                            } catch (e) {
                                console.error(e);
                            }
                        },
                        onReadyForServerCompletion: async (paymentId, txid) => {
                            txHash = txid;
                            tipPaymentId = paymentId;
                            paymentComplete = true;
                            try {
                                await AppAPI.post('/api/user/payment/complete', { paymentId, txid });
                            } catch (e) {
                                console.error(e);
                            }
                        },
                        onCancel: (paymentId) => {
                            paymentError = 'CANCELLED';
                        },
                        onError: (error) => {
                            paymentError = error?.message || 'PAYMENT_ERROR';
                        },
                    }
                );

                const startTime = Date.now();
                while (!paymentComplete && !paymentError && Date.now() - startTime < 120000) {
                    await new Promise((r) => setTimeout(r, 300));
                }

                if (window.UIShell && typeof window.UIShell.dismissToast === 'function') {
                    window.UIShell.dismissToast(loadingToast);
                } else if (loadingToast && typeof loadingToast.remove === 'function') {
                    loadingToast.remove();
                }

                if (paymentError) {
                    showToast(paymentError === 'CANCELLED' ? 'Payment was cancelled.' : 'Payment failed.', 'warning');
                    return;
                }

                if (!txHash) {
                    showToast('?��?超�?，�??�試', 'warning');
                    return;
                }
            } else {
                txHash = 'mock_tip_' + Date.now();
            }

            await ForumAPI.tipPost(postId, tipAmount, txHash, tipPaymentId);
            showToast('Tip sent successfully. Thank you for your support.', 'success');
            this.loadPostDetail(postId);
        } catch (e) {
            showToast('?��?失�?: ' + e.message, 'error');
        }
    },

    // ===========================================
    // Create Post Logic
    // ===========================================
    initCreatePage() {
        const log = (msg, data = {}) => {
            window.APP_CONFIG?.DEBUG_MODE && console.log('[CreatePost]', msg, data);
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
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('[CreatePost] UI Update limits data:', limitsData);

                if (limitsData.success) {
                    const isPro = limitsData.membership?.is_premium ?? false;
                    // 使用後端返�??��??��?fallback 使用?��?載入?��?�?
                    const defaultLimit = getLimit('daily_post_free');
                    const postLimit = limitsData.limits?.post || {
                        count: 0,
                        limit: defaultLimit,
                        remaining: defaultLimit,
                    };

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
                            const total =
                                postLimit.limit !== null
                                    ? postLimit.limit
                                    : getLimit('daily_post_free') || 0;
                            const used = postLimit.count || 0;
                            // Ensure remaining logic is consistent
                            const remaining =
                                postLimit.remaining !== undefined
                                    ? postLimit.remaining
                                    : total - used;
                            const isLow = remaining <= 0;

                            limitDisplay.innerHTML = `
                                <div class="bg-white/5 px-3 py-1 rounded-full border border-white/10 flex items-center gap-1.5">
                                    <span class="opacity-60">Daily Posts:</span>
                                    <span class="font-bold ${isLow ? 'text-danger' : 'text-success'}">${used}/${total}</span>
                                </div>
                            `;
                        }
                        AppUtils.refreshIcons();
                    }

                    // Update Submit Button and Cost Info
                    const submitButton = document.querySelector('button[type="submit"]');
                    const paySpan = submitButton?.querySelector('span');
                    if (paySpan) {
                        if (isPro) {
                            paySpan.textContent = 'Post for Free (PREMIUM)';
                        } else {
                            const postAmount = getPrice('create_post');
                            if (postAmount !== null) {
                                paySpan.innerHTML = `Pay <span class="font-bold text-white">${Number(postAmount)}</span> Pi & Post`;
                            }
                        }
                    }

                    const costElements = document.querySelectorAll('.text-sm.text-textMuted');
                    costElements.forEach((el) => {
                        if (el.textContent.includes('Cost to post:')) {
                            if (isPro) {
                                el.innerHTML =
                                    'Cost to post: <span class="text-success font-bold">FREE</span> <br><span class="text-xs opacity-60">(For Premium members)</span>';
                            } else {
                                // Reset to default if needed or keep existing
                            }
                        }
                    });
                }
            } catch (error) {
                console.warn('[CreatePost] Failed to update UI status:', error);
                if (limitDisplay) {
                    if (error?.status === 401) {
                        limitDisplay.innerHTML =
                            '<span class="text-warning text-xs">?�入已�??��?請�??�整?��???/span>';
                    } else {
                        limitDisplay.innerHTML =
                            '<span class="text-danger text-xs">Connection Error</span>';
                    }
                }
            }
        };

        if (AuthManager.currentUser) {
            updateUIForMembership();
        } else {
            // Auth completes async ??re-run when user logs in
            const onAuthReady = () => {
                if (AuthManager.currentUser) {
                    updateUIForMembership();
                    window.removeEventListener('pi-auth-success', onAuthReady);
                }
            };
            window.addEventListener('pi-auth-success', onAuthReady);
            // Also poll briefly in case auth restores from backend before event fires
            const checkAuth = setInterval(() => {
                if (AuthManager.currentUser) {
                    clearInterval(checkAuth);
                    updateUIForMembership();
                }
            }, 500);
            setTimeout(() => clearInterval(checkAuth), 10000); // stop after 10s
        }

        // ?��??��??�統計�???
        const initCharCounters = () => {
            const titleInput = document.getElementById('input-title');
            const contentInput = document.getElementById('input-content');
            const titleCurrent = document.getElementById('title-current');
            const contentCurrent = document.getElementById('content-current');
            const titleMax = document.getElementById('title-max');
            const contentMax = document.getElementById('content-max');

            // 從�?端�?置獲?��??��??��?端�??��??��?
            const MAX_TITLE = 200;
            const MAX_CONTENT = 10000;

            // ?�新顯示?��?大�?
            if (titleMax) titleMax.textContent = MAX_TITLE;
            if (contentMax) contentMax.textContent = MAX_CONTENT;

            // 標�?字數統�?
            if (titleInput && titleCurrent) {
                const updateTitleCount = () => {
                    const count = titleInput.value.length;
                    titleCurrent.textContent = count;

                    // 顏色變�??�示
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
                updateTitleCount(); // ?��???
            }

            // ?�容字數統�?
            if (contentInput && contentCurrent) {
                const updateContentCount = () => {
                    const count = contentInput.value.length;
                    contentCurrent.textContent = count;

                    // 顏色變�??�示
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
                updateContentCount(); // ?��???
            }

            window.APP_CONFIG?.DEBUG_MODE &&
                console.log('[CharCounter] Character counters initialized');
        };

        // ?��??��???
        initCharCounters();

        document.getElementById('post-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            window.APP_CONFIG?.DEBUG_MODE && console.log('[CreatePost] V38 Handler Active');
            window.APP_CONFIG?.DEBUG_MODE && console.log('[CreatePost] Form submitted');

            // Disable button to prevent double submit
            const submitBtn = document.querySelector('button[type="submit"]');
            let originalBtnContent = '';

            if (submitBtn) {
                if (submitBtn.disabled) return; // Already processing
                submitBtn.disabled = true;
                originalBtnContent = submitBtn.innerHTML;
                submitBtn.innerHTML =
                    '<i class="animate-spin" data-lucide="loader-2"></i> Processing...';
                AppUtils.refreshIcons();
            }

            // Function to reset button state
            const resetButton = () => {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnContent;
                    AppUtils.refreshIcons();
                }
            };

            if (!AuthManager?.currentUser) {
                showToast('請�??�入', 'warning');
                resetButton();
                return;
            }

            const title = document.getElementById('input-title').value;
            const content = document.getElementById('input-content').value;
            const category = document.getElementById('input-category').value;
            const tagsStr = document.getElementById('input-tags').value;
            const tags = tagsStr
                .split(' ')
                .map((t) => t.replace('#', '').trim())
                .filter((t) => t);

            const postAmount = getPrice('create_post');
            if (postAmount === null) {
                showToast('?�格?�置載入失�?，�??�新?��??�面', 'error');
                resetButton();
                return;
            }
            const isPiBrowserContext =
                typeof isPiBrowser === 'function' ? isPiBrowser() : false;
            const hasPiPaymentSdk =
                typeof window.Pi !== 'undefined' &&
                window.Pi !== null &&
                typeof window.Pi.createPayment === 'function' &&
                typeof window.Pi.authenticate === 'function';
            const isPi = isPiBrowserContext || hasPiPaymentSdk;
            const createPostWarning = document.getElementById('create-post-warning');
            const setCreatePostWarning = (message) => {
                if (!createPostWarning) {
                    showToast(message, 'warning');
                    return;
                }
                createPostWarning.textContent = message;
                createPostWarning.classList.remove('hidden');
            };
            const clearCreatePostWarning = () => {
                if (!createPostWarning) return;
                createPostWarning.textContent = '';
                createPostWarning.classList.add('hidden');
            };
            let txHash = '';
            clearCreatePostWarning();

            const userId = AuthManager.currentUser?.user_id || AuthManager.currentUser?.uid;
            let isProMember = false;

            if (userId) {
                try {
                    // First, check limits and membership status
                    window.APP_CONFIG?.DEBUG_MODE &&
                        console.log('[CreatePost] Checking limits and membership...');
                    const limitsData = await ForumAPI.checkLimits();

                    if (limitsData.success) {
                        const postLimit = limitsData.limits.post;
                        isProMember = limitsData.membership?.is_premium ?? false;

                        // Check if limit reached
                        // limit === null means unlimited (Pro)
                        if (postLimit.limit !== null && postLimit.remaining <= 0) {
                            console.warn('[CreatePost] Daily limit reached:', postLimit);

                            // Custom Styled Modal
                            const modal = document.createElement('div');
                            modal.className =
                                'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                            modal.innerHTML = `
                                            <div class="bg-surface w-full max-w-sm p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in text-center">
                                                <div class="w-16 h-16 bg-warning/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-warning/20">
                                                    <i data-lucide="lock" class="w-8 h-8 text-warning"></i>
                                                </div>
                                                <h3 class="text-xl font-bold text-secondary mb-2">?��?額度已滿</h3>
                                                <div class="text-textMuted text-sm mb-6 leading-relaxed">
                                                    今日已發�?<span class="text-textMain font-bold text-base">${postLimit.count}</span> / <span class="text-textMain font-bold text-base">${postLimit.limit}</span> 篇�?�?br>
                                                    <span class="opacity-70">?��? Premium ?�員?�可?��??��?�?/span>
                                                </div>
                                                <div class="flex flex-col gap-3">
                                                    <button onclick="smoothNavigate('/static/forum/premium.html')" class="w-full py-3.5 bg-gradient-to-r from-primary to-primary/80 hover:to-primary text-background font-bold rounded-2xl transition shadow-lg flex items-center justify-center gap-2 transform active:scale-95">
                                                        <i data-lucide="crown" class="w-4 h-4"></i>
                                                        <span>?��? Premium ?�員</span>
                                                    </button>
                                                    <button onclick="this.closest('.fixed').remove()" class="w-full py-3.5 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5 hover:text-white">
                                                        ?��?�?
                                                    </button>
                                                </div>
                                            </div>
                                        `;
                            document.body.appendChild(modal);
                            AppUtils.refreshIcons();

                            resetButton();
                            return; // STOP HERE - Do not proceed to payment
                        }
                    }
                } catch (error) {
                    console.warn('[CreatePost] Failed to check limits:', error);
                    if (error?.status === 401) {
                        if (typeof showToast === 'function')
                            showToast('?�入已�??��?請�??�整?��??��??�入', 'error');
                        resetButton();
                        return;
                    } else {
                        if (typeof showToast === 'function')
                            showToast('?��?驗�??��??�制，�?稍�??�試', 'warning');
                        // ?��?證錯誤�?如�??��?，�?許繼續由伺�??�端?��??�制
                    }
                }
            }

            window.APP_CONFIG?.DEBUG_MODE &&
                console.log(
                    `[CreatePost] User: ${userId}, IsPro: ${isProMember}, Amount: ${postAmount}`
                );

            if (isProMember) {
                txHash = 'pro_member_free';
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('[CreatePost] Pro member, skipping payment');
            } else {
                // ?�鍵修復：檢?��?實�? Pi Browser UA，而�??�檢??SDK 存在
                const userAgent = navigator.userAgent || '';
                const isRealPiBrowser =
                    hasPiPaymentSdk || userAgent.includes('PiBrowser');

                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('[CreatePost] ?? Environment:', {
                        ua: userAgent.substring(0, 60),
                        isRealPiBrowser,
                        isPiBrowserContext,
                        hasPiPaymentSdk,
                        isPi,
                    });

                try {
                    if (hasPiPaymentSdk) {
                        window.APP_CONFIG?.DEBUG_MODE &&
                            console.log('[CreatePost] ?�� Real Pi Browser - Starting payment...');
                        try {
                            await window.Pi.authenticate(
                                ['username', 'payments', 'wallet_address'],
                                (incompletePayment) => {
                                    if (!incompletePayment?.identifier) return;
                                    AppAPI.post('/api/user/payment/complete', {
                                        paymentId: incompletePayment.identifier,
                                        txid: incompletePayment.transaction?.txid || null,
                                    }).catch((err) => {
                                        console.warn(
                                            '[CreatePost] Failed to complete incomplete payment:',
                                            err
                                        );
                                    });
                                }
                            );
                        } catch (authErr) {
                            console.error('[CreatePost] Pi Auth failed:', authErr);
                            showToast('?��?權�?不足，�??�新?�入', 'error');
                            resetButton();
                            return;
                        }

                        let paymentComplete = false;
                        let paymentError = null;
                        let serverCompletionCalled = false;

                        await Pi.createPayment(
                            {
                                amount: postAmount,
                                memo: `?��?: ${title.substring(0, 20)}`,
                                metadata: { type: 'create_post' },
                            },
                            {
                                onReadyForServerApproval: async (paymentId) => {
                                    window.APP_CONFIG?.DEBUG_MODE &&
                                        console.log(
                                            '[CreatePost] onReadyForServerApproval',
                                            paymentId
                                        );
                                    try {
                                        await AppAPI.post('/api/user/payment/approve', { paymentId });
                                    } catch (e) {
                                        console.error('[CreatePost] Approve failed:', e);
                                        // Don't throw here, let Pi SDK handle timeout if needed
                                    }
                                },
                                onReadyForServerCompletion: async (paymentId, txid) => {
                                    window.APP_CONFIG?.DEBUG_MODE &&
                                        console.log(
                                            '[CreatePost] onReadyForServerCompletion',
                                            paymentId,
                                            txid
                                        );
                                    txHash = txid; // CRITICAL: Capture txid immediately
                                    serverCompletionCalled = true;

                                    // Non-blocking call to server completion
                                    AppAPI.post('/api/user/payment/complete', { paymentId, txid })
                                        .then(() => {
                                            window.APP_CONFIG?.DEBUG_MODE &&
                                                console.log('[CreatePost] Server completion notified');
                                        })
                                        .catch((err) => {
                                            window.APP_CONFIG?.DEBUG_MODE &&
                                                console.error(
                                                    '[CreatePost] Server completion notification failed (ignoring):',
                                                    err
                                                );
                                        })
                                        .finally(() => {
                                            paymentComplete = true; // Mark done regardless of backend success
                                        });
                                },
                                onCancel: (paymentId) => {
                                    window.APP_CONFIG?.DEBUG_MODE &&
                                        console.log('[CreatePost] Payment cancelled', paymentId);
                                    paymentError = 'CANCELLED';
                                },
                                onError: (error) => {
                                    console.error('[CreatePost] Payment error', error);
                                    paymentError = error?.message || 'ERROR';
                                },
                            }
                        );

                        // Wait for txHash (preferred) or paymentComplete flag
                        window.APP_CONFIG?.DEBUG_MODE &&
                            console.log('[CreatePost] Waiting for payment result...');
                        const startTime = Date.now();

                        while (!txHash && !paymentError && Date.now() - startTime < 120000) {
                            if (serverCompletionCalled && txHash) break; // We have what we need
                            await new Promise((r) => setTimeout(r, 500));
                        }

                        if (paymentError) {
                            showToast(
                                paymentError === 'CANCELLED' ? 'Payment was cancelled.' : 'Payment failed.',
                                'warning'
                            );
                            resetButton();
                            return;
                        }

                        if (!txHash) {
                            console.error('[CreatePost] Payment timed out (no txHash)');
                            showToast('?��?超�??��??�異常�?請聯繫管?�員', 'warning');
                            resetButton();
                            return;
                        }

                        window.APP_CONFIG?.DEBUG_MODE &&
                            console.log('[CreatePost] Payment successful, txHash:', txHash);
                    } else {
                        setCreatePostWarning('Please complete posting inside Pi Browser.');
                        resetButton();
                        return;
                    }
                } catch (paymentError) {
                    console.error('[CreatePost] Exception during payment setup:', paymentError);
                    showToast('An error occurred while preparing the payment.', 'error');
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
                    payment_tx_hash: txHash,
                };

                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('[Forum] Sending post data:', postData);
                const result = await ForumAPI.createPost(postData);
                window.APP_CONFIG?.DEBUG_MODE &&
                    console.log('[Forum] Post created successfully:', result);

                if (window.UIShell && typeof window.UIShell.clearToasts === 'function') {
                    window.UIShell.clearToasts();
                }
                clearCreatePostWarning();

                // Success Modal
                const successModal = document.createElement('div');
                successModal.className =
                    'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                successModal.innerHTML = `
                                <div class="bg-surface w-full max-w-sm p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in text-center">
                                    <div class="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-success/20">
                                        <i data-lucide="check-circle-2" class="w-8 h-8 text-success"></i>
                                    </div>
                                    <h3 class="text-xl font-bold text-secondary mb-2">?��??��?�?/h3>
                                    <div class="text-textMuted text-sm mb-6">
                                        ?��??��?已�??��??�儲存�?br>
                                        <span class="text-primary animate-pulse">�?��?��??��?詳�???..</span>
                                    </div>
                                    <button id="btn-go-now" class="w-full py-3.5 bg-gradient-to-r from-success/80 to-success text-background font-bold rounded-2xl transition shadow-lg transform active:scale-95">
                                        立即?��?
                                    </button>
                                </div>
                            `;
                document.body.appendChild(successModal);
                AppUtils.refreshIcons();

                // Determine redirect URL
                const targetUrl = result.post_id
                    ? `/static/forum/post.html?id=${result.post_id}`
                    : '/static/forum/index.html';

                // Redirect Action (with smooth transition)
                const doRedirect = () => {
                    window.APP_CONFIG?.DEBUG_MODE &&
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
                    submitBtn.innerHTML =
                        '<i class="w-4 h-4 animate-spin" data-lucide="loader-2"></i> Redirecting...';
                    AppUtils.refreshIcons();
                }
            } catch (err) {
                console.error('[Forum] CreatePost API failed:', err);
                // If payment was made but post failed, we should alert the user to copy their content
                if (txHash && txHash !== 'pro_member_free' && !txHash.startsWith('mock_')) {
                    // 顯示?�好?�錯�?Modal ?��? alert
                    const errorModal = document.createElement('div');
                    errorModal.className =
                        'fixed inset-0 bg-background/90 backdrop-blur-sm z-[150] flex items-center justify-center p-4 animate-fade-in';
                    errorModal.innerHTML = `
                        <div class="bg-surface w-full max-w-md p-6 rounded-3xl border border-white/10 shadow-2xl animate-scale-in">
                            <div class="w-16 h-16 bg-danger/10 rounded-full flex items-center justify-center mx-auto mb-5 border border-danger/20">
                                <i data-lucide="alert-triangle" class="w-8 h-8 text-danger"></i>
                            </div>
                            <h3 class="text-xl font-bold text-secondary mb-3 text-center">?��?失�?但支付已完�?</h3>
                            <div class="text-textMuted text-sm mb-4 leading-relaxed">
                                <p class="mb-2">?��??��?已�??��?但�?章發布失?�。�?保�?以�?交�? ID 並聯繫客?��??��?</p>
                                <div class="bg-background/50 p-3 rounded-xl border border-white/10 mb-3">
                                    <div class="text-xs text-textMuted mb-1">交�? ID</div>
                                    <div class="text-textMain font-mono text-xs break-all" id="error-txhash">${SecurityUtils.escapeHTML(txHash || '')}</div>
                                </div>
                                <p class="text-xs opacity-60">?�誤訊息�?{SecurityUtils.escapeHTML(err.message || '')}</p>
                            </div>
                            <div class="flex flex-col gap-2">
                                <button id="copy-txhash-btn" class="w-full py-3 bg-primary hover:brightness-110 text-background font-bold rounded-2xl transition shadow-lg flex items-center justify-center gap-2">
                                    <i data-lucide="copy" class="w-4 h-4"></i>
                                    <span>複製交�? ID</span>
                                </button>
                                <button onclick="this.closest('.fixed').remove()" class="w-full py-3 bg-surfaceHighlight hover:bg-white/10 text-textMuted font-bold rounded-2xl transition border border-white/5">
                                    ?��?
                                </button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(errorModal);
                    AppUtils.refreshIcons();

                    // 複製?�能
                    document.getElementById('copy-txhash-btn').onclick = () => {
                        navigator.clipboard
                            .writeText(txHash)
                            .then(() => {
                                showToast('Transaction ID copied.', 'success');
                            })
                            .catch(() => {
                                // Fallback for older browsers
                                const textArea = document.createElement('textarea');
                                textArea.value = txHash;
                                document.body.appendChild(textArea);
                                textArea.select();
                                document.execCommand('copy');
                                document.body.removeChild(textArea);
                                showToast('Transaction ID copied.', 'success');
                            });
                    };
                } else {
                    showToast('?��?失�?: ' + err.message, 'error');
                }
                resetButton();
            }
        });
    },

    // ===========================================
    // Dashboard Logic
    // ===========================================
    async initDashboardPage() {
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
            // XSS Fix: 使用 textContent ?�代 innerHTML
            const span = document.createElement('span');
            span.className = 'text-primary font-bold';
            span.textContent = user.username[0].toUpperCase();
            avatarEl.innerHTML = '';
            avatarEl.appendChild(span);
        }

        const loaders = [
            this.loadWalletStatus().catch((err) =>
                console.error('Wallet Status Load Failed:', err)
            ),
            this.loadStats().catch((err) => console.error('Stats Load Failed:', err)),
            this.loadMyPosts().catch((err) => console.error('Posts Load Failed:', err)),
            this.loadTransactions().catch((err) => console.error('Tx Load Failed:', err)),
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
                statusText.textContent = '已�?��';
                statusText.classList.remove('text-textMuted', 'text-danger');
                statusText.classList.add('text-success');

                if (iconEl) {
                    iconEl.classList.remove('bg-primary/20');
                    iconEl.classList.add('bg-success/20');
                    iconEl.innerHTML =
                        '<i data-lucide="check-circle" class="w-7 h-7 text-success"></i>';
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
                statusText.textContent = 'Unavailable';
                statusText.classList.remove('text-success', 'text-danger');
                statusText.classList.add('text-textMuted');

                actionArea.innerHTML = `
                    <button onclick="safePiLogin()" class="bg-primary/10 hover:bg-primary/20 text-primary px-4 py-2 rounded-xl flex items-center gap-2 transition text-sm font-bold border border-primary/20">
                        <i data-lucide="log-in" class="w-4 h-4"></i>
                        ?�入 Pi 帳�?
                    </button>
                `;
            }

            AppUtils.refreshIcons();
        } catch (e) {
            statusText.textContent = '載入失�?';
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
                    const totalSent = sentData.tips.reduce(
                        (acc, tip) => acc + (tip.amount || 0),
                        0
                    );
                    tipsSentEl.textContent = totalSent.toFixed(1);
                } else {
                    tipsSentEl.textContent = '0';
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
                container.innerHTML =
                    '<div class="text-center text-textMuted py-4">No posts yet</div>';
                return;
            }

            posts.forEach((post) => {
                const el = document.createElement('div');
                el.className =
                    'flex items-center justify-between border-b border-white/5 pb-3 last:border-0 last:pb-0';

                const pushCount = Math.max(0, post.push_count || 0);

                el.innerHTML = `
                    <div class="overflow-hidden mr-4">
                         <a href="/static/forum/post.html?id=${post.id}" class="font-bold text-textMain hover:text-primary transition truncate block">${typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(post.title || '') : post.title || ''}</a>
                         <div class="text-xs text-textMuted mt-1 flex items-center gap-2">
                            <span>${formatTWDate(post.created_at)}</span>
                            <span class="bg-white/10 px-1.5 rounded text-[10px] uppercase">${typeof SecurityUtils !== 'undefined' ? SecurityUtils.escapeHTML(post.category) : post.category}</span>
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
            AppUtils.refreshIcons();
        } catch (e) {
            console.error('loadMyPosts error', e);
            container.innerHTML = '<div class="text-center text-danger py-4">Failed to load</div>';
        }
    },

    async loadTransactions() {
        const container = document.getElementById('dash-tx-list');
        if (!container) return;

        try {
            // 使用 Promise.allSettled 確�??��? API 失�??��??�顯示可?�數??
            const results = await Promise.allSettled([
                ForumAPI.getMyPayments(),
                ForumAPI.getMyTipsSent(),
            ]);

            // 記�?失�???API
            results.forEach((result, index) => {
                if (result.status === 'rejected') {
                    const apiNames = ['getMyPayments', 'getMyTipsSent'];
                    console.warn(`[Dashboard] ${apiNames[index]} failed:`, result.reason);
                }
            });

            // ?��??��?，失?��?使用空數�?
            const paymentsData =
                results[0].status === 'fulfilled' ? results[0].value : { payments: [] };
            const tipsSentData =
                results[1].status === 'fulfilled' ? results[1].value : { tips: [] };

            const payments = (paymentsData.payments || [])
                // 保�? Premium ?�員?�費?��?記�?但�?記為?�費
                .map((p) => {
                    const isFree = p.tx_hash === 'pro_member_free';
                    return {
                        ...p,
                        type: isFree ? 'post_payment_free' : 'post_payment',
                        amount: isFree ? 0 : -(p.amount || getPrice('create_post') || 0),
                        isFree: isFree,
                    };
                });
            const tips = (tipsSentData.tips || []).map((t) => ({
                ...t,
                type: 'tip_sent',
                amount: -t.amount,
                title: `Tip: ${t.post_title || 'Post'}`,
            }));

            const allTx = [...payments, ...tips].sort(
                (a, b) => new Date(b.created_at) - new Date(a.created_at)
            );

            container.innerHTML = '';
            if (allTx.length === 0) {
                container.innerHTML =
                    '<div class="text-center text-textMuted py-4">No transactions</div>';
                return;
            }

            allTx.slice(0, 20).forEach((tx, idx) => {
                const el = document.createElement('div');
                el.className =
                    'flex items-center justify-between border-b border-white/5 py-4 hover:bg-white/5 px-2 rounded-xl transition cursor-pointer last:border-0';

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

                const safeTitle = typeof escapeHtml === 'function' ? escapeHtml(title) : title.replace(/</g, '&lt;');

                const amountClass = tx.isFree
                    ? 'text-success'
                    : tx.amount < 0
                      ? 'text-danger'
                      : 'text-success';
                const amountText = tx.isFree
                    ? 'FREE'
                    : `${tx.amount > 0 ? '+' : ''}${Math.abs(tx.amount).toFixed(1)} Pi`;

                el.innerHTML = `
                    <div class="flex items-center gap-3 overflow-hidden">
                         <div class="w-10 h-10 rounded-full bg-surfaceHighlight flex items-center justify-center shrink-0">
                            <i data-lucide="${icon}" class="w-5 h-5 text-textMuted"></i>
                         </div>
                         <div class="overflow-hidden">
                              <div class="font-bold text-textMain truncate">${safeTitle}</div>
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

            AppUtils.refreshIcons();
        } catch (e) {
            console.error('loadTransactions error', e);
            container.innerHTML = '<div class="text-center text-danger py-4">Failed to load</div>';
        }
    },

    showTransactionDetail(tx) {
        const txId = tx.tx_hash || tx.payment_tx_hash || 'N/A';
        const typeLabel =
            tx.type === 'post_payment' ? 'Post Publication Fee' : 'Article Tip Support';
        const status = 'Completed';
        const memo =
            tx.title || (tx.type === 'post_payment' ? 'Forum Posting Fee' : 'Tip to Author');

        const modal = document.createElement('div');
        modal.id = 'tx-detail-modal';
        modal.className =
            'fixed inset-0 bg-background/90 backdrop-blur-md z-[110] flex items-center justify-center p-4 animate-fade-in';
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
        AppUtils.refreshIcons();
    },

    // ===========================================
    // Reporting Logic
    // ===========================================
    openReportModal(type, id) {
        if (!AuthManager.currentUser) return showToast('請�??�入', 'warning');

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
        AppUtils.refreshIcons();
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
            return showError('Please select a report reason.');
        }

        const btn = document.getElementById('btn-submit-report');
        if (!btn) return;

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="animate-spin" data-lucide="loader-2"></i> Submitting...';
        AppUtils.refreshIcons();

        // Clear previous error
        if (errorDiv) errorDiv.classList.add('hidden');

        try {
            const res = await AppAPI.post('/api/governance/reports', {
                content_type: contentType,
                content_id: parseInt(contentId),
                report_type: reportType,
                description: description,
            });

            showToast('Report submitted successfully. We will review it soon.', 'success');
        } catch (e) {
            showError('?�交失�?: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
            AppUtils.refreshIcons();
        }
    },
};

// ?�露?�全局
window.ForumApp = ForumApp;
export { ForumApp };


// 確�???DOM 載入後執行�??��??��? forum ?�面，SPA 主�???switchTab 觸發�?
document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (e) => {
        const trigger = e.target.closest('.report-trigger');
        if (trigger) {
            const type = trigger.dataset.reportType;
            const id = trigger.dataset.reportId;
            if (type && id && window.ForumApp && ForumApp.openReportModal) {
                ForumApp.openReportModal(type, id);
            }
        }
    });
    const page = document.body.dataset.page;
    if (!page) return; // SPA mode: skip, forum content loaded via switchTab()
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
