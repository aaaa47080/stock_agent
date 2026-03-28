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

    // Boards
    async getBoards() {
        return AppAPI.get('/api/forum/boards');
    },

    // Posts
    async getPosts(filters = {}) {
        const query = new URLSearchParams(filters).toString();
        return AppAPI.get(`/api/forum/posts?${query}`);
    },
    async getPost(id) {
        const userId = this._getUserId();
        const query = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
        return AppAPI.get(`/api/forum/posts/${id}${query}`);
    },
    async createPost(data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.post(`/api/forum/posts?user_id=${encodeURIComponent(userId)}`, data);
    },

    // Comments & Reactions
    async getComments(postId) {
        return AppAPI.get(`/api/forum/posts/${postId}/comments`);
    },
    async createComment(postId, data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        const query = new URLSearchParams({ user_id: userId }).toString();
        return AppAPI.post(`/api/forum/posts/${postId}/comments?${query}`, data);
    },
    async pushPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.post(`/api/forum/posts/${postId}/push?user_id=${userId}`);
    },
    async booPost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.post(`/api/forum/posts/${postId}/boo?user_id=${userId}`);
    },

    // Tags
    async getTrendingTags() {
        return AppAPI.get('/api/forum/tags/trending');
    },

    // Tips
    async tipPost(postId, amount, txHash, paymentId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.post(`/api/forum/posts/${postId}/tip?user_id=${userId}`, {
            amount,
            tx_hash: txHash,
            payment_id: paymentId,
        });
    },

    // Delete Post
    async deletePost(postId) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.delete(`/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`);
    },

    // Update Post
    async updatePost(postId, data) {
        const userId = this._getUserId();
        if (!userId) throw new Error('Please login first');

        return AppAPI.put(`/api/forum/posts/${postId}?user_id=${encodeURIComponent(userId)}`, data);
    },

    // My Stats (Me)
    async getMyStats() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        return AppAPI.get(`/api/forum/me/stats?user_id=${userId}`);
    },
    async getMyPosts() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        return AppAPI.get(`/api/forum/me/posts?user_id=${userId}`);
    },
    async getMyTipsSent() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        return AppAPI.get(`/api/forum/me/tips/sent?user_id=${userId}`);
    },
    async getMyTipsReceived() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        return AppAPI.get(`/api/forum/me/tips/received?user_id=${userId}`);
    },
    async getMyPayments() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');
        return AppAPI.get(`/api/forum/me/payments?user_id=${userId}`);
    },
    async checkLimits() {
        const userId = this._getUserId();
        if (!userId) throw new Error('User not logged in');

        return AppAPI.get(`/api/forum/me/limits?user_id=${userId}`, { timeout: 5000 });
    },
};

// Expose globally
window.ForumAPI = ForumAPI;
export { ForumAPI };

