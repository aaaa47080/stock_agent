// ========================================
// components.js - 頁面組件模板與動態注入
// ========================================

const Components = {
    // Tab: Market
    market: `
        <div class="flex items-center justify-between mb-8">
            <h2 class="font-serif text-3xl text-secondary">Market Watch</h2>
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5" title="即時更新狀態">
                    <div id="ticker-ws-indicator" class="w-2 h-2 rounded-full bg-gray-500 transition-colors"></div>
                    <span class="text-[9px] text-textMuted uppercase tracking-wider">LIVE</span>
                </div>
                <span id="screener-last-updated" class="text-[10px] text-textMuted uppercase tracking-widest opacity-60"></span>
                <button onclick="refreshScreener(true)" class="p-2 hover:bg-white/5 rounded-full text-textMuted transition"><i data-lucide="refresh-cw" class="w-4 h-4"></i></button>
            </div>
        </div>

        <div class="space-y-12">
            <!-- Section 1: Top Movers -->
            <section>
                <div class="flex items-center gap-3 mb-6 px-2">
                    <div class="h-px flex-1 bg-gradient-to-r from-primary/30 to-transparent"></div>
                    <h3 class="text-xs font-bold text-primary uppercase tracking-[0.2em] whitespace-nowrap">Top Performers</h3>
                    <div class="h-px flex-1 bg-gradient-to-l from-primary/30 to-transparent"></div>
                </div>
                <div id="top-list" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
            </section>

            <!-- Section 2: Market Dynamics (RSI & Funding) -->
            <section>
                <div class="flex items-center gap-3 mb-8 px-2">
                    <div class="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent"></div>
                    <h3 class="text-xs font-bold text-textMuted uppercase tracking-[0.2em] whitespace-nowrap">Market Dynamics</h3>
                    <div class="h-px flex-1 bg-gradient-to-l from-white/10 to-transparent"></div>
                </div>

                <div class="space-y-10 px-2">
                    <!-- RSI Radar (Side by Side) -->
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h4 class="text-xs font-bold text-success mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <span class="w-1.5 h-1.5 rounded-full bg-success"></span> Oversold Radar
                            </h4>
                            <div id="oversold-list" class="space-y-3"></div>
                        </div>
                        <div>
                            <h4 class="text-xs font-bold text-danger mb-4 flex items-center gap-2 opacity-80 uppercase tracking-wider">
                                <span class="w-1.5 h-1.5 rounded-full bg-danger"></span> Overbought Radar
                            </h4>
                            <div id="overbought-list" class="space-y-3"></div>
                        </div>
                    </div>

                    <!-- Funding Heatmap (Side by Side) -->
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
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
        <div class="flex justify-between items-end mb-8">
            <h2 class="font-serif text-3xl text-secondary">Market Pulse</h2>
            <button onclick="refreshMarketPulse()" class="p-2 bg-surface hover:bg-surfaceHighlight rounded-full text-textMuted transition"><i data-lucide="refresh-cw" class="w-4 h-4"></i></button>
        </div>

        <!-- Progress -->
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

        <div id="pulse-grid" class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Cards injected here -->
        </div>
    `,

    // Tab: Settings
    settings: `
        <div class="max-w-2xl mx-auto">
             <h2 class="font-serif text-3xl text-secondary mb-8">Settings</h2>

             <div class="space-y-10">
                <!-- User Profile Section -->
                <div id="settings-profile-card" class="bg-surface p-6 md:p-8 rounded-3xl border border-white/5">
                    <div class="flex items-center gap-4 mb-6">
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
                    
                    <button onclick="handleLogout()" class="w-full py-3 bg-white/5 hover:bg-danger/10 text-textMuted hover:text-danger border border-white/5 hover:border-danger/20 font-bold rounded-xl transition flex items-center justify-center gap-2">
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
                        <!-- 未綁定狀態 -->
                        <div id="wallet-not-linked" class="hidden">
                            <div class="bg-background/50 rounded-xl p-4 border border-white/5 mb-4">
                                <p class="text-sm text-textMuted leading-relaxed">
                                    <i data-lucide="info" class="w-4 h-4 inline-block mr-1 opacity-60"></i>
                                    綁定 Pi 錢包後可以：
                                </p>
                                <ul class="text-xs text-textMuted mt-2 space-y-1 ml-5">
                                    <li>• 在論壇發布文章（需支付 1 Pi）</li>
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

                        <!-- 已綁定狀態 -->
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
                        <!-- LLM Status Badge -->
                        <div id="llm-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                            <!-- Will be updated by JS -->
                        </div>
                    </div>

                    <div class="space-y-6">
                        <!-- Provider -->
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Provider</label>
                            <select id="llm-provider-select" onchange="updateLLMKeyInput(); updateAvailableModels()" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 transition appearance-none">
                                <option value="openai">OpenAI</option>
                                <option value="google_gemini">Google Gemini</option>
                                <option value="openrouter">OpenRouter</option>
                            </select>
                        </div>

                        <!-- API Key -->
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">API Key</label>
                            <div class="flex gap-3">
                                <input type="password" id="llm-api-key-input" class="flex-1 bg-background border border-white/5 rounded-xl px-4 py-3.5 text-secondary outline-none focus:border-primary/50 font-mono text-sm" placeholder="sk-...">
                                <button onclick="testLLMKey()" class="px-5 bg-surfaceHighlight hover:bg-white/10 text-secondary rounded-xl transition font-bold text-xs whitespace-nowrap">TEST</button>
                            </div>
                        </div>

                        <!-- Model -->
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
                            <input type="checkbox" id="set-committee-mode" class="sr-only peer">
                            <div class="w-12 h-7 bg-background rounded-full peer peer-focus:ring-0 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-accent"></div>
                        </label>
                    </div>

                    <div id="committee-management-panel" class="hidden space-y-6 pt-6 mt-6 border-t border-white/5">
                        <!-- Provider Selection -->
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Provider</label>
                            <select id="committee-provider-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-accent/50 transition appearance-none">
                                <option value="">Select Provider...</option>
                            </select>
                            <p id="committee-no-key-hint" class="text-xs text-warning mt-2 hidden">
                                請先在 AI Intelligence 區塊設定 API Key
                            </p>
                        </div>

                        <!-- Model Selection -->
                        <div>
                            <label class="block text-xs font-bold text-textMuted uppercase tracking-wider mb-2">Model</label>
                            <select id="committee-model-select" class="w-full bg-background border border-white/5 rounded-xl px-4 py-3.5 text-sm text-secondary outline-none focus:border-accent/50 transition appearance-none" disabled>
                                <option value="">先選擇 Provider...</option>
                            </select>
                        </div>

                        <!-- Add to Team Buttons -->
                        <div class="grid grid-cols-2 gap-3">
                            <button id="add-bull-btn" class="py-3 bg-success/10 text-success rounded-xl text-sm font-bold border border-success/20 hover:bg-success/20 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                <i data-lucide="plus" class="w-4 h-4"></i> Bull Team
                            </button>
                            <button id="add-bear-btn" class="py-3 bg-danger/10 text-danger rounded-xl text-sm font-bold border border-danger/20 hover:bg-danger/20 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                                <i data-lucide="plus" class="w-4 h-4"></i> Bear Team
                            </button>
                        </div>

                        <!-- Team Members -->
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
                        <!-- Connection Status Badge -->
                        <div id="okx-status-badge" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium">
                            <!-- Will be updated by JS -->
                        </div>
                    </div>

                    <!-- Not Connected State -->
                    <div id="okx-not-connected" class="hidden">
                        <div class="text-center py-4 mb-4 bg-background/50 rounded-xl">
                            <i data-lucide="unplug" class="w-8 h-8 text-textMuted mx-auto mb-2"></i>
                            <p class="text-sm text-textMuted">No exchange connected</p>
                        </div>
                        <button onclick="document.getElementById('apikey-modal').classList.remove('hidden')" class="w-full py-3.5 bg-gradient-to-r from-primary to-accent text-background font-bold rounded-2xl transition flex items-center justify-center gap-2 shadow-lg shadow-primary/20 hover:scale-[1.02]">
                            <i data-lucide="plug" class="w-4 h-4"></i> Connect OKX
                        </button>
                    </div>

                    <!-- Connected State -->
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
                
                <!-- Version Info -->
                <div class="text-center pt-8 opacity-20 text-[10px] font-mono tracking-widest uppercase">
                    CryptoMind v1.2.0-Pi-Integrated
                </div>
             </div>
        </div>
    `,

    /**
     * 將組件注入到指定的容器中
     * @param {string} id - 分頁 ID (如 'market', 'pulse', 'settings')
     * @returns {Promise<boolean>}
     */
    async inject(id) {
        console.log(`[Components] Attempting to inject: ${id}`);
        const container = document.getElementById(id + '-tab');
        if (container && this[id]) {
            // 強制注入，不檢查是否為空，確保修正顯示問題
            container.innerHTML = this[id];
            
            // 使用 requestAnimationFrame 確保瀏覽器已經完成 DOM 解析
            return new Promise((resolve) => {
                requestAnimationFrame(() => {
                    // 重新初始化 Lucide 圖標
                    if (window.lucide) {
                        window.lucide.createIcons();
                    }
                    console.log(`[Components] Successfully injected ${id} content`);
                    resolve(true);
                });
            });
        }
        console.error(`[Components] Failed to inject ${id}: Container or template not found`, {
            hasContainer: !!container,
            hasTemplate: !!this[id]
        });
        return Promise.resolve(false);
    }
};

// 標記組件系統已就緒
window.ComponentsReady = true;
window.Components = Components;
