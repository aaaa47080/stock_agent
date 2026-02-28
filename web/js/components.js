// ========================================
// components.js - 頁面組件模板與動態注入
// ========================================

const Components = {
    // 追蹤已注入的組件
    _injected: {},

    // Tab: Crypto (Combined Market & Pulse)
    crypto: `
        <div class="h-full flex flex-col px-4 md:px-6 pt-6 md:pt-8">
            <!-- Header with Sub-tab Switcher -->
            <div class="flex items-center justify-between mb-4 pr-12 md:pr-16">
                <h2 class="font-serif text-3xl text-secondary" data-i18n="crypto.title">Crypto</h2>
                <div class="flex items-center gap-2">
                    <button onclick="window.CryptoTab.refreshCurrent()" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Sub-tab Navigation -->
            <div class="flex gap-1 p-1 bg-background/50 border border-white/5 rounded-xl mb-6">
                <button onclick="window.CryptoTab.switchSubTab('market')" id="crypto-tab-market"
                    class="crypto-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background shadow-md">
                    <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                    <span data-i18n="nav.market">Market Watch</span>
                </button>
                <button onclick="window.CryptoTab.switchSubTab('pulse')" id="crypto-tab-pulse"
                    class="crypto-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5">
                    <i data-lucide="activity" class="w-4 h-4"></i>
                    <span data-i18n="nav.pulse">AI Pulse</span>
                </button>
            </div>

            <!-- Content Area -->
            <div class="flex-1 overflow-visible relative">
                
                <!-- Sub-tab: Market Watch -->
                <div id="crypto-content-market" class="absolute inset-0 overflow-y-auto custom-scrollbar">
                    <div class="mb-6 md:mb-8">
                        <!-- 篩選器行 -->
                        <div class="flex flex-wrap items-center justify-between gap-2 md:gap-3">
                            <div class="flex gap-2 items-center">
                                <button onclick="openGlobalFilter()" class="flex items-center gap-2 px-3 py-1.5 bg-surface hover:bg-surfaceHighlight rounded-lg text-textMuted hover:text-primary transition border border-white/5">
                                    <i data-lucide="filter" class="w-4 h-4"></i>
                                    <span class="text-xs font-bold" data-i18n="market.filter">Filter</span>
                                    <span id="global-count-badge" class="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded" data-i18n="market.autoBadge">Auto</span>
                                </button>
                                <div id="active-filter-indicator" class="hidden flex items-center gap-1 text-xs text-primary">
                                    <span id="filter-count">0</span> <span data-i18n="market.selected">Selected</span>
                                </div>
                            </div>
                            <!-- 狀態指示器 -->
                            <div class="flex items-center gap-2">
                                <div class="flex items-center gap-1.5" title="Live Data">
                                    <div id="ticker-ws-indicator" class="w-2 h-2 rounded-full bg-gray-500 transition-colors"></div>
                                    <span class="text-[9px] text-textMuted uppercase tracking-wider hidden md:inline">LIVE</span>
                                </div>
                                <span id="screener-last-updated" class="text-[10px] text-textMuted opacity-60 hidden md:inline"></span>
                            </div>
                        </div>
                    </div>

                    <div class="space-y-12 pb-32">
                        <section>
                            <div class="flex items-center gap-3 mb-6 px-2">
                                <div class="h-px flex-1 bg-gradient-to-r from-primary/30 to-transparent"></div>
                                <h3 class="text-xs font-bold text-primary uppercase tracking-[0.2em] whitespace-nowrap" data-i18n="market.topPerformers">Top Performers</h3>
                                <div class="h-px flex-1 bg-gradient-to-l from-primary/30 to-transparent"></div>
                            </div>
                            <div id="top-list" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
                        </section>

                        <section>
                            <div class="flex items-center gap-3 mb-8 px-2">
                                <div class="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent"></div>
                                <h3 class="text-xs font-bold text-textMuted uppercase tracking-[0.2em] whitespace-nowrap" data-i18n="market.marketDynamics">Market Dynamics</h3>
                                <div class="h-px flex-1 bg-gradient-to-l from-white/10 to-transparent"></div>
                            </div>

                            <div class="space-y-10 px-2">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div>
                                        <h4 class="text-xs font-bold text-success mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                            <i data-lucide="trending-up" class="w-4 h-4 text-success"></i> <span data-i18n="market.topGainers">Top Gainers</span>
                                        </h4>
                                        <div id="top-gainers-list" class="space-y-3"></div>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-danger mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                            <i data-lucide="trending-down" class="w-4 h-4 text-danger"></i> <span data-i18n="market.topLosers">Top Losers</span>
                                        </h4>
                                        <div id="top-losers-list" class="space-y-3"></div>
                                    </div>
                                </div>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div>
                                        <h4 class="text-xs font-bold text-secondary mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                            <i data-lucide="zap" class="w-3.5 h-3.5 text-accent"></i> <span data-i18n="market.bullishSqueeze">Bullish / Squeeze</span>
                                        </h4>
                                        <div id="low-funding-list" class="space-y-3"></div>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-secondary mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                            <i data-lucide="flame" class="w-3.5 h-3.5 text-danger"></i> <span data-i18n="market.overheated">Overheated Short</span>
                                        </h4>
                                        <div id="high-funding-list" class="space-y-3"></div>
                                    </div>
                                </div>
                            </div>
                        </section>
                    </div>
                </div>

                <!-- Sub-tab: AI Pulse -->
                <div id="crypto-content-pulse" class="absolute inset-0 overflow-y-auto custom-scrollbar hidden">
                    <!-- Filter UI (Synced with Market Watch) -->
                    <div class="flex flex-wrap items-center gap-2 md:gap-3 mb-8">
                        <button onclick="openGlobalFilter()" class="flex items-center gap-2 px-3 py-1.5 bg-surface hover:bg-surfaceHighlight rounded-lg text-textMuted hover:text-primary transition border border-white/5">
                            <i data-lucide="filter" class="w-4 h-4"></i>
                            <span class="text-xs font-bold" data-i18n="pulse.filter">Filter Signals</span>
                            <span id="pulse-count-badge" class="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded" data-i18n="pulse.autoBadge">Auto</span>
                        </button>
                        <div id="active-pulse-filter-indicator" class="hidden flex items-center gap-1 text-xs text-primary">
                            <span id="pulse-filter-count">0</span> <span data-i18n="pulse.selected">Selected</span>
                        </div>
                    </div>

                    <div id="analysis-progress-container" class="hidden mb-6 bg-surface rounded-2xl p-4 border border-primary/10">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs font-bold text-primary flex items-center gap-2">
                                <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                                <span data-i18n="pulse.scanning">Scanning Markets...</span>
                            </span>
                            <span id="analysis-progress-text" class="text-xs text-textMuted">0%</span>
                        </div>
                        <div class="w-full bg-background rounded-full h-1">
                            <div id="analysis-progress-bar" class="bg-primary h-1 rounded-full transition-all duration-500" style="width: 0%"></div>
                        </div>
                    </div>

                    <div id="pulse-grid" class="grid grid-cols-1 md:grid-cols-2 gap-6 pb-32"></div>
                </div>

            </div>
        </div>
    `,

    // Tab: Taiwan Stock
    twstock: `
        <div class="h-full flex flex-col px-4 md:px-6 pt-6 md:pt-8">
            <!-- Header with Sub-tab Switcher -->
            <div class="flex items-center justify-between mb-4 pr-12 md:pr-16">
                <h2 class="font-serif text-3xl text-secondary" data-i18n="twstock.title">TW Stock</h2>
                <div class="flex items-center gap-2">
                    <button onclick="window.TWStockTab.refreshCurrent()" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Sub-tab Navigation (2 tabs only) -->
            <div class="flex gap-1 p-1 bg-background/50 border border-white/5 rounded-xl mb-6">
                <button id="twstock-btn-market" onclick="window.TWStockTab.switchSubTab('market')"
                    class="twstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background shadow-md">
                    <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                    <span data-i18n="nav.market">Market Watch</span>
                </button>
                <button id="twstock-btn-pulse" onclick="window.TWStockTab.switchSubTab('pulse')"
                    class="twstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5">
                    <i data-lucide="activity" class="w-4 h-4"></i>
                    <span data-i18n="nav.pulse">AI Pulse</span>
                </button>
            </div>

            <!-- Content Area -->
            <div class="flex-1 overflow-visible relative">

                <!-- Market Watch Container -->
                <div id="twstock-market-content" class="absolute inset-0 overflow-y-auto custom-scrollbar pb-32">
                    <div class="space-y-8">

                        <!-- ① Watchlist section -->
                        <section>
                            <div class="flex items-center gap-3 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-primary/40 to-transparent"></div>
                                <h3 class="text-[10px] font-black text-primary uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                    <i data-lucide="star" class="w-3 h-3 text-yellow-400"></i>
                                    自選清單
                                </h3>
                                <div class="h-px flex-1 bg-gradient-to-l from-primary/40 to-transparent"></div>
                            </div>
                            <!-- Custom Watchlist Controls Area -->
                            <div id="twstock-screener-controls" class="px-1"></div>
                            <div id="twstock-market-loader" class="hidden items-center justify-center py-10 flex">
                                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                            </div>
                            <div id="twstock-screener-list" class="space-y-2 px-1"></div>

                            <!-- My Alerts (TW Stock) -->
                            <div id="alert-list-section-twstock" class="mt-4 px-1">
                                <h4 class="text-textMuted text-xs font-medium uppercase tracking-wide mb-2" data-i18n="modals.priceAlert.myAlerts">我的警報</h4>
                                <div id="alert-list-twstock" class="space-y-0">
                                    <p class="text-textMuted text-xs py-1" data-i18n="modals.priceAlert.noAlerts">尚無警報</p>
                                </div>
                            </div>
                        </section>

                        <!-- ② PE / Valuation section -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-primary/40 to-transparent"></div>
                                <button onclick="window.TWStockTab.toggleSection('pe')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-primary uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="percent" class="w-3 h-3"></i>
                                        估值指標 (P/E · 殖利率 · P/B)
                                    </h3>
                                    <i id="twstock-chevron-pe" data-lucide="chevron-up" class="w-3.5 h-3.5 text-primary/60 group-hover:text-primary transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-primary/40 to-transparent"></div>
                            </div>
                            <div id="twstock-section-body-pe">
                                <div id="twstock-info-pe-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                                </div>
                                <div id="twstock-info-pe" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 px-1"></div>
                            </div>
                        </section>

                        <!-- ③ Major Announcements section -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-yellow-500/40 to-transparent"></div>
                                <button onclick="window.TWStockTab.toggleSection('news')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-yellow-400 uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="megaphone" class="w-3 h-3"></i>
                                        今日重大訊息
                                    </h3>
                                    <i id="twstock-chevron-news" data-lucide="chevron-up" class="w-3.5 h-3.5 text-yellow-400/60 group-hover:text-yellow-400 transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-yellow-500/40 to-transparent"></div>
                            </div>
                            <div id="twstock-section-body-news">
                                <div id="twstock-info-news-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-400"></div>
                                </div>
                                <div id="twstock-info-news" class="space-y-2 px-1"></div>
                            </div>
                        </section>

                        <!-- ④ Dividend Calendar -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-success/40 to-transparent"></div>
                                <button onclick="window.TWStockTab.toggleSection('dividend')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-success uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="calendar-check" class="w-3 h-3"></i>
                                        股利分派行事曆
                                    </h3>
                                    <i id="twstock-chevron-dividend" data-lucide="chevron-up" class="w-3.5 h-3.5 text-success/60 group-hover:text-success transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-success/40 to-transparent"></div>
                            </div>
                            <div id="twstock-section-body-dividend">
                                <div id="twstock-info-div-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-success"></div>
                                </div>
                                <div id="twstock-info-dividend" class="grid grid-cols-1 sm:grid-cols-2 gap-2 px-1"></div>
                            </div>
                        </section>

                        <!-- ⑤ Foreign Holding Top 20 -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-accent/40 to-transparent"></div>
                                <button onclick="window.TWStockTab.toggleSection('foreign')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-accent uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="globe" class="w-3 h-3"></i>
                                        外資持股前 20 名
                                    </h3>
                                    <i id="twstock-chevron-foreign" data-lucide="chevron-up" class="w-3.5 h-3.5 text-accent/60 group-hover:text-accent transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-accent/40 to-transparent"></div>
                            </div>
                            <div id="twstock-section-body-foreign">
                                <div id="twstock-info-foreign-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-accent"></div>
                                </div>
                                <div id="twstock-info-foreign" class="overflow-x-auto rounded-2xl border border-white/5 px-1"></div>
                            </div>
                        </section>

                    </div>
                </div>

                <!-- AI Pulse Container -->
                <div id="twstock-pulse-content" class="absolute inset-0 overflow-y-auto custom-scrollbar hidden pb-32">
                    <div class="max-w-5xl mx-auto pt-4 px-2">
                        <!-- Premium Search Input for Pulse -->
                        <div class="relative mb-8">
                            <div class="absolute inset-0 bg-gradient-to-r from-primary/10 via-accent/5 to-transparent rounded-3xl blur-2xl opacity-50"></div>
                            <div class="relative flex items-center gap-3 bg-surface/60 backdrop-blur-xl border border-white/10 p-2 rounded-2xl shadow-xl">
                                <div class="pl-4 flex-shrink-0">
                                    <i data-lucide="search" class="w-5 h-5 text-primary/70"></i>
                                </div>
                                <input type="text" id="twstockPulseSearchInput" placeholder="輸入台股代號 (如: 2330)"
                                    class="flex-1 bg-transparent border-none outline-none text-textMain placeholder-textMuted/50 text-base font-mono tracking-wider focus:ring-0 w-full min-w-0">
                                <button id="twstockPulseSearchBtn" class="bg-primary/20 hover:bg-primary text-primary hover:text-background border border-primary/30 hover:border-primary transition-all duration-300 px-6 py-3 rounded-xl font-bold tracking-[0.1em] text-sm flex items-center gap-2 flex-shrink-0">
                                    <span class="hidden sm:inline">深度分析</span>
                                    <i data-lucide="zap" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>

                        <div id="twstock-pulse-loader" class="hidden items-center justify-center py-20 flex flex-col">
                            <div class="w-16 h-16 relative">
                                <div class="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                                <div class="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                <i data-lucide="brain" class="absolute inset-0 m-auto w-6 h-6 text-primary animate-pulse"></i>
                            </div>
                            <p class="text-[11px] text-primary font-bold tracking-widest uppercase mt-6 animate-pulse">AI 正在深度分析籌碼與基本面...</p>
                        </div>

                        <div id="twstock-pulse-result" class="space-y-6 hidden"></div>
                    </div>
                </div>
            </div>
        </div>
    `,

    // Tab: US Stock
    usstock: `
        <div class="h-full flex flex-col px-4 md:px-6 pt-6 md:pt-8">
            <!-- Header -->
            <div class="flex items-center justify-between mb-4 pr-12 md:pr-16">
                <h2 class="font-serif text-3xl text-secondary" data-i18n="usstock.title">US Stock</h2>
                <div class="flex items-center gap-2">
                    <button onclick="window.USStockTab.refreshCurrent()" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Sub-tab Navigation -->
            <div class="flex gap-1 p-1 bg-background/50 border border-white/5 rounded-xl mb-6">
                <button id="usstock-btn-market" onclick="window.USStockTab.switchSubTab('market')"
                    class="usstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background shadow-md">
                    <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                    <span data-i18n="nav.market">Market Watch</span>
                </button>
                <button id="usstock-btn-pulse" onclick="window.USStockTab.switchSubTab('pulse')"
                    class="usstock-sub-tab flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5">
                    <i data-lucide="activity" class="w-4 h-4"></i>
                    <span data-i18n="nav.pulse">AI Pulse</span>
                </button>
            </div>

            <!-- Content Area -->
            <div class="flex-1 overflow-visible relative">

                <!-- Market Watch Content -->
                <div id="usstock-market-content" class="absolute inset-0 overflow-y-auto custom-scrollbar pb-32">
                    <div class="space-y-8">

                        <!-- ① Watchlist -->
                        <section>
                            <div class="flex items-center gap-3 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-primary/40 to-transparent"></div>
                                <h3 class="text-[10px] font-black text-primary uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                    <i data-lucide="star" class="w-3 h-3 text-yellow-400"></i>
                                    自選清單
                                </h3>
                                <div class="h-px flex-1 bg-gradient-to-l from-primary/40 to-transparent"></div>
                            </div>
                            <div id="usstock-screener-controls" class="px-1"></div>
                            <div id="usstock-market-loader" class="hidden items-center justify-center py-10 flex">
                                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                            </div>
                            <div id="usstock-screener-list" class="space-y-2 px-1"></div>

                            <!-- My Alerts (US Stock) -->
                            <div id="alert-list-section-usstock" class="mt-4 px-1">
                                <h4 class="text-textMuted text-xs font-medium uppercase tracking-wide mb-2" data-i18n="modals.priceAlert.myAlerts">我的警報</h4>
                                <div id="alert-list-usstock" class="space-y-0">
                                    <p class="text-textMuted text-xs py-1" data-i18n="modals.priceAlert.noAlerts">尚無警報</p>
                                </div>
                            </div>
                        </section>

                        <!-- ② 大盤指數 (collapsible) -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-primary/40 to-transparent"></div>
                                <button onclick="window.USStockTab.toggleSection('indices')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-primary uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="trending-up" class="w-3 h-3"></i>
                                        大盤指數
                                    </h3>
                                    <i id="usstock-chevron-indices" data-lucide="chevron-up" class="w-3.5 h-3.5 text-primary/60 group-hover:text-primary transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-primary/40 to-transparent"></div>
                            </div>
                            <div id="usstock-section-body-indices">
                                <div id="usstock-info-indices-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                                </div>
                                <div id="usstock-info-indices" class="grid grid-cols-1 sm:grid-cols-3 gap-3 px-1"></div>
                            </div>
                        </section>

                        <!-- ③ 今日新聞 (collapsible) -->
                        <section>
                            <div class="flex items-center gap-2 mb-4 px-1">
                                <div class="h-px flex-1 bg-gradient-to-r from-yellow-500/40 to-transparent"></div>
                                <button onclick="window.USStockTab.toggleSection('news')" class="flex items-center gap-1.5 group">
                                    <h3 class="text-[10px] font-black text-yellow-400 uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5">
                                        <i data-lucide="megaphone" class="w-3 h-3"></i>
                                        今日美股新聞
                                    </h3>
                                    <i id="usstock-chevron-news" data-lucide="chevron-up" class="w-3.5 h-3.5 text-yellow-400/60 group-hover:text-yellow-400 transition-transform duration-200"></i>
                                </button>
                                <div class="h-px flex-1 bg-gradient-to-l from-yellow-500/40 to-transparent"></div>
                            </div>
                            <div id="usstock-section-body-news">
                                <div id="usstock-info-news-loader" class="hidden py-6 flex items-center justify-center">
                                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-400"></div>
                                </div>
                                <div id="usstock-info-news" class="space-y-2 px-1"></div>
                            </div>
                        </section>

                    </div>
                </div>

                <!-- AI Pulse Content -->
                <div id="usstock-pulse-content" class="absolute inset-0 overflow-y-auto custom-scrollbar hidden pb-32">
                    <div class="max-w-5xl mx-auto pt-4 px-2">
                        <div class="relative mb-8">
                            <div class="absolute inset-0 bg-gradient-to-r from-primary/10 via-accent/5 to-transparent rounded-3xl blur-2xl opacity-50"></div>
                            <div class="relative flex items-center gap-3 bg-surface/60 backdrop-blur-xl border border-white/10 p-2 rounded-2xl shadow-xl">
                                <div class="pl-4 flex-shrink-0">
                                    <i data-lucide="search" class="w-5 h-5 text-primary/70"></i>
                                </div>
                                <input type="text" id="usstockPulseSearchInput" placeholder="輸入美股代號 (如: AAPL)"
                                    class="flex-1 bg-transparent border-none outline-none text-textMain placeholder-textMuted/50 text-base font-mono tracking-wider focus:ring-0 w-full min-w-0"
                                    oninput="this.value = this.value.replace(/[^A-Za-z.^]/g, '').toUpperCase()">
                                <button id="usstockPulseSearchBtn" class="bg-primary/20 hover:bg-primary text-primary hover:text-background border border-primary/30 hover:border-primary transition-all duration-300 px-6 py-3 rounded-xl font-bold tracking-[0.1em] text-sm flex items-center gap-2 flex-shrink-0">
                                    <span class="hidden sm:inline">深度分析</span>
                                    <i data-lucide="zap" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>
                        <div id="usstock-pulse-loader" class="hidden items-center justify-center py-20 flex flex-col">
                            <div class="w-16 h-16 relative">
                                <div class="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                                <div class="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                <i data-lucide="brain" class="absolute inset-0 m-auto w-6 h-6 text-primary animate-pulse"></i>
                            </div>
                            <p class="text-[11px] text-primary font-bold tracking-widest uppercase mt-6 animate-pulse">AI 正在深度分析技術面與基本面...</p>
                        </div>
                        <div id="usstock-pulse-result" class="space-y-6 hidden"></div>
                    </div>
                </div>

            </div>
        </div>
    `,


    // Tab: Friends (Integrated Social Hub - Friends + Messages)
    friends: `
    <div class="h-full flex flex-col">
            <!-- Header with Tab Switcher -->
            <div class="flex items-center justify-between pl-4 pr-4 md:pr-16 py-3 border-b border-white/5 bg-surface/50">
                <h2 class="font-serif text-2xl text-secondary" data-i18n="friends.title"></h2>
                <div class="flex items-center gap-2">
                    <span id="friends-badge-total" class="hidden px-2 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                    <button onclick="SocialHub.refresh()" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Sub-tab Navigation -->
            <div class="flex gap-1 p-2 bg-background/50 border-b border-white/5">
                <button onclick="SocialHub.switchSubTab('messages')" id="social-tab-messages"
                    class="social-sub-tab flex-1 py-2.5 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 bg-primary text-background">
                    <i data-lucide="message-circle" class="w-4 h-4"></i>
                    <span data-i18n="friends.messages"></span>
                    <span id="messages-unread-badge" class="hidden px-1.5 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                </button>
                <button onclick="SocialHub.switchSubTab('friends')" id="social-tab-friends"
                    class="social-sub-tab flex-1 py-2.5 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5">
                    <i data-lucide="users" class="w-4 h-4"></i>
                    <span data-i18n="friends.friends"></span>
                    <span id="friends-request-badge" class="hidden px-1.5 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                </button>
            </div>

            <!-- ==================== MESSAGES SUB - TAB ==================== -->
            <div id="social-content-messages" class="flex-1 flex overflow-hidden">
                <!-- Conversation List (Left) -->
                <div id="social-conv-sidebar" class="w-full md:w-80 lg:w-96 border-r border-white/5 flex flex-col bg-surface/30">
                    <div id="social-conv-list" class="flex-1 overflow-y-auto">
                        <div class="flex items-center justify-center h-full">
                            <div class="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full"></div>
                        </div>
                    </div>
                    <!-- Message Limit Info (Non-Pro) -->
                    <div id="social-msg-limit" class="p-3 border-t border-white/5 bg-background/50 text-xs text-textMuted hidden">
                        <div class="flex items-center justify-between">
                            <span><span data-i18n="friends.dailySent">Sent today:</span> <span id="social-limit-used">0</span>/<span id="social-limit-total">20</span></span>
                            <a href="/static/forum/premium.html" onclick="sessionStorage.setItem('returnToTab', 'friends')" class="text-primary hover:underline" data-i18n="friends.upgradePro">Upgrade Pro</a>
                        </div>
                    </div>
                </div>

                <!-- Chat Section (Desktop: inline, Mobile: hidden) -->
                <div id="social-chat-section" class="hidden md:flex flex-1 flex-col bg-background relative h-full">
                    <!-- Empty State (shown when no conversation selected) -->
                    <div id="social-chat-empty" class="flex-1 flex items-center justify-center">
                        <div class="text-center text-textMuted opacity-60">
                            <i data-lucide="message-circle" class="w-12 h-12 mx-auto mb-4"></i>
                            <p class="text-lg font-medium mb-2" data-i18n="friends.selectConversation">Select a conversation</p>
                            <p class="text-sm" data-i18n="friends.clickToStart">Click a conversation on the left to start chatting</p>
                        </div>
                    </div>

                    <!-- Chat Content (hidden until conversation selected) -->
                    <div id="social-chat-content" class="hidden flex-1 flex flex-col h-full">
                        <!-- Chat Header -->
                        <div id="social-chat-header" class="p-3 border-b border-white/5 flex items-center gap-3 bg-surface/50">
                            <a id="social-chat-profile-link" href="#" class="flex items-center gap-3 flex-1 min-w-0 hover:opacity-80 transition">
                                <div id="social-chat-avatar" class="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold flex-shrink-0">U</div>
                                <span id="social-chat-username" class="font-bold text-textMain truncate">Username</span>
                            </a>
                        </div>

                        <!-- Messages Container -->
                        <div id="social-messages-container" class="flex-1 overflow-y-auto p-4 messages-scroll">
                            <!-- Messages will be rendered here -->
                        </div>

                        <!-- Message Input -->
                        <div id="social-msg-input-container" class="p-3 border-t border-white/5 bg-surface/30">
                            <form id="social-msg-form" onsubmit="SocialHub.sendMessage(event)" class="w-full">
                                <div class="flex items-end gap-2">
                                    <div class="flex-1 bg-background border border-white/10 rounded-xl px-3 py-2 focus-within:border-primary/50 transition">
                                        <textarea id="social-msg-input"
                                            class="w-full bg-transparent text-textMain placeholder-textMuted resize-none leading-6 outline-none text-sm"
                                            placeholder="Type a message..." data-i18n="friends.typeMessage" data-i18n-attr="placeholder" rows="1" maxlength="500"
                                            onkeydown="SocialHub.handleInputKeydown(event)"
                                            oninput="SocialHub.autoResizeInput(this); SocialHub.updateCharCount()"></textarea>
                                    </div>
                                    <button type="submit" id="social-send-btn"
                                        class="p-2.5 bg-primary hover:brightness-110 text-background rounded-xl transition disabled:opacity-50 shadow-lg shadow-primary/20 flex-shrink-0"
                                        disabled>
                                        <i data-lucide="send" class="w-5 h-5"></i>
                                    </button>
                                </div>
                                <div class="flex items-center justify-end mt-1 px-1">
                                    <span id="social-char-count" class="text-[10px] text-textMuted/50">0/500</span>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ==================== FRIENDS SUB - TAB ==================== -->
    <div id="social-content-friends" class="flex-1 overflow-y-auto p-4 hidden">
        <div class="max-w-4xl mx-auto space-y-6">
            <!-- Search Section -->
            <div class="bg-surface border border-white/5 rounded-2xl p-6">
                <h3 class="font-bold text-secondary text-lg mb-4 flex items-center gap-2">
                    <i data-lucide="search" class="w-5 h-5"></i>
                    <span data-i18n="friends.findFriends">Find Friends</span>
                </h3>
                <div class="relative">
                    <input type="text" id="friend-search-input" placeholder="Search by username..." data-i18n="friends.searchPlaceholder" data-i18n-attr="placeholder"
                        class="w-full bg-background border border-white/10 rounded-xl px-4 py-3 pl-10 text-secondary outline-none focus:border-primary/50 transition"
                        oninput="if(typeof handleFriendSearch === 'function') handleFriendSearch(this.value)">
                        <i data-lucide="search" class="w-5 h-5 text-textMuted absolute left-3 top-1/2 -translate-y-1/2"></i>
                </div>
                <div id="search-results" class="mt-4 space-y-2 hidden"></div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Pending Requests -->
                <div class="bg-surface border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary text-lg mb-4 flex items-center gap-2">
                        <i data-lucide="user-plus" class="w-5 h-5 text-primary"></i>
                        <span data-i18n="friends.friendRequests">Friend Requests</span>
                        <span id="pending-count-badge" class="hidden px-2 py-0.5 text-xs bg-danger text-white rounded-full"></span>
                    </h3>
                    <div id="pending-requests-list" class="space-y-2">
                        <div class="text-center text-textMuted py-6 opacity-50">
                            <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                            <span data-i18n="friends.loadingRequests">Loading requests...</span>
                        </div>
                    </div>
                </div>

                <!-- My Friends -->
                <div class="bg-surface border border-white/5 rounded-2xl p-6">
                    <h3 class="font-bold text-secondary text-lg mb-4 flex items-center gap-2">
                        <i data-lucide="users" class="w-5 h-5 text-success"></i>
                        <span data-i18n="friends.myFriends">My Friends</span>
                        <span id="friends-count-badge" class="hidden px-2 py-0.5 text-xs bg-white/10 text-textMuted rounded-full">0</span>
                    </h3>
                    <!-- My Friends -->
                    <div class="bg-surface border border-white/5 rounded-2xl p-6 relative">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="font-bold text-secondary text-lg flex items-center gap-2">
                                <i data-lucide="users" class="w-5 h-5 text-success"></i>
                                <span data-i18n="friends.myFriends">My Friends</span>
                                <span id="friends-count-badge" class="hidden px-2 py-0.5 text-xs bg-white/10 text-textMuted rounded-full">0</span>
                            </h3>
                            <button onclick="FriendsUI.toggleBlockedView()" class="text-xs text-textMuted hover:text-danger transition flex items-center gap-1">
                                <i data-lucide="ban" class="w-3 h-3"></i>
                                <span data-i18n="friends.manageBlocked">Manage Blocklist</span>
                            </button>
                        </div>

                        <!-- Friends List View -->
                        <div id="friends-view-container">
                            <div id="friends-list" class="space-y-2">
                                <div class="text-center text-textMuted py-6 opacity-50">
                                    <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                                    <span data-i18n="friends.loadingFriends">Loading friends...</span>
                                </div>
                            </div>
                        </div>

                        <!-- Blocked List View (Hidden by default) -->
                        <div id="blocked-view-container" class="hidden">
                            <div class="flex items-center gap-2 mb-4 p-3 bg-danger/5 rounded-lg border border-danger/10">
                                <i data-lucide="info" class="w-4 h-4 text-danger"></i>
                                <p class="text-xs text-textMuted" data-i18n="friends.blockedInfo">Blocked users cannot send you messages or friend requests.</p>
                            </div>
                            <div id="blocked-users-list" class="space-y-2">
                                <!-- Blocked users injected here -->
                            </div>
                        </div>
                    </div>
                </div>

                <div class="h-20"></div>
            </div>
        </div>
    </div>
`,

    // Tab: Settings (保持原樣，這裡省略以節省空間)
    settings: `
    <div class="max-w-2xl mx-auto">
             <h2 class="font-serif text-3xl text-secondary mb-8" data-i18n="settings.title">Settings</h2>

             <div class="space-y-10">
                <!-- User Profile Section -->
                <div id="settings-profile-card" class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-start justify-between mb-6">
                        <div class="flex items-center gap-4">
                            <div class="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-background font-bold text-2xl shadow-lg shadow-primary/20" id="profile-avatar">
                                U
                            </div>
                            <div>
                                <h3 class="text-xl font-serif text-secondary" id="profile-username">User</h3>
                                <p class="text-xs text-textMuted font-mono" id="profile-uid">UID: --</p>
                                <div class="mt-1 flex items-center gap-2">
                                    <span class="px-2 py-0.5 rounded-md bg-white/5 text-[10px] text-textMuted border border-white/5 uppercase" id="profile-method">PASSWORD</span>
                                </div>
                            </div>
                        </div>
                        <div id="premium-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted">
                            <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                            <span data-i18n="settings.wallet.loading">Loading</span>
                        </div>
                    </div>

                    <!-- TEST MODE: Multi-User Switcher (hidden in production, shown by auth.js when test_mode=true) -->
                    <div id="dev-user-switcher" class="mt-4 pt-4 border-t border-white/5 hidden">
                        <p class="text-[10px] text-textMuted uppercase tracking-wider mb-2 font-bold opacity-50" data-i18n="settings.profile.devSwitchUser">Dev: Switch User</p>
                        <div class="grid grid-cols-2 gap-2">
                            <button onclick="handleDevSwitchUser('test-user-001')" class="py-2 bg-white/5 hover:bg-primary/20 hover:text-primary rounded-lg text-xs font-mono transition border border-white/5">
                                User 001
                            </button>
                            <button onclick="handleDevSwitchUser('test-user-002')" class="py-2 bg-white/5 hover:bg-accent/20 hover:text-accent rounded-lg text-xs font-mono transition border border-white/5">
                                User 002
                            </button>
                            <button onclick="handleDevSwitchUser('test-user-003')" class="py-2 bg-white/5 hover:bg-success/20 hover:text-success rounded-lg text-xs font-mono transition border border-white/5">
                                User 003 (PRO)
                            </button>
                            <button onclick="handleDevSwitchUser('test-user-004')" class="py-2 bg-white/5 hover:bg-warning/20 hover:text-warning rounded-lg text-xs font-mono transition border border-white/5">
                                User 004 (PRO)
                            </button>
                        </div>
                    </div>

                    <button onclick="handleLogout()" class="w-full py-3 bg-white/5 hover:bg-danger/10 text-textMuted hover:text-danger border border-white/5 hover:border-danger/20 font-bold rounded-xl transition flex items-center justify-center gap-2 mt-4">
                        <i data-lucide="log-out" class="w-4 h-4"></i>
                        <span data-i18n="settings.profile.logout">Logout</span>
                    </button>
                </div>

                <!-- Pi Wallet Section -->
                <div id="settings-wallet-card" class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between mb-6">
                        <div class="flex items-center gap-3">
                            <div id="settings-wallet-icon" class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                <i data-lucide="wallet" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary" data-i18n="settings.wallet.title">Pi Wallet</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.wallet.description">Connect your Pi wallet for transactions</p>
                            </div>
                        </div>
                        <div id="settings-wallet-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted">
                            <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                            <span data-i18n="settings.wallet.loading">Loading</span>
                        </div>
                    </div>

                    <div id="settings-wallet-content" class="space-y-4">
                        <div id="wallet-not-linked" class="hidden">
                            <div class="bg-background/50 rounded-xl p-4 border border-white/5 mb-4">
                                <p class="text-sm text-textMuted leading-relaxed">
                                    <i data-lucide="info" class="w-4 h-4 inline-block mr-1 opacity-60"></i>
                                    <span data-i18n="settings.wallet.benefits">After linking your Pi Wallet:</span>
                                </p>
                                <ul class="text-xs text-textMuted mt-2 space-y-1 ml-5">
                                    <li><span data-i18n="settings.wallet.benefit1">Post on the forum (costs</span> <span data-price="create_post"><i data-lucide="loader" class="w-3 h-3 animate-spin inline-block"></i></span>)</li>
                                    <li data-i18n="settings.wallet.benefit2">Tip quality content creators</li>
                                    <li data-i18n="settings.wallet.benefit3">Receive tips from other users</li>
                                </ul>
                            </div>
                            <button onclick="handleSettingsLinkWallet()" class="w-full py-3.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 font-bold rounded-xl transition flex items-center justify-center gap-2">
                                <i data-lucide="link" class="w-4 h-4"></i>
                                <span data-i18n="settings.wallet.linkButton">Link Pi Wallet</span>
                            </button>
                            <p class="text-[10px] text-textMuted/60 text-center mt-2" data-i18n="settings.wallet.requirePiBrowser">Must be opened in Pi Browser</p>
                        </div>

                        <div id="wallet-linked" class="hidden">
                            <div class="bg-success/5 rounded-xl p-4 border border-success/10">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
                                        <i data-lucide="check-circle" class="w-5 h-5 text-success"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-success" data-i18n="settings.wallet.connected">Pi Wallet Connected</p>
                                        <p id="settings-wallet-username" class="text-xs text-textMuted font-mono">@username</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                 <!-- LLM Configuration -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between mb-6">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                <i data-lucide="brain" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary" data-i18n="settings.ai.title">AI Intelligence</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.ai.description">Configure your LLM provider</p>
                            </div>
                        </div>
                        <div id="llm-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                        </div>
                    </div>

                    <div class="space-y-6">
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.provider">Provider</label>
                            <select id="llm-provider-select" onchange="updateLLMKeyInput(); updateAvailableModels()" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none">
                                <option value="openai">OpenAI</option>
                                <option value="google_gemini">Google Gemini</option>
                                <option value="openrouter">OpenRouter</option>
                            </select>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.apiKey">API Key</label>
                            <div class="flex gap-3">
                                <input type="password" id="llm-api-key-input" class="flex-1 bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 font-mono text-sm" placeholder="sk-...">
                                <button onclick="testLLMKey()" class="px-5 bg-surfaceHighlight hover:bg-white/10 text-secondary rounded-xl transition font-bold text-xs whitespace-nowrap" data-i18n="settings.ai.test">TEST</button>
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.model">Model</label>
                            <select id="llm-model-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none" style="display: block;">
                                <option value="" data-i18n="settings.ai.selectModel">Select a model</option>
                            </select>
                            <input type="text" id="llm-model-input" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-primary/50 transition mt-3"
                                   placeholder="e.g., openai/gpt-4o, anthropic/claude-3.5-sonnet" data-i18n="settings.ai.modelPlaceholder" data-i18n-attr="placeholder"
                                   style="display: none;" />
                            <p id="llm-key-status" class="mt-2 text-xs text-textMuted hidden"></p>
                        </div>

                        <button id="save-llm-key-btn" onclick="saveLLMKey()" class="w-full py-3.5 bg-primary text-background font-bold rounded-xl shadow-lg shadow-primary/10 opacity-50 cursor-not-allowed transition mt-2" disabled data-i18n="settings.ai.saveConfig">
                            Save AI Configuration
                        </button>
                    </div>
                </div>

                <!-- Tool Settings -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between mb-6">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                <i data-lucide="wrench" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary">工具設定</h3>
                                <p class="text-xs text-textMuted">選擇 AI 分析時使用的工具</p>
                            </div>
                        </div>
                    </div>
                    <div id="tool-settings-list" class="space-y-1">
                        <!-- Populated by initToolSettings() -->
                    </div>
                    <div id="tool-settings-free-notice" class="mt-4 hidden">
                        <div class="bg-yellow-400/5 border border-yellow-400/20 rounded-xl p-3 text-xs text-yellow-300/80 flex items-start gap-2">
                            <i data-lucide="lock" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0"></i>
                            <span>升級 Premium 會員即可自由開關所有工具，並解鎖 PRO 專屬資料來源。</span>
                        </div>
                    </div>
                </div>

                <!-- Navigation Customization -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                <i data-lucide="layout-grid" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary" data-i18n="settings.navigation.title">Navigation Customization</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.navigation.description">Customize your bottom navigation bar</p>
                            </div>
                        </div>
                        <button onclick="FeatureMenu.open()" class="px-4 py-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-xl transition font-bold text-sm flex items-center gap-2">
                            <i data-lucide="settings-2" class="w-4 h-4"></i>
                            <span data-i18n="settings.navigation.customize">Customize</span>
                        </button>
                    </div>
                    <div class="mt-4 bg-background/50 rounded-xl p-4 border border-white/5">
                        <p class="text-sm text-textMuted leading-relaxed">
                            <i data-lucide="info" class="w-4 h-4 inline-block mr-1 opacity-60"></i>
                            <span data-i18n="settings.navigation.info">Choose which features appear in your bottom navigation bar. At least 2 items must be enabled.</span>
                        </p>
                    </div>
                </div>

                <!-- Premium Membership -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center gap-3 mb-6">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-500 flex items-center justify-center">
                            <i data-lucide="star" class="w-5 h-5 text-white"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-serif text-yellow-400" data-i18n="settings.premium.title">Premium Membership</h3>
                            <p class="text-xs text-textMuted" data-i18n="settings.premium.description">Unlock advanced features</p>
                        </div>
                    </div>

                    <div class="space-y-4">
                        <div class="bg-background/50 rounded-xl p-4 border border-white/5">
                            <p class="text-sm text-textMuted leading-relaxed">
                                <i data-lucide="crown" class="w-4 h-4 inline-block mr-1 text-yellow-400"></i>
                                <span data-i18n="settings.premium.benefits">Premium members enjoy:</span>
                            </p>
                            <ul class="text-xs text-textMuted mt-2 space-y-1 ml-5">
                                <li data-i18n="settings.premium.benefit1">Unlimited posting</li>
                                <li data-i18n="settings.premium.benefit2">Unlimited replies</li>
                                <li data-i18n="settings.premium.benefit3">Early access to new features</li>
                                <li data-i18n="settings.premium.benefit4">Exclusive premium badge</li>
                            </ul>
                        </div>

                        <button onclick="handleUpgradeToPremium()" class="w-full py-3.5 bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-400 hover:to-orange-400 text-background font-bold rounded-xl transition flex items-center justify-center gap-2 upgrade-premium-btn">
                            <i data-lucide="zap" class="w-4 h-4"></i>
                            <span><span data-i18n="settings.premium.upgradeButton">Upgrade to Premium -</span> <span data-price="premium"><i data-lucide="loader" class="w-3 h-3 animate-spin"></i></span></span>
                        </button>

                        <p class="text-[10px] text-textMuted/60 text-center" data-i18n="settings.premium.oneTimePayment">One-time payment, effective immediately</p>
                    </div>
                </div>

                <!-- Exchange Keys -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between mb-6">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center">
                                <i data-lucide="key" class="w-5 h-5 text-secondary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-secondary" data-i18n="settings.exchange.title">Exchange Keys</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.exchange.description">Connect your OKX account</p>
                            </div>
                        </div>
                        <div id="okx-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                        </div>
                    </div>

                    <div id="okx-not-connected" class="hidden">
                        <div class="text-center py-4 mb-4 bg-background/50 rounded-xl">
                            <i data-lucide="unplug" class="w-8 h-8 text-textMuted mx-auto mb-2"></i>
                            <p class="text-sm text-textMuted" data-i18n="settings.exchange.notConnected">No exchange connected</p>
                        </div>
                        <button onclick="document.getElementById('apikey-modal').classList.remove('hidden')" class="w-full py-3.5 bg-gradient-to-r from-primary to-accent text-background font-bold rounded-2xl transition flex items-center justify-center gap-2 shadow-lg shadow-primary/20 hover:scale-[1.02]">
                            <i data-lucide="plug" class="w-4 h-4"></i> <span data-i18n="settings.exchange.connectButton">Connect OKX</span>
                        </button>
                    </div>

                    <div id="okx-connected" class="hidden">
                        <div class="flex items-center justify-between p-4 bg-success/5 border border-success/20 rounded-xl mb-4">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
                                    <i data-lucide="check" class="w-5 h-5 text-success"></i>
                                </div>
                                <div>
                                    <p class="text-sm font-medium text-secondary" data-i18n="settings.exchange.connected">OKX Connected</p>
                                    <p class="text-xs text-textMuted" data-i18n="settings.exchange.storedLocally">API key stored locally</p>
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <button onclick="document.getElementById('apikey-modal').classList.remove('hidden')" class="py-3 bg-surfaceHighlight hover:bg-white/10 border border-white/5 text-secondary rounded-xl transition flex items-center justify-center gap-2 text-sm font-medium">
                                <i data-lucide="edit-3" class="w-4 h-4"></i> <span data-i18n="settings.exchange.update">Update</span>
                            </button>
                            <button onclick="disconnectOKX()" class="py-3 bg-danger/10 hover:bg-danger/20 border border-danger/20 text-danger rounded-xl transition flex items-center justify-center gap-2 text-sm font-medium">
                                <i data-lucide="unplug" class="w-4 h-4"></i> <span data-i18n="settings.exchange.disconnect">Disconnect</span>
                            </button>
                        </div>
                    </div>
                </div>

                <button onclick="saveSettings()" id="btn-save-settings" class="w-full py-4 bg-secondary text-background font-bold rounded-2xl shadow-xl hover:scale-[1.02] transition" data-i18n="settings.saveAll">
                    Save All Settings
                </button>

                <!-- About & Legal -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center gap-3 mb-6">
                        <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <i data-lucide="info" class="w-5 h-5 text-primary"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-serif text-primary" data-i18n="settings.legal.title">About & Legal</h3>
                            <p class="text-xs text-textMuted" data-i18n="settings.legal.description">Terms, Privacy, and Community Guidelines</p>
                        </div>
                    </div>

                    <div class="space-y-3">
                        <a href="javascript:void(0)" onclick="showLegalPage('terms')" class="block w-full p-4 bg-background/50 hover:bg-background rounded-xl border border-white/5 hover:border-primary/20 transition group cursor-pointer">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <i data-lucide="file-text" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                                    <div>
                                        <p class="text-sm font-medium text-secondary" data-i18n="settings.legal.termsTitle">Terms of Service</p>
                                        <p class="text-xs text-textMuted" data-i18n="settings.legal.termsDesc">Usage rules and policies</p>
                                    </div>
                                </div>
                                <i data-lucide="chevron-right" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                            </div>
                        </a>

                        <a href="javascript:void(0)" onclick="showLegalPage('privacy')" class="block w-full p-4 bg-background/50 hover:bg-background rounded-xl border border-white/5 hover:border-primary/20 transition group cursor-pointer">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <i data-lucide="shield" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                                    <div>
                                        <p class="text-sm font-medium text-secondary" data-i18n="settings.legal.privacyTitle">Privacy Policy</p>
                                        <p class="text-xs text-textMuted" data-i18n="settings.legal.privacyDesc">Data protection and privacy</p>
                                    </div>
                                </div>
                                <i data-lucide="chevron-right" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                            </div>
                        </a>

                        <a href="javascript:void(0)" onclick="showLegalPage('guidelines')" class="block w-full p-4 bg-background/50 hover:bg-background rounded-xl border border-white/5 hover:border-primary/20 transition group cursor-pointer">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <i data-lucide="users" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                                    <div>
                                        <p class="text-sm font-medium text-secondary" data-i18n="settings.legal.guidelinesTitle">Community Guidelines</p>
                                        <p class="text-xs text-textMuted" data-i18n="settings.legal.guidelinesDesc">Governance and moderation rules</p>
                                    </div>
                                </div>
                                <i data-lucide="chevron-right" class="w-4 h-4 text-textMuted group-hover:text-primary transition"></i>
                            </div>
                        </a>
                    </div>
                </div>

                <div class="text-center pt-8 opacity-20 text-[10px] font-mono tracking-widest uppercase">
                    PI CryptoMind v1.2.0-Pi-Integrated
                </div>
             </div>
        </div >
    `,

    // Tab: Safety (Scam Tracker + Governance)
    safety: `
    <div class="max-w-4xl mx-auto space-y-6">
            <!-- Header -->
            <div class="flex items-center justify-between">
                <h2 class="font-serif text-2xl md:text-3xl text-secondary flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-danger/10 flex items-center justify-center">
                        <i data-lucide="shield-alert" class="w-5 h-5 text-danger"></i>
                    </div>
                    <span data-i18n="safety.title">Community Safety</span>
                </h2>
                <div class="flex items-center gap-2">
                    <button onclick="SafetyTab.openGovernanceModal()" class="px-3 py-2 bg-accent/10 hover:bg-accent/20 text-accent rounded-xl text-sm font-bold flex items-center gap-1.5 transition">
                        <i data-lucide="scale" class="w-4 h-4"></i>
                        <span class="hidden sm:inline" data-i18n="safety.governance">Governance</span>
                    </button>
                    <button onclick="SafetyTab.openSubmitModal()" class="px-3 py-2 bg-primary/10 hover:bg-primary/20 text-primary rounded-xl text-sm font-bold flex items-center gap-1.5 transition">
                        <i data-lucide="alert-triangle" class="w-4 h-4"></i>
                        <span class="hidden sm:inline" data-i18n="safety.reportWallet">Report Wallet</span>
                    </button>
                </div>
            </div>

            <!-- Search -->
            <div class="bg-surface border border-white/5 rounded-2xl p-4">
                <div class="flex gap-2">
                    <input type="text" id="safety-search-wallet" placeholder="Search wallet address..." data-i18n="safety.searchPlaceholder" data-i18n-attr="placeholder"
                        class="flex-1 bg-background border border-white/10 rounded-xl px-4 py-2.5 text-textMain focus:border-primary outline-none text-sm"
                        onkeypress="if(event.key==='Enter') SafetyTab.handleSearch()">
                    <button onclick="SafetyTab.handleSearch()" class="bg-primary text-background px-5 py-2.5 rounded-xl font-bold hover:brightness-110 transition text-sm">
                        <i data-lucide="search" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Filters -->
            <div class="flex flex-wrap gap-2">
                <select id="safety-filter-type" onchange="SafetyTab.applyFilters()"
                    class="bg-surface border border-white/5 rounded-xl px-3 py-2 text-textMuted text-xs font-bold outline-none focus:border-primary/50 cursor-pointer">
                    <option value="" data-i18n="safety.filters.allTypes">All Types</option>
                </select>
                <select id="safety-filter-status" onchange="SafetyTab.applyFilters()"
                    class="bg-surface border border-white/5 rounded-xl px-3 py-2 text-textMuted text-xs font-bold outline-none focus:border-primary/50 cursor-pointer">
                    <option value="" data-i18n="safety.filters.allStatus">All Status</option>
                    <option value="verified" data-i18n="safety.filters.verified">Verified</option>
                    <option value="pending" data-i18n="safety.filters.pending">Pending</option>
                    <option value="disputed" data-i18n="safety.filters.disputed">Disputed</option>
                </select>
                <select id="safety-sort-by" onchange="SafetyTab.applyFilters()"
                    class="bg-surface border border-white/5 rounded-xl px-3 py-2 text-textMuted text-xs font-bold outline-none focus:border-primary/50 cursor-pointer">
                    <option value="latest" data-i18n="safety.filters.latest">Latest</option>
                    <option value="most_voted" data-i18n="safety.filters.mostVoted">Most Voted</option>
                    <option value="most_viewed" data-i18n="safety.filters.mostViewed">Most Viewed</option>
                </select>
            </div>

            <!-- Report List -->
            <div id="safety-report-list" class="space-y-3">
                <div class="text-center text-textMuted py-8">
                    <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
                    <span data-i18n="common.loading">Loading...</span>
                </div>
            </div>

            <!-- Load More -->
    <div class="text-center">
        <button id="safety-btn-load-more" onclick="SafetyTab.loadMore()" class="bg-surface hover:bg-surfaceHighlight text-textMuted px-6 py-3 rounded-xl font-bold transition border border-white/5 hidden" data-i18n="safety.loadMore">
            Load More
        </button>
    </div>
        </div>

        <!-- Submit Scam Report Modal -->
        <div id="safety-submit-modal" class="fixed inset-0 bg-background/90 backdrop-blur-sm z-[70] hidden flex items-center justify-center p-4">
            <div class="bg-surface w-full max-w-lg max-h-[85vh] flex flex-col rounded-[2rem] border border-white/5 shadow-2xl">
                <div class="p-6 border-b border-white/5 flex justify-between items-center shrink-0">
                    <h3 class="font-serif text-xl text-secondary flex items-center gap-2">
                        <i data-lucide="alert-triangle" class="w-5 h-5 text-danger"></i> <span data-i18n="safety.submit.title">Report Scam Wallet</span>
                    </h3>
                    <button onclick="SafetyTab.closeSubmitModal()" class="w-8 h-8 rounded-full bg-background flex items-center justify-center text-textMuted hover:text-secondary transition">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
                <div class="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
                    <div>
                        <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2"><span data-i18n="safety.submit.scamWallet">Scam Wallet Address</span> <span class="text-danger">*</span></label>
                        <input type="text" id="safety-scam-wallet" placeholder="G..."
                            class="w-full bg-background border border-white/5 rounded-xl px-4 py-3 text-secondary outline-none focus:border-primary/50 transition font-mono text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2"><span data-i18n="safety.submit.yourWallet">Your Wallet Address</span> <span class="text-danger">*</span></label>
                        <input type="text" id="safety-reporter-wallet" placeholder="G..."
                            class="w-full bg-background border border-white/5 rounded-xl px-4 py-3 text-secondary outline-none focus:border-primary/50 transition font-mono text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2"><span data-i18n="safety.submit.scamType">Scam Type</span> <span class="text-danger">*</span></label>
                        <select id="safety-scam-type"
                            class="w-full bg-background border border-white/5 rounded-xl px-4 py-3 text-secondary outline-none focus:border-primary/50 transition text-sm">
                            <option value="" data-i18n="safety.submit.selectType">Select type...</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2"><span data-i18n="safety.submit.description">Description</span> <span class="text-danger">*</span></label>
                        <textarea id="safety-description" rows="4" placeholder="Describe the scam details (min 20 chars)..." data-i18n="safety.submit.descPlaceholder" data-i18n-attr="placeholder"
                            class="w-full bg-background border border-white/5 rounded-xl px-4 py-3 text-secondary outline-none focus:border-primary/50 transition text-sm resize-none"></textarea>
                        <p class="text-[10px] text-textMuted mt-1"><span id="safety-char-count">0</span> / 2000</p>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2"><span data-i18n="safety.submit.txHash">Transaction Hash</span> <span class="text-textMuted/50">(Optional)</span></label>
                        <input type="text" id="safety-tx-hash" placeholder="64-char hash..." data-i18n="safety.submit.txHashPlaceholder" data-i18n-attr="placeholder"
                            class="w-full bg-background border border-white/5 rounded-xl px-4 py-3 text-secondary outline-none focus:border-primary/50 transition font-mono text-sm">
                    </div>
                </div>
                <div class="p-6 border-t border-white/5 shrink-0">
                    <button onclick="SafetyTab.submitReport()" id="safety-btn-submit"
                        class="w-full py-3.5 bg-danger hover:brightness-110 text-white font-bold rounded-xl transition shadow-lg flex items-center justify-center gap-2">
                        <i data-lucide="send" class="w-4 h-4"></i> <span data-i18n="safety.submit.submitButton">Submit Report</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Scam Report Detail Modal -->
        <div id="safety-detail-modal" class="fixed inset-0 bg-background/90 backdrop-blur-sm z-[70] hidden flex items-center justify-center p-4">
            <div class="bg-surface w-full max-w-lg max-h-[85vh] flex flex-col rounded-[2rem] border border-white/5 shadow-2xl">
                <div class="p-6 border-b border-white/5 flex justify-between items-center shrink-0">
                    <h3 class="font-serif text-xl text-secondary" data-i18n="safety.detail.title">Report Detail</h3>
                    <button onclick="SafetyTab.closeDetailModal()" class="w-8 h-8 rounded-full bg-background flex items-center justify-center text-textMuted hover:text-secondary transition">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
                <div id="safety-detail-content" class="flex-1 overflow-y-auto p-6 custom-scrollbar">
                    <div class="text-center text-textMuted py-8" data-i18n="common.loading">Loading...</div>
                </div>
                <div class="p-6 border-t border-white/5 shrink-0">
                    <div class="flex gap-3">
                        <button onclick="SafetyTab.voteOnDetail('approve')" class="flex-1 py-3 bg-success/10 hover:bg-success/20 text-success font-bold rounded-xl transition flex items-center justify-center gap-2">
                            <i data-lucide="thumbs-up" class="w-4 h-4"></i> <span data-i18n="safety.detail.confirm">Confirm</span> (<span id="safety-detail-approve">0</span>)
                        </button>
                        <button onclick="SafetyTab.voteOnDetail('reject')" class="flex-1 py-3 bg-danger/10 hover:bg-danger/20 text-danger font-bold rounded-xl transition flex items-center justify-center gap-2">
                            <i data-lucide="thumbs-down" class="w-4 h-4"></i> <span data-i18n="safety.detail.dispute">Dispute</span> (<span id="safety-detail-reject">0</span>)
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Governance Report Modal -->
    <div id="governance-modal" class="fixed inset-0 bg-background/90 backdrop-blur-sm z-[70] hidden flex items-center justify-center p-4">
        <div class="bg-surface w-full max-w-lg max-h-[85vh] flex flex-col rounded-[2rem] border border-white/5 shadow-2xl">
            <div class="p-6 border-b border-white/5 flex justify-between items-center shrink-0">
                <h3 class="font-serif text-xl text-secondary flex items-center gap-2">
                    <i data-lucide="scale" class="w-5 h-5 text-accent"></i> <span data-i18n="safety.gov.title">Community Governance</span>
                </h3>
                <button onclick="SafetyTab.closeGovernanceModal()" class="w-8 h-8 rounded-full bg-background flex items-center justify-center text-textMuted hover:text-secondary transition">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>

            <!-- Governance Tabs -->
            <div class="flex border-b border-white/5 px-6 pt-2 gap-1 overflow-x-auto shrink-0">
                <button onclick="SafetyTab.switchGovTab('gov-my-reports')" class="gov-tab-btn px-3 py-2 text-xs font-bold rounded-t-lg border-b-2 border-primary text-primary transition" data-gov-tab="gov-my-reports" data-i18n="safety.gov.myReportsTab">My Reports</button>
                <button onclick="SafetyTab.switchGovTab('gov-review')" class="gov-tab-btn px-3 py-2 text-xs font-bold rounded-t-lg border-b-2 border-transparent text-textMuted hover:text-secondary transition" data-gov-tab="gov-review"><span data-i18n="safety.gov.reviewTab">Review</span> <span class="text-[9px] bg-accent/20 text-accent px-1.5 py-0.5 rounded ml-1">PRO</span></button>
                <button onclick="SafetyTab.switchGovTab('gov-leaderboard')" class="gov-tab-btn px-3 py-2 text-xs font-bold rounded-t-lg border-b-2 border-transparent text-textMuted hover:text-secondary transition" data-gov-tab="gov-leaderboard" data-i18n="safety.gov.rankingTab">Ranking</button>
            </div>

            <div class="flex-1 overflow-y-auto custom-scrollbar">

                <!-- My Reports Tab (Active by Default) -->
                <div id="gov-my-reports-tab" class="gov-tab-content p-6">
                    <div class="flex gap-2 mb-4 overflow-x-auto pb-1">
                        <button onclick="SafetyTab.loadMyGovReports('all', this)" class="gov-filter-btn px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-primary border border-primary/20" data-i18n="common.all">All</button>
                        <button onclick="SafetyTab.loadMyGovReports('pending', this)" class="gov-filter-btn px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-textMuted border border-white/5" data-i18n="safety.filters.pending">Pending</button>
                        <button onclick="SafetyTab.loadMyGovReports('approved', this)" class="gov-filter-btn px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-textMuted border border-white/5" data-i18n="safety.gov.approved">Approved</button>
                        <button onclick="SafetyTab.loadMyGovReports('rejected', this)" class="gov-filter-btn px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-textMuted border border-white/5" data-i18n="safety.gov.rejected">Rejected</button>
                    </div>
                    <div id="gov-my-reports-list" class="space-y-3">
                        <div class="text-center text-textMuted py-8 text-sm" data-i18n="safety.gov.selectFilter">Select a filter to load reports</div>
                    </div>
                </div>

                <!-- Review Tab (PRO) -->
                <div id="gov-review-tab" class="gov-tab-content hidden p-6">
                    <div id="gov-pro-notice" class="text-center py-8">
                        <div class="w-16 h-16 bg-accent/10 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i data-lucide="lock" class="w-8 h-8 text-accent"></i>
                        </div>
                        <h4 class="font-bold text-secondary mb-2" data-i18n="safety.gov.proOnly">PRO Members Only</h4>
                        <p class="text-textMuted text-sm mb-4" data-i18n="safety.gov.proDesc">Upgrade to PRO to review reports and earn reputation.</p>
                    </div>
                    <div id="gov-review-content" class="hidden space-y-3">
                        <div id="gov-quota-display" class="bg-background/50 rounded-xl p-4 space-y-3 mb-4">
                            <div class="flex items-center justify-between">
                                <h4 class="text-xs font-bold text-textMuted flex items-center gap-1"><i data-lucide="info" class="w-3 h-3"></i> <span data-i18n="safety.gov.dailyQuota">Daily Quota</span></h4>
                                <span id="gov-quota-badge" class="text-[10px] px-2 py-0.5 rounded bg-white/5 text-textMuted">--</span>
                            </div>
                            <div class="w-full bg-white/5 rounded-full h-2">
                                <div id="gov-quota-bar" class="h-2 rounded-full bg-accent transition-all" style="width: 0%"></div>
                            </div>
                            <div class="text-[11px] text-textMuted/70 flex justify-between">
                                <span id="gov-quota-text">Loading...</span>
                                <span id="gov-quota-tier" class="text-textMuted/50"></span>
                            </div>
                        </div>
                        <div id="gov-pending-list" class="space-y-3">
                            <div class="text-center text-textMuted py-4 text-sm" data-i18n="common.loading">Loading...</div>
                        </div>
                    </div>
                </div>

                <!-- Leaderboard Tab -->
                <div id="gov-leaderboard-tab" class="gov-tab-content hidden p-6">
                    <div id="gov-leaderboard-list" class="space-y-2">
                        <div class="text-center text-textMuted py-8 text-sm" data-i18n="common.loading">Loading...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
`,

    // Feature Menu: Navigation Customization
    featureMenu: `
    <div id="feature-menu-modal" class="fixed inset-0 z-50 hidden">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="FeatureMenu.close()"></div>

            <!-- Modal Container -->
    <div class="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
        <div class="feature-menu-content bg-surface rounded-3xl border border-white/5 shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col pointer-events-auto transform transition-all duration-300 scale-95 opacity-0">

            <!-- Header -->
            <div class="p-6 border-b border-white/5">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <i data-lucide="layout-grid" class="w-5 h-5 text-primary"></i>
                        </div>
                        <div>
                            <h2 class="text-xl font-serif text-secondary" data-i18n="featureMenu.title">Customize Navigation</h2>
                            <p class="text-xs text-textMuted" data-i18n="featureMenu.description">Choose which features appear in your bottom navigation</p>
                        </div>
                    </div>
                    <button onclick="FeatureMenu.close()" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="x" class="w-5 h-5"></i>
                    </button>
                </div>
            </div>

            <!-- Warning Banner -->
            <div id="feature-menu-warning" class="hidden mx-6 mt-4 p-3 bg-warning/10 border border-warning/20 rounded-xl">
                <div class="flex items-start gap-2">
                    <i data-lucide="alert-triangle" class="w-4 h-4 text-warning flex-shrink-0 mt-0.5"></i>
                    <p class="text-xs text-warning" data-i18n="featureMenu.minWarning">At least 2 items must be enabled in your navigation bar.</p>
                </div>
            </div>

            <!-- Items Grid -->
            <div class="flex-1 overflow-y-auto p-6">
                <div id="feature-menu-items" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <!-- Items will be dynamically inserted here -->
                </div>
            </div>

            <!-- Footer -->
            <div class="p-6 border-t border-white/5 space-y-3">
                <div class="flex items-center gap-3">
                    <button onclick="FeatureMenu.save()" class="flex-1 py-3 bg-primary hover:brightness-110 text-background font-bold rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-primary/20">
                        <i data-lucide="check" class="w-4 h-4"></i>
                        <span data-i18n="featureMenu.saveChanges">Save Changes</span>
                    </button>
                    <button onclick="FeatureMenu.resetToDefaults()" class="px-4 py-3 bg-white/5 hover:bg-white/10 text-textMuted rounded-xl transition flex items-center justify-center gap-2 border border-white/5">
                        <i data-lucide="rotate-ccw" class="w-4 h-4"></i>
                        <span data-i18n="featureMenu.reset">Reset</span>
                    </button>
                </div>
                <button onclick="FeatureMenu.close()" class="w-full py-2.5 text-textMuted hover:text-textMain text-sm transition" data-i18n="common.cancel">
                    Cancel
                </button>
            </div>
        </div>
    </div>
        </div>
    `,

    // Tab: Forum
    forum: `
    <div class="h-full flex flex-col">
            <!-- Header -->
            <div class="flex items-center justify-between mb-4 px-2">
                <h2 class="font-serif text-2xl md:text-3xl text-secondary flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <i data-lucide="messages-square" class="w-5 h-5 text-primary"></i>
                    </div>
                    <span>Pi Forum</span>
                </h2>
                <div class="flex items-center gap-2">
                    <!-- 發文按鈕 -->
                    <a href="/static/forum/create.html"
                        class="bg-primary/10 hover:bg-primary/20 text-primary px-3 py-1.5 rounded-lg text-sm font-bold flex items-center gap-1 transition">
                        <i data-lucide="plus" class="w-4 h-4"></i>
                        <span class="hidden sm:inline">發文</span>
                    </a>
                </div>
            </div>

            <!-- Main Content Grid -->
    <div class="flex-1 grid grid-cols-1 md:grid-cols-4 gap-4 overflow-hidden">
        <!-- Sidebar (Filters & Trending) -->
        <aside class="md:col-span-1 space-y-4 overflow-y-auto custom-scrollbar">
            <div class="bg-surface border border-white/5 rounded-2xl p-4">
                <h3 class="font-bold text-secondary mb-3 flex items-center gap-2">
                    <i data-lucide="filter" class="w-4 h-4"></i> Filter
                </h3>
                <div class="space-y-1">
                    <select id="category-filter"
                        class="appearance-none w-full bg-background border border-white/10 rounded-lg p-2 text-sm text-textMain focus:border-primary outline-none">
                        <option value="">All Categories</option>
                        <option value="analysis">Analysis [分析]</option>
                        <option value="question">Question [請益]</option>
                        <option value="tutorial">Tutorial [教學]</option>
                        <option value="news">News [新聞]</option>
                        <option value="chat">Chat [閒聊]</option>
                        <option value="insight">Insight [心得]</option>
                    </select>
                </div>
            </div>

            <div class="bg-surface border border-white/5 rounded-2xl p-4">
                <h3 class="font-bold text-secondary mb-3 flex items-center gap-2">
                    <i data-lucide="trending-up" class="w-4 h-4"></i> Trending Tags
                </h3>
                <div id="trending-tags" class="space-y-1">
                    <div class="text-xs text-textMuted">Loading...</div>
                </div>
            </div>
        </aside>

        <!-- Post List -->
        <div class="md:col-span-3 overflow-y-auto custom-scrollbar">
            <div id="post-list" class="space-y-3 pr-2">
                <div class="text-center text-textMuted py-8">
                    <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
                    <span>載入中...</span>
                </div>
            </div>
        </div>
    </div>
        </div >
    `,

    // Tab: Admin Panel (admin-only)
    admin: `
    <div id="admin-content" class="max-w-5xl mx-auto p-4">
        <div class="text-center text-textMuted py-12">Loading admin panel...</div>
        </div>
    `,

    /**
     * 同步注入組件並確保 DOM 更新完成
     * @param {string} id - 分頁 ID (如 'market', 'pulse', 'settings')
     * @returns {Promise<boolean>}
     */
    async inject(id) {
        const container = document.getElementById(id + '-tab');
        if (!container || !this[id]) {
            console.error(`[Components] inject failed: container = ${!!container}, template = ${!!this[id]} `);
            return false;
        }

        // 如果已經注入過，直接返回
        if (this._injected[id]) {
            console.log(`[Components] ${id} already injected, skipping`);
            return true;
        }

        console.log(`[Components] Injecting ${id}...`);

        // 直接設置 innerHTML
        container.innerHTML = this[id];
        this._injected[id] = true;

        // 等待 DOM 更新完成（使用 setTimeout 比 requestAnimationFrame 更可靠）
        await new Promise(resolve => setTimeout(resolve, 50));

        // 初始化 Lucide 圖標
        if (window.lucide) {
            window.lucide.createIcons();
        }

        // 更新 i18n 翻譯（動態注入的 data-i18n 元素需要重新翻譯）
        if (window.I18n && typeof window.I18n.updatePageContent === 'function') {
            window.I18n.updatePageContent();
        }

        console.log(`[Components] ${id} injected successfully`);
        return true;
    },

    /**
     * 檢查組件是否已注入
     */
    isInjected(id) {
        return !!this._injected[id];
    },

    /**
     * 強制重新注入
     */
    async forceInject(id) {
        this._injected[id] = false;
        return this.inject(id);
    }
};

// 標記組件系統已就緒
window.ComponentsReady = true;
window.Components = Components;
