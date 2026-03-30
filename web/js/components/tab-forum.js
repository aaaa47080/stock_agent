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

        <div class="mb-4 flex flex-wrap items-center gap-2 text-xs">
            <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border bg-white/5 text-textMuted border-white/10 font-bold">Community Board</span>
            <span class="text-textMuted/80">看分析、問問題、分享心得</span>
        </div>

        <div class="mb-5 rounded-xl border border-white/5 bg-background/50 p-3">
            <div class="flex items-center gap-3 overflow-x-auto pb-2" style="-ms-overflow-style:none;scrollbar-width:none">
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

            <div id="active-post-filters" class="hidden mt-1 flex items-center gap-2.5 px-1">
                <span class="text-xs text-textMuted/60">篩選：</span>
                <span id="active-post-filters-text" class="text-xs font-medium text-primary bg-primary/10 px-3.5 py-1.5 rounded-full border border-primary/15"></span>
                <button id="clear-post-filters" type="button" class="text-xs text-textMuted hover:text-primary transition">
                    <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        </div>

        <div class="${TAB_CONTENT_AREA_CLASS}">
            <div ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS}">
                <div class="space-y-5 px-1 pb-8">
                    <div class="${SECTION_HEADER_ROW_CLASS}">
                        <div class="${PRIMARY_DIVIDER_LEFT_CLASS}"></div>
                        <h3 class="${SECTION_TITLE_CLASS} text-primary">
                            <i data-lucide="messages-square" class="w-3 h-3"></i>
                            <span>最新討論</span>
                        </h3>
                        <div class="${PRIMARY_DIVIDER_RIGHT_CLASS}"></div>
                    </div>

                    <div id="post-list" class="space-y-5">
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
