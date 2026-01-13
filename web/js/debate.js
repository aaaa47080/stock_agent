// ========================================
// debate.js - AI 辯論劇本流 (War Room Experience)
// ========================================

const DebateTheater = {
    // 角色定義
    characters: {
        bull: {
            name: 'Bull Warrior',
            nameZh: '牛戰士',
            emoji: '🐂',
            color: 'success',
            bgGradient: 'from-success/20 to-success/5',
            borderColor: 'border-success/30',
            textColor: 'text-success',
            avatar: `<div class="w-12 h-12 rounded-full bg-gradient-to-br from-success to-emerald-600 flex items-center justify-center text-2xl shadow-lg shadow-success/30">🐂</div>`,
            personality: '激進樂觀，看好市場'
        },
        bear: {
            name: 'Bear Analyst',
            nameZh: '熊分析師',
            emoji: '🐻',
            color: 'danger',
            bgGradient: 'from-danger/20 to-danger/5',
            borderColor: 'border-danger/30',
            textColor: 'text-danger',
            avatar: `<div class="w-12 h-12 rounded-full bg-gradient-to-br from-danger to-rose-600 flex items-center justify-center text-2xl shadow-lg shadow-danger/30">🐻</div>`,
            personality: '保守謹慎，風險意識強'
        },
        judge: {
            name: 'Judge AI',
            nameZh: '裁判',
            emoji: '⚖️',
            color: 'primary',
            bgGradient: 'from-primary/20 to-primary/5',
            borderColor: 'border-primary/30',
            textColor: 'text-primary',
            avatar: `<div class="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-2xl shadow-lg shadow-primary/30">⚖️</div>`,
            personality: '公正客觀，綜合評判'
        }
    },

    // 當前辯論狀態
    currentDebate: null,
    userVote: null,

    /**
     * 開始辯論展示
     * @param {string} symbol - 交易對符號
     * @param {HTMLElement} container - 容器元素
     */
    async startDebate(symbol, container) {
        this.currentDebate = { symbol, startTime: Date.now() };
        this.userVote = null;

        // 清空容器並顯示開場
        container.innerHTML = this.renderOpening(symbol);
        lucide.createIcons();

        // 延遲後開始獲取辯論數據
        await this.delay(500);

        let statusInterval;

        try {
            // 顯示載入動畫
            this.appendToContainer(container, this.renderLoadingState());

            // 啟動狀態輪播
            const statuses = [
                "正在召集分析師團隊...",
                "技術分析師正在檢視圖表...",
                "新聞分析師正在掃描全球資訊...",
                "多頭代表正在整理論點...",
                "空頭代表正在尋找漏洞...",
                "AI 裁判正在準備入場..."
            ];
            let statusIdx = 0;
            statusInterval = setInterval(() => {
                statusIdx = (statusIdx + 1) % statuses.length;
                this.updateLoadingStatus(statuses[statusIdx]);
            }, 2500);

            // 獲取辯論數據
            const startTime = Date.now(); // 記錄開始時間
            const res = await fetch(`/api/debate/${symbol}`);
            const data = await res.json();
            const endTime = Date.now(); // 記錄結束時間
            const duration = ((endTime - startTime) / 1000).toFixed(2); // 計算耗時（秒）

            clearInterval(statusInterval);

            if (data.error) throw new Error(data.error);

            // 移除載入動畫
            container.querySelector('.debate-loading')?.remove();

            // 逐步展示辯論內容
            await this.renderDebateFlow(container, data, duration);

        } catch (e) {
            clearInterval(statusInterval);
            console.error('Debate failed:', e);
            this.appendToContainer(container, `
                <div class="text-center py-8">
                    <div class="w-16 h-16 rounded-full bg-danger/20 flex items-center justify-center mx-auto mb-4">
                        <i data-lucide="alert-circle" class="w-8 h-8 text-danger"></i>
                    </div>
                    <p class="text-danger">辯論載入失敗: ${e.message}</p>
                </div>
            `);
            lucide.createIcons();
        }
    },

    /**
     * 渲染開場白
     */
    renderOpening(symbol) {
        return `
            <div class="debate-opening text-center py-6 animate-fade-in">
                <div class="inline-flex items-center gap-2 px-4 py-2 bg-surface rounded-full border border-white/10 mb-4">
                    <i data-lucide="swords" class="w-4 h-4 text-primary"></i>
                    <span class="text-sm font-medium text-secondary">AI War Room</span>
                </div>
                <h3 class="text-2xl font-serif text-secondary mb-2">${symbol} 辯論分析</h3>
                <p class="text-textMuted text-sm">多空雙方即將展開激辯...</p>
            </div>
        `;
    },

    /**
     * 渲染載入狀態
     */
    renderLoadingState() {
        return `
            <div class="debate-loading flex flex-col items-center justify-center gap-6 py-8 animate-fade-in">
                <div class="flex justify-center items-center gap-8">
                    <div class="text-center relative">
                        ${this.characters.bull.avatar}
                        <div class="absolute -bottom-1 -right-1 w-3 h-3 bg-success rounded-full border border-surface animate-pulse"></div>
                    </div>
                    <div class="flex flex-col items-center gap-2">
                        <div class="relative">
                            <div class="w-12 h-12 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
                            <div class="absolute inset-0 flex items-center justify-center font-mono text-xs text-primary font-bold">VS</div>
                        </div>
                    </div>
                    <div class="text-center relative">
                        ${this.characters.bear.avatar}
                         <div class="absolute -bottom-1 -right-1 w-3 h-3 bg-danger rounded-full border border-surface animate-pulse"></div>
                    </div>
                </div>
                
                <div id="debate-loading-status" class="bg-surface/50 px-6 py-2 rounded-full border border-white/5 text-xs text-textMuted font-mono flex items-center gap-2">
                    <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>
                    <span>初始化辯論場景...</span>
                </div>
            </div>
        `;
    },

    /**
     * 更新載入狀態文字
     */
    updateLoadingStatus(text) {
        const el = document.getElementById('debate-loading-status');
        if (el) {
            const span = el.querySelector('span');
            if (span) span.textContent = text;
        }
    },

    /**
     * 逐步渲染辯論流程
     */
    async renderDebateFlow(container, data, duration = null) {
        const { bull_argument, bear_argument, debate_judgment } = data;

        // 1. Bull 發言
        await this.delay(300);
        this.appendToContainer(container, this.renderDialogue('bull', '看多觀點', bull_argument));
        await this.typewriterEffect(container.querySelector('.debate-dialogue:last-child .dialogue-content'), bull_argument);

        // 2. Bear 發言
        await this.delay(800);
        this.appendToContainer(container, this.renderDialogue('bear', '看空觀點', bear_argument));
        await this.typewriterEffect(container.querySelector('.debate-dialogue:last-child .dialogue-content'), bear_argument);

        // 3. 用戶投票
        await this.delay(500);
        this.appendToContainer(container, this.renderVotingSection(data.symbol, duration));
        lucide.createIcons();

        // 4. 等待用戶投票或自動顯示結果
        // 投票結果會在用戶點擊後顯示
        this.pendingJudgment = { container, debate_judgment, duration };
    },

    /**
     * 渲染對話氣泡
     */
    renderDialogue(character, title, content) {
        const char = this.characters[character];
        const isLeft = character === 'bull';

        return `
            <div class="debate-dialogue flex gap-4 mb-6 animate-fade-in ${isLeft ? '' : 'flex-row-reverse'}">
                <div class="flex-shrink-0">
                    ${char.avatar}
                </div>
                <div class="flex-1 max-w-[80%]">
                    <div class="flex items-center gap-2 mb-2 ${isLeft ? '' : 'flex-row-reverse'}">
                        <span class="font-bold ${char.textColor}">${char.nameZh}</span>
                        <span class="text-xs text-textMuted">${title}</span>
                    </div>
                    <div class="bg-gradient-to-br ${char.bgGradient} rounded-2xl ${isLeft ? 'rounded-tl-sm' : 'rounded-tr-sm'} p-4 border ${char.borderColor}">
                        <p class="dialogue-content text-sm text-secondary leading-relaxed"></p>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * 渲染投票區域
     */
    renderVotingSection(symbol, duration = null) {
        const timeInfo = duration ?
            `<div class="text-center mb-2">
                <p class="text-xs text-textMuted/70">⏱️ 分析耗時: ${duration} 秒</p>
             </div>` : '';

        return `
            <div class="debate-voting bg-surface/50 rounded-2xl p-6 border border-white/10 my-6 animate-fade-in">
                <div class="text-center mb-4">
                    <h4 class="font-serif text-lg text-secondary mb-1">你支持誰的觀點？</h4>
                    <p class="text-xs text-textMuted">投票後查看 AI 裁判的最終判決</p>
                </div>
                ${timeInfo}
                <div class="grid grid-cols-2 gap-4">
                    <button onclick="DebateTheater.vote('bull')" class="vote-btn group p-4 rounded-xl border-2 border-success/30 hover:border-success hover:bg-success/10 transition-all duration-300">
                        <div class="text-3xl mb-2">🐂</div>
                        <p class="font-bold text-success">支持看多</p>
                        <p class="text-xs text-textMuted mt-1">Bull Warrior</p>
                    </button>
                    <button onclick="DebateTheater.vote('bear')" class="vote-btn group p-4 rounded-xl border-2 border-danger/30 hover:border-danger hover:bg-danger/10 transition-all duration-300">
                        <div class="text-3xl mb-2">🐻</div>
                        <p class="font-bold text-danger">支持看空</p>
                        <p class="text-xs text-textMuted mt-1">Bear Analyst</p>
                    </button>
                </div>
                <button onclick="DebateTheater.skipVote()" class="w-full mt-4 py-2 text-xs text-textMuted hover:text-secondary transition">
                    跳過投票，直接看結果
                </button>
            </div>
        `;
    },

    /**
     * 用戶投票
     */
    vote(side) {
        this.userVote = side;

        // 更新按鈕狀態
        document.querySelectorAll('.vote-btn').forEach(btn => {
            btn.disabled = true;
            btn.classList.add('opacity-50');
        });

        const selectedBtn = event.currentTarget;
        selectedBtn.classList.remove('opacity-50');
        selectedBtn.classList.add('ring-2', side === 'bull' ? 'ring-success' : 'ring-danger');

        // 顯示裁判結果
        this.showJudgment();
    },

    /**
     * 跳過投票
     */
    skipVote() {
        this.userVote = null;
        document.querySelector('.debate-voting')?.remove();
        this.showJudgment();
    },

    /**
     * 顯示裁判結果
     */
    async showJudgment() {
        if (!this.pendingJudgment) return;

        const { container, debate_judgment, duration } = this.pendingJudgment;
        const { bull_score, bear_score, final_recommendation, reasoning } = debate_judgment;

        // 移除投票區域
        document.querySelector('.debate-voting')?.remove();

        // 計算勝負
        const winner = bull_score > bear_score ? 'bull' : 'bear';
        const totalScore = bull_score + bear_score;
        const bullPct = Math.round((bull_score / totalScore) * 100);
        const bearPct = 100 - bullPct;

        // 用戶是否猜對
        const userCorrect = this.userVote === winner;

        await this.delay(300);

        // 時間統計信息
        const timeInfo = duration ?
            `<div class="mt-4 p-3 rounded-xl bg-surface border border-white/10">
                <div class="flex items-center gap-2 text-sm">
                    <span class="text-primary">⏱️</span>
                    <span class="text-textMuted">分析耗時: <span class="text-secondary font-mono">${duration} 秒</span></span>
                </div>
            </div>` : '';

        // 渲染裁判發言
        this.appendToContainer(container, `
            <div class="debate-judgment animate-fade-in">
                <!-- 裁判頭像和標題 -->
                <div class="flex items-center gap-4 mb-4">
                    ${this.characters.judge.avatar}
                    <div>
                        <h4 class="font-bold text-primary">AI 裁判判決</h4>
                        <p class="text-xs text-textMuted">綜合分析雙方論點</p>
                    </div>
                </div>

                <!-- 分數條 -->
                <div class="bg-surface rounded-xl p-4 border border-white/10 mb-4">
                    <div class="flex justify-between text-sm mb-2">
                        <span class="text-success font-bold">🐂 ${bull_score} 分</span>
                        <span class="text-danger font-bold">${bear_score} 分 🐻</span>
                    </div>
                    <div class="h-3 bg-white/10 rounded-full overflow-hidden flex">
                        <div class="h-full bg-gradient-to-r from-success to-emerald-400 transition-all duration-1000" style="width: ${bullPct}%"></div>
                        <div class="h-full bg-gradient-to-r from-rose-400 to-danger transition-all duration-1000" style="width: ${bearPct}%"></div>
                    </div>
                    <div class="flex justify-between text-xs text-textMuted mt-1">
                        <span>${bullPct}%</span>
                        <span>${bearPct}%</span>
                    </div>
                </div>

                <!-- 最終建議 -->
                <div class="bg-gradient-to-br ${winner === 'bull' ? 'from-success/20 to-success/5 border-success/30' : 'from-danger/20 to-danger/5 border-danger/30'} rounded-xl p-4 border mb-4">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-2xl">${winner === 'bull' ? '🐂' : '🐻'}</span>
                        <span class="font-bold ${winner === 'bull' ? 'text-success' : 'text-danger'}">${winner === 'bull' ? '看多方勝出' : '看空方勝出'}</span>
                    </div>
                    <p class="text-sm text-secondary">${final_recommendation}</p>
                </div>

                <!-- 裁判理由 -->
                <div class="bg-surface/50 rounded-xl p-4 border border-white/5">
                    <p class="text-xs text-textMuted mb-2">裁判理由：</p>
                    <p class="text-sm text-secondary/80 leading-relaxed">${reasoning}</p>
                </div>

                ${this.userVote ? `
                <!-- 用戶投票結果 -->
                <div class="mt-4 p-4 rounded-xl ${userCorrect ? 'bg-success/10 border border-success/30' : 'bg-white/5 border border-white/10'}">
                    <div class="flex items-center gap-2">
                        <span class="text-xl">${userCorrect ? '🎯' : '💡'}</span>
                        <span class="text-sm ${userCorrect ? 'text-success' : 'text-textMuted'}">
                            ${userCorrect ? '恭喜！你的判斷與 AI 裁判一致！' : '這次與裁判判斷不同，但市場總有不同聲音'}
                        </span>
                    </div>
                </div>
                ` : ''}

                ${timeInfo}
            </div>
        `);

        lucide.createIcons();
        this.pendingJudgment = null;
    },

    /**
     * 打字機效果
     */
    async typewriterEffect(element, text, speed = 15) {
        if (!element) return;
        element.textContent = '';

        for (let i = 0; i < text.length; i++) {
            element.textContent += text[i];
            if (i % 3 === 0) { // 每3個字符滾動一次，減少性能消耗
                element.closest('.debate-dialogue')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
            await this.delay(speed);
        }
    },

    /**
     * 工具函數
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    appendToContainer(container, html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        while (div.firstChild) {
            container.appendChild(div.firstChild);
        }
        container.scrollTop = container.scrollHeight;
    }
};

// 全局導出
window.DebateTheater = DebateTheater;

/**
 * 在 Chat 中啟動辯論模式
 */
async function startDebateInChat(symbol) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    // 添加用戶消息
    appendMessage('user', `分析 ${symbol} 的多空觀點`);

    // 創建辯論容器
    const debateContainer = document.createElement('div');
    debateContainer.className = 'debate-container bg-background/50 rounded-2xl p-4 my-4 border border-white/5';
    container.appendChild(debateContainer);

    // 開始辯論
    await DebateTheater.startDebate(symbol, debateContainer);
}

// 全局導出
window.startDebateInChat = startDebateInChat;
