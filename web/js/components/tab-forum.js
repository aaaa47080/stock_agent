// Auto-generated from components.js split
// Tab: Forum - redesigned to match platform style
window.Components = window.Components || {};
window.Components.forum = `

    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
        <h2 class="${HERO_TITLE_CLASS}">
            <div class="${HERO_ICON_BOX_CLASS}">
                <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
            </div>
            <span class="hidden sm:inline">Pi Forum</span>
            <span class="sm:hidden">Forum</span>
        </h2>
        <a href="/static/forum/create.html"
            class="flex items-center gap-2 bg-primary/15 hover:bg-primary/25 text-primary px-4 py-2.5 rounded-full text-sm font-bold transition border border-primary/20 shadow-lg shadow-primary/10">
            <i data-lucide="pen-line" class="w-4 h-4"></i>
            <span class="hidden sm:inline">發布文章</span>
            <span class="sm:hidden">發文</span>
        </a>
    </div>

    <!-- Hidden category select for JS state -->
    <select id="category-filter" class="hidden" aria-hidden="true">
        <option value="" data-i18n="forum.allCategories">全部分類</option>
        <option value="analysis" data-i18n="forum.categoryAnalysis">分析</option>
        <option value="question" data-i18n="forum.categoryQuestion">請問</option>
        <option value="tutorial" data-i18n="forum.categoryTutorial">學習</option>
        <option value="news" data-i18n="forum.categoryNews">新聞</option>
        <option value="chat" data-i18n="forum.categoryChat">閒聊</option>
        <option value="insight" data-i18n="forum.categoryInsight">心得</option>
    </select>

    <!-- Category Pills -->
    <div class="mb-3 flex items-center gap-2 overflow-x-auto" style="-ms-overflow-style:none;scrollbar-width:none">
        <button data-category="" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-primary/30 bg-primary/10 text-primary">
            <i data-lucide="layout-grid" class="w-3 h-3"></i>全部
        </button>
        <button data-category="analysis" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-amber-400/50 hover:text-amber-400 hover:bg-amber-400/10">
            <i data-lucide="bar-chart-2" class="w-3 h-3"></i>分析
        </button>
        <button data-category="question" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-blue-400/50 hover:text-blue-400 hover:bg-blue-400/10">
            <i data-lucide="help-circle" class="w-3 h-3"></i>請問
        </button>
        <button data-category="tutorial" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-emerald-400/50 hover:text-emerald-400 hover:bg-emerald-400/10">
            <i data-lucide="book-open" class="w-3 h-3"></i>學習
        </button>
        <button data-category="news" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-violet-400/50 hover:text-violet-400 hover:bg-violet-400/10">
            <i data-lucide="newspaper" class="w-3 h-3"></i>新聞
        </button>
        <button data-category="chat" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-rose-400/50 hover:text-rose-400 hover:bg-rose-400/10">
            <i data-lucide="coffee" class="w-3 h-3"></i>閒聊
        </button>
        <button data-category="insight" class="category-pill shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap border border-white/8 text-textMuted hover:border-cyan-400/50 hover:text-cyan-400 hover:bg-cyan-400/10">
            <i data-lucide="lightbulb" class="w-3 h-3"></i>心得
        </button>
    </div>

    <!-- Trending Tags -->
    <div id="trending-tags" class="mb-3 flex items-center gap-2 overflow-x-auto min-w-0" style="-ms-overflow-style:none;scrollbar-width:none">
        <span class="text-xs text-textMuted/30 italic shrink-0">載入中...</span>
    </div>

    <!-- Active Filter Indicator -->
    <div id="active-post-filters" class="hidden mb-4 flex items-center gap-2.5">
        <span class="text-xs text-textMuted/60">已篩選：</span>
        <span id="active-post-filters-text" class="text-xs font-medium text-primary bg-primary/10 px-3.5 py-1.5 rounded-full border border-primary/15"></span>
        <button id="clear-post-filters" type="button" class="text-xs text-textMuted hover:text-primary transition p-1 ml-auto">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
        </button>
    </div>

    <!-- Stats (compact inline) -->
    <div class="mb-5 flex items-center gap-4 text-xs text-textMuted/50">
        <span><span class="font-bold text-primary" id="forum-stat-posts">--</span> 文章</span>
        <span class="text-textMuted/20">&middot;</span>
        <span><span class="font-bold text-accent" id="forum-stat-users">--</span> 用戶</span>
        <span class="text-textMuted/20">&middot;</span>
        <span><span class="font-bold text-success" id="forum-stat-comments">--</span> 回覆</span>
    </div>

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
    <div id="post-list" class="space-y-3">
        <div class="${LOADING_PLACEHOLDER_CLASS}">
            <div class="${PRIMARY_RING_SPINNER_CLASS} mx-auto mb-3"></div>
            <span data-i18n="common.loading">Loading...</span>
        </div>
    </div>

`;

// Side-effect module — assigns to window.Components
export {};
