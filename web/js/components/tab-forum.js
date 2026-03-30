// Auto-generated from components.js split
// Tab: Forum - follows TAB_SHELL_CLASS / TAB_HEADER_CLASS / TAB_CONTENT_AREA_CLASS pattern
window.Components = window.Components || {};
window.Components.forum = `
    <div class="${TAB_SHELL_CLASS}">

        <!-- Hero Section with Gradient Background -->
        <div class="relative mb-6 -mx-4 md:-mx-6 px-4 md:px-6 pt-4 pb-5">
            <!-- Gradient Background Effects -->
            <div aria-hidden="true" class="absolute inset-x-0 top-0 h-[180px] bg-[linear-gradient(180deg,rgba(212,182,147,0.12),transparent)] pointer-events-none"></div>
            <div aria-hidden="true" class="absolute -left-8 top-12 h-32 w-32 rounded-full bg-primary/8 blur-3xl pointer-events-none"></div>

            <div class="relative">
                <div class="${TAB_HEADER_CLASS}">
                    <h2 class="font-serif text-2xl md:text-3xl text-secondary flex items-center gap-3">
                        <div class="${HERO_ICON_BOX_CLASS}">
                            <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
                        </div>
                        <span class="hidden sm:inline">Pi Forum</span>
                        <span class="sm:hidden">Forum</span>
                    </h2>
                    <a href="/static/forum/create.html"
                        class="flex items-center gap-2 bg-primary/15 hover:bg-primary/25 text-primary px-4 py-2.5 rounded-full text-sm font-bold transition shadow-lg shadow-primary/10">
                        <i data-lucide="plus" class="w-4 h-4"></i>
                        <span class="hidden sm:inline">發布文章</span>
                    </a>
                </div>

                <!-- Welcome Banner -->
                <div class="mt-3 flex flex-wrap items-center gap-3">
                    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-primary/20 bg-primary/10 text-primary text-xs font-bold">
                        <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
                        Community Board
                    </span>
                    <span class="text-textMuted/80 text-sm">分享觀點、提問、學習</span>
                </div>
            </div>
        </div>

        <!-- Category Filter Bar -->
        <div class="mb-5 rounded-2xl border border-white/5 bg-surface/60 p-4 backdrop-blur-sm">
            <div class="flex items-center gap-3 overflow-x-auto pb-2" style="-ms-overflow-style:none;scrollbar-width:none">
                <select id="category-filter"
                    class="appearance-none shrink-0 rounded-xl border border-white/10 bg-background/80 px-4 py-2.5 text-xs font-bold text-textMuted outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-primary/20">
                    <option value="" data-i18n="forum.allCategories">全部分類</option>
                    <option value="analysis" data-i18n="forum.categoryAnalysis">分析</option>
                    <option value="question" data-i18n="forum.categoryQuestion">請問</option>
                    <option value="tutorial" data-i18n="forum.categoryTutorial">學習</option>
                    <option value="news" data-i18n="forum.categoryNews">新聞</option>
                    <option value="chat" data-i18n="forum.categoryChat">閒聊</option>
                    <option value="insight" data-i18n="forum.categoryInsight">心得</option>
                </select>
                <div id="trending-tags"
                    class="flex items-center gap-2 overflow-x-auto flex-1 min-w-0"
                    style="-ms-overflow-style:none;scrollbar-width:none">
                    <span class="text-xs text-textMuted/30 italic shrink-0">載入中...</span>
                </div>
            </div>

            <div id="active-post-filters" class="hidden mt-3 flex items-center gap-2.5 px-1 pt-2 border-t border-white/5">
                <span class="text-xs text-textMuted/60">已篩選：</span>
                <span id="active-post-filters-text" class="text-xs font-medium text-primary bg-primary/10 px-3.5 py-1.5 rounded-full border border-primary/15"></span>
                <button id="clear-post-filters" type="button" class="text-xs text-textMuted hover:text-primary transition p-1">
                    <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        </div>

        <!-- Quick Stats Row -->
        <div class="mb-6 grid grid-cols-3 gap-3">
            <div class="rounded-xl border border-white/5 bg-surface/40 p-3 text-center">
                <div class="text-lg font-bold text-primary" id="forum-stat-posts">--</div>
                <div class="text-[10px] text-textMuted/60 uppercase tracking-wider">文章</div>
            </div>
            <div class="rounded-xl border border-white/5 bg-surface/40 p-3 text-center">
                <div class="text-lg font-bold text-accent" id="forum-stat-users">--</div>
                <div class="text-[10px] text-textMuted/60 uppercase tracking-wider">用戶</div>
            </div>
            <div class="rounded-xl border border-white/5 bg-surface/40 p-3 text-center">
                <div class="text-lg font-bold text-success" id="forum-stat-comments">--</div>
                <div class="text-[10px] text-textMuted/60 uppercase tracking-wider">回覆</div>
            </div>
        </div>

        <div class="${TAB_CONTENT_AREA_CLASS}">
            <div ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS}">
                <div class="space-y-5 px-1 pb-8">
                    <!-- Section Header -->
                    <div class="${SECTION_HEADER_ROW_CLASS}">
                        <div class="${PRIMARY_DIVIDER_LEFT_CLASS}"></div>
                        <h3 class="${SECTION_TITLE_CLASS} text-primary">
                            <i data-lucide="clock" class="w-3 h-3"></i>
                            <span>最新討論</span>
                        </h3>
                        <div class="${PRIMARY_DIVIDER_RIGHT_CLASS}"></div>
                    </div>

                    <!-- Post List -->
                    <div id="post-list" class="space-y-4">
                        <div class="${LOADING_PLACEHOLDER_CLASS}">
                            <i data-lucide="loader-2" class="${LOADER_ICON_CLASS}"></i>
                            <span data-i18n="common.loading">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>
    `;

// Side-effect module — assigns to window.Components
export {};
