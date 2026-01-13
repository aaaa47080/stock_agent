/**
 * committeeManager.js - Manages the "Committee Mode" configuration
 * Handles provider selection, model selection (filtered by validated keys),
 * and team member management.
 */

const CommitteeManager = {
    // State to track team members
    bullTeam: [],
    bearTeam: [],

    init() {
        this.bindEvents();
        this.updateProviders();
        this.updateTeamUI();
    },

    bindEvents() {
        const providerSelect = document.getElementById('committee-provider-select');
        const modelSelect = document.getElementById('committee-model-select');
        const addBullBtn = document.getElementById('add-bull-btn');
        const addBearBtn = document.getElementById('add-bear-btn');
        const toggleCheckbox = document.getElementById('set-committee-mode');

        if (providerSelect) {
            providerSelect.addEventListener('change', () => this.handleProviderChange());
        }

        if (modelSelect) {
            modelSelect.addEventListener('change', () => this.updateAddButtons());
        }

        if (addBullBtn) {
            addBullBtn.addEventListener('click', () => this.addMember('bull'));
        }

        if (addBearBtn) {
            addBearBtn.addEventListener('click', () => this.addMember('bear'));
        }
        
        if (toggleCheckbox) {
             toggleCheckbox.addEventListener('change', (e) => this.togglePanel(e.target.checked));
        }
    },

    togglePanel(isChecked) {
        const panel = document.getElementById('committee-management-panel');
        if (!panel) return;
        
        if (isChecked) {
            panel.classList.remove('hidden');
            this.updateProviders(); // Refresh providers when opening
        } else {
            panel.classList.add('hidden');
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
                     // Ideally, this should be an input for OpenRouter, but keeping it consistent for now.
                     models = [
                        { value: 'anthropic/claude-3.5-sonnet', display: 'Claude 3.5 Sonnet' },
                        { value: 'openai/gpt-4o', display: 'GPT-4o (via OR)' },
                        { value: 'google/gemini-pro-1.5', display: 'Gemini 1.5 Pro (via OR)' }
                     ];
                     
                     // If the user has a manually entered model saved for OpenRouter, add it
                     const savedModel = window.APIKeyManager.getModelForProvider('openrouter');
                     if (savedModel) {
                         // Check if already in list
                         if (!models.find(m => m.value === savedModel)) {
                             models.unshift({ value: savedModel, display: savedModel });
                         }
                     }
                }
            }

            // Populate Dropdown
            models.forEach(m => {
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
window.toggleCommitteePanel = (e) => CommitteeManager.togglePanel(document.getElementById('set-committee-mode')?.checked);
window.updateCommitteeModels = () => CommitteeManager.handleProviderChange();
window.addModelToCommittee = (team) => CommitteeManager.addMember(team);
