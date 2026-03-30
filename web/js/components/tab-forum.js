// Auto-generated from components.js split
// Tab: Forum - original lines 1387-1451
window.Components = window.Components || {};
window.Components.forum = `
    <div class="h-full flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between mb-3 px-1">
            <h2 class="${HERO_TITLE_CLASS}">
                <div class="${HERO_ICON_BOX_CLASS}">
                    <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
                </div>
                <span>Pi Forum</span>
            </h2>
            <a href="/static/forum/create.html"
                class="bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-full text-sm font-bold flex items-center gap-1 transition">
                <i data-lucide="plus" class="w-4 h-4"></i>
                <span class="hidden sm:inline" data-i18n="forum.createPost">New Post</span>
            </a>
        </div>

        <!-- Filter + Trending row -->
        <div class="flex items-center gap-2 px-1 mb-2">
            <select id="category-filter"
                class="shrink-0 appearance-none bg-surface/80 border border-white/8 rounded-full px-3.5 py-1.5 text-xs font-semibold text-textMain outline-none focus:border-primary/50 cursor-pointer">
                <option value="" data-i18n="forum.allCategories">全部</option>
                <option value="analysis" data-i18n="forum.categoryAnalysis">分析</option>
                <option value="question" data-i18n="forum.categoryQuestion">請問</option>
                <option value="tutorial" data-i18n="forum.categoryTutorial">學習</option>
                <option value="news" data-i18n="forum.categoryNews">新聞</option>
                <option value="chat" data-i18n="forum.categoryChat">閒聊</option>
                <option value="insight" data-i18n="forum.categoryInsight">心得</option>
            </select>
            <div id="trending-tags" class="flex items-center gap-1.5 overflow-x-auto min-w-0 flex-1" style="-ms-overflow-style:none;scrollbar-width:none">
                <span class="text-xs text-textMuted/40 italic shrink-0">載入中...</span>
            </div>
        </div>

        <!-- Post list -->
        <div class="flex-1 overflow-y-auto custom-scrollbar pr-0.5">
            <div id="post-list" class="space-y-3 pb-28">
                <div class="${LOADING_PLACEHOLDER_CLASS}">
                    <i data-lucide="loader-2" class="${LOADER_ICON_CLASS}"></i>
                    <span data-i18n="common.loading">Loading...</span>
                </div>
            </div>
        </div>
    </div>
    `;

// Side-effect module — assigns to window.Components
export {};
