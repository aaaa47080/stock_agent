// ========================================
// admin-stats.js - Statistics Dashboard (P2)
// ========================================

const AdminStatsManager = {
    charts: {},
    currentRange: 30,

    render() {
        const container = document.getElementById('admin-subpage-content');
        if (!container) return;

        container.innerHTML = `
            <!-- Time Range Selector -->
            <div class="flex gap-2 mb-5">
                <button onclick="AdminStatsManager.changeRange(7)" id="stats-range-7"
                        class="stats-range-btn px-3 py-1.5 rounded-lg text-xs font-medium transition">7 Days</button>
                <button onclick="AdminStatsManager.changeRange(30)" id="stats-range-30"
                        class="stats-range-btn px-3 py-1.5 rounded-lg text-xs font-medium transition">30 Days</button>
                <button onclick="AdminStatsManager.changeRange(90)" id="stats-range-90"
                        class="stats-range-btn px-3 py-1.5 rounded-lg text-xs font-medium transition">90 Days</button>
            </div>

            <!-- Overview Cards -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" id="stats-overview-cards">
                ${this._renderCardSkeleton('Total Users', 'users')}
                ${this._renderCardSkeleton('Active Today', 'activity')}
                ${this._renderCardSkeleton('Total Posts', 'message-square')}
                ${this._renderCardSkeleton('Total Tips (Pi)', 'coins')}
            </div>

            <!-- Charts -->
            <div class="space-y-6">
                <div class="bg-surface rounded-2xl border border-white/5 p-5">
                    <h3 class="font-bold text-secondary mb-3 text-sm flex items-center gap-2">
                        <i data-lucide="trending-up" class="w-4 h-4"></i> User Growth
                    </h3>
                    <div style="height: 220px; position: relative;">
                        <canvas id="chart-users"></canvas>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-surface rounded-2xl border border-white/5 p-5">
                        <h3 class="font-bold text-secondary mb-3 text-sm flex items-center gap-2">
                            <i data-lucide="message-square" class="w-4 h-4"></i> Forum Activity
                        </h3>
                        <div style="height: 200px; position: relative;">
                            <canvas id="chart-forum"></canvas>
                        </div>
                    </div>
                    <div class="bg-surface rounded-2xl border border-white/5 p-5">
                        <h3 class="font-bold text-secondary mb-3 text-sm flex items-center gap-2">
                            <i data-lucide="coins" class="w-4 h-4"></i> Revenue
                        </h3>
                        <div style="height: 200px; position: relative;">
                            <canvas id="chart-revenue"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (window.lucide) lucide.createIcons();
        this._updateRangeButtons();
        this.loadAll();
    },

    changeRange(days) {
        this.currentRange = days;
        this._updateRangeButtons();
        this.destroyCharts();
        this.loadUserChart();
        this.loadForumChart();
        this.loadRevenueChart();
    },

    _updateRangeButtons() {
        document.querySelectorAll('.stats-range-btn').forEach(b => {
            b.classList.remove('bg-primary/20', 'text-primary');
            b.classList.add('text-textMuted', 'hover:bg-white/5');
        });
        const active = document.getElementById(`stats-range-${this.currentRange}`);
        if (active) {
            active.classList.add('bg-primary/20', 'text-primary');
            active.classList.remove('text-textMuted', 'hover:bg-white/5');
        }
    },

    _renderCardSkeleton(label, icon) {
        return `
            <div class="bg-surface rounded-2xl border border-white/5 p-4">
                <div class="flex items-center gap-2 mb-2">
                    <i data-lucide="${icon}" class="w-4 h-4 text-textMuted"></i>
                    <span class="text-xs text-textMuted">${label}</span>
                </div>
                <div class="text-xl font-bold text-secondary stats-value" data-stat="${label}">--</div>
            </div>
        `;
    },

    async loadAll() {
        this.loadOverview();
        this.loadUserChart();
        this.loadForumChart();
        this.loadRevenueChart();
    },

    async loadOverview() {
        try {
            const res = await fetch('/api/admin/stats/overview', {
                headers: AdminPanel._getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();

            const cards = document.getElementById('stats-overview-cards');
            if (!cards) return;

            const values = [
                { label: 'Total Users', value: `${data.total_users}`, sub: `+${data.new_users_today} today | ${data.pro_users} PRO` },
                { label: 'Active Today', value: `${data.active_today}`, sub: `${data.pending_reports} pending reports` },
                { label: 'Total Posts', value: `${data.total_posts}`, sub: `${data.total_comments} comments` },
                { label: 'Total Tips (Pi)', value: `${data.total_tips_amount.toFixed(2)}`, sub: `${data.total_tips_count} transactions` }
            ];

            const icons = ['users', 'activity', 'message-square', 'coins'];

            cards.innerHTML = values.map((v, i) => `
                <div class="bg-surface rounded-2xl border border-white/5 p-4">
                    <div class="flex items-center gap-2 mb-1">
                        <i data-lucide="${icons[i]}" class="w-4 h-4 text-textMuted"></i>
                        <span class="text-xs text-textMuted">${v.label}</span>
                    </div>
                    <div class="text-xl font-bold text-secondary">${v.value}</div>
                    <div class="text-[10px] text-textMuted mt-0.5">${v.sub}</div>
                </div>
            `).join('');

            if (window.lucide) lucide.createIcons();
        } catch (e) {
            console.warn('Failed to load overview stats:', e);
        }
    },

    async loadUserChart() {
        try {
            const res = await fetch(`/api/admin/stats/users?days=${this.currentRange}`, {
                headers: AdminPanel._getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();

            const filled = this._fillMissingDates(data.data, this.currentRange);
            const labels = filled.map(d => d.date.substring(5)); // MM-DD
            const counts = filled.map(d => d.count);

            // Cumulative
            let cumulative = [];
            let sum = 0;
            counts.forEach(c => { sum += c; cumulative.push(sum); });

            this._createChart('chart-users', {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'New Users',
                            data: counts,
                            borderColor: 'rgba(168, 130, 82, 1)',
                            backgroundColor: 'rgba(168, 130, 82, 0.1)',
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Cumulative',
                            data: cumulative,
                            borderColor: 'rgba(100, 180, 100, 0.6)',
                            borderDash: [5, 5],
                            tension: 0.3,
                            pointRadius: 0,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: this._chartOptions({
                    y: { position: 'left', title: { display: true, text: 'New', color: '#888' } },
                    y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Total', color: '#888' } }
                })
            });
        } catch (e) {
            console.warn('Failed to load user chart:', e);
        }
    },

    async loadForumChart() {
        try {
            const res = await fetch(`/api/admin/stats/forum?days=${this.currentRange}`, {
                headers: AdminPanel._getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();

            const postsFilled = this._fillMissingDates(data.posts, this.currentRange);
            const commentsFilled = this._fillMissingDates(data.comments, this.currentRange);
            const labels = postsFilled.map(d => d.date.substring(5));

            this._createChart('chart-forum', {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Posts',
                            data: postsFilled.map(d => d.count),
                            backgroundColor: 'rgba(168, 130, 82, 0.7)',
                            borderRadius: 4
                        },
                        {
                            label: 'Comments',
                            data: commentsFilled.map(d => d.count),
                            backgroundColor: 'rgba(100, 180, 100, 0.5)',
                            borderRadius: 4
                        }
                    ]
                },
                options: this._chartOptions()
            });
        } catch (e) {
            console.warn('Failed to load forum chart:', e);
        }
    },

    async loadRevenueChart() {
        try {
            const res = await fetch(`/api/admin/stats/revenue?days=${this.currentRange}`, {
                headers: AdminPanel._getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();

            const tipsFilled = this._fillMissingDates(data.tips.map(d => ({ date: d.date, count: d.amount })), this.currentRange);
            const memFilled = this._fillMissingDates(data.memberships.map(d => ({ date: d.date, count: d.amount })), this.currentRange);
            const labels = tipsFilled.map(d => d.date.substring(5));

            this._createChart('chart-revenue', {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Tips (Pi)',
                            data: tipsFilled.map(d => d.count),
                            borderColor: 'rgba(168, 130, 82, 1)',
                            backgroundColor: 'rgba(168, 130, 82, 0.1)',
                            fill: true,
                            tension: 0.3
                        },
                        {
                            label: 'Memberships (Pi)',
                            data: memFilled.map(d => d.count),
                            borderColor: 'rgba(130, 100, 200, 0.8)',
                            backgroundColor: 'rgba(130, 100, 200, 0.1)',
                            fill: true,
                            tension: 0.3
                        }
                    ]
                },
                options: this._chartOptions()
            });
        } catch (e) {
            console.warn('Failed to load revenue chart:', e);
        }
    },

    _chartOptions(scalesOverride) {
        const base = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#888', boxWidth: 12, font: { size: 10 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#666', font: { size: 9 }, maxRotation: 0 },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#666', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            }
        };

        if (scalesOverride) {
            base.scales = { x: base.scales.x, ...scalesOverride };
            // Ensure common x axis style
            Object.values(base.scales).forEach(s => {
                if (!s.ticks) s.ticks = {};
                if (!s.ticks.color) s.ticks.color = '#666';
            });
        }

        return base;
    },

    _createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // Destroy existing
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
            delete this.charts[canvasId];
        }

        this.charts[canvasId] = new Chart(canvas, config);
    },

    destroyCharts() {
        Object.keys(this.charts).forEach(key => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                delete this.charts[key];
            }
        });
    },

    _fillMissingDates(data, days) {
        const dateMap = {};
        (data || []).forEach(d => { dateMap[d.date] = d.count || 0; });

        const result = [];
        const now = new Date();
        for (let i = days - 1; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - i);
            const key = d.toISOString().split('T')[0];
            result.push({ date: key, count: dateMap[key] || 0 });
        }
        return result;
    }
};

window.AdminStatsManager = AdminStatsManager;
