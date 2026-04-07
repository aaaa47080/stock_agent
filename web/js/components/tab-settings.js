// Auto-generated from components.js split
// Tab: Settings - original lines 733-1100
window.Components = window.Components || {};
window.Components.settings = `
    <div class="max-w-2xl mx-auto px-1 sm:px-0">
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

                    <!-- TEST MODE: Multi-User Switcher (預設隱藏，由 auth.js 根據 API 控制) -->
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
                                User 003 (PREMIUM)
                            </button>
                            <button onclick="handleDevSwitchUser('test-user-004')" class="py-2 bg-white/5 hover:bg-warning/20 hover:text-warning rounded-lg text-xs font-mono transition border border-white/5">
                                User 004 (PREMIUM)
                            </button>
                        </div>
                    </div>

                    <!-- TEST MODE: Tier Switcher (僅測試模式顯示) -->
                    <div id="test-tier-switcher" class="mt-4 pt-4 border-t border-white/5 hidden">
                        <div class="flex items-center justify-between mb-3">
                            <p class="text-[10px] text-primary uppercase tracking-wider font-bold" data-i18n="settings.testModeSwitchTier">TEST MODE: Switch Membership Tier</p>
                            <span id="current-test-tier" class="px-2 py-0.5 rounded-md bg-primary/20 text-primary text-[10px] font-mono font-bold">PREMIUM</span>
                        </div>
                        <p class="text-[10px] text-textMuted mb-3" data-i18n="settings.testModeTierDesc">Test different membership tier permissions (no charges)</p>
                        <div class="grid grid-cols-2 gap-2">
                            <button onclick="handleSwitchTestTier('free')" class="test-tier-btn py-2 bg-white/5 hover:bg-textMuted/10 rounded-lg text-xs font-mono transition border border-white/5" data-tier="free">
                                FREE
                            </button>
                            <button onclick="handleSwitchTestTier('premium')" class="test-tier-btn py-2 bg-white/5 hover:bg-primary/20 hover:text-primary rounded-lg text-xs font-mono transition border border-primary/20 text-primary" data-tier="premium">
                                PREMIUM
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
                        <div class="${CARD_HEADER_ROW_CLASS}">
                            <div id="settings-wallet-icon" class="${HERO_ICON_BOX_CLASS}">
                                <i data-lucide="wallet" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary" data-i18n="settings.wallet.title">Pi Wallet</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.wallet.description">Connect your Pi wallet for transactions</p>
                            </div>
                        </div>
                        <div id="settings-wallet-status-badge" class="${STATUS_BADGE_MUTED_CLASS}">
                            <i data-lucide="loader" class="w-3 h-3 animate-spin"></i>
                            <span data-i18n="settings.wallet.loading">Loading</span>
                        </div>
                    </div>

                    <div id="settings-wallet-content" class="space-y-4">
                        <div id="wallet-not-linked" class="hidden">
                            <div class="${INFO_PANEL_CLASS}">
                                <div class="flex items-start gap-3">
                                    <i data-lucide="info" class="w-4 h-4 text-primary/60 mt-0.5 flex-shrink-0"></i>
                                    <div>
                                        <p class="text-sm text-textMuted leading-relaxed mb-1" data-i18n="settings.wallet.reloginHint">您的登入資訊已更新，請重新登入以完成錢包連結。</p>
                                        <p class="text-xs text-textMuted/60" data-i18n="settings.wallet.reloginDesc">重新登入後即可使用付款、發文及收打賞等功能。</p>
                                    </div>
                                </div>
                                <button onclick="AuthManager.logout()" class="w-full mt-4 py-3 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 font-bold rounded-xl transition flex items-center justify-center gap-2">
                                    <i data-lucide="log-in" class="w-4 h-4"></i>
                                    <span data-i18n="settings.wallet.reloginButton">重新登入以連結錢包</span>
                                </button>
                            </div>
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
                <div id="settings-llm-card" class="bg-surface p-5 md:p-8 rounded-3xl border border-white/5 shadow-[0_20px_60px_rgba(0,0,0,0.18)]">
                    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
                        <div class="${CARD_HEADER_ROW_CLASS}">
                            <div class="${HERO_ICON_BOX_CLASS}">
                                <i data-lucide="brain" class="w-5 h-5 text-primary"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-primary" data-i18n="settings.ai.title">AI Intelligence</h3>
                                <p class="text-xs text-textMuted" data-i18n="settings.ai.description">Configure your LLM provider</p>
                            </div>
                        </div>
                        <div id="llm-status-badge" class="${STATUS_BADGE_CLASS} self-start sm:self-auto">
                        </div>
                    </div>

                    <div class="space-y-5">
                        <div class="space-y-2">
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.provider">Provider</label>
                            <select id="llm-provider-select" onchange="updateLLMKeyInput(); updateAvailableModels()" class="w-full bg-background border border-white/5 rounded-2xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none">
                                <option value="openai">OpenAI</option>
                                <option value="google_gemini">Google Gemini</option>
                                <option value="openrouter">OpenRouter</option>
                            </select>
                            <p class="text-xs leading-5 text-textMuted/75">先選擇你要綁定的 AI 供應商，再決定要使用的模型。</p>
                        </div>

                        <div class="space-y-2">
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.model">Model</label>
                            <select id="llm-model-select" class="w-full bg-background border border-white/5 rounded-2xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none" style="display: block;">
                            <!-- Models loaded dynamically via updateAvailableModels() -->
                            </select>
                            <input type="text" id="llm-model-input" class="w-full bg-background border border-white/5 rounded-2xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-primary/50 transition mt-3"
                                   placeholder="e.g., openai/gpt-4o, anthropic/claude-3.5-sonnet" data-i18n="settings.ai.modelPlaceholder" data-i18n-attr="placeholder"
                                   style="display: none;" />
                            <p id="llm-model-hint" class="text-xs leading-5 text-textMuted/75">先選模型，再輸入對應的 API 金鑰，流程會比較順。</p>
                        </div>

                        <div class="space-y-2">
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2" data-i18n="settings.ai.apiKey">API Key</label>
                            <div class="flex flex-col gap-3 sm:flex-row">
                                <input type="password" id="llm-api-key-input" class="flex-1 min-w-0 bg-background border border-white/5 rounded-2xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 font-mono text-sm disabled:cursor-not-allowed disabled:opacity-50" placeholder="sk-..." disabled>
                                <button id="test-llm-key-btn" onclick="testLLMKey()" class="shrink-0 min-w-[104px] px-5 py-3.5 bg-surfaceHighlight hover:bg-white/10 text-secondary rounded-2xl transition font-bold text-xs whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed" disabled data-i18n="settings.ai.test">TEST</button>
                            </div>
                            <p id="llm-key-status" class="text-xs leading-5 text-textMuted/75">請先選擇供應商與模型，再輸入 API 金鑰。</p>
                            <p id="llm-binding-status" class="text-xs leading-5 text-success hidden"></p>
                        </div>

                        <button id="save-llm-key-btn" onclick="saveLLMKey()" class="w-full py-3.5 bg-primary text-background font-bold rounded-xl shadow-lg shadow-primary/10 opacity-50 cursor-not-allowed transition mt-2" disabled data-i18n="settings.ai.saveConfig">
                            Save AI Configuration
                        </button>
                    </div>
                </div>

                <!-- Navigation Customization -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="${HERO_ICON_BOX_CLASS}">
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
                    <div class="mt-4 ${INFO_PANEL_CLASS}">
                        <p class="text-sm text-textMuted leading-relaxed">
                            <i data-lucide="info" class="w-4 h-4 inline-block mr-1 opacity-60"></i>
                            <span data-i18n="settings.navigation.info">Choose which features appear in your bottom navigation bar. At least 2 items must be enabled.</span>
                        </p>
                    </div>
                </div>

                <!-- AI Tool Selection -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center justify-between mb-6">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                                <i data-lucide="sliders-horizontal" class="w-5 h-5 text-accent"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-serif text-accent">AI Tool Selection</h3>
                                <p class="text-xs text-textMuted">Choose which analysis tools your agent can use</p>
                            </div>
                        </div>
                    </div>

                    <div id="tool-settings-free-notice" class="hidden mb-4 bg-background/50 rounded-xl p-4 border border-white/5">
                        <p class="text-sm text-textMuted leading-relaxed">
                            <i data-lucide="lock" class="w-4 h-4 inline-block mr-1 opacity-70"></i>
                            <span data-i18n="settings.upgradeForTools">Upgrade to Premium to customize your agent's tool set.</span>
                        </p>
                    </div>

                    <div id="tool-settings-list" class="space-y-2"></div>
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
                        <div class="${INFO_PANEL_CLASS}">
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

                        <p class="text-[10px] text-textMuted/60 text-center" data-i18n="settings.premium.oneTimePayment">Monthly subscription. Renew to keep Premium access.</p>
                    </div>
                </div>

                <button onclick="saveSettings()" id="btn-save-settings" class="w-full py-4 bg-secondary text-background font-bold rounded-2xl shadow-xl hover:scale-[1.02] transition" data-i18n="settings.saveAll">
                    Save All Settings
                </button>

                <!-- About & Legal -->
                <div class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="${CARD_HEADER_ROW_CLASS} mb-6">
                        <div class="${HERO_ICON_BOX_CLASS}">
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
        </div>
    `;

// Side-effect module — assigns to window.Components
export {};
