// Auto-generated from components.js split
// Tab: Friends (Integrated Social Hub - Friends + Messages) - original lines 549-731
window.Components = window.Components || {};
window.Components.friends = `
    <div class="h-full flex flex-col">
            <!--Header with Tab Switcher-->
            <div class="flex items-center justify-between pl-4 pr-4 md:pr-16 py-3 border-b border-white/5 bg-surface/50">
                <h2 class="font-serif text-2xl text-secondary" data-i18n="friends.title"></h2>
                <div class="flex items-center gap-2">
                    <span id="friends-badge-total" class="hidden px-2 py-0.5 text-xs bg-danger text-white rounded-full">0</span>
                    <button onclick="SocialHub.refresh()" class="${ICON_ACTION_BUTTON_CLASS}">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <!--Sub-tab Navigation-->
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
    `;

// Side-effect module — assigns to window.Components
export {};
