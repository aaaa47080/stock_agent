// ========================================
// components.js - 頁面組件模板與動態注入
// ========================================

const Components = {
    // 追蹤已注入的組件
    _injected: {},

    // Tab: Market
    market: `
        <div class="mb-6 md:mb-8">
            <!-- 標題行 -->
            <div class="flex items-center justify-between mb-3">
                <h2 class="font-serif text-2xl md:text-3xl text-secondary">Market Watch</h2>
                <div class="flex items-center gap-2">
                    <!-- 狀態指示器 -->
                    <div class="flex items-center gap-1.5" title="Live Update Status">
                        <div id="ticker-ws-indicator" class="w-2 h-2 rounded-full bg-gray-500 transition-colors"></div>
                        <span class="text-[9px] text-textMuted uppercase tracking-wider hidden md:inline">LIVE</span>
                    </div>
                    <!-- 刷新按鈕 -->
                    <button onclick="refreshScreener(true, true)" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
            <!-- 篩選器行 (手機換行顯示) -->
            <div class="flex flex-wrap items-center gap-2 md:gap-3">
                <button onclick="openGlobalFilter()" class="flex items-center gap-2 px-3 py-1.5 bg-surface hover:bg-surfaceHighlight rounded-lg text-textMuted hover:text-primary transition border border-white/5">
                    <i data-lucide="filter" class="w-4 h-4"></i>
                    <span class="text-xs font-bold">Filter</span>
                    <span id="global-count-badge" class="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded">Auto</span>
                </button>
                <div id="active-filter-indicator" class="hidden flex items-center gap-1 text-xs text-primary">
                    <span id="filter-count">0</span> selected
                </div>
                <span id="screener-last-updated" class="text-[10px] text-textMuted opacity-60 hidden md:inline"></span>
            </div>
        </div>

        <div class="space-y-12">
            <section>
                <div class="flex items-center gap-3 mb-6 px-2">
                    <div class="h-px flex-1 bg-gradient-to-r from-primary/30 to-transparent"></div>
                    <h3 class="text-xs font-bold text-primary uppercase tracking-[0.2em] whitespace-nowrap">Top Performers</h3>
                    <div class="h-px flex-1 bg-gradient-to-l from-primary/30 to-transparent"></div>
                </div>
                <div id="top-list" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
            </section>

            <section>
                <div class="flex items-center gap-3 mb-8 px-2">
                    <div class="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent"></div>
                    <h3 class="text-xs font-bold text-textMuted uppercase tracking-[0.2em] whitespace-nowrap">Market Dynamics</h3>
                    <div class="h-px flex-1 bg-gradient-to-l from-white/10 to-transparent"></div>
                </div>

                <div class="space-y-10 px-2">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h4 class="text-xs font-bold text-success mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <i data-lucide="trending-up" class="w-4 h-4 text-success"></i> Top Gainers (24H)
                            </h4>
                            <div id="top-gainers-list" class="space-y-3"></div>
                        </div>
                        <div>
                            <h4 class="text-xs font-bold text-danger mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <i data-lucide="trending-down" class="w-4 h-4 text-danger"></i> Top Losers (24H)
                            </h4>
                            <div id="top-losers-list" class="space-y-3"></div>
                        </div>
                    </div>
                        <div>
                            <h4 class="text-xs font-bold text-secondary mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <i data-lucide="zap" class="w-3.5 h-3.5 text-accent"></i> Bullish Squeeze (Low Funding)
                            </h4>
                            <div id="low-funding-list" class="space-y-3"></div>
                        </div>
                        <div>
                            <h4 class="text-xs font-bold text-secondary mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <i data-lucide="flame" class="w-3.5 h-3.5 text-danger"></i> Overheated (High Funding)
                            </h4>
                            <div id="high-funding-list" class="space-y-3"></div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    `,

    // Tab: Pulse
    pulse: `
        <div class="flex justify-between items-end mb-4">
            <h2 class="font-serif text-3xl text-secondary">Market Pulse</h2>
            <button id="pulse-refresh-btn" onclick="refreshMarketPulse()" class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition">
                <i id="pulse-refresh-icon" data-lucide="refresh-cw" class="w-4 h-4"></i>
            </button>
        </div>

        <!-- Filter UI (Synced with Market Watch) -->
        <div class="flex flex-wrap items-center gap-2 md:gap-3 mb-8">
            <button onclick="openGlobalFilter()" class="flex items-center gap-2 px-3 py-1.5 bg-surface hover:bg-surfaceHighlight rounded-lg text-textMuted hover:text-primary transition border border-white/5">
                <i data-lucide="filter" class="w-4 h-4"></i>
                <span class="text-xs font-bold">Filter</span>
                <!-- Reusing the global count badge ID might cause conflicts if IDs must be unique, 
                     but since tabs are hidden, it might be okay. 
                     Safest is to use a class or a new ID and update logic to target multiple. 
                     However, the logic in market.js updates 'document.getElementById...'.
                     Let's use a NEW ID for Pulse and update logic to sync both. -->
                <span id="pulse-count-badge" class="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded">Auto</span>
            </button>
            <div id="active-pulse-filter-indicator" class="hidden flex items-center gap-1 text-xs text-primary">
                <span id="pulse-filter-count">0</span> selected
            </div>
        </div>

        <div id="analysis-progress-container" class="hidden mb-6 bg-surface rounded-2xl p-4 border border-primary/10">
            <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-bold text-primary flex items-center gap-2">
                    <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                    Scanning
                </span>
                <span id="analysis-progress-text" class="text-xs text-textMuted">0%</span>
            </div>
            <div class="w-full bg-background rounded-full h-1">
                <div id="analysis-progress-bar" class="bg-primary h-1 rounded-full transition-all duration-500" style="width: 0%"></div>
            </div>
        </div>

        <div id="pulse-grid" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
    `,

    // Tab: Friends (Integrated Social Hub - Friends + Messages)
    friends: `
        <div class="h-full flex flex-col">
            <!-- Header with Tab Switcher -->
            <div class="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-surface/50">
                <h2 class="font-serif text-2xl text-secondary">Social</h2>
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
                    <span>聊天</span>
                    <span id="messages-unread-badge" class="hidden px-1.5 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                </button>
                <button onclick="SocialHub.switchSubTab('friends')" id="social-tab-friends"
                    class="social-sub-tab flex-1 py-2.5 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2 text-textMuted hover:text-textMain hover:bg-white/5">
                    <i data-lucide="users" class="w-4 h-4"></i>
                    <span>好友</span>
                    <span id="friends-request-badge" class="hidden px-1.5 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                </button>
            </div>

            <!-- ==================== MESSAGES SUB-TAB ==================== -->
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
                            <span>今日已發送: <span id="social-limit-used">0</span>/<span id="social-limit-total">20</span></span>
                            <a href="/static/forum/premium.html" onclick="sessionStorage.setItem('returnToTab', 'friends')" class="text-primary hover:underline">升級 Pro</a>
                        </div>
                    </div>
                </div>

                <!-- Chat Section (Desktop: inline, Mobile: hidden) -->
                <div id="social-chat-section" class="hidden md:flex flex-1 flex-col bg-background relative h-full">
                    <!-- Empty State (shown when no conversation selected) -->
                    <div id="social-chat-empty" class="flex-1 flex items-center justify-center">
                        <div class="text-center text-textMuted opacity-60">
                            <i data-lucide="message-circle" class="w-12 h-12 mx-auto mb-4"></i>
                            <p class="text-lg font-medium mb-2">選擇一個對話</p>
                            <p class="text-sm">點擊左側的對話開始聊天</p>
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
                                            placeholder="輸入訊息..." rows="1" maxlength="500"
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

            <!-- ==================== FRIENDS SUB-TAB ==================== -->
            <div id="social-content-friends" class="flex-1 overflow-y-auto p-4 hidden">
                <div class="max-w-4xl mx-auto space-y-6">
                    <!-- Search Section -->
                    <div class="bg-surface border border-white/5 rounded-2xl p-6">
                        <h3 class="font-bold text-secondary text-lg mb-4 flex items-center gap-2">
                            <i data-lucide="search" class="w-5 h-5"></i>
                            Find Friends
                        </h3>
                        <div class="relative">
                            <input type="text" id="friend-search-input" placeholder="Search by username..."
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
                                Friend Requests
                                <span id="pending-count-badge" class="hidden px-2 py-0.5 text-xs bg-danger text-white rounded-full"></span>
                            </h3>
                            <div id="pending-requests-list" class="space-y-2">
                                <div class="text-center text-textMuted py-6 opacity-50">
                                    <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                                    Loading requests...
                                </div>
                            </div>
                        </div>

                        <!-- My Friends -->
                        <div class="bg-surface border border-white/5 rounded-2xl p-6">
                            <h3 class="font-bold text-secondary text-lg mb-4 flex items-center gap-2">
                                <i data-lucide="users" class="w-5 h-5 text-success"></i>
                                My Friends
                                <span id="friends-count-badge" class="hidden px-2 py-0.5 text-xs bg-white/10 text-textMuted rounded-full">0</span>
                            </h3>
                            <div id="friends-list" class="space-y-2">
                                <div class="text-center text-textMuted py-6 opacity-50">
                                    <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                                    Loading friends...
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Blocked Users (Collapsible) -->
                    <div class="bg-surface border border-white/5 rounded-2xl overflow-hidden">
                        <button onclick="document.getElementById('blocked-list').classList.toggle('hidden'); document.getElementById('blocked-chevron').classList.toggle('rotate-180');" class="w-full p-6 flex items-center justify-between hover:bg-white/5 transition">
                            <h3 class="font-bold text-textMuted text-lg flex items-center gap-2">
                                <i data-lucide="ban" class="w-5 h-5 text-danger"></i>
                                Blocked Users
                                <span id="blocked-count-badge" class="px-2 py-0.5 text-xs bg-white/10 text-textMuted rounded-full">0</span>
                            </h3>
                            <i data-lucide="chevron-down" id="blocked-chevron" class="w-5 h-5 text-textMuted transition-transform"></i>
                        </button>
                        <div id="blocked-list" class="px-6 pb-6 hidden">
                            <div class="space-y-2" id="blocked-users-container">
                                <div class="text-center text-textMuted py-4 opacity-50">
                                    No blocked users
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
             <h2 class="font-serif text-3xl text-secondary mb-8">Settings</h2>

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
                            Loading
                        </div>
                    </div>

                    <!-- TEST MODE: Multi-User Switcher -->
                    <div id="dev-user-switcher" class="mt-4 pt-4 border-t border-white/5">
                        <p class="text-[10px] text-textMuted uppercase tracking-wider mb-2 font-bold opacity-50">Dev: Switch User</p>
                        <div class="grid grid-cols-2 gap-2">
                            <button onclick="handleDevSwitchUser('test-user-001')" class="py-2 bg-white/5 hover:bg-primary/20 hover:text-primary rounded-lg text-xs font-mono transition border border-white/5">
                                User 001
                            </button>
                            <button onclick="handleDevSwitchUser('test-user-002')" class="py-2 bg-white/5 hover:bg-accent/20 hover:text-accent rounded-lg text-xs font-mono transition border border-white/5">
                                User 002
                            </button>
                        </div>
                    </div>

                    <button onclick="handleLogout()" class="w-full py-3 bg-white/5 hover:bg-danger/10 text-textMuted hover:text-danger border border-white/5 hover:border-danger/20 font-bold rounded-xl transition flex items-center justify-center gap-2 mt-4">
                        <i data-lucide="log-out" class="w-4 h-4"></i>
                        Logout
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
                                <h3 class="text-lg font-serif text-primary">Pi Wallet</h3>
                                <p class="text-xs text-textMuted">連接您的 Pi 錢包以進行交易</p>
                            </div>
                        </div>
                        <div id="settings-wallet-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 text-textMuted">
                            <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                            載入中
                        </div>
                    </div>

                    <div id="settings-wallet-content" class="space-y-4">
                        <div id="wallet-not-linked" class="hidden">
                            <div class="bg-background/50 rounded-xl p-4 border border-white/5 mb-4">
                                <p class="text-sm text-textMuted leading-relaxed">
                                    <i data-lucide="info" class="w-4 h-4 inline-block mr-1 opacity-60"></i>
                                    綁定 Pi 錢包後可以：
                                </p>
                                <ul class="text-xs text-textMuted mt-2 space-y-1 ml-5">
                                    <li>• 在論壇發布文章（需支付 <span data-price="create_post"><i data-lucide="loader" class="w-3 h-3 animate-spin inline-block"></i></span>）</li>
                                    <li>• 打賞優質內容創作者</li>
                                    <li>• 接收來自其他用戶的打賞</li>
                                </ul>
                            </div>
                            <button onclick="handleSettingsLinkWallet()" class="w-full py-3.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 font-bold rounded-xl transition flex items-center justify-center gap-2">
                                <i data-lucide="link" class="w-4 h-4"></i>
                                綁定 Pi 錢包
                            </button>
                            <p class="text-[10px] text-textMuted/60 text-center mt-2">需要在 Pi Browser 中開啟</p>
                        </div>

                        <div id="wallet-linked" class="hidden">
                            <div class="bg-success/5 rounded-xl p-4 border border-success/10">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
                                        <i data-lucide="check-circle" class="w-5 h-5 text-success"></i>
                                    </div>
                                    <div>
                                        <p class="text-sm font-bold text-success">Pi 錢包已連接</p>
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
                                <h3 class="text-lg font-serif text-primary">AI Intelligence</h3>
                                <p class="text-xs text-textMuted">Configure your LLM provider</p>
                            </div>
                        </div>
                        <div id="llm-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                        </div>
                    </div>

                    <div class="space-y-6">
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Provider</label>
                            <select id="llm-provider-select" onchange="updateLLMKeyInput(); updateAvailableModels()" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none">
                                <option value="openai">OpenAI</option>
                                <option value="google_gemini">Google Gemini</option>
                                <option value="openrouter">OpenRouter</option>
                            </select>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">API Key</label>
                            <div class="flex gap-3">
                                <input type="password" id="llm-api-key-input" class="flex-1 bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 font-mono text-sm" placeholder="sk-...">
                                <button onclick="testLLMKey()" class="px-5 bg-surfaceHighlight hover:bg-white/10 text-secondary rounded-xl transition font-bold text-xs whitespace-nowrap">TEST</button>
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Model</label>
                            <select id="llm-model-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none" style="display: block;">
                                <option value="">Select a model</option>
                            </select>
                            <input type="text" id="llm-model-input" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-primary/50 transition mt-3"
                                   placeholder="e.g., openai/gpt-4o, anthropic/claude-3.5-sonnet"
                                   style="display: none;" />
                            <p id="llm-key-status" class="mt-2 text-xs text-textMuted hidden"></p>
                        </div>

                        <button id="save-llm-key-btn" onclick="saveLLMKey()" class="w-full py-3.5 bg-primary text-background font-bold rounded-xl shadow-lg shadow-primary/10 opacity-50 cursor-not-allowed transition mt-2" disabled>
                            Save AI Configuration
                        </button>
                    </div>
                </div>

                <!-- Committee Mode -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                                <i data-lucide="users" class="w-5 h-5 text-accent"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-accent">Committee Mode</h3>
                                <p class="text-xs text-textMuted">Multi-model consensus</p>
                            </div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="set-committee-mode" class="sr-only peer" onchange="toggleCommitteePanel(this)">
                            <div class="w-12 h-7 bg-background rounded-full peer peer-focus:ring-0 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-accent"></div>
                        </label>
                    </div>

                    <div id="committee-management-panel" class="hidden space-y-6 pt-6 mt-6 border-t border-white/5">
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Provider</label>
                            <select id="committee-provider-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-accent/50 transition appearance-none">
                                <option value="">Select Provider...</option>
                            </select>
                            <p id="committee-no-key-hint" class="text-xs text-warning mt-2 hidden">
                                請先在 AI Intelligence 區塊設定 API Key
                            </p>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Model</label>
                            <select id="committee-model-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-accent/50 transition appearance-none" disabled>
                                <option value="">先選擇 Provider...</option>
                            </select>
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <button id="add-bull-btn" class="py-3 bg-success/10 text-success rounded-xl text-sm font-bold border border-success/20 hover:bg-success/20 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                <i data-lucide="plus" class="w-4 h-4"></i> Bull Team
                            </button>
                            <button id="add-bear-btn" class="py-3 bg-danger/10 text-danger rounded-xl text-sm font-bold border border-danger/20 hover:bg-danger/20 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                <i data-lucide="plus" class="w-4 h-4"></i> Bear Team
                            </button>
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div class="bg-background p-4 rounded-xl">
                                <span class="text-success font-bold text-sm flex items-center gap-2 mb-3">
                                    <span class="w-2 h-2 rounded-full bg-success"></span> Bull Team
                                </span>
                                <ul id="bull-committee-list" class="space-y-2 text-xs"></ul>
                                <p id="bull-empty-hint" class="text-textMuted/50 text-xs">尚未添加成員</p>
                            </div>
                            <div class="bg-background p-4 rounded-xl">
                                <span class="text-danger font-bold text-sm flex items-center gap-2 mb-3">
                                    <span class="w-2 h-2 rounded-full bg-danger"></span> Bear Team
                                </span>
                                <ul id="bear-committee-list" class="space-y-2 text-xs"></ul>
                                <p id="bear-empty-hint" class="text-textMuted/50 text-xs">尚未添加成員</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Premium Membership -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center gap-3 mb-6">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-500 flex items-center justify-center">
                            <i data-lucide="star" class="w-5 h-5 text-white"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-serif text-yellow-400">Premium Membership</h3>
                            <p class="text-xs text-textMuted">Unlock advanced features</p>
                        </div>
                    </div>

                    <div class="space-y-4">
                        <div class="bg-background/50 rounded-xl p-4 border border-white/5">
                            <p class="text-sm text-textMuted leading-relaxed">
                                <i data-lucide="crown" class="w-4 h-4 inline-block mr-1 text-yellow-400"></i>
                                高級會員享有：
                            </p>
                            <ul class="text-xs text-textMuted mt-2 space-y-1 ml-5">
                                <li>• 無限發文權限</li>
                                <li>• 無限回覆權限</li>
                                <li>• 優先訪問新功能</li>
                                <li>• 專屬高級會員標識</li>
                            </ul>
                        </div>

                        <button onclick="handleUpgradeToPremium()" class="w-full py-3.5 bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-400 hover:to-orange-400 text-background font-bold rounded-xl transition flex items-center justify-center gap-2 upgrade-premium-btn">
                            <i data-lucide="zap" class="w-4 h-4"></i>
                            <span>升級到高級會員 - <span data-price="premium"><i data-lucide="loader" class="w-3 h-3 animate-spin"></i></span></span>
                        </button>

                        <p class="text-[10px] text-textMuted/60 text-center">一次性付費，立即生效</p>
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
                                <h3 class="text-lg font-serif text-secondary">Exchange Keys</h3>
                                <p class="text-xs text-textMuted">Connect your OKX account</p>
                            </div>
                        </div>
                        <div id="okx-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                        </div>
                    </div>

                    <div id="okx-not-connected" class="hidden">
                        <div class="text-center py-4 mb-4 bg-background/50 rounded-xl">
                            <i data-lucide="unplug" class="w-8 h-8 text-textMuted mx-auto mb-2"></i>
                            <p class="text-sm text-textMuted">No exchange connected</p>
                        </div>
                        <button onclick="document.getElementById('apikey-modal').classList.remove('hidden')" class="w-full py-3.5 bg-gradient-to-r from-primary to-accent text-background font-bold rounded-2xl transition flex items-center justify-center gap-2 shadow-lg shadow-primary/20 hover:scale-[1.02]">
                            <i data-lucide="plug" class="w-4 h-4"></i> Connect OKX
                        </button>
                    </div>

                    <div id="okx-connected" class="hidden">
                        <div class="flex items-center justify-between p-4 bg-success/5 border border-success/20 rounded-xl mb-4">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
                                    <i data-lucide="check" class="w-5 h-5 text-success"></i>
                                </div>
                                <div>
                                    <p class="text-sm font-medium text-secondary">OKX Connected</p>
                                    <p class="text-xs text-textMuted">API key stored locally</p>
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <button onclick="document.getElementById('apikey-modal').classList.remove('hidden')" class="py-3 bg-surfaceHighlight hover:bg-white/10 border border-white/5 text-secondary rounded-xl transition flex items-center justify-center gap-2 text-sm font-medium">
                                <i data-lucide="edit-3" class="w-4 h-4"></i> Update
                            </button>
                            <button onclick="disconnectOKX()" class="py-3 bg-danger/10 hover:bg-danger/20 border border-danger/20 text-danger rounded-xl transition flex items-center justify-center gap-2 text-sm font-medium">
                                <i data-lucide="unplug" class="w-4 h-4"></i> Disconnect
                            </button>
                        </div>
                    </div>
                </div>

                <button onclick="saveSettings()" id="btn-save-settings" class="w-full py-4 bg-secondary text-background font-bold rounded-2xl shadow-xl hover:scale-[1.02] transition">
                    Save All Settings
                </button>

                <div class="text-center pt-8 opacity-20 text-[10px] font-mono tracking-widest uppercase">
                    CryptoMind v1.2.0-Pi-Integrated
                </div>
             </div>
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
            console.error(`[Components] inject failed: container=${!!container}, template=${!!this[id]}`);
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
