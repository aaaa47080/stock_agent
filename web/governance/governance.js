/**
 * 社群治理系統前端邏輯
 */

// API 基礎路徑
const API_BASE = '/api/governance';

// 當前用戶信息
let currentUser = null;
let isProMember = false;

// ============================================
// 初始化
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // 標籤切換
    setupTabs();

    // 檢舉表單
    setupReportForm();

    // 檢查用戶登入狀態
    checkAuthStatus();

    // 模態框關閉
    setupModal();
});

// ============================================
// 標籤切換
// ============================================

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.dataset.tab;

            // 更新按鈕狀態
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');

            // 更新內容顯示
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${tabName}-tab`) {
                    content.classList.add('active');

                    // 載入相應數據
                    loadTabData(tabName);
                }
            });
        });
    });
}

function switchTab(tabName) {
    const tabButton = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (tabButton) {
        tabButton.click();
    }
}

// ============================================
// 用戶認證
// ============================================

async function checkAuthStatus() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        showToast('請先登入', 'error');
        return;
    }

    try {
        const response = await fetch('/api/user/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            currentUser = data;
            isProMember = data.is_pro || false;

            // 更新 UI
            updateUIForUser();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

function updateUIForUser() {
    // 更新 PRO 專用內容
    if (isProMember) {
        document.getElementById('pro-notice').style.display = 'none';
        document.getElementById('review-content').style.display = 'block';
    }

    // 載入每日限制
    loadDailyLimit();
}

// ============================================
// 檢舉表單
// ============================================

function setupReportForm() {
    const form = document.getElementById('report-form');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (!currentUser) {
            showToast('請先登入', 'error');
            return;
        }

        const formData = new FormData(form);
        const data = {
            content_type: formData.get('content_type'),
            content_id: parseInt(formData.get('content_id')),
            report_type: formData.get('report_type'),
            description: formData.get('description') || null
        };

        // 驗證
        if (!data.content_type || !data.content_id || !data.report_type) {
            showToast('請填寫所有必填欄位', 'error');
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/reports`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {
                showToast('檢舉提交成功！', 'success');
                form.reset();
                loadDailyLimit();
            } else {
                showToast(result.detail || '提交失敗', 'error');
            }
        } catch (error) {
            console.error('Submit report error:', error);
            showToast('提交失敗，請稍後再試', 'error');
        }
    });
}

async function loadDailyLimit() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/reports`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const todayReports = data.reports ? data.reports.filter(r => {
                const reportDate = new Date(r.created_at).toDateString();
                const today = new Date().toDateString();
                return reportDate === today;
            }).length : 0;

            const limit = isProMember ? 10 : 5;
            const remaining = limit - todayReports;

            document.getElementById('daily-limit').textContent =
                `今日剩餘：${remaining} / ${limit}`;
        }
    } catch (error) {
        console.error('Load daily limit error:', error);
    }
}

// ============================================
// 標籤數據載入
// ============================================

async function loadTabData(tabName) {
    switch(tabName) {
        case 'review':
            await loadPendingReports();
            await loadMyReputation();
            break;
        case 'my-reports':
            await loadMyReports();
            break;
        case 'violations':
            await loadViolationPoints();
            break;
        case 'leaderboard':
            await loadLeaderboard();
            break;
    }
}

// ============================================
// 審核隊列
// ============================================

async function loadPendingReports() {
    const listElement = document.getElementById('pending-reports-list');
    const loadingElement = document.getElementById('review-loading');
    const emptyElement = document.getElementById('review-empty');

    loadingElement.style.display = 'block';
    listElement.innerHTML = '';
    emptyElement.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/reports/pending`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const reports = data.reports || [];

            loadingElement.style.display = 'none';

            if (reports.length === 0) {
                emptyElement.style.display = 'block';
                return;
            }

            reports.forEach(report => {
                const reportElement = createReportElement(report, true);
                listElement.appendChild(reportElement);
            });
        } else {
            const result = await response.json();
            if (result.detail && result.detail.includes('PRO')) {
                document.getElementById('pro-notice').style.display = 'block';
                document.getElementById('review-content').style.display = 'none';
            }
            loadingElement.style.display = 'none';
        }
    } catch (error) {
        console.error('Load pending reports error:', error);
        loadingElement.style.display = 'none';
        showToast('載入失敗', 'error');
    }
}

