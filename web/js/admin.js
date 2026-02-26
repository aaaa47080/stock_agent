// ========================================
// admin.js - Admin Panel Module
// ========================================

const AdminPanel = {
    currentSubPage: 'broadcast',
    initialized: false,

    _getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            const token = AuthManager.currentUser.accessToken || AuthManager.currentUser.token;
            if (token) headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    },

    init() {
        const container = document.getElementById('admin-content');
        if (!container) return;

        // Render shell with sub-nav
        container.innerHTML = `
            <!-- Sub Navigation -->
            <div class="flex gap-2 mb-4 border-b border-white/5 pb-3">
                <button id="admin-subnav-broadcast" onclick="AdminPanel.switchSubPage('broadcast')"
                        class="admin-subnav-btn px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2">
                    <i data-lucide="megaphone" class="w-4 h-4"></i>
                    <span>Broadcast</span>
                </button>
                <button id="admin-subnav-users" onclick="AdminPanel.switchSubPage('users')"
                        class="admin-subnav-btn px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2">
                    <i data-lucide="users" class="w-4 h-4"></i>
                    <span>Users</span>
                </button>
                <button id="admin-subnav-forum" onclick="AdminPanel.switchSubPage('forum')"
                        class="admin-subnav-btn px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2">
                    <i data-lucide="message-square" class="w-4 h-4"></i>
                    <span>Forum</span>
                </button>
                <button id="admin-subnav-config" onclick="AdminPanel.switchSubPage('config')"
                        class="admin-subnav-btn px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2">
                    <i data-lucide="sliders" class="w-4 h-4"></i>
                    <span>Config</span>
                </button>
                <button id="admin-subnav-stats" onclick="AdminPanel.switchSubPage('stats')"
                        class="admin-subnav-btn px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2">
                    <i data-lucide="bar-chart-3" class="w-4 h-4"></i>
                    <span>Stats</span>
                </button>
            </div>
            <!-- Sub Page Content -->
            <div id="admin-subpage-content"></div>
        `;

        if (window.lucide) lucide.createIcons();
        this.switchSubPage(this.currentSubPage);
        this.initialized = true;
    },

    switchSubPage(page) {
        this.currentSubPage = page;

        // Update sub-nav active state
        document.querySelectorAll('.admin-subnav-btn').forEach(btn => {
            btn.classList.remove('bg-primary/20', 'text-primary');
            btn.classList.add('text-textMuted', 'hover:bg-white/5');
        });
        const activeBtn = document.getElementById(`admin-subnav-${page}`);
        if (activeBtn) {
            activeBtn.classList.add('bg-primary/20', 'text-primary');
            activeBtn.classList.remove('text-textMuted', 'hover:bg-white/5');
        }

        // Render sub page
        switch (page) {
            case 'broadcast':
                this.BroadcastManager.render();
                break;
            case 'users':
                this.UserManager.render();
                break;
            case 'forum':
                this.ForumManager.render();
                break;
            case 'config':
                this.ConfigManager.render();
                break;
            case 'stats':
                if (window.AdminStatsManager) AdminStatsManager.render();
                else document.getElementById('admin-subpage-content').innerHTML = '<div class="text-center text-textMuted py-12">Stats module loading...</div>';
                break;
        }
    },

    // ========================================
    // Broadcast Manager
    // ========================================
    BroadcastManager: {
        render() {
            const container = document.getElementById('admin-subpage-content');
            if (!container) return;

            container.innerHTML = `
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Send Form -->
                    <div class="bg-surface rounded-2xl border border-white/5 p-5">
                        <h3 class="font-bold text-secondary mb-4 flex items-center gap-2">
                            <i data-lucide="send" class="w-4 h-4"></i> Send Broadcast
                        </h3>
                        <div class="space-y-4">
                            <div>
                                <label class="text-xs text-textMuted mb-1 block">Type</label>
                                <select id="broadcast-type" class="w-full bg-background border border-white/10 rounded-xl px-3 py-2 text-sm text-secondary">
                                    <option value="announcement">Announcement</option>
                                    <option value="system_update">System Update</option>
                                </select>
                            </div>
                            <div>
                                <label class="text-xs text-textMuted mb-1 block">Title</label>
                                <input id="broadcast-title" type="text" maxlength="200" placeholder="Notification title..."
                                       class="w-full bg-background border border-white/10 rounded-xl px-3 py-2 text-sm text-secondary placeholder:text-textMuted/50 focus:border-primary/50 focus:outline-none">
                            </div>
                            <div>
                                <label class="text-xs text-textMuted mb-1 block">Body</label>
                                <textarea id="broadcast-body" rows="4" maxlength="1000" placeholder="Notification content..."
                                          class="w-full bg-background border border-white/10 rounded-xl px-3 py-2 text-sm text-secondary placeholder:text-textMuted/50 focus:border-primary/50 focus:outline-none resize-none"></textarea>
                            </div>
                            <!-- Preview -->
                            <div id="broadcast-preview" class="hidden bg-background/50 rounded-xl p-3 border border-white/5">
                                <div class="text-[10px] text-textMuted mb-1 uppercase tracking-wider">Preview</div>
                                <div id="broadcast-preview-title" class="text-sm font-medium text-secondary"></div>
                                <div id="broadcast-preview-body" class="text-xs text-textMuted mt-1"></div>
                            </div>
                            <button onclick="AdminPanel.BroadcastManager.send()"
                                    id="broadcast-send-btn"
                                    class="w-full py-2.5 bg-primary hover:bg-primary/80 text-white rounded-xl text-sm font-bold transition flex items-center justify-center gap-2">
                                <i data-lucide="send" class="w-4 h-4"></i> Send to All Users
                            </button>
                        </div>
                    </div>

                    <!-- History -->
                    <div class="bg-surface rounded-2xl border border-white/5 p-5">
                        <h3 class="font-bold text-secondary mb-4 flex items-center gap-2">
                            <i data-lucide="history" class="w-4 h-4"></i> Broadcast History
                        </h3>
                        <div id="broadcast-history" class="space-y-3">
                            <div class="text-center text-textMuted text-sm py-8">Loading...</div>
                        </div>
                    </div>
                </div>
            `;

            if (window.lucide) lucide.createIcons();
            this._attachPreviewListeners();
            this.loadHistory();
        },

        _attachPreviewListeners() {
            const title = document.getElementById('broadcast-title');
            const body = document.getElementById('broadcast-body');
            const preview = document.getElementById('broadcast-preview');

            const update = () => {
                const t = title?.value?.trim();
                const b = body?.value?.trim();
                if (t || b) {
                    preview.classList.remove('hidden');
                    document.getElementById('broadcast-preview-title').textContent = t || '(no title)';
                    document.getElementById('broadcast-preview-body').textContent = b || '(no body)';
                } else {
                    preview.classList.add('hidden');
                }
            };

            if (title) title.addEventListener('input', update);
            if (body) body.addEventListener('input', update);
        },

        async send() {
            const title = document.getElementById('broadcast-title')?.value?.trim();
            const body = document.getElementById('broadcast-body')?.value?.trim();
            const type = document.getElementById('broadcast-type')?.value || 'announcement';
            const btn = document.getElementById('broadcast-send-btn');

            if (!title || !body) {
                if (typeof showToast === 'function') showToast('Please fill in title and body', 'error');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<div class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> Sending...';

            try {
                const res = await fetch('/api/admin/notifications/broadcast', {
                    method: 'POST',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ title, body, type })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Failed to send');
                }

                const data = await res.json();
                if (typeof showToast === 'function') {
                    showToast(`Sent to ${data.sent_count} users (${data.online_count} online)`, 'success');
                }

                // Clear form
                document.getElementById('broadcast-title').value = '';
                document.getElementById('broadcast-body').value = '';
                document.getElementById('broadcast-preview').classList.add('hidden');

                // Reload history
                this.loadHistory();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i> Send to All Users';
                if (window.lucide) lucide.createIcons();
            }
        },

        async loadHistory() {
            const container = document.getElementById('broadcast-history');
            if (!container) return;

            try {
                const res = await fetch('/api/admin/notifications/history?limit=20', {
                    headers: AdminPanel._getAuthHeaders()
                });
                if (!res.ok) throw new Error('Failed to load');

                const data = await res.json();
                if (!data.broadcasts || data.broadcasts.length === 0) {
                    container.innerHTML = '<div class="text-center text-textMuted text-sm py-8">No broadcasts yet</div>';
                    return;
                }

                container.innerHTML = data.broadcasts.map(b => {
                    const typeLabel = b.type === 'system_update' ? 'System Update' : 'Announcement';
                    const typeColor = b.type === 'system_update' ? 'text-success' : 'text-accent';
                    const time = b.created_at ? new Date(b.created_at).toLocaleString() : '';

                    return `
                        <div class="p-3 bg-background/50 rounded-xl border border-white/5">
                            <div class="flex items-center justify-between mb-1">
                                <span class="text-xs font-medium ${typeColor}">${typeLabel}</span>
                                <span class="text-[10px] text-textMuted">${time}</span>
                            </div>
                            <div class="text-sm font-medium text-secondary">${this._escapeHtml(b.title)}</div>
                            <div class="text-xs text-textMuted mt-0.5 line-clamp-2">${this._escapeHtml(b.body)}</div>
                            <div class="text-[10px] text-textMuted/60 mt-1">${b.recipient_count} recipients</div>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                container.innerHTML = `<div class="text-center text-danger text-sm py-4">Failed to load history</div>`;
            }
        },

        _escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
    },

    // ========================================
    // User Manager
    // ========================================
    UserManager: {
        currentPage: 1,
        searchQuery: '',

        render() {
            const container = document.getElementById('admin-subpage-content');
            if (!container) return;

            container.innerHTML = `
                <div class="bg-surface rounded-2xl border border-white/5 p-5">
                    <!-- Search Bar -->
                    <div class="flex gap-3 mb-4">
                        <div class="flex-1 relative">
                            <i data-lucide="search" class="w-4 h-4 text-textMuted absolute left-3 top-1/2 -translate-y-1/2"></i>
                            <input id="admin-user-search" type="text" placeholder="Search by username or user ID..."
                                   value="${this._escapeHtml(this.searchQuery)}"
                                   class="w-full bg-background border border-white/10 rounded-xl pl-10 pr-3 py-2 text-sm text-secondary placeholder:text-textMuted/50 focus:border-primary/50 focus:outline-none">
                        </div>
                        <button onclick="AdminPanel.UserManager.doSearch()"
                                class="px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-xl text-sm font-medium transition">
                            Search
                        </button>
                    </div>

                    <!-- User List -->
                    <div id="admin-user-list">
                        <div class="text-center text-textMuted text-sm py-8">Loading...</div>
                    </div>

                    <!-- Pagination -->
                    <div id="admin-user-pagination" class="flex items-center justify-between mt-4 hidden">
                        <button onclick="AdminPanel.UserManager.prevPage()" id="admin-users-prev"
                                class="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-textMuted transition">
                            Previous
                        </button>
                        <span id="admin-users-page-info" class="text-xs text-textMuted"></span>
                        <button onclick="AdminPanel.UserManager.nextPage()" id="admin-users-next"
                                class="px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-textMuted transition">
                            Next
                        </button>
                    </div>
                </div>

                <!-- User Action Modal -->
                <div id="admin-user-modal" class="fixed inset-0 bg-black/60 z-[70] hidden flex items-center justify-center p-4">
                    <div class="bg-surface rounded-2xl border border-white/10 w-full max-w-md max-h-[80vh] overflow-y-auto" id="admin-user-modal-content">
                    </div>
                </div>
            `;

            if (window.lucide) lucide.createIcons();

            // Enter key search
            const searchInput = document.getElementById('admin-user-search');
            if (searchInput) {
                searchInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') this.doSearch();
                });
            }

            this.loadUsers();
        },

        doSearch() {
            this.searchQuery = document.getElementById('admin-user-search')?.value?.trim() || '';
            this.currentPage = 1;
            this.loadUsers();
        },

        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadUsers();
            }
        },

        nextPage() {
            this.currentPage++;
            this.loadUsers();
        },

        async loadUsers() {
            const listEl = document.getElementById('admin-user-list');
            if (!listEl) return;

            listEl.innerHTML = '<div class="text-center text-textMuted text-sm py-8"><div class="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin mx-auto mb-2"></div>Loading...</div>';

            try {
                let url = `/api/admin/users?page=${this.currentPage}&limit=20`;
                if (this.searchQuery) url += `&search=${encodeURIComponent(this.searchQuery)}`;

                const res = await fetch(url, { headers: AdminPanel._getAuthHeaders() });
                if (!res.ok) throw new Error('Failed to load users');

                const data = await res.json();
                const users = data.users || [];
                const total = data.total || 0;
                const totalPages = Math.ceil(total / 20);

                if (users.length === 0) {
                    listEl.innerHTML = '<div class="text-center text-textMuted text-sm py-8">No users found</div>';
                    document.getElementById('admin-user-pagination')?.classList.add('hidden');
                    return;
                }

                listEl.innerHTML = `
                    <div class="text-xs text-textMuted mb-3">${total} users total</div>
                    <div class="space-y-2">
                        ${users.map(u => this._renderUserRow(u)).join('')}
                    </div>
                `;

                // Pagination
                const pagEl = document.getElementById('admin-user-pagination');
                if (pagEl && totalPages > 1) {
                    pagEl.classList.remove('hidden');
                    document.getElementById('admin-users-page-info').textContent = `Page ${this.currentPage} / ${totalPages}`;
                    document.getElementById('admin-users-prev').disabled = this.currentPage <= 1;
                    document.getElementById('admin-users-next').disabled = this.currentPage >= totalPages;
                } else if (pagEl) {
                    pagEl.classList.add('hidden');
                }

                if (window.lucide) lucide.createIcons();
            } catch (e) {
                listEl.innerHTML = `<div class="text-center text-danger text-sm py-4">Failed to load users: ${e.message}</div>`;
            }
        },

        _renderUserRow(user) {
            const roleBadge = user.role === 'admin'
                ? '<span class="text-[10px] px-1.5 py-0.5 bg-danger/20 text-danger rounded-full font-bold">ADMIN</span>'
                : '';
            const proBadge = user.membership_tier === 'pro'
                ? '<span class="text-[10px] px-1.5 py-0.5 bg-accent/20 text-accent rounded-full font-bold">PRO</span>'
                : '';
            const statusDot = user.is_active
                ? '<div class="w-2 h-2 rounded-full bg-success shrink-0" title="Active"></div>'
                : '<div class="w-2 h-2 rounded-full bg-danger shrink-0" title="Suspended"></div>';
            const time = user.created_at ? new Date(user.created_at).toLocaleDateString() : '';

            return `
                <div class="flex items-center gap-3 p-3 bg-background/50 rounded-xl border border-white/5 hover:border-white/10 transition cursor-pointer"
                     onclick="AdminPanel.UserManager.openUserModal('${user.user_id}')">
                    ${statusDot}
                    <div class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-sm font-bold shrink-0">
                        ${(user.username || '?')[0].toUpperCase()}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium text-secondary truncate">${this._escapeHtml(user.username)}</span>
                            ${roleBadge}${proBadge}
                        </div>
                        <div class="text-[10px] text-textMuted truncate">${user.user_id}</div>
                    </div>
                    <div class="text-[10px] text-textMuted shrink-0">${time}</div>
                    <i data-lucide="chevron-right" class="w-4 h-4 text-textMuted/50 shrink-0"></i>
                </div>
            `;
        },

        async openUserModal(userId) {
            const modal = document.getElementById('admin-user-modal');
            const content = document.getElementById('admin-user-modal-content');
            if (!modal || !content) return;

            modal.classList.remove('hidden');
            content.innerHTML = '<div class="p-8 text-center"><div class="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin mx-auto"></div></div>';

            // Close on backdrop click
            modal.onclick = (e) => { if (e.target === modal) modal.classList.add('hidden'); };

            try {
                const res = await fetch(`/api/admin/users/${userId}`, { headers: AdminPanel._getAuthHeaders() });
                if (!res.ok) throw new Error('Failed to load user');
                const data = await res.json();
                const u = data.user;

                const isActive = u.is_active;
                const isPro = u.membership_tier === 'pro';
                const isAdmin = u.role === 'admin';

                content.innerHTML = `
                    <div class="p-5">
                        <!-- Header -->
                        <div class="flex items-center gap-3 mb-5">
                            <div class="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-primary text-lg font-bold">
                                ${(u.username || '?')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="font-bold text-secondary">${this._escapeHtml(u.username)}</div>
                                <div class="text-xs text-textMuted">${u.user_id}</div>
                            </div>
                            <button onclick="document.getElementById('admin-user-modal').classList.add('hidden')"
                                    class="ml-auto p-2 hover:bg-white/5 rounded-lg transition">
                                <i data-lucide="x" class="w-4 h-4 text-textMuted"></i>
                            </button>
                        </div>

                        <!-- Info Grid -->
                        <div class="grid grid-cols-2 gap-3 mb-5 text-xs">
                            <div class="bg-background/50 rounded-xl p-3">
                                <div class="text-textMuted mb-0.5">Role</div>
                                <div class="text-secondary font-medium">${u.role || 'user'}</div>
                            </div>
                            <div class="bg-background/50 rounded-xl p-3">
                                <div class="text-textMuted mb-0.5">Membership</div>
                                <div class="text-secondary font-medium">${u.membership_tier || 'free'}${u.membership_expires_at ? ' (expires ' + new Date(u.membership_expires_at).toLocaleDateString() + ')' : ''}</div>
                            </div>
                            <div class="bg-background/50 rounded-xl p-3">
                                <div class="text-textMuted mb-0.5">Status</div>
                                <div class="${isActive ? 'text-success' : 'text-danger'} font-medium">${isActive ? 'Active' : 'Suspended'}</div>
                            </div>
                            <div class="bg-background/50 rounded-xl p-3">
                                <div class="text-textMuted mb-0.5">Joined</div>
                                <div class="text-secondary font-medium">${u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}</div>
                            </div>
                        </div>

                        <!-- Actions -->
                        <div class="space-y-2">
                            <h4 class="text-xs text-textMuted font-medium uppercase tracking-wider mb-2">Actions</h4>

                            <!-- Role Toggle -->
                            <button onclick="AdminPanel.UserManager.setRole('${u.user_id}', '${isAdmin ? 'user' : 'admin'}')"
                                    class="w-full flex items-center gap-3 p-3 rounded-xl border border-white/5 hover:bg-white/5 transition text-left">
                                <i data-lucide="${isAdmin ? 'shield-off' : 'shield'}" class="w-4 h-4 ${isAdmin ? 'text-textMuted' : 'text-danger'}"></i>
                                <div>
                                    <div class="text-sm text-secondary">${isAdmin ? 'Remove Admin' : 'Make Admin'}</div>
                                    <div class="text-[10px] text-textMuted">${isAdmin ? 'Demote to regular user' : 'Grant admin privileges'}</div>
                                </div>
                            </button>

                            <!-- Membership Toggle -->
                            <button onclick="AdminPanel.UserManager.setMembership('${u.user_id}', '${isPro ? 'free' : 'pro'}')"
                                    class="w-full flex items-center gap-3 p-3 rounded-xl border border-white/5 hover:bg-white/5 transition text-left">
                                <i data-lucide="${isPro ? 'star-off' : 'star'}" class="w-4 h-4 ${isPro ? 'text-textMuted' : 'text-accent'}"></i>
                                <div>
                                    <div class="text-sm text-secondary">${isPro ? 'Remove Pro' : 'Grant Pro (1 month)'}</div>
                                    <div class="text-[10px] text-textMuted">${isPro ? 'Downgrade to free tier' : 'Upgrade to pro membership'}</div>
                                </div>
                            </button>

                            <!-- Status Toggle -->
                            <button onclick="AdminPanel.UserManager.toggleStatus('${u.user_id}', ${!isActive})"
                                    class="w-full flex items-center gap-3 p-3 rounded-xl border ${isActive ? 'border-danger/20 hover:bg-danger/5' : 'border-success/20 hover:bg-success/5'} transition text-left">
                                <i data-lucide="${isActive ? 'ban' : 'check-circle'}" class="w-4 h-4 ${isActive ? 'text-danger' : 'text-success'}"></i>
                                <div>
                                    <div class="text-sm ${isActive ? 'text-danger' : 'text-success'}">${isActive ? 'Suspend Account' : 'Reactivate Account'}</div>
                                    <div class="text-[10px] text-textMuted">${isActive ? 'Block user from accessing the platform' : 'Restore user access'}</div>
                                </div>
                            </button>
                        </div>
                    </div>
                `;

                if (window.lucide) lucide.createIcons();
            } catch (e) {
                content.innerHTML = `<div class="p-8 text-center text-danger text-sm">Failed to load user: ${e.message}</div>`;
            }
        },

        async setRole(userId, newRole) {
            try {
                const res = await fetch(`/api/admin/users/${userId}/role`, {
                    method: 'PUT',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ role: newRole })
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(`Role updated to ${newRole}`, 'success');
                this.openUserModal(userId); // Refresh modal
                this.loadUsers(); // Refresh list
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        async setMembership(userId, tier) {
            try {
                const body = { tier };
                if (tier === 'pro') body.months = 1;

                const res = await fetch(`/api/admin/users/${userId}/membership`, {
                    method: 'PUT',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify(body)
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(`Membership set to ${tier}`, 'success');
                this.openUserModal(userId);
                this.loadUsers();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        async toggleStatus(userId, active) {
            const reason = active ? null : prompt('Suspension reason (optional):');
            try {
                const res = await fetch(`/api/admin/users/${userId}/status`, {
                    method: 'PUT',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ active, reason })
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(active ? 'Account reactivated' : 'Account suspended', 'success');
                this.openUserModal(userId);
                this.loadUsers();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        _escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
    },

    // ========================================
    // Forum Manager (P1)
    // ========================================
    ForumManager: {
        currentView: 'posts', // posts | reports
        currentPage: 1,
        searchQuery: '',
        statusFilter: 'all',

        render() {
            const container = document.getElementById('admin-subpage-content');
            if (!container) return;

            container.innerHTML = `
                <div class="bg-surface rounded-2xl border border-white/5 p-5">
                    <!-- View Toggle -->
                    <div class="flex gap-2 mb-4">
                        <button onclick="AdminPanel.ForumManager.switchView('posts')" id="forum-view-posts"
                                class="forum-view-btn px-3 py-1.5 rounded-lg text-xs font-medium transition">Posts</button>
                        <button onclick="AdminPanel.ForumManager.switchView('reports')" id="forum-view-reports"
                                class="forum-view-btn px-3 py-1.5 rounded-lg text-xs font-medium transition">
                            Reports <span id="forum-report-badge" class="hidden ml-1 px-1.5 py-0.5 bg-danger/20 text-danger rounded-full text-[10px]"></span>
                        </button>
                    </div>
                    <div id="forum-content"></div>
                </div>
            `;
            this.switchView(this.currentView);
        },

        switchView(view) {
            this.currentView = view;
            document.querySelectorAll('.forum-view-btn').forEach(b => {
                b.classList.remove('bg-primary/20', 'text-primary');
                b.classList.add('text-textMuted', 'hover:bg-white/5');
            });
            const active = document.getElementById(`forum-view-${view}`);
            if (active) {
                active.classList.add('bg-primary/20', 'text-primary');
                active.classList.remove('text-textMuted', 'hover:bg-white/5');
            }
            if (view === 'posts') this.loadPosts();
            else this.loadReports();
        },

        async loadPosts() {
            const el = document.getElementById('forum-content');
            if (!el) return;

            el.innerHTML = `
                <div class="flex gap-3 mb-4">
                    <div class="flex-1 relative">
                        <input id="forum-search" type="text" placeholder="Search posts..."
                               value="${this._esc(this.searchQuery)}"
                               class="w-full bg-background border border-white/10 rounded-xl pl-3 pr-3 py-2 text-sm text-secondary placeholder:text-textMuted/50 focus:border-primary/50 focus:outline-none">
                    </div>
                    <select id="forum-status-filter" onchange="AdminPanel.ForumManager.filterByStatus(this.value)"
                            class="bg-background border border-white/10 rounded-xl px-3 py-2 text-sm text-secondary">
                        <option value="all" ${this.statusFilter === 'all' ? 'selected' : ''}>All</option>
                        <option value="hidden" ${this.statusFilter === 'hidden' ? 'selected' : ''}>Hidden</option>
                        <option value="pinned" ${this.statusFilter === 'pinned' ? 'selected' : ''}>Pinned</option>
                    </select>
                    <button onclick="AdminPanel.ForumManager.doSearch()"
                            class="px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-xl text-sm font-medium transition">Search</button>
                </div>
                <div id="forum-posts-list"><div class="text-center text-textMuted text-sm py-8">Loading...</div></div>
            `;

            const searchInput = document.getElementById('forum-search');
            if (searchInput) searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') this.doSearch(); });

            try {
                let url = `/api/admin/forum/posts?page=${this.currentPage}&limit=20&status=${this.statusFilter}`;
                if (this.searchQuery) url += `&search=${encodeURIComponent(this.searchQuery)}`;

                const res = await fetch(url, { headers: AdminPanel._getAuthHeaders() });
                if (!res.ok) throw new Error('Failed to load posts');
                const data = await res.json();
                const posts = data.posts || [];

                const listEl = document.getElementById('forum-posts-list');
                if (posts.length === 0) {
                    listEl.innerHTML = '<div class="text-center text-textMuted text-sm py-8">No posts found</div>';
                    return;
                }

                listEl.innerHTML = `
                    <div class="text-xs text-textMuted mb-2">${data.total} posts</div>
                    <div class="space-y-2">${posts.map(p => this._renderPostRow(p)).join('')}</div>
                `;
                if (window.lucide) lucide.createIcons();
            } catch (e) {
                document.getElementById('forum-posts-list').innerHTML = `<div class="text-danger text-sm py-4 text-center">${e.message}</div>`;
            }
        },

        _renderPostRow(p) {
            const hiddenBadge = p.is_hidden ? '<span class="text-[10px] px-1.5 py-0.5 bg-danger/20 text-danger rounded-full">HIDDEN</span>' : '';
            const pinnedBadge = p.is_pinned ? '<span class="text-[10px] px-1.5 py-0.5 bg-accent/20 text-accent rounded-full">PINNED</span>' : '';
            const time = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';

            return `
                <div class="flex items-center gap-3 p-3 bg-background/50 rounded-xl border border-white/5">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="text-sm font-medium text-secondary truncate">${this._esc(p.title)}</span>
                            ${hiddenBadge}${pinnedBadge}
                        </div>
                        <div class="text-[10px] text-textMuted mt-0.5">
                            by ${this._esc(p.username)} | ${p.category || ''} | ${p.view_count} views | ${p.comment_count} comments | ${time}
                        </div>
                    </div>
                    <div class="flex gap-1 shrink-0">
                        <button onclick="AdminPanel.ForumManager.toggleVisibility(${p.id}, ${p.is_hidden})"
                                class="p-1.5 rounded-lg hover:bg-white/10 transition" title="${p.is_hidden ? 'Show' : 'Hide'}">
                            <i data-lucide="${p.is_hidden ? 'eye' : 'eye-off'}" class="w-3.5 h-3.5 ${p.is_hidden ? 'text-success' : 'text-danger'}"></i>
                        </button>
                        <button onclick="AdminPanel.ForumManager.togglePin(${p.id}, ${p.is_pinned})"
                                class="p-1.5 rounded-lg hover:bg-white/10 transition" title="${p.is_pinned ? 'Unpin' : 'Pin'}">
                            <i data-lucide="pin" class="w-3.5 h-3.5 ${p.is_pinned ? 'text-accent' : 'text-textMuted'}"></i>
                        </button>
                    </div>
                </div>
            `;
        },

        doSearch() {
            this.searchQuery = document.getElementById('forum-search')?.value?.trim() || '';
            this.currentPage = 1;
            this.loadPosts();
        },

        filterByStatus(status) {
            this.statusFilter = status;
            this.currentPage = 1;
            this.loadPosts();
        },

        async toggleVisibility(postId, currentlyHidden) {
            try {
                const res = await fetch(`/api/admin/forum/posts/${postId}/visibility`, {
                    method: 'PATCH',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ is_hidden: !currentlyHidden })
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(currentlyHidden ? 'Post shown' : 'Post hidden', 'success');
                this.loadPosts();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        async togglePin(postId, currentlyPinned) {
            try {
                const res = await fetch(`/api/admin/forum/posts/${postId}/pin`, {
                    method: 'PATCH',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ is_pinned: !currentlyPinned })
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(currentlyPinned ? 'Post unpinned' : 'Post pinned', 'success');
                this.loadPosts();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        async loadReports() {
            const el = document.getElementById('forum-content');
            if (!el) return;

            el.innerHTML = '<div class="text-center text-textMuted text-sm py-8">Loading reports...</div>';

            try {
                const res = await fetch('/api/admin/forum/reports?status=pending&limit=50', {
                    headers: AdminPanel._getAuthHeaders()
                });
                if (!res.ok) throw new Error('Failed to load reports');
                const data = await res.json();
                const reports = data.reports || [];

                // Update badge
                const badge = document.getElementById('forum-report-badge');
                if (badge && data.total > 0) {
                    badge.textContent = data.total;
                    badge.classList.remove('hidden');
                }

                if (reports.length === 0) {
                    el.innerHTML = '<div class="text-center text-textMuted text-sm py-8">No pending reports</div>';
                    return;
                }

                el.innerHTML = `
                    <div class="text-xs text-textMuted mb-2">${data.total} pending reports</div>
                    <div class="space-y-3">${reports.map(r => this._renderReportRow(r)).join('')}</div>
                `;
                if (window.lucide) lucide.createIcons();
            } catch (e) {
                el.innerHTML = `<div class="text-danger text-sm py-4 text-center">${e.message}</div>`;
            }
        },

        _renderReportRow(r) {
            const typeColors = { spam: 'text-warning', harassment: 'text-danger', misinformation: 'text-accent', scam: 'text-danger', other: 'text-textMuted' };
            const color = typeColors[r.report_type] || 'text-textMuted';
            const time = r.created_at ? new Date(r.created_at).toLocaleDateString() : '';

            return `
                <div class="p-3 bg-background/50 rounded-xl border border-white/5">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] px-1.5 py-0.5 bg-white/5 rounded-full ${color} font-medium">${r.report_type}</span>
                            <span class="text-[10px] text-textMuted">${r.content_type} #${r.content_id}</span>
                        </div>
                        <span class="text-[10px] text-textMuted">${time}</span>
                    </div>
                    ${r.content_preview ? `<div class="text-xs text-secondary mb-1 line-clamp-1">"${this._esc(r.content_preview)}"</div>` : ''}
                    <div class="text-[10px] text-textMuted mb-2">Reported by ${this._esc(r.reporter_username)} | Votes: ${r.approve_count} approve / ${r.reject_count} reject</div>
                    ${r.description ? `<div class="text-[10px] text-textMuted/80 mb-2 italic">${this._esc(r.description)}</div>` : ''}
                    <div class="flex gap-2">
                        <button onclick="AdminPanel.ForumManager.resolveReport(${r.id}, 'approved')"
                                class="px-3 py-1 bg-danger/20 hover:bg-danger/30 text-danger rounded-lg text-xs transition">
                            Approve (Hide Content)
                        </button>
                        <button onclick="AdminPanel.ForumManager.resolveReport(${r.id}, 'rejected')"
                                class="px-3 py-1 bg-white/5 hover:bg-white/10 text-textMuted rounded-lg text-xs transition">
                            Reject
                        </button>
                    </div>
                </div>
            `;
        },

        async resolveReport(reportId, decision) {
            try {
                const body = { decision };
                if (decision === 'approved') body.violation_level = 'mild';

                const res = await fetch(`/api/admin/forum/reports/${reportId}/resolve`, {
                    method: 'POST',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify(body)
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(`Report ${decision}`, 'success');
                this.loadReports();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        _esc(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
    },

    // ========================================
    // Config Manager (P1)
    // ========================================
    ConfigManager: {
        configs: {},
        editingKey: null,

        render() {
            const container = document.getElementById('admin-subpage-content');
            if (!container) return;

            container.innerHTML = `
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div class="lg:col-span-2">
                        <div id="config-groups">
                            <div class="text-center text-textMuted text-sm py-8">Loading configs...</div>
                        </div>
                    </div>
                    <div>
                        <div class="bg-surface rounded-2xl border border-white/5 p-5">
                            <h3 class="font-bold text-secondary mb-3 flex items-center gap-2 text-sm">
                                <i data-lucide="history" class="w-4 h-4"></i> Recent Changes
                            </h3>
                            <div id="config-audit-log" class="space-y-2">Loading...</div>
                        </div>
                    </div>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            this.loadConfigs();
            this.loadAuditLog();
        },

        async loadConfigs() {
            const el = document.getElementById('config-groups');
            if (!el) return;

            try {
                const res = await fetch('/api/admin/config/all', { headers: AdminPanel._getAuthHeaders() });
                if (!res.ok) throw new Error('Failed to load configs');
                const data = await res.json();
                this.configs = data.configs_by_category || {};

                const categoryLabels = {
                    pricing: { icon: 'coins', label: 'Pricing' },
                    limits: { icon: 'gauge', label: 'Limits' },
                    general: { icon: 'settings', label: 'General' },
                    scam_tracker: { icon: 'shield-alert', label: 'Scam Tracker' }
                };

                const order = ['pricing', 'limits', 'general', 'scam_tracker'];
                const categories = [...order.filter(k => this.configs[k]), ...Object.keys(this.configs).filter(k => !order.includes(k))];

                el.innerHTML = categories.map(cat => {
                    const info = categoryLabels[cat] || { icon: 'folder', label: cat };
                    const items = this.configs[cat] || [];
                    return `
                        <div class="bg-surface rounded-2xl border border-white/5 p-5 mb-4">
                            <h3 class="font-bold text-secondary mb-3 flex items-center gap-2 text-sm">
                                <i data-lucide="${info.icon}" class="w-4 h-4"></i> ${info.label}
                                <span class="text-[10px] text-textMuted font-normal">(${items.length})</span>
                            </h3>
                            <div class="space-y-2">
                                ${items.map(cfg => this._renderConfigRow(cfg)).join('')}
                            </div>
                        </div>
                    `;
                }).join('');

                if (window.lucide) lucide.createIcons();
            } catch (e) {
                el.innerHTML = `<div class="text-danger text-sm py-4 text-center">${e.message}</div>`;
            }
        },

        _renderConfigRow(cfg) {
            const isEditing = this.editingKey === cfg.key;
            const val = cfg.value !== null && cfg.value !== undefined ? String(cfg.value) : '';
            const desc = cfg.description || '';
            const typeBadge = `<span class="text-[9px] px-1 py-0.5 bg-white/5 rounded text-textMuted/60">${cfg.value_type || 'string'}</span>`;

            if (isEditing) {
                return `
                    <div class="p-3 bg-primary/5 rounded-xl border border-primary/20">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-xs font-medium text-secondary">${this._esc(cfg.key)}</span>
                            ${typeBadge}
                        </div>
                        <div class="flex gap-2">
                            <input id="config-edit-input" type="text" value="${this._esc(val)}"
                                   class="flex-1 bg-background border border-white/10 rounded-lg px-3 py-1.5 text-sm text-secondary focus:border-primary/50 focus:outline-none">
                            <button onclick="AdminPanel.ConfigManager.saveConfig('${cfg.key}')"
                                    class="px-3 py-1.5 bg-primary hover:bg-primary/80 text-white rounded-lg text-xs font-medium transition">Save</button>
                            <button onclick="AdminPanel.ConfigManager.cancelEdit()"
                                    class="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-textMuted rounded-lg text-xs transition">Cancel</button>
                        </div>
                        ${desc ? `<div class="text-[10px] text-textMuted mt-1">${this._esc(desc)}</div>` : ''}
                    </div>
                `;
            }

            return `
                <div class="flex items-center gap-3 p-3 bg-background/50 rounded-xl border border-white/5 hover:border-white/10 transition group">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-medium text-secondary">${this._esc(cfg.key)}</span>
                            ${typeBadge}
                        </div>
                        <div class="text-sm text-primary font-mono mt-0.5">${this._esc(val) || '<em class="text-textMuted">null</em>'}</div>
                        ${desc ? `<div class="text-[10px] text-textMuted mt-0.5">${this._esc(desc)}</div>` : ''}
                    </div>
                    <button onclick="AdminPanel.ConfigManager.startEdit('${cfg.key}')"
                            class="px-2 py-1 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-textMuted opacity-0 group-hover:opacity-100 transition shrink-0">
                        Edit
                    </button>
                </div>
            `;
        },

        startEdit(key) {
            this.editingKey = key;
            this.loadConfigs(); // Re-render with edit mode
        },

        cancelEdit() {
            this.editingKey = null;
            this.loadConfigs();
        },

        async saveConfig(key) {
            const input = document.getElementById('config-edit-input');
            if (!input) return;

            try {
                const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, {
                    method: 'PUT',
                    headers: AdminPanel._getAuthHeaders(),
                    body: JSON.stringify({ value: input.value })
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
                if (typeof showToast === 'function') showToast(`Config "${key}" updated`, 'success');
                this.editingKey = null;
                this.loadConfigs();
                this.loadAuditLog();
            } catch (e) {
                if (typeof showToast === 'function') showToast(e.message, 'error');
            }
        },

        async loadAuditLog() {
            const el = document.getElementById('config-audit-log');
            if (!el) return;

            try {
                const res = await fetch('/api/admin/config/audit?limit=30', { headers: AdminPanel._getAuthHeaders() });
                if (!res.ok) throw new Error('Failed');
                const data = await res.json();
                const logs = data.logs || [];

                if (logs.length === 0) {
                    el.innerHTML = '<div class="text-xs text-textMuted text-center py-4">No changes yet</div>';
                    return;
                }

                el.innerHTML = logs.map(l => {
                    const time = l.changed_at ? new Date(l.changed_at).toLocaleString() : '';
                    return `
                        <div class="text-[10px] p-2 bg-background/50 rounded-lg border border-white/5">
                            <div class="flex justify-between mb-0.5">
                                <span class="text-secondary font-medium truncate">${this._esc(l.key)}</span>
                                <span class="text-textMuted/60 shrink-0 ml-2">${time}</span>
                            </div>
                            <div class="text-textMuted">
                                ${l.old_value ? `<span class="text-danger line-through">${this._esc(String(l.old_value).substring(0, 40))}</span> → ` : ''}
                                <span class="text-success">${this._esc(String(l.new_value || '').substring(0, 40))}</span>
                            </div>
                            <div class="text-textMuted/50 mt-0.5">by ${this._esc(l.changed_by)}</div>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                el.innerHTML = '<div class="text-xs text-danger text-center py-4">Failed to load</div>';
            }
        },

        _esc(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
    }
};

window.AdminPanel = AdminPanel;
