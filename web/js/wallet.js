// ========================================
// wallet.js - Wallet & Transaction History
// ========================================

const WalletApp = {
    initialized: false,

    async init() {
        this.log('Init called');
        
        // Ensure AuthManager is ready
        if (typeof AuthManager === 'undefined') {
            this.log('AuthManager undefined');
            this.renderError('System Error: Auth module missing');
            return;
        }

        if (!AuthManager.isLoggedIn()) {
            this.log('User not logged in');
            this.renderEmptyState('Please login to view wallet history');
            return;
        }

        this.initialized = true;
        await this.loadData();
    },

    log(msg, data) {
        console.log(`[WalletApp] ${msg}`, data || '');
        // Optional: Send to backend for remote debugging
        // fetch('/api/debug-log', { method: 'POST', body: JSON.stringify({ level: 'info', message: `[WalletApp] ${msg}`, data }) }).catch(() => {});
    },

    async loadData() {
        this.log('Loading data...');
        const container = document.getElementById('wallet-tx-list');
        
        if (!container) {
            this.log('Container not found');
            return;
        }

        // Loading State
        container.innerHTML = '<div class="text-center text-textMuted py-10 opacity-50"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i>Loading history...</div>';
        if (window.lucide) lucide.createIcons();

        try {
            // Check ForumAPI
            if (typeof ForumAPI === 'undefined') {
                throw new Error('ForumAPI library not loaded');
            }

            this.log('Fetching API data...');

            // Fetch Data in Parallel
            const results = await Promise.allSettled([
                ForumAPI.getMyPayments(),      // 0: Out: Post fees
                ForumAPI.getMyTipsSent(),      // 1: Out: Tips sent
                ForumAPI.getMyTipsReceived()   // 2: In: Tips received
            ]);

            const paymentsData = results[0].status === 'fulfilled' ? results[0].value : { payments: [] };
            const tipsSentData = results[1].status === 'fulfilled' ? results[1].value : { tips: [] };
            const tipsReceivedData = results[2].status === 'fulfilled' ? results[2].value : { tips: [] };

            // Process Outgoing
            const payments = (paymentsData.payments || []).map(p => {
                let type = 'post_payment';
                let icon = 'file-text';
                
                if (p.type === 'membership') {
                    type = 'membership_payment';
                    icon = 'crown';
                }

                return {
                    ...p,
                    type: type,
                    amount: -(p.amount || 1.0), // Ensure expense is negative
                    icon: icon
                };
            });

            const tipsSent = (tipsSentData.tips || [])
                .map(t => ({...t, type: 'tip_sent', amount: -(t.amount || 0), title: `Tip: ${t.post_title || 'Post'}`}));

            // Process Incoming
            const tipsReceived = (tipsReceivedData.tips || [])
                .map(t => ({...t, type: 'tip_received', amount: (t.amount || 0), title: `Tip from ${t.from_username || 'User'}`}));

            // Combine & Sort & Store globally
            this.allTransactions = [...payments, ...tipsSent, ...tipsReceived]
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

            this.log(`Processed ${this.allTransactions.length} transactions`);

            // Apply default filters (All) which will also render the list
            this.applyFilters();

        } catch (e) {
            console.error('[WalletApp] Load Error:', e);
            this.renderError(e.message);
        }
    },

    applyFilters() {
        if (!this.allTransactions) return;

        const typeFilter = document.getElementById('wallet-filter-type')?.value || 'all';
        const timeFilter = document.getElementById('wallet-filter-time')?.value || 'all';
        
        const now = Date.now();
        const oneDay = 24 * 60 * 60 * 1000;

        const filtered = this.allTransactions.filter(tx => {
            // 1. Filter by Type
            let typeMatch = true;
            if (typeFilter === 'in') typeMatch = tx.amount > 0;
            else if (typeFilter === 'out') typeMatch = tx.amount < 0;
            else if (typeFilter === 'membership') typeMatch = tx.type === 'membership_payment';
            else if (typeFilter === 'tip') typeMatch = tx.type === 'tip_sent' || tx.type === 'tip_received';
            else if (typeFilter === 'post') typeMatch = tx.type === 'post_payment';

            // 2. Filter by Time
            let timeMatch = true;
            if (timeFilter !== 'all') {
                const txTime = new Date(tx.created_at).getTime();
                const days = parseInt(timeFilter);
                timeMatch = (now - txTime) < (days * oneDay);
            }

            return typeMatch && timeMatch;
        });

        // Calculate Totals based on Filtered Data
        // This gives users insight into "How much did I spend on TIPS in the last 7 DAYS"
        const totalOutEl = document.getElementById('wallet-total-out');
        const totalInEl = document.getElementById('wallet-total-in');
        
        const totalOut = filtered.filter(t => t.amount < 0).reduce((acc, t) => acc + Math.abs(t.amount), 0);
        const totalIn = filtered.filter(t => t.amount > 0).reduce((acc, t) => acc + t.amount, 0);

        if (totalOutEl) totalOutEl.textContent = totalOut.toFixed(1);
        if (totalInEl) totalInEl.textContent = totalIn.toFixed(1);

        this.renderList(filtered);
    },

    renderList(list) {
        const container = document.getElementById('wallet-tx-list');
        if (!container) return;

        container.innerHTML = '';
        
        if (list.length === 0) {
            this.renderEmptyState('No transactions found matching filters');
            return;
        }

        list.forEach(tx => {
            const el = document.createElement('div');
            el.className = 'flex items-center justify-between border-b border-white/5 py-4 hover:bg-white/5 px-3 rounded-2xl transition cursor-pointer last:border-0 group animate-fade-in-up';
            
            let icon = 'circle-dollar-sign';
            let title = 'Transaction';
            let subtext = '';
            let colorClass = tx.amount < 0 ? 'bg-danger/10 text-danger' : 'bg-success/10 text-success';
            
            if (tx.type === 'post_payment') {
                title = 'Post Fee';
                subtext = tx.title || 'Forum Post';
                icon = 'file-text';
            } else if (tx.type === 'membership_payment') {
                title = 'Premium Upgrade';
                subtext = tx.title || 'Membership';
                icon = 'crown';
                colorClass = 'bg-primary/10 text-primary';
            } else if (tx.type === 'tip_sent') {
                title = 'Tip Sent';
                subtext = tx.title || 'Tip Support';
                icon = 'gift';
            } else if (tx.type === 'tip_received') {
                title = 'Tip Received';
                subtext = tx.title || 'Content Reward';
                icon = 'trophy';
            }

            el.onclick = () => this.showDetail(tx);

            el.innerHTML = `
               <div class="flex items-center gap-4 overflow-hidden">
                    <div class="w-12 h-12 rounded-full ${colorClass} flex items-center justify-center shrink-0 group-hover:scale-110 transition">
                       <i data-lucide="${icon}" class="w-5 h-5"></i>
                    </div>
                    <div class="overflow-hidden">
                        <div class="font-bold text-textMain truncate">${title}</div>
                        <div class="text-xs text-textMuted mt-0.5 truncate">${subtext}</div>
                    </div>
               </div>
               <div class="text-right shrink-0">
                   <div class="font-bold text-base ${tx.amount < 0 && tx.type !== 'membership_payment' ? 'text-textMain' : (tx.type === 'membership_payment' ? 'text-primary' : 'text-success')}">
                       ${tx.amount > 0 ? '+' : ''}${Math.abs(tx.amount).toFixed(1)} Pi
                   </div>
                   <div class="text-[10px] text-textMuted opacity-50 mt-1">${this.formatDate(tx.created_at)}</div>
               </div>
            `;
            container.appendChild(el);
        });
        
        if (window.lucide) lucide.createIcons();
    },

    renderEmptyState(msg = 'No transactions yet') {
        const container = document.getElementById('wallet-tx-list');
        if (container) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center py-12 text-textMuted opacity-60">
                    <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4">
                        <i data-lucide="history" class="w-8 h-8"></i>
                    </div>
                    <p>${msg}</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
        }
    },

    renderError(msg) {
        const container = document.getElementById('wallet-tx-list');
        if (container) {
            container.innerHTML = `
                <div class="text-center py-10">
                    <div class="text-danger font-bold mb-2">Failed to load history</div>
                    <div class="text-xs text-textMuted">${msg}</div>
                    <button onclick="WalletApp.loadData()" class="mt-4 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition">Retry</button>
                </div>
            `;
        }
    },

    showDetail(tx) {
        if (typeof ForumApp !== 'undefined' && typeof ForumApp.showTransactionDetail === 'function') {
            ForumApp.showTransactionDetail(tx);
        } else {
            alert(`Transaction: ${tx.amount} Pi\nHash: ${tx.tx_hash}`);
        }
    },

    formatDate(dateStr) {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit' });
        } catch(e) {
            return dateStr;
        }
    }
};

// Auto-init if tab is already active (e.g. reload)
document.addEventListener('DOMContentLoaded', () => {
   // Wait for auth to be ready
   setTimeout(() => {
       if (document.getElementById('wallet-tab') && !document.getElementById('wallet-tab').classList.contains('hidden')) {
           WalletApp.init();
       }
   }, 1000);
});