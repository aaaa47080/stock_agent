// Auto-generated from components.js split
// Tab: Crypto (Combined Market & Pulse) - original lines 105-244
window.Components = window.Components || {};
window.Components.crypto = `
        <div class="${TAB_SHELL_CLASS}">
            <!-- Header with Sub-tab Switcher -->
            <div class="${TAB_HEADER_CLASS}">
                <h2 class="font-serif text-3xl text-secondary" data-i18n="crypto.title">Crypto</h2>
                <div class="flex items-center gap-2">
                    <button onclick="window.CryptoTab.refreshCurrent()" class="${ICON_ACTION_BUTTON_CLASS}">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!-- Sub-tab Navigation -->
            <div class="${TAB_SWITCHER_CLASS}">
                <button onclick="window.CryptoTab.switchSubTab('market')" id="crypto-tab-market"
                    class="crypto-sub-tab ${SUB_TAB_BUTTON_BASE_CLASS} ${SUB_TAB_BUTTON_ACTIVE_CLASS}">
                    <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                    <span data-i18n="nav.market">Market Watch</span>
                </button>
                <button onclick="window.CryptoTab.switchSubTab('pulse')" id="crypto-tab-pulse"
                    class="crypto-sub-tab ${SUB_TAB_BUTTON_BASE_CLASS} ${SUB_TAB_BUTTON_INACTIVE_CLASS}">
                    <i data-lucide="activity" class="w-4 h-4"></i>
                    <span data-i18n="nav.pulse">AI Pulse</span>
                </button>
            </div>

            <!-- Content Area -->
            <div class="${TAB_CONTENT_AREA_CLASS}">
                
                <!-- Sub-tab: Market Watch -->
                <div id="crypto-content-market" ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS}">
                    <div class="mb-6 md:mb-8">
                        <!-- 篩選器行 -->
                        <div class="flex flex-wrap items-center justify-between gap-2 md:gap-3">
                            <div class="flex gap-2 items-center">
                                <button onclick="openGlobalFilter()" class="${FILTER_TRIGGER_BUTTON_CLASS}">
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

                    <div class="space-y-12">
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
                <div id="crypto-content-pulse" ${SHELL_SCROLL_ATTR} class="absolute inset-0 ${SHELL_SCROLLBAR_CLASS} hidden">
                    <!-- Filter UI (Synced with Market Watch) -->
                    <div class="flex flex-wrap items-center gap-2 md:gap-3 mb-8">
                        <button onclick="openGlobalFilter()" class="${FILTER_TRIGGER_BUTTON_CLASS}">
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

                    <div id="pulse-grid" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
                </div>

            </div>
        </div>
    `;

// Side-effect module — assigns to window.Components
export {};