function createReportElement(report, showVoteButtons = false) {
    const div = document.createElement('div');
    div.className = 'report-item';
    div.dataset.reportId = report.id;

    const typeLabels = {
        spam: '垃圾信息',
        harassment: '騷擾',
        misinformation: '虛假信息',
        scam: '詐騙',
        illegal: '違法內容',
        other: '其他'
    };

    let html = `
        <div class="report-header">
            <span class="report-id">#${report.id}</span>
            <span class="report-status status-${report.review_status}">
                ${getStatusText(report.review_status)}
            </span>
        </div>
        <div class="report-content">
            <div class="report-icon">📋</div>
            <div class="report-details">
                <span class="report-type">${typeLabels[report.report_type] || report.report_type}</span>
                ${report.description ? `<p class="report-description">${escapeHtml(report.description)}</p>` : ''}
                <div class="report-meta">
                    <span>${report.content_type === 'post' ? '文章' : '評論'} #${report.content_id}</span>
                    <span>${formatDate(report.created_at)}</span>
                    ${showVoteButtons ? `
                        <span>👍 ${report.approve_count || 0} / 👎 ${report.reject_count || 0}</span>
                    ` : ''}
                </div>
            </div>
        </div>
    `;

    if (showVoteButtons && report.review_status === 'pending') {
        html += `
            <div class="vote-section">
                <div class="vote-buttons">
                    <button class="vote-btn approve" onclick="voteOnReport(${report.id}, 'approve')">
                        👍 認為違規
                    </button>
                    <button class="vote-btn reject" onclick="voteOnReport(${report.id}, 'reject')">
                        👎 認為不違規
                    </button>
                </div>
            </div>
        `;
    }

    div.innerHTML = html;
    return div;
}

async function voteOnReport(reportId, voteType) {
    try {
        const response = await fetch(`${API_BASE}/reports/${reportId}/vote`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({ vote_type: voteType })
        });

        const result = await response.json();

        if (response.ok) {
            showToast(result.message || '投票成功', 'success');

            // 如果達成共識，顯示提示
            if (result.consensus_reached) {
                showToast(result.consensus_message || '已達成共識', 'info');
            }

            // 重新載入列表
            loadPendingReports();
        } else {
            showToast(result.detail || '投票失敗', 'error');
        }
    } catch (error) {
        console.error('Vote error:', error);
        showToast('投票失敗', 'error');
    }
}

// ============================================
// 我的檢舉
// ============================================

async function loadMyReports(status = 'all') {
    const listElement = document.getElementById('my-reports-list');
    const loadingElement = document.getElementById('my-reports-loading');
    const emptyElement = document.getElementById('my-reports-empty');

    loadingElement.style.display = 'block';
    listElement.innerHTML = '';
    emptyElement.style.display = 'none';

    try {
        const url = status === 'all' ? `${API_BASE}/reports` : `${API_BASE}/reports?status=${status}`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const reports = data.reports || [];

            loadingElement.style.display = 'none';

            if (reports.length === 0) {
                emptyElement.style.display = 'block';
                return;
            }

            reports.forEach(report => {
                const reportElement = createReportElement(report);
                listElement.appendChild(reportElement);
            });
        } else {
            loadingElement.style.display = 'none';
        }
    } catch (error) {
        console.error('Load my reports error:', error);
        loadingElement.style.display = 'none';
        showToast('載入失敗', 'error');
    }
}

// 篩選按鈕
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('filter-btn')) {
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        e.target.classList.add('active');
        loadMyReports(e.target.dataset.status);
    }
});

// ============================================
// 違規記錄
// ============================================

async function loadViolationPoints() {
    const pointsElement = document.getElementById('violation-points');
    const listElement = document.getElementById('violations-list');
    const loadingElement = document.getElementById('violations-loading');

    loadingElement.style.display = 'true';

    try {
        const response = await fetch(`${API_BASE}/violations`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const points = data.points || {};
            const violations = data.recent_violations || [];

            // 顯示點數摘要
            pointsElement.innerHTML = `
                <div class="points-summary">
                    <div class="points-header">
                        <div>
                            <div class="points-value">${points.points || 0}</div>
                            <div class="points-label">違規點數</div>
                        </div>
                    </div>
                    <div class="points-actions">
                        <div class="points-action">
                            <div class="points-action-value">${points.total_violations || 0}</div>
                            <div class="points-action-label">總違規次數</div>
                        </div>
                        <div class="points-action">
                            <div class="points-action-value">${points.suspension_count || 0}</div>
                            <div class="points-action-label">被暫停次數</div>
                        </div>
                    </div>
                </div>
            `;

            // 顯示違規列表
            listElement.innerHTML = '';
            if (violations.length === 0) {
                listElement.innerHTML = '<p class="empty-state">✅ 沒有違規記錄</p>';
            } else {
                violations.forEach(violation => {
                    const violationElement = createViolationElement(violation);
                    listElement.appendChild(violationElement);
                });
            }
        }

        loadingElement.style.display = 'none';
    } catch (error) {
        console.error('Load violation points error:', error);
        loadingElement.style.display = 'none';
        showToast('載入失敗', 'error');
    }
}

