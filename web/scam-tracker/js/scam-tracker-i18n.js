(function () {
    'use strict';

    function t(key, options) {
        return window.I18n ? window.I18n.t(key, options) : key;
    }

    function getLang() {
        return window.I18n ? window.I18n.getLanguage() : 'en';
    }

    function escapeHtml(value) {
        if (value === null || value === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(value);
        return div.innerHTML;
    }

    function formatDate(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return t('time.justNow');
        if (diffMins < 60) return t('time.minutesAgo', { count: diffMins });

        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return t('time.hoursAgo', { count: diffHours });

        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 7) return t('time.daysAgo', { count: diffDays });

        return date.toLocaleDateString(getLang() === 'zh-TW' ? 'zh-TW' : 'en-US');
    }

    function fallbackTypes() {
        if (getLang() === 'zh-TW') {
            return [
                { id: 'fake_official', name: '假冒官方', icon: '🎭' },
                { id: 'investment_scam', name: '投資詐騙', icon: '💰' },
                { id: 'fake_airdrop', name: '空投詐騙', icon: '🎁' },
                { id: 'trading_fraud', name: '交易詐騙', icon: '🔄' },
                { id: 'gambling', name: '賭博騙局', icon: '🎰' },
                { id: 'phishing', name: '釣魚網站', icon: '🎣' },
                { id: 'other', name: '其他詐騙', icon: '⚠️' },
            ];
        }

        return [
            { id: 'fake_official', name: 'Fake Official', icon: '🎭' },
            { id: 'investment_scam', name: 'Investment Scam', icon: '💰' },
            { id: 'fake_airdrop', name: 'Fake Airdrop', icon: '🎁' },
            { id: 'trading_fraud', name: 'Trading Fraud', icon: '🔄' },
            { id: 'gambling', name: 'Gambling Scam', icon: '🎰' },
            { id: 'phishing', name: 'Phishing Site', icon: '🎣' },
            { id: 'other', name: 'Other Scam', icon: '⚠️' },
        ];
    }

    function setLangToggleLabel() {
        const el = document.getElementById('lang-toggle-label');
        if (el) el.textContent = t('safety.languageToggle');
    }

    window.toggleScamLanguage = async function toggleScamLanguage() {
        if (!window.I18n) return;
        await window.I18n.changeLanguage(getLang() === 'zh-TW' ? 'en' : 'zh-TW');
    };

    window.copyScamTrackerText = function copyScamTrackerText(elementId) {
        const el = document.getElementById(elementId);
        if (!el) return;
        navigator.clipboard.writeText(el.textContent || '');
        window.showToast?.(t('safety.copySuccess'), 'success');
    };

    function patchApp() {
        const app = window.ScamTrackerApp;
        if (!app) return false;

        app.formatDate = formatDate;

        app.getStatusBadge = function getStatusBadge(status) {
            const map = {
                verified: {
                    label: t('safety.statusVerified'),
                    classes: 'bg-success/20 text-success',
                    icon: '✅',
                },
                pending: {
                    label: t('safety.statusPending'),
                    classes: 'bg-warning/20 text-warning',
                    icon: '⏳',
                },
                disputed: {
                    label: t('safety.statusDisputed'),
                    classes: 'bg-danger/20 text-danger',
                    icon: '⚠️',
                },
            };
            const item = map[status] || map.pending;
            return `<span class="${item.classes} px-2 py-0.5 rounded text-xs font-bold">${item.icon} ${item.label}</span>`;
        };

        app.getTypeBadge = function getTypeBadge(type) {
            const match = (this.scamTypes || []).find((item) => item.id === type);
            const label = match ? `${match.icon} ${match.name}` : type;
            return `<span class="bg-primary/10 text-primary px-2 py-0.5 rounded text-xs font-bold">${escapeHtml(label)}</span>`;
        };

        app.loadScamTypes = async function loadScamTypesPatched() {
            try {
                const config = await window.ScamTrackerAPI.getConfig();
                this.scamTypes = config.scam_types?.length ? config.scam_types : fallbackTypes();
            } catch (error) {
                this.scamTypes = fallbackTypes();
            }

            const localizedFallbacks = fallbackTypes();
            this.scamTypes = this.scamTypes.map((type) => {
                const localized = localizedFallbacks.find((item) => item.id === type.id);
                return localized ? { ...type, name: localized.name, icon: type.icon || localized.icon } : type;
            });

            const filterSelect = document.getElementById('filter-type');
            if (filterSelect) {
                filterSelect.innerHTML = `<option value="">${t('safety.filters.allTypes')}</option>`;
                this.scamTypes.forEach((type) => {
                    const option = document.createElement('option');
                    option.value = type.id;
                    option.textContent = `${type.icon} ${type.name}`;
                    filterSelect.appendChild(option);
                });
                filterSelect.value = this.currentFilters?.scam_type || '';
            }

            const submitSelect = document.getElementById('scam-type');
            if (submitSelect) {
                submitSelect.innerHTML = `<option value="">${t('safety.selectScamType')}</option>`;
                this.scamTypes.forEach((type) => {
                    const option = document.createElement('option');
                    option.value = type.id;
                    option.textContent = `${type.icon} ${type.name}`;
                    submitSelect.appendChild(option);
                });
            }
        };

        app.renderReports = function renderReportsPatched() {
            const container = document.getElementById('report-list');
            if (!container) return;

            if (!this.reports || this.reports.length === 0) {
                container.innerHTML = `<div class="text-center text-textMuted py-8">${t('safety.noReports')}</div>`;
                return;
            }

            container.innerHTML = this.reports
                .map(
                    (report) => `
                        <div class="bg-surface border border-white/5 rounded-2xl p-5 hover:border-primary/30 transition cursor-pointer"
                            onclick="window.location.href='/static/scam-tracker/detail.html?id=${report.id}'">
                            <div class="flex items-start justify-between mb-3">
                                <div class="flex items-center gap-2 flex-wrap">
                                    ${this.getStatusBadge(report.verification_status)}
                                    ${this.getTypeBadge(report.scam_type)}
                                </div>
                                <span class="text-xs text-textMuted">${formatDate(report.created_at)}</span>
                            </div>
                            <div class="font-mono text-primary text-sm md:text-base mb-2 break-all">${escapeHtml(report.scam_wallet_address)}</div>
                            <p class="text-textMuted text-sm mb-4 line-clamp-2">${escapeHtml(report.description)}</p>
                            <div class="flex items-center justify-between text-sm">
                                <div class="flex items-center gap-3 md:gap-4">
                                    <span class="text-success flex items-center gap-1"><i data-lucide="thumbs-up" class="w-4 h-4"></i>${report.approve_count}</span>
                                    <span class="text-danger flex items-center gap-1"><i data-lucide="thumbs-down" class="w-4 h-4"></i>${report.reject_count}</span>
                                    <span class="text-textMuted flex items-center gap-1"><i data-lucide="message-circle" class="w-4 h-4"></i>${report.comment_count}</span>
                                    <span class="text-textMuted flex items-center gap-1"><i data-lucide="eye" class="w-4 h-4"></i>${report.view_count}</span>
                                </div>
                                <span class="text-xs text-textMuted hidden sm:block">${t('safety.reporter')}: ${escapeHtml(report.reporter_wallet_masked)}</span>
                            </div>
                        </div>
                    `
                )
                .join('');

            window.lucide?.createIcons();
        };

        app.renderReportDetail = function renderReportDetailPatched(report) {
            const container = document.getElementById('report-detail');
            if (!container) return;

            container.innerHTML = `
                <div class="flex items-center gap-2 mb-4 flex-wrap">
                    ${this.getStatusBadge(report.verification_status)}
                    ${this.getTypeBadge(report.scam_type)}
                    <span class="text-xs text-textMuted ml-auto">${formatDate(report.created_at)}</span>
                </div>
                <div class="mb-4">
                    <label class="text-xs text-textMuted">${t('safety.suspiciousWallet')}</label>
                    <div class="flex items-center gap-2 bg-background rounded-xl p-3 mt-1">
                        <code class="flex-1 font-mono text-primary text-sm break-all" id="wallet-address-display">${escapeHtml(report.scam_wallet_address)}</code>
                        <button onclick="copyScamTrackerText('wallet-address-display')" class="text-textMuted hover:text-primary transition flex-shrink-0">
                            <i data-lucide="copy" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
                ${
                    report.transaction_hash
                        ? `
                            <div class="mb-4">
                                <label class="text-xs text-textMuted">${t('safety.transactionHash')}</label>
                                <div class="flex items-center gap-2 bg-background rounded-xl p-3 mt-1">
                                    <code class="flex-1 font-mono text-xs text-textMuted break-all" id="tx-hash-display">${escapeHtml(report.transaction_hash)}</code>
                                    <button onclick="copyScamTrackerText('tx-hash-display')" class="text-textMuted hover:text-primary transition flex-shrink-0">
                                        <i data-lucide="copy" class="w-4 h-4"></i>
                                    </button>
                                </div>
                            </div>
                        `
                        : ''
                }
                <div class="mb-4">
                    <label class="text-xs text-textMuted">${t('safety.scamDescription')}</label>
                    <div class="bg-background rounded-xl p-4 mt-1 text-textMuted leading-relaxed text-sm">
                        ${escapeHtml(report.description).replace(/\n/g, '<br>')}
                    </div>
                </div>
                <div class="flex items-center justify-between text-xs text-textMuted border-t border-white/5 pt-4">
                    <span>${t('safety.reporter')}: ${escapeHtml(report.reporter_wallet_masked)}</span>
                    <span>${t('safety.views')}: ${report.view_count}</span>
                </div>
            `;

            document.getElementById('count-approve').textContent = report.approve_count;
            document.getElementById('count-reject').textContent = report.reject_count;
            this.updateVoteProgress(report.approve_count, report.reject_count);
            window.lucide?.createIcons();
        };

        app.renderComments = function renderCommentsPatched(comments) {
            const container = document.getElementById('comments-list');
            if (!container) return;

            if (!comments || comments.length === 0) {
                container.innerHTML = `<div class="text-center text-textMuted py-4">${t('safety.noComments')}</div>`;
                return;
            }

            container.innerHTML = comments
                .map(
                    (comment) => `
                        <div class="bg-background rounded-xl p-4">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-bold text-secondary text-sm">${escapeHtml(comment.username || t('safety.anonymous'))}</span>
                                <span class="text-xs text-textMuted">${formatDate(comment.created_at)}</span>
                            </div>
                            <p class="text-textMuted text-sm">${escapeHtml(comment.content).replace(/\n/g, '<br>')}</p>
                            ${
                                comment.transaction_hash
                                    ? `<div class="mt-2 pt-2 border-t border-white/5"><code class="text-xs text-textMuted font-mono">TX: ${escapeHtml(comment.transaction_hash)}</code></div>`
                                    : ''
                            }
                        </div>
                    `
                )
                .join('');
        };

        app.handleSearch = async function handleSearchPatched() {
            const input = document.getElementById('search-wallet');
            if (!input) return;
            const address = input.value.trim().toUpperCase();

            if (!address) {
                window.showToast?.(t('safety.searchEmpty'), 'warning');
                return;
            }
            if (!/^G[A-Z234567]{55}$/.test(address)) {
                window.showToast?.(t('safety.invalidWalletFormat'), 'error');
                return;
            }

            try {
                const data = await window.ScamTrackerAPI.searchWallet(address);
                if (data.found && data.report) {
                    window.location.href = `/static/scam-tracker/detail.html?id=${data.report.id}`;
                    return;
                }
                window.showToast?.(t('safety.walletNotReported'), 'info');
            } catch (error) {
                window.showToast?.(t('safety.searchFailed'), 'error');
            }
        };

        app.handleVote = async function handleVotePatched(voteType) {
            try {
                const result = await window.ScamTrackerAPI.vote(this.currentReportId, voteType);
                const messages = {
                    voted: voteType === 'approve' ? t('safety.voteSuccessApprove') : t('safety.voteSuccessReject'),
                    cancelled:
                        voteType === 'approve'
                            ? t('safety.voteCancelledApprove')
                            : t('safety.voteCancelledReject'),
                    switched:
                        voteType === 'approve'
                            ? t('safety.voteSwitchedApprove')
                            : t('safety.voteSwitchedReject'),
                };
                window.showToast?.(messages[result.action] || t('safety.voteFailed'), 'success');
                this.loadReportDetail();
            } catch (error) {
                window.showToast?.(error.message || t('safety.voteFailed'), 'error');
            }
        };

        app.handleSubmitComment = async function handleSubmitCommentPatched() {
            const contentInput = document.getElementById('comment-content');
            const txHashInput = document.getElementById('comment-tx-hash');
            if (!contentInput || !txHashInput) return;

            const content = contentInput.value.trim();
            const txHash = txHashInput.value.trim();
            if (!content || content.length < 10) {
                window.showToast?.(t('safety.commentMinLength'), 'warning');
                return;
            }

            try {
                await window.ScamTrackerAPI.addComment(this.currentReportId, content, txHash || null);
                window.showToast?.(t('safety.commentSuccess'), 'success');
                contentInput.value = '';
                txHashInput.value = '';
                this.loadComments();
                this.loadReportDetail();
            } catch (error) {
                window.showToast?.(error.message || t('safety.commentFailed'), 'error');
            }
        };

        app.handleSubmitReport = async function handleSubmitReportPatched(event) {
            event.preventDefault();

            const scamWallet = document.getElementById('scam-wallet').value.trim().toUpperCase();
            const reporterWallet = document.getElementById('reporter-wallet').value.trim().toUpperCase();
            const scamType = document.getElementById('scam-type').value;
            const description = document.getElementById('description').value.trim();
            const txHash = document.getElementById('tx-hash').value.trim().toLowerCase();

            if (!/^G[A-Z234567]{55}$/.test(scamWallet)) {
                window.showToast?.(t('safety.invalidWalletFormat'), 'error');
                return;
            }
            if (!/^G[A-Z234567]{55}$/.test(reporterWallet)) {
                window.showToast?.(t('safety.invalidReporterWalletFormat'), 'error');
                return;
            }
            if (!scamType) {
                window.showToast?.(t('safety.selectScamType'), 'warning');
                return;
            }
            if (description.length < 20 || description.length > 2000) {
                window.showToast?.(t('safety.descriptionLength'), 'error');
                return;
            }
            if (txHash && !/^[a-f0-9]{64}$/.test(txHash)) {
                window.showToast?.(t('safety.invalidTxHash'), 'error');
                return;
            }

            const btnSubmit = document.getElementById('btn-submit');
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i>${t('safety.submitting')}`;
            window.lucide?.createIcons();

            try {
                const result = await window.ScamTrackerAPI.submitReport({
                    scam_wallet_address: scamWallet,
                    reporter_wallet_address: reporterWallet,
                    scam_type: scamType,
                    description,
                    transaction_hash: txHash || null,
                });
                window.showToast?.(t('safety.reportSuccess'), 'success');
                setTimeout(() => {
                    window.location.href = `/static/scam-tracker/detail.html?id=${result.report_id}`;
                }, 1000);
            } catch (error) {
                window.showToast?.(error.message || t('safety.reportFailed'), 'error');
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = `<i data-lucide="send" class="w-5 h-5"></i>${t('safety.submitButton')}`;
                window.lucide?.createIcons();
            }
        };

        const originalCheckPROStatus = app.checkPROStatus?.bind(app);
        app.checkPROStatus = function checkPROStatusPatched() {
            originalCheckPROStatus?.();
            const quota = document.getElementById('daily-limit-copy');
            if (quota) quota.textContent = t('safety.dailyQuota', { count: '5' });
        };

        return true;
    }

    function refreshDynamicUi() {
        setLangToggleLabel();

        const page = document.body.dataset.page;
        const base = t('safety.trackerTitle');
        if (page === 'scam-detail') document.title = `${t('safety.reportDetail')} - ${base}`;
        if (page === 'scam-submit') document.title = `${t('safety.reportSubmitTitle')} - ${base}`;
        if (page === 'scam-list') document.title = `${base} - Pi Crypto Forum`;

        const app = window.ScamTrackerApp;
        if (!app) return;
        app.loadScamTypes?.();
        if (page === 'scam-list' && app.reports?.length) app.renderReports?.();
        if (page === 'scam-detail' && app.currentReport) {
            app.renderReportDetail?.(app.currentReport);
            if (Array.isArray(app.comments)) app.renderComments?.(app.comments);
        }
        if (page === 'scam-submit') {
            const quota = document.getElementById('daily-limit-copy');
            if (quota) quota.textContent = t('safety.dailyQuota', { count: '5' });
        }
    }

    if (!patchApp()) {
        const timer = setInterval(() => {
            if (patchApp()) {
                clearInterval(timer);
                refreshDynamicUi();
            }
        }, 100);
    } else {
        refreshDynamicUi();
    }

    window.addEventListener('languageChanged', refreshDynamicUi);
})();
