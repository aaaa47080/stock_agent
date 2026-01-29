/**
 * committeeManager.js - Manages the "Committee Mode" configuration
 * Handles provider selection, model selection (filtered by validated keys),
 * and team member management.
 */

const CommitteeManager = {
    // State to track team members
    bullTeam: [],
    bearTeam: [],
    _initialized: false, // 🔒 防止重複初始化

    init() {
        // 防止重複初始化
        if (this._initialized) {
            console.log('[CommitteeManager] Already initialized, skipping');
            return;
        }

        this.bindEvents();
        this.updateProviders();
        this.updateTeamUI();
        this._initialized = true;
    },

    bindEvents() {
        const providerSelect = document.getElementById('committee-provider-select');
        const modelSelect = document.getElementById('committee-model-select');
        const addBullBtn = document.getElementById('add-bull-btn');
        const addBearBtn = document.getElementById('add-bear-btn');
        const toggleCheckbox = document.getElementById('set-committee-mode');

        console.log('[CommitteeManager] Binding events...', {
            providerSelect: !!providerSelect,
            modelSelect: !!modelSelect,
            toggleCheckbox: !!toggleCheckbox
        });

        // 如果關鍵元素不存在，跳過綁定（可能組件還未注入）
        if (!toggleCheckbox) {
            console.log('[CommitteeManager] Committee checkbox not found, skipping event binding');
            return;
        }

        // 🔧 移除舊的事件監聽器（如果存在）以防止重複綁定
        if (this._boundHandlers) {
            if (providerSelect) providerSelect.removeEventListener('change', this._boundHandlers.providerChange);
            if (modelSelect) modelSelect.removeEventListener('change', this._boundHandlers.modelChange);
            if (addBullBtn) addBullBtn.removeEventListener('click', this._boundHandlers.addBull);
            if (addBearBtn) addBearBtn.removeEventListener('click', this._boundHandlers.addBear);
            if (toggleCheckbox) toggleCheckbox.removeEventListener('change', this._boundHandlers.toggle);
        }

        // 創建綁定的處理函數（保存引用以便後續移除）
        this._boundHandlers = {
            providerChange: () => this.handleProviderChange(),
            modelChange: () => this.updateAddButtons(),
            addBull: () => this.addMember('bull'),
            addBear: () => this.addMember('bear'),
            toggle: (e) => {
                console.log('[CommitteeManager] Toggle event fired:', e.target.checked);
                this.togglePanel(e.target.checked);
            }
        };

        // 綁定新的事件監聽器
        if (providerSelect) {
            providerSelect.addEventListener('change', this._boundHandlers.providerChange);
        }

        if (modelSelect) {
            modelSelect.addEventListener('change', this._boundHandlers.modelChange);
        }

        if (addBullBtn) {
            addBullBtn.addEventListener('click', this._boundHandlers.addBull);
        }

        if (addBearBtn) {
            addBearBtn.addEventListener('click', this._boundHandlers.addBear);
        }

        if (toggleCheckbox) {
            toggleCheckbox.addEventListener('change', this._boundHandlers.toggle);
        }

        console.log('[CommitteeManager] Events bound successfully');
    },

    togglePanel(isChecked) {
        const panel = document.getElementById('committee-management-panel');
        console.log('[CommitteeManager] togglePanel called:', { isChecked, panel: !!panel });

        if (!panel) {
            console.error('[CommitteeManager] Panel not found!');
            return;
        }

        if (isChecked) {
            panel.classList.remove('hidden');
            this.updateProviders(); // Refresh providers when opening
            console.log('[CommitteeManager] Panel opened');
        } else {
            panel.classList.add('hidden');
            console.log('[CommitteeManager] Panel closed');
        }
    },

    /**
     * Updates the provider dropdown based on validated keys in APIKeyManager.
     */
    updateProviders() {
        const providerSelect = document.getElementById('committee-provider-select');
        const noKeyHint = document.getElementById('committee-no-key-hint');
        if (!providerSelect) return;

        // Clear existing options
        providerSelect.innerHTML = '<option value="">Select Provider...</option>';

        // Get all keys
        const allKeys = window.APIKeyManager.getAllKeys();
        let hasValidKey = false;

        // Check each provider
        const providers = [
            { id: 'openai', name: 'OpenAI' },
            { id: 'google_gemini', name: 'Google Gemini' },
            { id: 'openrouter', name: 'OpenRouter' }
        ];

        providers.forEach(p => {
            if (allKeys[p.id]) {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.name;
                providerSelect.appendChild(option);
                hasValidKey = true;
            }
        });

        // Show hint if no keys are configured
        if (noKeyHint) {
            if (!hasValidKey) {
                noKeyHint.classList.remove('hidden');
                providerSelect.disabled = true;
            } else {
                noKeyHint.classList.add('hidden');
                providerSelect.disabled = false;
            }
        }
    },

    /**
     * Handles provider change: fetches models and updates the model dropdown.
     */
    async handleProviderChange() {
        const providerSelect = document.getElementById('committee-provider-select');
        const modelSelect = document.getElementById('committee-model-select');

        if (!providerSelect || !modelSelect) return;

        const provider = providerSelect.value;

        // Reset model select
        modelSelect.innerHTML = '<option value="">Select Model...</option>';
        modelSelect.disabled = true;
        this.updateAddButtons();

        if (!provider) return;

        modelSelect.disabled = false;

        // Fetch models (using the existing fetchModelConfig from llmSettings.js if available, or fallback)
        let models = [];

        try {
            // Try to get models from the shared config function if it exists
            if (typeof fetchModelConfig === 'function') {
                const config = await fetchModelConfig();
                if (config && config[provider] && config[provider].available_models) {
                    models = config[provider].available_models;
                }
            }

            // If fetching failed or returned empty (or specific logic for OpenRouter)
            if (models.length === 0) {
                if (provider === 'openai') {
                    models = [
                        { value: 'gpt-4o', display: 'GPT-4o' },
                        { value: 'gpt-4o-mini', display: 'GPT-4o Mini' }
                    ];
                } else if (provider === 'google_gemini') {
                    models = [
                        { value: 'gemini-1.5-pro', display: 'Gemini 1.5 Pro' },
                        { value: 'gemini-1.5-flash', display: 'Gemini 1.5 Flash' }
                    ];
                } else if (provider === 'openrouter') {
                    // For OpenRouter, we might just let them type or show common ones
                    // Since this is a select box, we'll provide common ones.
                    models = [
                        { value: 'anthropic/claude-3.5-sonnet', display: 'Claude 3.5 Sonnet' },
                        { value: 'openai/gpt-4o', display: 'GPT-4o (via OR)' },
                        { value: 'google/gemini-pro-1.5', display: 'Gemini 1.5 Pro (via OR)' }
                    ];
                }
            }

            // Deduplicate models by value using Set
            const uniqueModels = [];
            const seenValues = new Set();

            models.forEach(m => {
                if (!seenValues.has(m.value)) {
                    seenValues.add(m.value);
                    uniqueModels.push(m);
                }
            });

            // Populate Dropdown with unique models only
            uniqueModels.forEach(m => {
                const option = document.createElement('option');
                option.value = m.value;
                option.textContent = m.display;
                modelSelect.appendChild(option);
            });

        } catch (e) {
            console.error("Error loading models for committee:", e);
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        }
    },

    updateAddButtons() {
        const provider = document.getElementById('committee-provider-select').value;
        const model = document.getElementById('committee-model-select').value;
        const addBullBtn = document.getElementById('add-bull-btn');
        const addBearBtn = document.getElementById('add-bear-btn');

        const isValid = provider && model;

        if (addBullBtn) addBullBtn.disabled = !isValid;
        if (addBearBtn) addBearBtn.disabled = !isValid;
    },

    addMember(team) {
        const providerSelect = document.getElementById('committee-provider-select');
        const modelSelect = document.getElementById('committee-model-select');

        const provider = providerSelect.value;
        const model = modelSelect.value;
        const providerName = providerSelect.options[providerSelect.selectedIndex].text;
        const modelName = modelSelect.options[modelSelect.selectedIndex].text;

        if (!provider || !model) return;

        const member = {
            id: Date.now(), // simple unique id
            provider,
            model,
            providerName,
            modelName
        };

        if (team === 'bull') {
            this.bullTeam.push(member);
        } else {
            this.bearTeam.push(member);
        }

        this.updateTeamUI();

        // Optional: Reset selection? No, keep it for easy adding to other team.
        // But maybe show a toast
        if (typeof showToast === 'function') {
            showToast(`Added ${modelName} to ${team === 'bull' ? 'Bull' : 'Bear'} Team`, 'success');
        }
    },

    removeMember(team, id) {
        if (team === 'bull') {
            this.bullTeam = this.bullTeam.filter(m => m.id !== id);
        } else {
            this.bearTeam = this.bearTeam.filter(m => m.id !== id);
        }
        this.updateTeamUI();
    },

    updateTeamUI() {
        this.renderList('bull', this.bullTeam);
        this.renderList('bear', this.bearTeam);
    },

    loadConfig(config) {
        if (!config) return;
        this.bullTeam = (config.bull || []).map((m, idx) => ({
            id: Date.now() + idx,
            provider: m.provider,
            model: m.model,
            providerName: this.getFriendlyProviderName(m.provider),
            modelName: m.model
        }));
        this.bearTeam = (config.bear || []).map((m, idx) => ({
            id: Date.now() + idx + 1000,
            provider: m.provider,
            model: m.model,
            providerName: this.getFriendlyProviderName(m.provider),
            modelName: m.model
        }));
        this.updateTeamUI();
    },

    getFriendlyProviderName(provider) {
        const names = {
            'openai': 'OpenAI',
            'google_gemini': 'Google Gemini',
            'openrouter': 'OpenRouter'
        };
        return names[provider] || provider;
    },

    renderList(team, members) {
        const listEl = document.getElementById(`${team}-committee-list`);
        const emptyHint = document.getElementById(`${team}-empty-hint`);

        if (!listEl) return;

        listEl.innerHTML = '';

        if (members.length === 0) {
            if (emptyHint) emptyHint.classList.remove('hidden');
        } else {
            if (emptyHint) emptyHint.classList.add('hidden');

            members.forEach(m => {
                const li = document.createElement('li');
                li.className = 'flex items-center justify-between bg-surface p-2 rounded-lg border border-white/5';
                li.innerHTML = `
                    <div class="flex flex-col">
                        <span class="font-bold text-secondary">${m.modelName}</span>
                        <span class="text-[10px] text-textMuted">${m.providerName}</span>
                    </div>
                    <button onclick="CommitteeManager.removeMember('${team}', ${m.id})" class="text-textMuted hover:text-danger transition p-1">
                        <i data-lucide="x" class="w-3 h-3"></i>
                    </button>
                `;
                listEl.appendChild(li);
            });
            // Re-render icons for new elements
            if (window.lucide) window.lucide.createIcons();
        }
    },

    // Get current configuration (for saving)
    getConfig() {
        return {
            bull: this.bullTeam.map(m => ({ provider: m.provider, model: m.model })),
            bear: this.bearTeam.map(m => ({ provider: m.provider, model: m.model }))
        };
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    CommitteeManager.init();
});

// Expose to global for HTML callbacks
window.CommitteeManager = CommitteeManager;
window.toggleCommitteePanel = (checkbox) => {
    if (checkbox && checkbox.checked !== undefined) {
        CommitteeManager.togglePanel(checkbox.checked);
    }
};
window.updateCommitteeModels = () => CommitteeManager.handleProviderChange();
window.addModelToCommittee = (team) => CommitteeManager.addMember(team);