function createViolationElement(violation) {
    const div = document.createElement('div');
    div.className = 'violation-item';

    const levelLabels = {
        mild: '輕微',
        medium: '中等',
        severe: '嚴重',
        critical: '極嚴重'
    };

    const typeLabels = {
        spam: '垃圾信息',
        harassment: '騷擾',
        misinformation: '虛假信息',
        scam: '詐騙',
        illegal: '違法內容',
        other: '其他'
    };

    div.innerHTML = `
        <span class="violation-level level-${violation.violation_level}">
            ${levelLabels[violation.violation_level] || violation.violation_level}
        </span>
        <div class="violation-details">
            <div class="violation-type">
                ${typeLabels[violation.violation_type] || violation.violation_type} - ${violation.points} 點
            </div>
            <div class="violation-meta">
                ${formatDate(violation.created_at)}
                ${violation.action_taken ? `· ${getActionText(violation.action_taken)}` : ''}
            </div>
        </div>
    `;

    return div;
}

// ============================================
// 排行榜
// ============================================

async function loadLeaderboard() {
    const listElement = document.getElementById('leaderboard-list');
    const loadingElement = document.getElementById('leaderboard-loading');

    loadingElement.style.display = 'block';
    listElement.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE}/reviewers/leaderboard`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const reviewers = data.leaderboard || [];

            loadingElement.style.display = 'none';

            reviewers.forEach((reviewer, index) => {
                const reviewerElement = createLeaderboardItem(reviewer, index + 1);
                listElement.appendChild(reviewerElement);
            });
        } else {
            loadingElement.style.display = 'none';
        }
    } catch (error) {
        console.error('Load leaderboard error:', error);
        loadingElement.style.display = 'none';
        showToast('載入失敗', 'error');
    }
}

function createLeaderboardItem(reviewer, rank) {
    const div = document.createElement('div');
    div.className = 'leaderboard-item';

    const rankClass = rank <= 3 ? `rank-${rank}` : '';

    div.innerHTML = `
        <div class="leaderboard-rank ${rankClass}">${rank}</div>
        <div class="leaderboard-avatar">
            ${reviewer.username ? reviewer.username.charAt(0).toUpperCase() : '?'}
        </div>
        <div class="leaderboard-info">
            <div class="leaderboard-name">${escapeHtml(reviewer.username || '匿名用戶')}</div>
            <div class="leaderboard-stats">
                審核 ${reviewer.total_reviews} 次 · 正確率 ${(reviewer.accuracy_rate * 100).toFixed(1)}%
            </div>
        </div>
        <div class="leaderboard-score">
            <div class="reputation-score">${reviewer.reputation_score}</div>
            <div class="accuracy-rate">聲望分</div>
        </div>
    `;

    return div;
}

// ============================================
// 聲望信息
// ============================================

async function loadMyReputation() {
    const reputationElement = document.getElementById('my-reputation');

    try {
        const response = await fetch(`${API_BASE}/reputation`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            const reputation = data.reputation || {};

            reputationElement.innerHTML = `
                <div class="reputation-display">
                    <div class="reputation-stat">
                        <div class="reputation-value">${reputation.total_reviews || 0}</div>
                        <div class="reputation-label">審核次數</div>
                    </div>
                    <div class="reputation-stat">
                        <div class="reputation-value">${reputation.correct_votes || 0}</div>
                        <div class="reputation-label">正確投票</div>
                    </div>
                    <div class="reputation-stat">
                        <div class="reputation-value">${(reputation.accuracy_rate * 100).toFixed(1)}%</div>
                        <div class="reputation-label">準確率</div>
                    </div>
                    <div class="reputation-stat">
                        <div class="reputation-value">${reputation.reputation_score || 0}</div>
                        <div class="reputation-label">聲望分</div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Load reputation error:', error);
    }
}

// ============================================
// 工具函數
// ============================================

function getStatusText(status) {
    const statusMap = {
        pending: '待審核',
        approved: '已通過',
        rejected: '已拒絕'
    };
    return statusMap[status] || status;
}

function getActionText(action) {
    const actionMap = {
        warning: '警告',
        suspend_3d: '暫停3天',
        suspend_7d: '暫停7天',
        suspend_30d: '暫停30天',
        permanent_ban: '永久停權'
    };
    return actionMap[action] || action;
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '剛剛';
    if (minutes < 60) return `${minutes} 分鐘前`;
    if (hours < 24) return `${hours} 小時前`;
    if (days < 7) return `${days} 天前`;

    return date.toLocaleDateString('zh-TW');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// 訊息提示
// ============================================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ============================================
// 模態框
// ============================================

function setupModal() {
    const modal = document.getElementById('report-detail-modal');
    const closeBtn = modal.querySelector('.close-btn');

    closeBtn.addEventListener('click', () => {
        modal.classList.remove('show');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
        }
    });
}

function showReportDetail(reportId) {
    // TODO: 實現檢舉詳情顯示
    const modal = document.getElementById('report-detail-modal');
    const content = document.getElementById('report-detail-content');

    content.innerHTML = '<p>載入中...</p>';
    modal.classList.add('show');

    // 載入詳情數據
    fetch(`${API_BASE}/reports/${reportId}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 顯示詳情
        }
    })
    .catch(error => {
        console.error('Load report detail error:', error);
        content.innerHTML = '<p>載入失敗</p>';
    });
}
