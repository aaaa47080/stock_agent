// Auto-generated from components.js split
// Tab: Forum - follows TAB_SHELL_CLASS / TAB_HEADER_CLASS / TAB_CONTENT_AREA_CLASS pattern
window.Components = window.Components || {};
window.Components.forum = `
    <div class="${TAB_SHELL_CLASS}">

        <div class="${TAB_HEADER_CLASS}">
            <h2 class="font-serif text-3xl text-secondary flex items-center gap-3">
                <div class="${HERO_ICON_BOX_CLASS}">
                    <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
                </div>
                Pi Forum
            </h2>
            <a href="/static/forum/create.html" class="${ICON_ACTION_BUTTON_CLASS}" title="發文">
                <i data-lucide="plus" class="w-5 h-5"></i>
            </a>
        </div>

        <div class="mb-6 rounded-[32px] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.02))] p-5 shadow-[0_18px_42px_rgba(0,0,0,0.18)]">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <p class="text-[11px] font-bold uppercase tracking-[0.24em] text-primary/70">Community Board</p>
                    <p class="mt-2 text-sm leading-6 text-textMuted">沿用 crypto 區的柔和圓角和分層感，讓討論流更自然，不要太硬。</p>
                </div>
                <div class="hidden rounded-2xl border border-primary/15 bg-primary/10 px-3.5 py-2 text-[11px] font-semibold text-primary md:block">
                    Crypto Focus
                </div>
            </div>

            <div class="mt-5 flex items-center gap-3 overflow-x-auto pb-1" style="-ms-overflow-style:none;scrollbar-width:none">
                <select id="category-filter"
                    class="appearance-none shrink-0 rounded-full border border-white/10 bg-background/70 px-4 py-2.5 text-xs font-bold text-textMuted outline-none transition focus:border-primary/50">
                    <option value="" data-i18n="forum.allCategories">全部分類</option>
                    <option value="analysis" data-i18n="forum.categoryAnalysis">分析</option>
                    <option value="question" data-i18n="forum.categoryQuestion">請問</option>
                    <option value="tutorial" data-i18n="forum.categoryTutorial">學習</option>
                    <option value="news" data-i18n="forum.categoryNews">新聞</option>
                    <option value="chat" data-i18n="forum.categoryChat">閒聊</option>
                    <option value="insight" data-i18n="forum.categoryInsight">心得</option>
                </select>
                <div id="trending-tags"
                    class="flex items-center gap-2.5 overflow-x-auto flex-1 min-w-0"
                    style="-ms-overflow-style:none;scrollbar-width:none">
                    <span class="text-xs text-textMuted/30 italic shrink-0">載入中...</span>
                </div>
            </div>
        </div>

        <div class="${TAB_CONTENT_AREA_CLASS}">
            <div ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS}">
                <div id="post-list" class="space-y-5 px-1 pb-8">
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
