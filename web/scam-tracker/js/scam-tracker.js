/**
 * 可疑錢包追蹤系統 - 前端模組
 */

function resolveScamTrackerCurrentUser() {
    if (typeof getCurrentUser === 'function') {
        try {
            return getCurrentUser();
        } catch (_) {
            // Fallback to AuthManager/localStorage for compatibility pages.
        }
    }

    if (window.AuthManager && window.AuthManager.currentUser) {
        return window.AuthManager.currentUser;
    }

    try {
        const raw = localStorage.getItem('pi_user');
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

const ScamTrackerAPI = {
    /**
     * 獲取舉報列表
     */
    async getReports(filters = {}) {
        const params = new URLSearchParams();
        if (filters.scam_type) params.append('scam_type', filters.scam_type);
        if (filters.status) params.append('status', filters.status);
        if (filters.sort_by) params.append('sort_by', filters.sort_by);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);

        const res = await fetch(`/api/scam-tracker/reports?${params}`);
        if (!res.ok) throw new Error('Failed to fetch reports');
        return await res.json();
    },

    /**
     * 獲取舉報詳情
     */
    async getReportDetail(reportId) {
        const token = localStorage.getItem('auth_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        const res = await fetch(`/api/scam-tracker/reports/${reportId}`, { headers });
        if (!res.ok) {
            if (res.status === 404) throw new Error('舉報不存在');
            throw new Error('Failed to fetch report detail');
        }
        return await res.json();
    },

    /**
     * 搜尋錢包
     */
    async searchWallet(address) {
        const params = new URLSearchParams({ wallet_address: address });
        const res = await fetch(`/api/scam-tracker/reports/search?${params}`);
        if (!res.ok && res.status !== 404) throw new Error('Search failed');
        return await res.json();
    },

    /**
     * 投票
     */
    async vote(reportId, voteType) {
        const token = localStorage.getItem('auth_token');
        if (!token) throw new Error('請先登入');

        const res = await fetch(`/api/scam-tracker/votes/${reportId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ vote_type: voteType })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || 'Vote failed');
        }
        return await res.json();
    },

    /**
     * 獲取評論列表
     */
    async getComments(reportId) {
        const res = await fetch(`/api/scam-tracker/comments/${reportId}`);
        if (!res.ok) throw new Error('Failed to fetch comments');
        return await res.json();
    },

    /**
     * 添加評論
     */
    async addComment(reportId, content, txHash = null) {
        const token = localStorage.getItem('auth_token');
        if (!token) throw new Error('請先登入');

        const res = await fetch(`/api/scam-tracker/comments/${reportId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                content,
                transaction_hash: txHash
            })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail?.message || error.detail || 'Comment failed');
        }
        return await res.json();
    },

    /**
     * 提交舉報
     */
    async submitReport(data) {
        const token = localStorage.getItem('auth_token');
        if (!token) throw new Error('請先登入');

        const res = await fetch('/api/scam-tracker/reports', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(data)
        });

        if (!res.ok) {
            const error = await res.json();
            const errorMsg = error.detail?.message || error.detail || 'Submit failed';
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    /**
     * 獲取系統配置
     */
    async getConfig() {
        const res = await fetch('/api/scam-tracker/reports/config');
        if (!res.ok) throw new Error('Failed to fetch config');
        return await res.json();
    }
};

const ScamTrackerApp = {
    currentFilters: {
        scam_type: '',
        status: '',
        sort_by: 'latest',
        limit: 20,
        offset: 0
    },
    reports: [],
    currentReportId: null,
    currentReport: null,
    scamTypes: [],

    /**
     * 初始化列表頁
     */
    initListPage() {
        this.loadScamTypes();
        this.loadReports();
        this.bindListEvents();
    },

    /**
     * 初始化詳情頁
     */
    initDetailPage() {
        const params = new URLSearchParams(window.location.search);
        const reportId = params.get('id');

        if (!reportId) {
            showToast('無效的舉報 ID', 'error');
            setTimeout(() => window.location.href = '/static/scam-tracker/index.html', 2000);
            return;
        }

        this.currentReportId = reportId;
        this.loadReportDetail();
        this.loadComments();
        this.bindDetailEvents();
    },

    /**
     * 初始化提交頁
     */
    initSubmitPage() {
        this.loadScamTypes();
        this.checkPROStatus();
        this.bindSubmitEvents();
    },

    /**
     * 載入詐騙類型（從配置）
     */
    async loadScamTypes() {
        try {
            const config = await ScamTrackerAPI.getConfig();
            this.scamTypes = config.scam_types || [
                {id: 'fake_official', name: '假冒官方', icon: '🎭'},
                {id: 'investment_scam', name: '投資詐騙', icon: '💰'},
                {id: 'fake_airdrop', name: '空投詐騙', icon: '🎁'},
                {id: 'trading_fraud', name: '交易詐騙', icon: '🔄'},
                {id: 'gambling', name: '賭博騙局', icon: '🎰'},
                {id: 'phishing', name: '釣魚網站', icon: '🎣'},
                {id: 'other', name: '其他詐騙', icon: '⚠️'}
            ];
        } catch (e) {
            this.scamTypes = [
                {id: 'fake_official', name: '假冒官方', icon: '🎭'},
                {id: 'investment_scam', name: '投資詐騙', icon: '💰'},
                {id: 'fake_airdrop', name: '空投詐騙', icon: '🎁'},
                {id: 'trading_fraud', name: '交易詐騙', icon: '🔄'},
                {id: 'gambling', name: '賭博騙局', icon: '🎰'},
                {id: 'phishing', name: '釣魚網站', icon: '🎣'},
                {id: 'other', name: '其他詐騙', icon: '⚠️'}
            ];
        }

        // 更新列表頁篩選器
        const filterSelect = document.getElementById('filter-type');
        if (filterSelect) {
            filterSelect.innerHTML = '<option value="">所有類型</option>';
            this.scamTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.id;
                option.textContent = `${type.icon} ${type.name}`;
                filterSelect.appendChild(option);
            });
        }

        // 更新提交頁選擇器
        const submitSelect = document.getElementById('scam-type');
        if (submitSelect) {
            submitSelect.innerHTML = '<option value="">請選擇詐騙類型</option>';
            this.scamTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.id;
                option.textContent = `${type.icon} ${type.name}`;
                submitSelect.appendChild(option);
            });
        }
    },

    /**
     * 檢查 PRO 狀態
     */
    checkPROStatus() {
        const user = resolveScamTrackerCurrentUser();
        if (!user) {
            window.location.href = '/static/forum/index.html';
            return;
        }

        const isPro = user.is_premium || user.is_pro;
        if (!isPro) {
            document.querySelector('form').innerHTML = `
                <div class="text-center py-12">
                    <i data-lucide="shield" class="w-16 h-16 text-textMuted mx-auto mb-4"></i>
                    <h3 class="text-xl font-bold text-secondary mb-2">需要 PRO 會員</h3>
                    <p class="text-textMuted mb-6">舉報功能僅開放給 PRO 會員使用</p>
                    <a href="/static/forum/premium.html" class="inline-block bg-primary text-background px-6 py-3 rounded-xl font-bold hover:opacity-90 transition">
                        升級為 PRO 會員
                    </a>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        // 顯示剩餘配額（預設值，實際應從 API 獲取）
        document.getElementById('remaining-quota').textContent = '5';
    },

    /**
     * 載入舉報列表
     */
    async loadReports(append = false) {
        try {
            const data = await ScamTrackerAPI.getReports(this.currentFilters);
            const reports = data.reports || [];

            if (append) {
                this.reports = this.reports.concat(reports);
            } else {
                this.reports = reports;
            }

            this.renderReports();

            // 顯示/隱藏載入更多按鈕
            const btnLoadMore = document.getElementById('btn-load-more');
            if (btnLoadMore) {
                if (reports.length >= this.currentFilters.limit) {
                    btnLoadMore.classList.remove('hidden');
                } else {
                    btnLoadMore.classList.add('hidden');
                }
            }
        } catch (error) {
            console.error('Load reports failed:', error);
            showToast('載入失敗', 'error');
        }
    },

    /**
     * 渲染舉報列表
     */
    renderReports() {
        const container = document.getElementById('report-list');
        if (!container) return;

        if (this.reports.length === 0) {
            container.innerHTML = '<div class="text-center text-textMuted py-8">暫無舉報記錄</div>';
            return;
        }

        container.innerHTML = this.reports.map((report, i) => `
            <div class="bg-surface border border-white/5 rounded-2xl p-5 hover:border-primary/30 transition cursor-pointer"
                 data-report-idx="${i}">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-2 flex-wrap">
                        ${this.getStatusBadge(report.verification_status)}
                        ${this.getTypeBadge(report.scam_type)}
                    </div>
                    <span class="text-xs text-textMuted">${this.formatDate(report.created_at)}</span>
                </div>

                <div class="font-mono text-primary text-sm md:text-base mb-2 break-all">
                    ${this.escapeHTML(report.scam_wallet_address)}
                </div>

                <p class="text-textMuted text-sm mb-4 line-clamp-2">
                    ${this.escapeHTML(report.description)}
                </p>

                <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center gap-3 md:gap-4">
                        <span class="text-success flex items-center gap-1">
                            <i data-lucide="thumbs-up" class="w-4 h-4"></i>
                            ${report.approve_count}
                        </span>
                        <span class="text-danger flex items-center gap-1">
                            <i data-lucide="thumbs-down" class="w-4 h-4"></i>
                            ${report.reject_count}
                        </span>
                        <span class="text-textMuted flex items-center gap-1">
                            <i data-lucide="message-circle" class="w-4 h-4"></i>
                            ${report.comment_count}
                        </span>
                        <span class="text-textMuted flex items-center gap-1">
                            <i data-lucide="eye" class="w-4 h-4"></i>
                            ${report.view_count}
                        </span>
                    </div>
                    <span class="text-xs text-textMuted hidden sm:block">
                        舉報者: ${this.escapeHTML(report.reporter_wallet_masked)}
                    </span>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('[data-report-idx]').forEach((el, i) => {
            el.addEventListener('click', (() => {
                window.location.href = '/static/scam-tracker/detail.html?id=' +
                    encodeURIComponent(this.reports[i].id);
            }).bind(this));
        });

        lucide.createIcons();
    },

    /**
     * 載入舉報詳情
     */
    async loadReportDetail() {
        try {
            const data = await ScamTrackerAPI.getReportDetail(this.currentReportId);
            this.currentReport = data.report;
            this.renderReportDetail(this.currentReport);
            this.updateVoteButtons(this.currentReport);
        } catch (error) {
            console.error('Load report detail failed:', error);
            const container = document.getElementById('report-detail');
            if (container) {
                container.innerHTML =
                    '<div class="text-center text-danger py-8">載入失敗: ' + this.escapeHTML(error.message) + '</div>';
            }
        }
    },

    /**
     * 渲染舉報詳情
     */
    renderReportDetail(report) {
        const container = document.getElementById('report-detail');
        if (!container) return;

        container.innerHTML = `
            <div class="flex items-center gap-2 mb-4 flex-wrap">
                ${this.getStatusBadge(report.verification_status)}
                ${this.getTypeBadge(report.scam_type)}
                <span class="text-xs text-textMuted ml-auto">${this.formatDate(report.created_at)}</span>
            </div>

            <div class="mb-4">
                <label class="text-xs text-textMuted">可疑錢包地址</label>
                <div class="flex items-center gap-2 bg-background rounded-xl p-3 mt-1">
                    <code class="flex-1 font-mono text-primary text-sm break-all" id="wallet-address-display">${this.escapeHTML(report.scam_wallet_address)}</code>
                    <button onclick="navigator.clipboard.writeText(document.getElementById('wallet-address-display').textContent); showToast('已複製', 'success')"
                        class="text-textMuted hover:text-primary transition flex-shrink-0">
                        <i data-lucide="copy" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            ${report.transaction_hash ? `
            <div class="mb-4">
                <label class="text-xs text-textMuted">交易哈希</label>
                <div class="flex items-center gap-2 bg-background rounded-xl p-3 mt-1">
                    <code class="flex-1 font-mono text-xs text-textMuted break-all" id="tx-hash-display">${this.escapeHTML(report.transaction_hash)}</code>
                    <button onclick="navigator.clipboard.writeText(document.getElementById('tx-hash-display').textContent); showToast('已複製', 'success')"
                        class="text-textMuted hover:text-primary transition flex-shrink-0">
                        <i data-lucide="copy" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
            ` : ''}

            <div class="mb-4">
                <label class="text-xs text-textMuted">詐騙描述</label>
                <div class="bg-background rounded-xl p-4 mt-1 text-textMuted leading-relaxed text-sm">
                    ${this.escapeHTML(report.description).replace(/\n/g, '<br>')}
                </div>
            </div>

            <div class="flex items-center justify-between text-xs text-textMuted border-t border-white/5 pt-4">
                <span>舉報者: ${this.escapeHTML(report.reporter_wallet_masked)}</span>
                <span>查看: ${report.view_count}</span>
            </div>
        `;

        // 更新投票計數
        document.getElementById('count-approve').textContent = report.approve_count;
        document.getElementById('count-reject').textContent = report.reject_count;

        // 更新進度條
        this.updateVoteProgress(report.approve_count, report.reject_count);

        lucide.createIcons();
    },

    /**
     * 更新投票按鈕狀態
     */
    updateVoteButtons(report) {
        const btnApprove = document.getElementById('btn-approve');
        const btnReject = document.getElementById('btn-reject');

        if (!btnApprove || !btnReject) return;

        // 重置按鈕狀態
        btnApprove.classList.remove('ring-2', 'ring-success');
        btnReject.classList.remove('ring-2', 'ring-danger');

        // 設置當前投票狀態
        if (report.viewer_vote === 'approve') {
            btnApprove.classList.add('ring-2', 'ring-success');
        } else if (report.viewer_vote === 'reject') {
            btnReject.classList.add('ring-2', 'ring-danger');
        }
    },

    /**
     * 更新投票進度條
     */
    updateVoteProgress(approve, reject) {
        const total = approve + reject;
        const percentage = total > 0 ? Math.round((approve / total) * 100) : 0;

        document.getElementById('vote-percentage').textContent = percentage + '%';
        document.getElementById('vote-progress-bar').style.width = percentage + '%';

        // 根據進度條顏色
        const progressBar = document.getElementById('vote-progress-bar');
        if (percentage >= 70) {
            progressBar.className = 'h-full bg-success transition-all duration-300';
        } else if (percentage >= 40) {
            progressBar.className = 'h-full bg-warning transition-all duration-300';
        } else {
            progressBar.className = 'h-full bg-danger transition-all duration-300';
        }
    },

    /**
     * 載入評論
     */
    async loadComments() {
        try {
            const data = await ScamTrackerAPI.getComments(this.currentReportId);
            const comments = data.comments || [];
            this.renderComments(comments);

            // 如果用戶是 PRO，顯示評論表單
            const user = resolveScamTrackerCurrentUser();
            if (user && (user.is_premium || user.is_pro)) {
                const commentForm = document.getElementById('comment-form');
                if (commentForm) commentForm.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Load comments failed:', error);
        }
    },

    /**
     * 渲染評論列表
     */
    renderComments(comments) {
        const container = document.getElementById('comments-list');
        if (!container) return;

        if (comments.length === 0) {
            container.innerHTML = '<div class="text-center text-textMuted py-4">暫無評論</div>';
            return;
        }

        container.innerHTML = comments.map(comment => `
            <div class="bg-background rounded-xl p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="font-bold text-secondary text-sm">${this.escapeHTML(comment.username || '匿名')}</span>
                    <span class="text-xs text-textMuted">${this.formatDate(comment.created_at)}</span>
                </div>
                <p class="text-textMuted text-sm">${this.escapeHTML(comment.content).replace(/\n/g, '<br>')}</p>
                ${comment.transaction_hash ? `
                    <div class="mt-2 pt-2 border-t border-white/5">
                        <code class="text-xs text-textMuted font-mono">TX: ${comment.transaction_hash}</code>
                    </div>
                ` : ''}
            </div>
        `).join('');
    },

    /**
     * 綁定列表頁事件
     */
    bindListEvents() {
        // 篩選器變更
        const filterType = document.getElementById('filter-type');
        const filterStatus = document.getElementById('filter-status');
        const sortBy = document.getElementById('sort-by');

        if (filterType) {
            filterType.addEventListener('change', (e) => {
                this.currentFilters.scam_type = e.target.value;
                this.currentFilters.offset = 0;
                this.loadReports();
            });
        }

        if (filterStatus) {
            filterStatus.addEventListener('change', (e) => {
                this.currentFilters.status = e.target.value;
                this.currentFilters.offset = 0;
                this.loadReports();
            });
        }

        if (sortBy) {
            sortBy.addEventListener('change', (e) => {
                this.currentFilters.sort_by = e.target.value;
                this.currentFilters.offset = 0;
                this.loadReports();
            });
        }

        // 搜尋
        const btnSearch = document.getElementById('btn-search');
        const searchWallet = document.getElementById('search-wallet');

        if (btnSearch) {
            btnSearch.addEventListener('click', () => this.handleSearch());
        }
        if (searchWallet) {
            searchWallet.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.handleSearch();
            });
        }

        // 載入更多
        const btnLoadMore = document.getElementById('btn-load-more');
        if (btnLoadMore) {
            btnLoadMore.addEventListener('click', () => {
                this.currentFilters.offset += this.currentFilters.limit;
                this.loadReports(true);
            });
        }

        // 舉報按鈕
        const btnSubmit = document.getElementById('btn-submit-report');
        if (btnSubmit) {
            btnSubmit.addEventListener('click', () => {
                window.location.href = '/static/scam-tracker/submit.html';
            });
        }
    },

    /**
     * 綁定詳情頁事件
     */
    bindDetailEvents() {
        // 投票按鈕
        const btnApprove = document.getElementById('btn-approve');
        const btnReject = document.getElementById('btn-reject');

        if (btnApprove) {
            btnApprove.addEventListener('click', () => this.handleVote('approve'));
        }
        if (btnReject) {
            btnReject.addEventListener('click', () => this.handleVote('reject'));
        }

        // 提交評論
        const btnSubmitComment = document.getElementById('btn-submit-comment');
        if (btnSubmitComment) {
            btnSubmitComment.addEventListener('click', () => this.handleSubmitComment());
        }
    },

    /**
     * 綁定提交頁事件
     */
    bindSubmitEvents() {
        const form = document.getElementById('scam-report-form');
        const description = document.getElementById('description');
        const charCount = document.getElementById('char-count');

        if (description && charCount) {
            description.addEventListener('input', () => {
                charCount.textContent = description.value.length;
            });
        }

        if (form) {
            form.addEventListener('submit', (e) => this.handleSubmitReport(e));
        }
    },

    /**
     * 處理搜尋
     */
    async handleSearch() {
        const input = document.getElementById('search-wallet');
        if (!input) return;

        const address = input.value.trim();

        if (!address) {
            showToast('請輸入錢包地址', 'warning');
            return;
        }

        if (!/^G[A-Z234567]{55}$/.test(address)) {
            showToast('地址格式錯誤（需 G 開頭，56 字元，僅 A-Z 及 2-7）', 'error');
            return;
        }

        try {
            const data = await ScamTrackerAPI.searchWallet(address);
            if (data.found && data.report) {
                window.location.href = `/static/scam-tracker/detail.html?id=${data.report.id}`;
            } else {
                showToast('該地址尚未被舉報', 'info');
            }
        } catch (error) {
            console.error('Search failed:', error);
            showToast('搜尋失敗', 'error');
        }
    },

    /**
     * 處理投票
     */
    async handleVote(voteType) {
        try {
            const result = await ScamTrackerAPI.vote(this.currentReportId, voteType);
            const actionMessages = {
                'voted': `已${voteType === 'approve' ? '贊同' : '反對'}`,
                'cancelled': `已取消${voteType === 'approve' ? '贊同' : '反對'}`,
                'switched': `已切換為${voteType === 'approve' ? '贊同' : '反對'}`
            };
            showToast(actionMessages[result.action] || '投票成功', 'success');
            this.loadReportDetail();
        } catch (error) {
            console.error('Vote failed:', error);
            showToast(error.message || '投票失敗', 'error');
        }
    },

    /**
     * 處理提交評論
     */
    async handleSubmitComment() {
        const contentInput = document.getElementById('comment-content');
        const txHashInput = document.getElementById('comment-tx-hash');

        const content = contentInput.value.trim();
        const txHash = txHashInput.value.trim();

        if (!content || content.length < 10) {
            showToast('評論內容至少 10 字', 'warning');
            return;
        }

        try {
            await ScamTrackerAPI.addComment(this.currentReportId, content, txHash || null);
            showToast('評論添加成功', 'success');
            contentInput.value = '';
            txHashInput.value = '';
            this.loadComments();
            this.loadReportDetail();
        } catch (error) {
            console.error('Add comment failed:', error);
            showToast(error.message || '添加評論失敗', 'error');
        }
    },

    /**
     * 處理提交舉報
     */
    async handleSubmitReport(e) {
        e.preventDefault();

        const scamWallet = document.getElementById('scam-wallet').value.trim().toUpperCase();
        const reporterWallet = document.getElementById('reporter-wallet').value.trim().toUpperCase();
        const scamType = document.getElementById('scam-type').value;
        const description = document.getElementById('description').value.trim();
        const txHash = document.getElementById('tx-hash').value.trim().toLowerCase();

        // 驗證
        if (!/^G[A-Z234567]{55}$/.test(scamWallet)) {
            showToast('可疑錢包地址格式錯誤（需 G 開頭，56 字元，僅 A-Z 及 2-7）', 'error');
            return;
        }
        if (!/^G[A-Z234567]{55}$/.test(reporterWallet)) {
            showToast('您的錢包地址格式錯誤（需 G 開頭，56 字元，僅 A-Z 及 2-7）', 'error');
            return;
        }
        if (!scamType) {
            showToast('請選擇詐騙類型', 'warning');
            return;
        }
        if (description.length < 20 || description.length > 2000) {
            showToast('描述長度必須在 20-2000 字之間', 'error');
            return;
        }
        if (txHash && !/^[a-f0-9]{64}$/.test(txHash)) {
            showToast('交易哈希格式錯誤（需 64 位十六進制字元）', 'error');
            return;
        }

        const btnSubmit = document.getElementById('btn-submit');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> 提交中...';
        lucide.createIcons();

        try {
            const result = await ScamTrackerAPI.submitReport({
                scam_wallet_address: scamWallet,
                reporter_wallet_address: reporterWallet,
                scam_type: scamType,
                description: description,
                transaction_hash: txHash || null
            });

            showToast('舉報提交成功！', 'success');
            setTimeout(() => {
                window.location.href = `/static/scam-tracker/detail.html?id=${result.report_id}`;
            }, 1000);
        } catch (error) {
            console.error('Submit report failed:', error);
            showToast(error.message || '提交失敗', 'error');
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = '<i data-lucide="send" class="w-5 h-5"></i> 提交舉報';
            lucide.createIcons();
        }
    },

    /**
     * 工具函數
     */
    getStatusBadge(status) {
        const badges = {
            'verified': '<span class="bg-success/20 text-success px-2 py-0.5 rounded text-xs font-bold">✅ 已驗證</span>',
            'pending': '<span class="bg-warning/20 text-warning px-2 py-0.5 rounded text-xs font-bold">⏳ 待驗證</span>',
            'disputed': '<span class="bg-danger/20 text-danger px-2 py-0.5 rounded text-xs font-bold">⚠️ 有爭議</span>'
        };
        return badges[status] || badges.pending;
    },

    getTypeBadge(type) {
        const typeObj = this.scamTypes.find(t => t.id === type);
        const name = typeObj ? `${typeObj.icon} ${typeObj.name}` : type;
        return `<span class="bg-primary/10 text-primary px-2 py-0.5 rounded text-xs font-bold">${name}</span>`;
    },

    formatDate(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return '剛剛';
        if (diffMins < 60) return `${diffMins} 分鐘前`;

        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours} 小時前`;

        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return `${diffDays} 天前`;

        return date.toLocaleDateString('zh-TW');
    },

    escapeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

// Expose to global scope for cross-module access (e.g. safetyTab.js, scam-tracker-i18n.js)
window.ScamTrackerAPI = ScamTrackerAPI;
