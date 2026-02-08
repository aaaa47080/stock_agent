/**
 * Safety Tab Controller
 * Manages the embedded scam tracker and governance features
 */
const SafetyTab = {
    _initialized: false,
    filters: { scam_type: '', status: '', sort_by: 'latest', limit: 20, offset: 0 },
    reports: [],
    scamTypes: [],
    currentDetailId: null,

    _getToken() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            return AuthManager.currentUser.accessToken || null;
        }
        return localStorage.getItem('auth_token') || null;
    },

    // ========================================
    // Initialization
    // ========================================

    async init() {
        if (this._initialized) return;
        this._initialized = true;

        await this.loadScamTypes();
        this.loadReports();
    },

    async loadScamTypes() {
        try {
            const config = await ScamTrackerAPI.getConfig();
            this.scamTypes = config.scam_types || this._defaultScamTypes();
        } catch (e) {
            this.scamTypes = this._defaultScamTypes();
        }

        // Populate filter dropdown
        const filterSelect = document.getElementById('safety-filter-type');
        if (filterSelect) {
            filterSelect.innerHTML = '<option value="">All Types</option>';
            this.scamTypes.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = `${t.icon} ${t.name}`;
                filterSelect.appendChild(opt);
            });
        }

        // Populate submit modal dropdown
        const submitSelect = document.getElementById('safety-scam-type');
        if (submitSelect) {
            submitSelect.innerHTML = '<option value="">Select type...</option>';
            this.scamTypes.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = `${t.icon} ${t.name}`;
                submitSelect.appendChild(opt);
            });
        }
    },

    _defaultScamTypes() {
        return [
            { id: 'fake_official', name: 'Fake Official', icon: '🎭' },
            { id: 'investment_scam', name: 'Investment Scam', icon: '💰' },
            { id: 'fake_airdrop', name: 'Fake Airdrop', icon: '🎁' },
            { id: 'trading_fraud', name: 'Trading Fraud', icon: '🔄' },
            { id: 'gambling', name: 'Gambling Scam', icon: '🎰' },
            { id: 'phishing', name: 'Phishing', icon: '🎣' },
            { id: 'other', name: 'Other', icon: '⚠️' }
        ];
    },

    // ========================================
    // Scam Report List
    // ========================================

    applyFilters() {
        const filterType = document.getElementById('safety-filter-type');
        const filterStatus = document.getElementById('safety-filter-status');
        const sortBy = document.getElementById('safety-sort-by');

        this.filters.scam_type = filterType ? filterType.value : '';
        this.filters.status = filterStatus ? filterStatus.value : '';
        this.filters.sort_by = sortBy ? sortBy.value : 'latest';
        this.filters.offset = 0;
        this.reports = [];
        this.loadReports();
    },

    async loadReports(append = false) {
        try {
            const data = await ScamTrackerAPI.getReports(this.filters);
            const reports = data.reports || [];

            if (append) {
                this.reports = this.reports.concat(reports);
            } else {
                this.reports = reports;
            }

            this.renderReports();

            const btnMore = document.getElementById('safety-btn-load-more');
            if (btnMore) {
                btnMore.classList.toggle('hidden', reports.length < this.filters.limit);
            }
        } catch (error) {
            console.error('SafetyTab: Load reports failed:', error);
            const container = document.getElementById('safety-report-list');
            if (container) {
                container.innerHTML = '<div class="text-center text-danger py-8">Failed to load reports</div>';
            }
        }
    },

    loadMore() {
        this.filters.offset += this.filters.limit;
        this.loadReports(true);
    },

    renderReports() {
        const container = document.getElementById('safety-report-list');
        if (!container) return;

        if (this.reports.length === 0) {
            container.innerHTML = '<div class="text-center text-textMuted py-8">No reports found</div>';
            return;
        }

        container.innerHTML = this.reports.map(report => `
            <div class="bg-surface border border-white/5 rounded-2xl p-5 hover:border-primary/30 transition cursor-pointer"
                onclick="SafetyTab.openDetailModal(${report.id})">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-2 flex-wrap">
                        ${this._statusBadge(report.verification_status)}
                        ${this._typeBadge(report.scam_type)}
                    </div>
                    <span class="text-xs text-textMuted">${this._formatDate(report.created_at)}</span>
                </div>
                <div class="font-mono text-primary text-sm mb-2 break-all">
                    ${report.scam_wallet_address}
                </div>
                <p class="text-textMuted text-sm mb-3 line-clamp-2">${this._escapeHTML(report.description)}</p>
                <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center gap-3">
                        <span class="text-success flex items-center gap-1"><i data-lucide="thumbs-up" class="w-3.5 h-3.5"></i> ${report.approve_count}</span>
                        <span class="text-danger flex items-center gap-1"><i data-lucide="thumbs-down" class="w-3.5 h-3.5"></i> ${report.reject_count}</span>
                        <span class="text-textMuted flex items-center gap-1"><i data-lucide="message-circle" class="w-3.5 h-3.5"></i> ${report.comment_count}</span>
                    </div>
                    <span class="text-[10px] text-textMuted hidden sm:block">${report.reporter_wallet_masked}</span>
                </div>
            </div>
        `).join('');

        if (window.lucide) lucide.createIcons();
    },

    // ========================================
    // Search
    // ========================================

    async handleSearch() {
        const input = document.getElementById('safety-search-wallet');
        if (!input) return;
        const addr = input.value.trim().toUpperCase();

        if (!addr) {
            this._toast('Please enter a wallet address', 'warning');
            return;
        }

        if (!this._isValidPiAddress(addr)) {
            this._toast('Invalid wallet address format', 'error');
            return;
        }

        try {
            const data = await ScamTrackerAPI.searchWallet(addr);
            if (data.found && data.report) {
                this.openDetailModal(data.report.id);
            } else {
                this._toast('No reports found for this address', 'info');
            }
        } catch (error) {
            this._toast('Search failed', 'error');
        }
    },

    // ========================================
    // Submit Scam Report Modal
    // ========================================

    openSubmitModal() {
        const modal = document.getElementById('safety-submit-modal');
        if (modal) modal.classList.remove('hidden');

        // Char count listener
        const desc = document.getElementById('safety-description');
        const count = document.getElementById('safety-char-count');
        if (desc && count) {
            desc.oninput = () => { count.textContent = desc.value.length; };
        }

        if (window.lucide) lucide.createIcons();
    },

    closeSubmitModal() {
        const modal = document.getElementById('safety-submit-modal');
        if (modal) modal.classList.add('hidden');
    },

    _isValidPiAddress(address) {
        return /^G[A-Z234567]{55}$/.test(address);
    },

    _isValidTxHash(hash) {
        return /^[a-f0-9]{64}$/.test(hash);
    },

    async submitReport() {
        const wallet = (document.getElementById('safety-scam-wallet').value || '').trim().toUpperCase();
        const reporter = (document.getElementById('safety-reporter-wallet').value || '').trim().toUpperCase();
        const scamType = document.getElementById('safety-scam-type').value;
        const desc = (document.getElementById('safety-description').value || '').trim();
        const txHash = (document.getElementById('safety-tx-hash').value || '').trim().toLowerCase();

        if (!this._isValidPiAddress(wallet)) {
            this._toast('Invalid scam wallet address (must be 56 chars, start with G, A-Z & 2-7 only)', 'error'); return;
        }
        if (!this._isValidPiAddress(reporter)) {
            this._toast('Invalid reporter wallet address (must be 56 chars, start with G, A-Z & 2-7 only)', 'error'); return;
        }
        if (!scamType) { this._toast('Select a scam type', 'warning'); return; }
        if (desc.length < 20 || desc.length > 2000) {
            this._toast('Description must be 20-2000 chars', 'error'); return;
        }
        if (txHash && !this._isValidTxHash(txHash)) {
            this._toast('Invalid transaction hash (must be 64 hex chars)', 'error'); return;
        }

        const btn = document.getElementById('safety-btn-submit');
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Submitting...';
        if (window.lucide) lucide.createIcons();

        try {
            await ScamTrackerAPI.submitReport({
                scam_wallet_address: wallet,
                reporter_wallet_address: reporter,
                scam_type: scamType,
                description: desc,
                transaction_hash: txHash || null
            });

            this._toast('Report submitted successfully!', 'success');
            this.closeSubmitModal();

            // Reset form
            document.getElementById('safety-scam-wallet').value = '';
            document.getElementById('safety-reporter-wallet').value = '';
            document.getElementById('safety-scam-type').value = '';
            document.getElementById('safety-description').value = '';
            document.getElementById('safety-tx-hash').value = '';
            document.getElementById('safety-char-count').textContent = '0';

            // Refresh list
            this.filters.offset = 0;
            this.reports = [];
            this.loadReports();
        } catch (error) {
            this._toast(error.message || 'Submit failed', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i> Submit Report';
            if (window.lucide) lucide.createIcons();
        }
    },

    // ========================================
    // Report Detail Modal
    // ========================================

    async openDetailModal(reportId) {
        this.currentDetailId = reportId;
        const modal = document.getElementById('safety-detail-modal');
        const content = document.getElementById('safety-detail-content');
        if (!modal || !content) return;

        modal.classList.remove('hidden');
        content.innerHTML = '<div class="text-center text-textMuted py-8"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i> Loading...</div>';
        if (window.lucide) lucide.createIcons();

        try {
            const data = await ScamTrackerAPI.getReportDetail(reportId);
            const r = data.report;

            document.getElementById('safety-detail-approve').textContent = r.approve_count;
            document.getElementById('safety-detail-reject').textContent = r.reject_count;

            content.innerHTML = `
                <div class="flex items-center gap-2 mb-4 flex-wrap">
                    ${this._statusBadge(r.verification_status)}
                    ${this._typeBadge(r.scam_type)}
                    <span class="text-xs text-textMuted ml-auto">${this._formatDate(r.created_at)}</span>
                </div>
                <div class="mb-4">
                    <label class="text-[10px] text-textMuted uppercase tracking-wider">Scam Wallet</label>
                    <div class="flex items-center gap-2 bg-background rounded-xl p-3 mt-1">
                        <code class="flex-1 font-mono text-primary text-sm break-all">${r.scam_wallet_address}</code>
                        <button onclick="navigator.clipboard.writeText('${r.scam_wallet_address}'); SafetyTab._toast('Copied!', 'success')"
                            class="text-textMuted hover:text-primary transition shrink-0">
                            <i data-lucide="copy" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
                ${r.transaction_hash ? `
                <div class="mb-4">
                    <label class="text-[10px] text-textMuted uppercase tracking-wider">Transaction Hash</label>
                    <div class="bg-background rounded-xl p-3 mt-1">
                        <code class="font-mono text-xs text-textMuted break-all">${r.transaction_hash}</code>
                    </div>
                </div>` : ''}
                <div class="mb-4">
                    <label class="text-[10px] text-textMuted uppercase tracking-wider">Description</label>
                    <div class="bg-background rounded-xl p-4 mt-1 text-textMuted text-sm leading-relaxed">
                        ${this._escapeHTML(r.description).replace(/\n/g, '<br>')}
                    </div>
                </div>
                <div class="flex items-center justify-between text-[10px] text-textMuted border-t border-white/5 pt-3">
                    <span>Reporter: ${r.reporter_wallet_masked}</span>
                    <span>Views: ${r.view_count}</span>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
        } catch (error) {
            content.innerHTML = `<div class="text-center text-danger py-8">${error.message || 'Failed to load'}</div>`;
        }
    },

    closeDetailModal() {
        const modal = document.getElementById('safety-detail-modal');
        if (modal) modal.classList.add('hidden');
        this.currentDetailId = null;
    },

    async voteOnDetail(voteType) {
        if (!this.currentDetailId) return;
        try {
            await ScamTrackerAPI.vote(this.currentDetailId, voteType);
            this._toast(voteType === 'approve' ? 'Confirmed' : 'Disputed', 'success');
            this.openDetailModal(this.currentDetailId);
            // Refresh list in background
            this.filters.offset = 0;
            this.reports = [];
            this.loadReports();
        } catch (error) {
            this._toast(error.message || 'Vote failed', 'error');
        }
    },

    // ========================================
    // Governance Modal
    // ========================================

    openGovernanceModal() {
        const modal = document.getElementById('governance-modal');
        if (modal) modal.classList.remove('hidden');
        if (window.lucide) lucide.createIcons();
        this.loadGovQuota();
    },

    async loadGovQuota() {
        const token = this._getToken();
        const badge = document.getElementById('gov-quota-badge');
        const bar = document.getElementById('gov-quota-bar');
        const text = document.getElementById('gov-quota-text');
        const tier = document.getElementById('gov-quota-tier');

        if (!token) {
            if (text) text.textContent = 'Login to view quota';
            if (badge) badge.textContent = '--';
            return;
        }

        try {
            const res = await fetch('/api/governance/report-quota', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                if (text) text.textContent = 'Could not load quota';
                return;
            }
            const data = await res.json();
            const pct = data.limit > 0 ? Math.round((data.used / data.limit) * 100) : 0;
            const barColor = pct >= 80 ? 'bg-danger' : pct >= 50 ? 'bg-warning' : 'bg-accent';

            if (badge) badge.textContent = `${data.remaining} left`;
            if (bar) {
                bar.style.width = pct + '%';
                bar.className = `h-2 rounded-full ${barColor} transition-all`;
            }
            if (text) text.textContent = `${data.used} / ${data.limit} reports used today`;
            if (tier) tier.textContent = data.is_pro ? 'PRO' : 'Free';
        } catch (error) {
            if (text) text.textContent = 'Could not load quota';
        }
    },

    closeGovernanceModal() {
        const modal = document.getElementById('governance-modal');
        if (modal) modal.classList.add('hidden');
    },

    switchGovTab(tabId) {
        // Update tab buttons
        document.querySelectorAll('.gov-tab-btn').forEach(btn => {
            btn.classList.remove('border-primary', 'text-primary');
            btn.classList.add('border-transparent', 'text-textMuted');
        });
        const activeBtn = document.querySelector(`.gov-tab-btn[data-gov-tab="${tabId}"]`);
        if (activeBtn) {
            activeBtn.classList.remove('border-transparent', 'text-textMuted');
            activeBtn.classList.add('border-primary', 'text-primary');
        }

        // Update tab content
        document.querySelectorAll('.gov-tab-content').forEach(el => el.classList.add('hidden'));
        const target = document.getElementById(tabId + '-tab');
        if (target) target.classList.remove('hidden');

        // Load data
        if (tabId === 'gov-my-reports') this.loadMyGovReports('all');
        if (tabId === 'gov-review') this.loadGovReview();
        if (tabId === 'gov-leaderboard') this.loadGovLeaderboard();
    },

    async submitGovernanceReport() {
        const contentType = document.getElementById('gov-content-type').value;
        const contentId = parseInt(document.getElementById('gov-content-id').value);
        const reportType = document.getElementById('gov-report-type').value;
        const description = (document.getElementById('gov-description').value || '').trim();

        if (!contentType || !contentId || !reportType) {
            this._toast('Please fill all required fields', 'error');
            return;
        }

        const token = this._getToken();
        if (!token) { this._toast('Please login first', 'error'); return; }

        try {
            const res = await fetch('/api/governance/reports', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    content_type: contentType,
                    content_id: contentId,
                    report_type: reportType,
                    description: description || null
                })
            });

            const result = await res.json();
            if (res.ok) {
                this._toast('Report submitted!', 'success');
                document.getElementById('gov-content-type').value = '';
                document.getElementById('gov-content-id').value = '';
                document.getElementById('gov-report-type').value = '';
                document.getElementById('gov-description').value = '';
                this.loadGovQuota();
            } else {
                this._toast(result.detail || 'Submit failed', 'error');
            }
        } catch (error) {
            this._toast('Submit failed', 'error');
        }
    },

    async loadMyGovReports(status, clickedBtn) {
        // Update filter button styles
        document.querySelectorAll('.gov-filter-btn').forEach(btn => {
            btn.classList.remove('text-primary', 'border-primary/20');
            btn.classList.add('text-textMuted', 'border-white/5');
        });
        if (clickedBtn) {
            clickedBtn.classList.remove('text-textMuted', 'border-white/5');
            clickedBtn.classList.add('text-primary', 'border-primary/20');
        }

        const list = document.getElementById('gov-my-reports-list');
        if (!list) return;
        list.innerHTML = '<div class="text-center text-textMuted py-4 text-sm"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i> Loading...</div>';
        if (window.lucide) lucide.createIcons();

        const token = this._getToken();
        if (!token) { list.innerHTML = '<div class="text-center text-textMuted py-4">Please login</div>'; return; }

        try {
            const url = status === 'all' ? '/api/governance/reports' : `/api/governance/reports?status=${status}`;
            const res = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
            if (!res.ok) {
                list.innerHTML = '<div class="text-center text-danger py-4 text-sm">Failed to load reports</div>';
                return;
            }
            const data = await res.json();
            const reports = data.reports || [];
            if (reports.length === 0) {
                list.innerHTML = '<div class="text-center text-textMuted py-4 text-sm">No reports found</div>';
                return;
            }
            list.innerHTML = reports.map(r => `
                <div class="bg-background rounded-xl p-4">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs text-textMuted">#${r.id}</span>
                        <span class="text-xs px-2 py-0.5 rounded ${r.review_status === 'pending' ? 'bg-warning/20 text-warning' : r.review_status === 'approved' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}">${r.review_status}</span>
                    </div>
                    <div class="text-sm text-secondary">${r.content_type === 'post' ? 'Post' : 'Comment'} #${r.content_id} - ${r.report_type}</div>
                    ${r.description ? `<p class="text-xs text-textMuted mt-1 line-clamp-2">${this._escapeHTML(r.description)}</p>` : ''}
                    <div class="text-[10px] text-textMuted mt-2">${this._formatDate(r.created_at)}</div>
                </div>
            `).join('');
        } catch (error) {
            list.innerHTML = '<div class="text-center text-danger py-4 text-sm">Failed to load</div>';
        }
    },

    async loadGovReview() {
        const token = this._getToken();
        const proNotice = document.getElementById('gov-pro-notice');
        const reviewContent = document.getElementById('gov-review-content');
        const pendingList = document.getElementById('gov-pending-list');

        if (!token) {
            if (pendingList) pendingList.innerHTML = '<div class="text-center text-textMuted py-4 text-sm">Please login to review</div>';
            return;
        }

        try {
            const res = await fetch('/api/governance/reports/pending', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                if (proNotice) proNotice.classList.add('hidden');
                if (reviewContent) reviewContent.classList.remove('hidden');

                const data = await res.json();
                const reports = data.reports || [];

                if (reports.length === 0) {
                    pendingList.innerHTML = '<div class="text-center text-textMuted py-4 text-sm">No pending reports</div>';
                    return;
                }

                pendingList.innerHTML = reports.map(r => `
                    <div class="bg-background rounded-xl p-4 space-y-3">
                        <div class="flex items-center justify-between">
                            <span class="text-xs text-textMuted">#${r.id}</span>
                            <span class="text-xs bg-warning/20 text-warning px-2 py-0.5 rounded">pending</span>
                        </div>
                        <div class="text-sm text-secondary">${r.content_type === 'post' ? 'Post' : 'Comment'} #${r.content_id} - ${r.report_type}</div>
                        ${r.description ? `<p class="text-xs text-textMuted">${this._escapeHTML(r.description)}</p>` : ''}
                        <div class="flex gap-2">
                            <button onclick="SafetyTab.govVote(${r.id}, 'approve')" class="flex-1 py-2 bg-success/10 hover:bg-success/20 text-success text-xs font-bold rounded-lg transition">Violation</button>
                            <button onclick="SafetyTab.govVote(${r.id}, 'reject')" class="flex-1 py-2 bg-danger/10 hover:bg-danger/20 text-danger text-xs font-bold rounded-lg transition">Not Violation</button>
                        </div>
                    </div>
                `).join('');
            } else {
                const result = await res.json();
                if (result.detail && result.detail.includes('PRO')) {
                    if (proNotice) proNotice.classList.remove('hidden');
                    if (reviewContent) reviewContent.classList.add('hidden');
                }
            }
        } catch (error) {
            pendingList.innerHTML = '<div class="text-center text-danger py-4 text-sm">Failed to load</div>';
        }
    },

    async govVote(reportId, voteType) {
        const token = this._getToken();
        if (!token) return;

        try {
            const res = await fetch(`/api/governance/reports/${reportId}/vote`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ vote_type: voteType })
            });
            const result = await res.json();
            if (res.ok) {
                this._toast(result.message || 'Vote submitted', 'success');
                this.loadGovReview();
            } else {
                this._toast(result.detail || 'Vote failed', 'error');
            }
        } catch (error) {
            this._toast('Vote failed', 'error');
        }
    },

    async loadGovLeaderboard() {
        const list = document.getElementById('gov-leaderboard-list');
        if (!list) return;
        list.innerHTML = '<div class="text-center text-textMuted py-4"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i></div>';
        if (window.lucide) lucide.createIcons();

        const token = this._getToken();
        if (!token) {
            list.innerHTML = '<div class="text-center text-textMuted py-4 text-sm">Please login to view leaderboard</div>';
            return;
        }

        try {
            const res = await fetch('/api/governance/reviewers/leaderboard', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                list.innerHTML = `<div class="text-center text-danger py-4 text-sm">${errData.detail || 'Failed to load leaderboard'}</div>`;
                return;
            }
            const data = await res.json();
            const reviewers = data.leaderboard || [];
            if (reviewers.length === 0) {
                list.innerHTML = '<div class="text-center text-textMuted py-4 text-sm">No reviewers yet</div>';
                return;
            }
            list.innerHTML = reviewers.map((r, i) => {
                const rank = i + 1;
                const rankColor = rank === 1 ? 'text-yellow-400' : rank === 2 ? 'text-gray-400' : rank === 3 ? 'text-amber-600' : 'text-textMuted';
                return `
                    <div class="flex items-center gap-3 bg-background rounded-xl p-3">
                        <span class="text-lg font-bold w-8 text-center ${rankColor}">${rank}</span>
                        <div class="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-accent font-bold">${(r.username || '?').charAt(0).toUpperCase()}</div>
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-bold text-secondary truncate">${this._escapeHTML(r.username || 'Anonymous')}</div>
                            <div class="text-[10px] text-textMuted">${r.total_reviews} reviews · ${(r.accuracy_rate * 100).toFixed(1)}% accuracy</div>
                        </div>
                        <div class="text-right">
                            <div class="text-lg font-bold text-accent">${r.reputation_score}</div>
                            <div class="text-[9px] text-textMuted">rep</div>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            list.innerHTML = '<div class="text-center text-danger py-4 text-sm">Failed to load leaderboard</div>';
        }
    },

    // ========================================
    // Utility
    // ========================================

    _statusBadge(status) {
        const badges = {
            'verified': '<span class="bg-success/20 text-success px-2 py-0.5 rounded text-[10px] font-bold">Verified</span>',
            'pending': '<span class="bg-warning/20 text-warning px-2 py-0.5 rounded text-[10px] font-bold">Pending</span>',
            'disputed': '<span class="bg-danger/20 text-danger px-2 py-0.5 rounded text-[10px] font-bold">Disputed</span>'
        };
        return badges[status] || badges.pending;
    },

    _typeBadge(type) {
        const t = this.scamTypes.find(s => s.id === type);
        const name = t ? `${t.icon} ${t.name}` : type;
        return `<span class="bg-primary/10 text-primary px-2 py-0.5 rounded text-[10px] font-bold">${name}</span>`;
    },

    _formatDate(iso) {
        const d = new Date(iso);
        const now = new Date();
        const diff = now - d;
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        const days = Math.floor(hrs / 24);
        if (days < 7) return `${days}d ago`;
        return d.toLocaleDateString('zh-TW');
    },

    _escapeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    _toast(message, type) {
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            const toast = document.createElement('div');
            const colors = { success: 'bg-success', error: 'bg-danger', warning: 'bg-yellow-500', info: 'bg-primary' };
            toast.className = `fixed bottom-8 left-1/2 transform -translate-x-1/2 ${colors[type] || colors.info} text-white px-6 py-3 rounded-xl shadow-lg z-[110] animate-fade-in-up text-sm font-bold`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 2000);
        }
    }
};

window.SafetyTab = SafetyTab;
