// Auto-generated from components.js split
// Tab: Forum - original lines 1387-1451
window.Components = window.Components || {};
window.Components.forum = `
    <div class="h-full flex flex-col">
            <!--Header -->
            <div class="flex items-center justify-between mb-4 px-2">
                <h2 class="${HERO_TITLE_CLASS}">
                    <div class="${HERO_ICON_BOX_CLASS}">
                        <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
                    </div>
                    <span>Pi Forum</span>
                </h2>
                <div class="flex items-center gap-2">
                    <!-- 發文按鈕 -->
                    <a href="/static/forum/create.html"
                        class="bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 transition">
                        <i data-lucide="plus" class="w-4 h-4"></i>
                        <span class="hidden sm:inline" data-i18n="forum.createPost">New Post</span>
                    </a>
                </div>
            </div>

            <!--Main Content Grid-->
    <div class="flex-1 grid grid-cols-1 md:grid-cols-4 gap-4 overflow-hidden">
        <!-- Sidebar (Filters & Trending) -->
        <aside class="md:col-span-1 space-y-4 overflow-y-auto custom-scrollbar">
            <div class="bg-surface border border-white/5 rounded-2xl p-4">
                <h3 class="font-bold text-secondary mb-3 flex items-center gap-2">
                    <i data-lucide="filter" class="w-4 h-4"></i> <span data-i18n="forum.filter">Filter</span>
                </h3>
                <div class="space-y-1">
                    <select id="category-filter"
                        class="appearance-none w-full bg-background border border-white/10 rounded-lg p-2 text-sm text-textMain focus:border-primary outline-none">
                        <option value="" data-i18n="forum.allCategories">All Categories</option>
                        <option value="analysis" data-i18n="forum.categoryAnalysis">Analysis</option>
                        <option value="question" data-i18n="forum.categoryQuestion">Question</option>
                        <option value="tutorial" data-i18n="forum.categoryTutorial">Tutorial</option>
                        <option value="news" data-i18n="forum.categoryNews">News</option>
                        <option value="chat" data-i18n="forum.categoryChat">Chat</option>
                        <option value="insight" data-i18n="forum.categoryInsight">Insight</option>
                    </select>
                </div>
            </div>

            <div class="bg-surface border border-white/5 rounded-2xl p-4">
                <h3 class="font-bold text-secondary mb-3 flex items-center gap-2">
                    <i data-lucide="trending-up" class="w-4 h-4"></i> <span data-i18n="forum.trendingTags">Trending Tags</span>
                </h3>
                <div id="trending-tags" class="space-y-1">
                    <div class="text-xs text-textMuted">Loading...</div>
                </div>
            </div>
        </aside>

        <!-- Post List -->
        <div class="md:col-span-3 overflow-y-auto custom-scrollbar">
            <div id="post-list" class="space-y-3 pr-2">
                <div class="${LOADING_PLACEHOLDER_CLASS}">
                    <i data-lucide="loader-2" class="${LOADER_ICON_CLASS}"></i>
                    <span data-i18n="common.loading">Loading...</span>
                </div>
            </div>
        </div>
    </div>
        </div>
    `;

// Side-effect module — assigns to window.Components
export {};
