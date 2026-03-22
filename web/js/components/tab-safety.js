// Auto-generated from components.js split
// Tab: Safety (Scam Tracker + Governance) - original lines 1102-1321
// Tab: Feature Menu (Navigation Customization) - original lines 1323-1385
window.Components = window.Components || {};

window.Components.safety = `
    <div class="max-w-4xl mx-auto space-y-6">
            <!--Header -->
            <div class="flex items-center justify-between">
                <h2 class="${HERO_TITLE_CLASS}">
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

            <!--Search -->
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

            <!--Filters -->
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

            <!--Report List-->
            <div id="safety-report-list" class="space-y-3">
                <div class="${LOADING_PLACEHOLDER_CLASS}">
                    <i data-lucide="loader-2" class="${LOADER_ICON_CLASS}"></i>
                    <span data-i18n="common.loading">Loading...</span>
                </div>
            </div>

            <!--Load More-->
    <div class="text-center">
        <button id="safety-btn-load-more" onclick="SafetyTab.loadMore()" class="bg-surface hover:bg-surfaceHighlight text-textMuted px-6 py-3 rounded-xl font-bold transition border border-white/5 hidden" data-i18n="safety.loadMore">
            Load More
        </button>
    </div>
        </div>

        <!--Submit Scam Report Modal-->
        <div id="safety-submit-modal" class="${MODAL_OVERLAY_CLASS}">
            <div class="${MODAL_PANEL_CLASS}">
                <div class="${MODAL_HEADER_CLASS}">
                    <h3 class="font-serif text-xl text-secondary flex items-center gap-2">
                        <i data-lucide="alert-triangle" class="w-5 h-5 text-danger"></i> <span data-i18n="safety.submit.title">Report Scam Wallet</span>
                    </h3>
                    <button onclick="SafetyTab.closeSubmitModal()" class="${MODAL_CLOSE_BUTTON_CLASS}">
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

        <!--Scam Report Detail Modal-->
        <div id="safety-detail-modal" class="${MODAL_OVERLAY_CLASS}">
            <div class="${MODAL_PANEL_CLASS}">
                <div class="${MODAL_HEADER_CLASS}">
                    <h3 class="font-serif text-xl text-secondary" data-i18n="safety.detail.title">Report Detail</h3>
                    <button onclick="SafetyTab.closeDetailModal()" class="${MODAL_CLOSE_BUTTON_CLASS}">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
                <div id="safety-detail-content" ${SHELL_MODAL_SCROLL_ATTR} class="flex-1 p-6 ${SHELL_SCROLLBAR_CLASS}">
                    <div class="${LOADING_PLACEHOLDER_CLASS}" data-i18n="common.loading">Loading...</div>
                </div>
                <div class="${MODAL_FOOTER_CLASS}">
                    <div class="${MODAL_ACTION_ROW_CLASS}">
                        <button onclick="SafetyTab.voteOnDetail('approve')" class="${SUCCESS_ACTION_BUTTON_CLASS}">
                            <i data-lucide="thumbs-up" class="w-4 h-4"></i> <span data-i18n="safety.detail.confirm">Confirm</span> (<span id="safety-detail-approve">0</span>)
                        </button>
                        <button onclick="SafetyTab.voteOnDetail('reject')" class="${DANGER_ACTION_BUTTON_CLASS}">
                            <i data-lucide="thumbs-down" class="w-4 h-4"></i> <span data-i18n="safety.detail.dispute">Dispute</span> (<span id="safety-detail-reject">0</span>)
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!--Governance Report Modal-->
    <div id="governance-modal" class="${MODAL_OVERLAY_CLASS}">
        <div class="${MODAL_PANEL_CLASS}">
            <div class="${MODAL_HEADER_CLASS}">
                <h3 class="font-serif text-xl text-secondary flex items-center gap-2">
                    <i data-lucide="scale" class="w-5 h-5 text-accent"></i> <span data-i18n="safety.gov.title">Community Governance</span>
                </h3>
                <button onclick="SafetyTab.closeGovernanceModal()" class="${MODAL_CLOSE_BUTTON_CLASS}">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>

            <!-- Governance Tabs -->
            <div class="flex border-b border-white/5 px-6 pt-2 gap-1 overflow-x-auto shrink-0">
                <button onclick="SafetyTab.switchGovTab('gov-my-reports')" class="${GOV_TAB_BUTTON_BASE_CLASS} ${GOV_TAB_BUTTON_ACTIVE_CLASS}" data-gov-tab="gov-my-reports" data-i18n="safety.gov.myReportsTab">My Reports</button>
                <button onclick="SafetyTab.switchGovTab('gov-review')" class="${GOV_TAB_BUTTON_BASE_CLASS} ${GOV_TAB_BUTTON_INACTIVE_CLASS}" data-gov-tab="gov-review"><span data-i18n="safety.gov.reviewTab">Review</span> <span class="text-[9px] bg-accent/20 text-accent px-1.5 py-0.5 rounded ml-1">PREMIUM</span></button>
                <button onclick="SafetyTab.switchGovTab('gov-leaderboard')" class="${GOV_TAB_BUTTON_BASE_CLASS} ${GOV_TAB_BUTTON_INACTIVE_CLASS}" data-gov-tab="gov-leaderboard" data-i18n="safety.gov.rankingTab">Ranking</button>
            </div>

            <div ${SHELL_MODAL_SCROLL_ATTR} class="flex-1 ${SHELL_SCROLLBAR_CLASS}">

                <!-- My Reports Tab (Active by Default) -->
                <div id="gov-my-reports-tab" class="gov-tab-content p-6">
                    <div class="${GOV_FILTER_ROW_CLASS}">
                        <button onclick="SafetyTab.loadMyGovReports('all', this)" class="${GOV_FILTER_BUTTON_BASE_CLASS} ${GOV_FILTER_BUTTON_ACTIVE_CLASS}" data-i18n="common.all">All</button>
                        <button onclick="SafetyTab.loadMyGovReports('pending', this)" class="${GOV_FILTER_BUTTON_BASE_CLASS} ${GOV_FILTER_BUTTON_INACTIVE_CLASS}" data-i18n="safety.filters.pending">Pending</button>
                        <button onclick="SafetyTab.loadMyGovReports('approved', this)" class="${GOV_FILTER_BUTTON_BASE_CLASS} ${GOV_FILTER_BUTTON_INACTIVE_CLASS}" data-i18n="safety.gov.approved">Approved</button>
                        <button onclick="SafetyTab.loadMyGovReports('rejected', this)" class="${GOV_FILTER_BUTTON_BASE_CLASS} ${GOV_FILTER_BUTTON_INACTIVE_CLASS}" data-i18n="safety.gov.rejected">Rejected</button>
                    </div>
                    <div id="gov-my-reports-list" class="space-y-3">
                        <div class="${LOADING_PLACEHOLDER_SMALL_CLASS}" data-i18n="safety.gov.selectFilter">Select a filter to load reports</div>
                    </div>
                </div>

                <!-- Review Tab (Premium) -->
                <div id="gov-review-tab" class="gov-tab-content hidden p-6">
                    <div id="gov-pro-notice" class="text-center py-8">
                        <div class="w-16 h-16 bg-accent/10 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i data-lucide="lock" class="w-8 h-8 text-accent"></i>
                        </div>
                        <h4 class="font-bold text-secondary mb-2" data-i18n="safety.gov.proOnly">Premium Members Only</h4>
                        <p class="text-textMuted text-sm mb-4" data-i18n="safety.gov.proDesc">Upgrade to Premium to review reports and earn reputation.</p>
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
                            <div class="${LOADING_PLACEHOLDER_TIGHT_CLASS}" data-i18n="common.loading">Loading...</div>
                        </div>
                    </div>
                </div>

                <!-- Leaderboard Tab -->
                <div id="gov-leaderboard-tab" class="gov-tab-content hidden p-6">
                    <div id="gov-leaderboard-list" class="space-y-2">
                        <div class="${LOADING_PLACEHOLDER_SMALL_CLASS}" data-i18n="common.loading">Loading...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;

// Feature Menu: Navigation Customization
window.Components.featureMenu = `
    <div id="feature-menu-modal" class="fixed inset-0 z-50 hidden">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="FeatureMenu.close()"></div>

        <!-- Modal Container -->
        <div class="${FEATURE_MODAL_STAGE_CLASS}">
            <div class="${FEATURE_MODAL_PANEL_CLASS}">

                <!-- Header -->
                <div class="p-6 border-b border-white/5">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="${HERO_ICON_BOX_CLASS}">
                                <i data-lucide="layout-grid" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h2 class="text-xl font-serif text-secondary" data-i18n="featureMenu.title">Customize Navigation</h2>
                                <p class="text-xs text-textMuted" data-i18n="featureMenu.description">Choose which features appear in your bottom navigation</p>
                            </div>
                        </div>
                        <button onclick="FeatureMenu.close()" class="${ICON_ACTION_BUTTON_CLASS}">
                            <i data-lucide="x" class="w-5 h-5"></i>
                        </button>
                    </div>
                </div>

                <!-- Warning Banner -->
                <div id="feature-menu-warning" class="${WARNING_BANNER_CLASS}">
                    <div class="${WARNING_BANNER_ROW_CLASS}">
                        <i data-lucide="alert-triangle" class="w-4 h-4 text-warning flex-shrink-0 mt-0.5"></i>
                        <p class="text-xs text-warning" data-i18n="featureMenu.minWarning">At least 2 items must be enabled in your navigation bar.</p>
                    </div>
                </div>

                <!-- Items Grid -->
                <div ${SHELL_MODAL_SCROLL_ATTR} class="flex-1 overflow-y-auto p-6">
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
    `;

// Side-effect module — assigns to window.Components
export {};
