// Auto-generated from components.js split
// Tab: Forum - original lines 1387-1451
window.Components = window.Components || {};
window.Components.forum = `
    <div class="h-full flex flex-col px-1 sm:px-2">
            <div class="mb-4 flex items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                    <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-white/5">
                        <i data-lucide="messages-square" class="w-5 h-5"></i>
                    </div>
                    <div>
                        <p class="text-[11px] font-bold uppercase tracking-[0.2em] text-primary/70">Community Board</p>
                        <h2 class="text-2xl font-extrabold tracking-tight text-textMain">Pi Forum</h2>
                    </div>
                </div>
                <a href="/static/forum/create.html"
                    class="inline-flex items-center gap-2 rounded-full bg-primary/12 px-4 py-2.5 text-sm font-bold text-primary transition hover:bg-primary/20">
                    <i data-lucide="plus" class="w-4 h-4"></i>
                    <span class="hidden sm:inline" data-i18n="forum.createPost">New Post</span>
                </a>
            </div>

            <div class="mb-4 rounded-[28px] bg-surface px-5 py-5 shadow-[0_14px_40px_rgba(0,0,0,0.16)] ring-1 ring-white/5">
                <p class="text-sm leading-6 text-textMuted">看分析、問問題、分享心得。保留論壇閱讀感，不用擁擠側欄和舊式控制面板。</p>
                <div class="mt-4 flex flex-col gap-3">
                    <div class="rounded-[22px] bg-surfaceHighlight/75 p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                        <div class="mb-2 flex items-center gap-2 text-sm font-bold text-secondary">
                            <i data-lucide="filter" class="w-4 h-4"></i>
                            <span data-i18n="forum.filter">Filter</span>
                        </div>
                        <select id="category-filter"
                            class="w-full appearance-none rounded-[16px] bg-background/75 px-3.5 py-3 text-sm text-textMain outline-none ring-1 ring-white/8 focus:ring-primary">
                            <option value="" data-i18n="forum.allCategories">All Categories</option>
                            <option value="analysis" data-i18n="forum.categoryAnalysis">Analysis</option>
                            <option value="question" data-i18n="forum.categoryQuestion">Question</option>
                            <option value="tutorial" data-i18n="forum.categoryTutorial">Tutorial</option>
                            <option value="news" data-i18n="forum.categoryNews">News</option>
                            <option value="chat" data-i18n="forum.categoryChat">Chat</option>
                            <option value="insight" data-i18n="forum.categoryInsight">Insight</option>
                        </select>
                    </div>
                    <div class="rounded-[22px] bg-surfaceHighlight/75 p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                        <div class="mb-2 flex items-center gap-2 text-sm font-bold text-secondary">
                            <i data-lucide="trending-up" class="w-4 h-4"></i>
                            <span data-i18n="forum.trendingTags">Trending Tags</span>
                        </div>
                        <div id="trending-tags" class="flex flex-wrap gap-2">
                            <div class="text-xs text-textMuted">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto custom-scrollbar pr-1">
                <div id="post-list" class="space-y-3.5 pb-28">
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
