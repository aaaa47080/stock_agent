// ============================================
// Forum API Client
// ============================================
const ForumAPI = {
    _getUserId() {
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            return AuthManager.currentUser.user_id || AuthManager.currentUser.uid;
        }
        return null;
    },

    _getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof AuthManager !== 'undefined' && AuthManager.currentUser) {
            // 修正：使用 accessToken 而不是 token
            const token =
                AuthManager.currentUser.accessToken ||
                AuthManager.currentUser.token ||
                localStorage.getItem('auth_token');
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return headers;
    },

    // Boards
    async getBoards() {
        const res = await fetch('/api/forum/boards');
        return await res.json();
    },

    // Posts
    async getPosts(filters = {}) {
        const query = new URLSearchParams(filters).toString();
        const res = await fetch(`/api/forum/posts?${query}`);
        return await res.json();
    },
    async getPost(id) {
        const userId = this._getUserId();
        const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
        const res = await fetch(`/api/forum/posts/${id}${query}`);
        return await res.json();
    },
    async createPost(data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts?user_id=${encodeURIComponent(userId)}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            let errorMsg = 'Failed to create post';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    // Pydantic validation error
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                } else {
                    errorMsg = JSON.stringify(err);
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Comments & Reactions
    async getComments(postId) {
        const res = await fetch(`/api/forum/posts/${postId}/comments`);
        return await res.json();
    },
    async createComment(postId, data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const query = new URLSearchParams({ user_id: userId }).toString();
        const res = await fetch(`/api/forum/posts/${postId}/comments?${query}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify(data),
        });
        if (!res.ok) {
            let errorMsg = 'Failed to create comment';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                } else {
                    errorMsg = JSON.stringify(err);
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },
    async pushPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}/push?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
        });
        if (!res.ok) {
            let errorMsg = 'Failed to push';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },
    async booPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}/boo?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
        });
        if (!res.ok) {
            let errorMsg = 'Failed to boo';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Tags
    async getTrendingTags() {
        const res = await fetch('/api/forum/tags/trending');
        return await res.json();
    },

    // Tips
    async tipPost(postId, amount, txHash) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(`/api/forum/posts/${postId}/tip?user_id=${userId}`, {
            method: 'POST',
            headers: this._getAuthHeaders(),
            body: JSON.stringify({ amount, tx_hash: txHash }),
        });
        if (!res.ok) {
            let errorMsg = 'Failed to tip';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Delete Post
    async deletePost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(
            `/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`,
            {
                method: 'DELETE',
                headers: this._getAuthHeaders(),
            }
        );
        if (!res.ok) {
            let errorMsg = 'Failed to delete post';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // Update Post
    async updatePost(postId, data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const res = await fetch(
            `/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`,
            {
                method: 'PUT',
                headers: this._getAuthHeaders(),
                body: JSON.stringify(data),
            }
        );
        if (!res.ok) {
            let errorMsg = 'Failed to update post';
            try {
                const err = await res.json();
                if (typeof err.detail === 'string') {
                    errorMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errorMsg = err.detail.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('\n');
                } else if (err.message) {
                    errorMsg = err.message;
                }
            } catch (e) {
                errorMsg = `Status ${res.status}: ${res.statusText}`;
            }
            throw new Error(errorMsg);
        }
        return await res.json();
    },

    // My Stats (Me)
    async getMyStats() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/stats?user_id=${userId}`, {
            headers: this._getAuthHeaders(),
        });
        return await res.json();
    },
    async getMyPosts() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/posts?user_id=${userId}`, {
            headers: this._getAuthHeaders(),
        });
        return await res.json();
    },
    async getMyTipsSent() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/sent?user_id=${userId}`, {
            headers: this._getAuthHeaders(),
        });
        return await res.json();
    },
    async getMyTipsReceived() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/tips/received?user_id=${userId}`, {
            headers: this._getAuthHeaders(),
        });
        return await res.json();
    },
    async getMyPayments() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        const res = await fetch(`/api/forum/me/payments?user_id=${userId}`, {
            headers: this._getAuthHeaders(),
        });
        return await res.json();
    },
    async checkLimits() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');

        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 5000); // 5s timeout

        try {
            const res = await fetch(`/api/forum/me/limits?user_id=${userId}`, {
                headers: this._getAuthHeaders(),
                signal: controller.signal,
            });
            clearTimeout(id);
            return await res.json();
        } catch (e) {
            clearTimeout(id);
            throw e;
        }
    },
};

// Expose globally
window.ForumAPI = ForumAPI;
