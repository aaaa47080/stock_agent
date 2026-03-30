// Auto-generated from components.js split
// Tab: Forum - follows TAB_SHELL_CLASS / TAB_HEADER_CLASS / TAB_CONTENT_AREA_CLASS pattern
window.Components = window.Components || {};
window.Components.forum = `
    <div class="${TAB_SHELL_CLASS}">

        <!-- Header — same structure as twstock / crypto tabs -->
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

        <!-- Filter row — same visual language as safety tab selects -->
        <div class="flex items-center gap-2 mb-4 px-1">
            <select id="category-filter"
                class="appearance-none bg-surface border border-white/5 rounded-xl px-3 py-1.5 text-textMuted text-xs font-bold outline-none focus:border-primary/50 cursor-pointer shrink-0">
                <option value="" data-i18n="forum.allCategories">全部分類</option>
                <option value="analysis" data-i18n="forum.categoryAnalysis">分析</option>
                <option value="question" data-i18n="forum.categoryQuestion">請問</option>
                <option value="tutorial" data-i18n="forum.categoryTutorial">學習</option>
                <option value="news" data-i18n="forum.categoryNews">新聞</option>
                <option value="chat" data-i18n="forum.categoryChat">閒聊</option>
                <option value="insight" data-i18n="forum.categoryInsight">心得</option>
            </select>
            <div id="trending-tags"
                class="flex items-center gap-1.5 overflow-x-auto flex-1 min-w-0"
                style="-ms-overflow-style:none;scrollbar-width:none">
                <span class="text-xs text-textMuted/30 italic shrink-0">載入中...</span>
            </div>
        </div>

        <!-- Content area — same absolute-inset scroll pattern as other tabs -->
        <div class="${TAB_CONTENT_AREA_CLASS}">
            <div ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS}">
                <div id="post-list" class="space-y-3 px-1 pb-8">
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
