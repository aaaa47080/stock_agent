// ========================================
// chat-hitl.js - Human-in-the-Loop 互動
// 職責：HITL modal、Pre-Research Card、Plan Card、submitHITLAnswer
// 依賴：chat-state.js
// ========================================


// ── HITL Web Mode ─────────────────────────────────────────────────────────────
// Stores context needed to resume the graph after user answers a HITL question

function showHITLModal(interruptData) {
    const modal = document.getElementById('hitl-modal');
    const questionEl = document.getElementById('hitl-question-text');
    const optionsEl = document.getElementById('hitl-options-container');
    const customInput = document.getElementById('hitl-custom-input');

    if (!modal) return;

    questionEl.textContent = interruptData.question || '請確認執行計畫';
    optionsEl.innerHTML = '';
    customInput.value = '';

    const options = interruptData.options || [];
    options.forEach((opt) => {
        const btn = document.createElement('button');
        btn.textContent = opt;
        btn.className =
            'w-full text-left px-5 py-3 rounded-2xl bg-background border border-white/5 text-secondary text-sm hover:border-primary/50 hover:bg-primary/5 transition';
        btn.onclick = () => window.submitHITLAnswer(opt);
        optionsEl.appendChild(btn);
    });

    modal.classList.remove('hidden');
    if (lucide) createIconsIn(modal);
}

function closeHITLModal() {
    const modal = document.getElementById('hitl-modal');
    if (modal) modal.classList.add('hidden');
}

// ── Pre-Research Card (pre_research HITL) ────────────────────────────────────

function renderPreResearchCard(idata, targetDiv) {
    console.log('[renderPreResearchCard] idata:', idata);
    if (!targetDiv) return;
    const summary = idata.research_summary || '';
    const message = idata.message || '已整理即時資料供您參考：';
    const question = idata.question || '有特別想深入的方向嗎？';

    // 若後端有 Q&A 回答，在主聊天顯示（純問答泡泡，不加 AI War Room 按鈕）
    if (idata.qa_question && idata.qa_answer) {
        const container = document.getElementById('chat-messages');
        if (container) {
            const qaDiv = document.createElement('div');
            qaDiv.className = 'message-bubble bot-bubble prose';
            // XSS Fix: 使用 SecurityUtils 清理 HTML
            const qRaw = window.md ? window.md.renderInline(idata.qa_question) : idata.qa_question;
            const aRaw = window.md ? window.md.render(idata.qa_answer) : idata.qa_answer;
            const qHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(qRaw) : qRaw;
            const aHtml = window.SecurityUtils ? window.SecurityUtils.sanitizeHTML(aRaw) : aRaw;
            qaDiv.innerHTML = `<p class="text-xs text-textMuted/60 mb-1">💬 ${qHtml}</p>${aHtml}`;
            container.appendChild(qaDiv);
            container.scrollTop = container.scrollHeight;
        }
    }

    // XSS Fix: 使用 SecurityUtils 清理 HTML
    const summaryRaw =
        summary && window.md
            ? window.md.render(summary)
            : summary
              ? summary.replace(/\n/g, '<br>')
              : '';
    const summaryHtml = window.SecurityUtils
        ? window.SecurityUtils.sanitizeHTML(summaryRaw)
        : summaryRaw;
    const messageRaw = window.md ? window.md.renderInline(message) : message;
    const messageHtml = window.SecurityUtils
        ? window.SecurityUtils.sanitizeHTML(messageRaw)
        : messageRaw;

    // Use a compact card if no summary is provided (e.g., follow-up Q&A)
    if (!summary) {
        targetDiv.innerHTML = `
            <div class="pre-research-card-compact rounded-2xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
                <div class="px-5 pt-4 pb-2">
                    <p class="text-sm text-secondary mb-2">${messageHtml}</p>
                    <p class="text-xs text-textMuted mb-2">${question}</p>
                </div>
                <div class="flex gap-2 px-5 py-3 border-t border-white/5 bg-background/30">
                    <button onclick="submitPreResearch()"
                        class="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border
                               border-primary/30 rounded-xl py-2 text-sm font-medium transition">
                        確認開始規劃
                    </button>
                    <!-- No cancel button needed in compact mode usually, but can keep -->
                </div>
            </div>`;
    } else {
        // Full card with summary
        targetDiv.innerHTML = `
            <div class="pre-research-card rounded-2xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
                <div class="px-5 pt-5 pb-4">
                    <p class="text-sm text-secondary mb-3">${messageHtml}</p>
                    <div class="prose prose-sm prose-invert max-w-none text-secondary leading-relaxed
                                max-h-72 overflow-y-auto bg-white/5 rounded-xl px-4 py-3 mb-4">
                        ${summaryHtml}
                    </div>
                    <p class="text-sm text-secondary mb-2">${question}</p>
                    <!-- Pre-Research Input Removed: Use main chat input -->
                </div>
                <div class="flex gap-2 px-5 py-4 border-t border-white/5 bg-background/30">
                    <button onclick="submitPreResearch()"
                        class="flex-1 bg-primary/20 hover:bg-primary/30 text-primary border
                               border-primary/30 rounded-xl py-2.5 text-sm font-medium transition">
                        開始規劃
                    </button>
                    <button onclick="window.submitHITLAnswer('取消')"
                        class="px-4 bg-white/5 hover:bg-white/10 text-secondary border
                               border-white/10 rounded-xl py-2.5 text-sm transition">
                        取消
                    </button>
                </div>
            </div>`;
    }

    if (window.lucide) createIconsIn(botMsgDiv);
}

window.submitPreResearch = function () {
    // No specific input from card anymore, just confirm.
    // If user wants to specify, they type in main chat.
    window.submitHITLAnswer('confirm');
};

// ── Removed client-side _isDiscussionQuestion check to rely on backend ──

// ── Plan Card (confirm_plan HITL) ──────────────────────────────────────────────

function renderPlanCard(interruptData, targetDiv) {
    if (!targetDiv) return;
    const plan = interruptData.plan || [];

    // 計畫為空時顯示錯誤訊息，不渲染空計畫卡
    if (plan.length === 0) {
        targetDiv.innerHTML = `
            <div class="rounded-2xl border border-red-500/20 bg-red-500/5 px-5 py-4 text-sm text-textMuted">
                ⚠️ 無法為此查詢建立執行計畫，請換個方式描述您的問題。
            </div>`;
        return;
    }

    const message = interruptData.message || '針對您的問題，我規劃了以下分析步驟：';

    const stepsHtml = plan
        .map(
            (t) => `
        <div class="plan-step flex items-center gap-3 py-2.5 px-3 rounded-xl hover:bg-white/5 transition"
             data-step="${t.step}" data-selected="true">
            <div class="plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10
                        flex items-center justify-center flex-shrink-0">
                <i data-lucide="check" class="w-3 h-3 text-primary"></i>
            </div>
            <span class="text-base leading-none">${t.icon || '🔧'}</span>
            <span class="text-sm text-secondary flex-1">${t.description || t.agent}</span>
        </div>`
        )
        .join('');

    // Negotiation Response as a clearer "Chat" element BEFORE the card
    const negotiationResponse = interruptData.negotiation_response
        ? `<div class="mb-4 text-base text-secondary leading-relaxed border-l-2 border-primary/40 pl-3">
             <span class="text-xs font-bold text-primary block mb-1">🤖 說明：</span>
             ${interruptData.negotiation_response}
           </div>`
        : '';

    targetDiv.innerHTML = `
        ${negotiationResponse}
        <div class="plan-card rounded-2xl border border-primary/20 bg-primary/5 overflow-hidden"
             id="active-plan-card">
            <div class="px-5 pt-5 pb-3">
                <div class="flex items-center gap-2 mb-3">
                    <div class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                        <i data-lucide="list-checks" class="w-4 h-4 text-primary"></i>
                    </div>
                    <span class="text-sm font-medium text-primary">AI 執行計畫</span>
                </div>
                
                <p class="text-sm text-textMuted mb-3">${message}</p>
                <div class="plan-steps space-y-0.5">${stepsHtml}</div>
                
                <!-- Negotiation Instructions (Shown in custom mode) -->
                <div id="plan-negotiate-container" class="hidden mt-3 pt-3 border-t border-white/5 animate-fade-in-up">
                    <p class="text-xs text-textMuted bg-white/5 px-3 py-2 rounded-lg border border-white/10">
                        <i data-lucide="info" class="w-3 h-3 inline mr-1"></i>
                        若需調整計畫（例如：「增加基本面分析」），請直接在下方<b>聊天輸入框</b>打字即可。
                    </p>
                </div>
            </div>
            <div class="plan-actions flex gap-2 px-5 py-4 border-t border-white/5 bg-background/30">
                <button id="plan-execute-btn" onclick="window.executePlan('all')"
                    class="flex-1 py-2.5 bg-primary hover:bg-primary/80 text-background font-bold
                           rounded-xl text-sm transition flex items-center justify-center gap-1.5">
                    <i data-lucide="play" class="w-4 h-4"></i>執行全部
                </button>
                <button id="plan-customize-btn" onclick="window.togglePlanCustomize()"
                    class="px-4 py-2.5 bg-white/5 hover:bg-white/10 text-textMuted rounded-xl
                           text-sm transition flex items-center gap-1.5 ${interruptData.negotiation_limit_reached ? 'hidden' : ''}"
                    ${interruptData.negotiation_limit_reached ? 'disabled' : ''}>
                    <i data-lucide="settings-2" class="w-4 h-4"></i>自訂/挑選
                </button>
                <button onclick="window.executePlan('cancel')"
                    class="px-4 py-2.5 bg-white/5 hover:bg-white/10 text-textMuted
                           hover:text-danger rounded-xl text-sm transition">
                    取消
                </button>
            </div>
        </div>`;
    if (lucide) createIconsIn(botMsgDiv);
}

window.togglePlanCustomize = function () {
    const card = document.getElementById('active-plan-card');
    if (!card) return;

    // Toggle class
    const isCustom = card.classList.toggle('plan-custom-mode');

    const executeBtn = document.getElementById('plan-execute-btn');
    const customizeBtn = document.getElementById('plan-customize-btn');
    const negotiateContainer = document.getElementById('plan-negotiate-container');

    if (isCustom) {
        // Show negotiation instruction
        if (negotiateContainer) negotiateContainer.classList.remove('hidden');

        // Enable clicking steps to toggle
        card.querySelectorAll('.plan-step').forEach((step) => {
            step.style.cursor = 'pointer';
            step.onclick = () => window.togglePlanStep(step);
        });

        // Update Buttons
        if (customizeBtn) {
            customizeBtn.innerHTML = '<i data-lucide="rotate-ccw" class="w-4 h-4"></i>重置';
            customizeBtn.classList.add('bg-primary/10', 'text-primary');
        }

        // Initial button state update
        window.updateCustomExecuteButton();
    } else {
        // Hide negotiation instruction
        if (negotiateContainer) {
            negotiateContainer.classList.add('hidden');
        }

        // Reset all steps to selected
        card.querySelectorAll('.plan-step').forEach((step) => {
            step.dataset.selected = 'true';
            step.style.cursor = '';
            step.onclick = null;
            step.classList.remove('opacity-40');
            const check = step.querySelector('.plan-check');
            if (check) {
                check.className =
                    'plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10 flex items-center justify-center flex-shrink-0';
                check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
            }
        });

        // Reset Buttons
        if (executeBtn) {
            executeBtn.onclick = () => window.executePlan('all');
            executeBtn.classList.remove('bg-white/10', 'text-white');
            executeBtn.classList.add('bg-primary', 'text-background');
            executeBtn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i>執行全部';
        }
        if (customizeBtn) {
            customizeBtn.innerHTML = '<i data-lucide="settings-2" class="w-4 h-4"></i>自訂/挑選';
            customizeBtn.classList.remove('bg-primary/10', 'text-primary');
        }
    }
    if (lucide) createIconsIn(document.getElementById('chat-messages'));
};

window.updateCustomExecuteButton = function () {
    const executeBtn = document.getElementById('plan-execute-btn');
    if (!executeBtn) return;

    // Main chat input is used for negotiation now, but execute button here is for "selected steps".
    // "execute_custom" action sends { selected_steps: [...] }.

    executeBtn.onclick = () => window.executePlan('custom');

    // Style remains Primary for execution
    executeBtn.classList.remove('bg-white/10', 'text-white');
    executeBtn.classList.add('bg-primary', 'text-background');
    executeBtn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i>執行已選步驟';

    createIconsIn(executeBtn);
};

window.togglePlanStep = function (step) {
    const wasSelected = step.dataset.selected === 'true';
    const nowSelected = !wasSelected;
    step.dataset.selected = String(nowSelected);
    step.classList.toggle('opacity-40', !nowSelected);
    const check = step.querySelector('.plan-check');
    if (!check) return;
    if (nowSelected) {
        check.className =
            'plan-check w-5 h-5 rounded border border-primary/30 bg-primary/10 flex items-center justify-center flex-shrink-0';
        check.innerHTML = '<i data-lucide="check" class="w-3 h-3 text-primary"></i>';
        if (lucide) lucide.createIcons({ nodes: [check] });
    } else {
        check.className =
            'plan-check w-5 h-5 rounded border border-white/20 flex items-center justify-center flex-shrink-0';
        check.innerHTML = '';
    }
};

window.executePlan = function (mode) {
    if (mode === 'cancel') {
        window.submitHITLAnswer(JSON.stringify({ action: 'cancel' }));
        return;
    }
    if (mode === 'all') {
        window.submitHITLAnswer(JSON.stringify({ action: 'execute' }));
        return;
    }

    if (mode === 'custom') {
        // Check negotiation text first
        const input = document.getElementById('plan-negotiate-input');
        const text = input ? input.value.trim() : '';

        if (text) {
            window.submitHITLAnswer(JSON.stringify({ action: 'modify_request', text: text }));
            return;
        }

        const card = document.getElementById('active-plan-card');
        if (!card) {
            window.submitHITLAnswer('執行');
            return;
        }

        const selected = [];
        card.querySelectorAll('.plan-step').forEach((step) => {
            if (step.dataset.selected === 'true') selected.push(parseInt(step.dataset.step, 10));
        });

        if (selected.length === 0) {
            // Hint user to select something or cancel
            alert('請至少選擇一個步驟，或點擊「取消」');
            return;
        }

        window.submitHITLAnswer(
            JSON.stringify({ action: 'execute_custom', selected_steps: selected })
        );
    }
};

window.submitHITLAnswer = async function (answer) {
    if (!answer || !answer.trim()) return;
    if (!_hitlContext) return;

    closeHITLModal();

    const ctx = _hitlContext;
    _hitlContext = null;

    // ── History Preservation ──
    // Instead of overwriting the old bot message, we mark it as "done" by REMOVING the buttons
    // and create a NEW bot message for the response/next step.
    // ── History Preservation ──
    // Instead of overwriting the old bot message, we mark it as "done" by REMOVING the buttons

    // 1. Clean up specific context message if it exists
    if (ctx.botMsgDiv) {
        const oldBtns = ctx.botMsgDiv.querySelectorAll('button');
        oldBtns.forEach((b) => b.remove());
        const btnContainer = ctx.botMsgDiv.querySelector('.flex.gap-2.border-t');
        if (btnContainer) btnContainer.remove();

        const oldCard = ctx.botMsgDiv.querySelector('#active-plan-card');
        if (oldCard) oldCard.removeAttribute('id');
    }

    // 2. Force Clean: Remove ALL persistence buttons from previous HITL cards in the chat
    // This ensures even if context was lost, we don't leave active buttons.
    document
        .querySelectorAll(
            '.pre-research-card button, .plan-card button, .pre-research-card-compact button'
        )
        .forEach((btn) => {
            // If the button is not in the NEW botMsgDiv (which isn't created yet), remove it.
            // Since we haven't created the new div yet, ALL existing buttons are "old".
            const parent = btn.closest('.flex');
            if (
                parent &&
                parent.className.includes('gap-2') &&
                parent.className.includes('border-t')
            ) {
                parent.remove();
            } else {
                btn.remove();
            }
        });

    // Create NEW bot message for the response logic
    const botMsgDiv = appendMessage('bot', '');
    ctx.botMsgDiv = botMsgDiv; // Update context to point to new div for streaming

    // Initial "Thinking" UI
    botMsgDiv.innerHTML = `
        <div class="process-container" style="border-style: dashed; opacity: 0.7;">
            <div class="flex items-center gap-2 px-4 py-3">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-primary"></i>
                <span class="font-medium text-sm text-textMuted">AI 正在思考調研...</span>
            </div>
        </div>`;
    if (window.lucide) createIconsIn(botMsgDiv);

    const token = AuthManager.currentUser.accessToken;
    let fullContent = '';

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                message: ctx.originalMessage,
                session_id: ctx.sessionId,
                user_api_key: ctx.userKey.key,
                user_provider: ctx.userKey.provider,
                user_model: ctx.userSelectedModel,
                language: window.I18n?.getLanguage() || 'zh-TW',
                // Ensure resume_answer is an object if it's a JSON string
                resume_answer: (() => {
                    const trimmed = answer.trim();
                    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                        try {
                            return JSON.parse(trimmed);
                        } catch (e) {
                            return trimmed;
                        }
                    }
                    return trimmed;
                })(),
            }),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server Error (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            for (const line of chunk.split('\n')) {
                if (!line.startsWith('data: ')) continue;
                let data;
                try {
                    data = JSON.parse(line.substring(6));
                } catch {
                    continue;
                }

                if (data.type === 'hitl_question') {
                    // Nested HITL — reuse same context, dispatch by type
                    _hitlContext = ctx;
                    const idata = data.data || {};
                    _hitlContext.hitlType = idata.type;
                    if (idata.type === 'pre_research') {
                        renderPreResearchCard(idata, ctx.botMsgDiv);
                    } else if (idata.type === 'confirm_plan') {
                        renderPlanCard(idata, ctx.botMsgDiv);
                    } else {
                        // Inline clarification (no modal, no stale spinner)
                        const question = idata.question || '請問您具體想了解什麼？';
                        ctx.botMsgDiv.innerHTML = `
                            <div class="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                                <div class="px-5 py-4 flex items-start gap-3">
                                    <i data-lucide="help-circle" class="w-4 h-4 text-primary mt-0.5 flex-shrink-0"></i>
                                    <div>
                                        <p class="text-sm text-secondary">${question}</p>
                                        <p class="text-xs text-textMuted mt-1.5">請在下方輸入框回覆</p>
                                    </div>
                                </div>
                            </div>`;
                        if (window.lucide) lucide.createIcons({ nodes: [ctx.botMsgDiv] });
                    }
                    return;
                }
                if (data.waiting) return;

                if (data.content) {
                    fullContent += data.content;
                    if (ctx.botMsgDiv) {
                        ctx.botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, true, null);
                    }
                }
                if (data.done) {
                    if (ctx.botMsgDiv) {
                        const totalTime = ((Date.now() - ctx.startTime) / 1000).toFixed(1);
                        ctx.botMsgDiv.innerHTML = renderStoredBotMessage(
                            fullContent,
                            false,
                            totalTime
                        );
                        const badge = document.createElement('div');
                        badge.className = 'mt-4 text-xs text-textMuted/60 font-mono';
                        badge.textContent = `分析完成，耗時 ${totalTime}s`;
                        ctx.botMsgDiv.appendChild(badge);
                        if (lucide) createIconsIn(ctx.botMsgDiv);
                    }
                    isAnalyzing = false;
                    loadSessions();
                }
                if (data.error) {
                    if (ctx.botMsgDiv) {
                        ctx.botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${escapeHtml(data.error)}</span>`;
                    }
                    isAnalyzing = false;
                }
            }
        }
    } catch (err) {
        console.error('[HITL resume error]', err);
        if (ctx.botMsgDiv) {
            // Fix [object Object] by properly stringifying error detail if it's an object
            // XSS Fix: 使用 escapeHtml 转义错误消息
            const rawError =
                typeof err.message === 'object'
                    ? JSON.stringify(err.message)
                    : err.message || String(err);
            const errorMsg = escapeHtml(rawError);
            ctx.botMsgDiv.innerHTML = `<span class="text-red-400">恢復分析失敗：${errorMsg}</span>`;
        }
        isAnalyzing = false;
    } finally {
        const input = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        // 只有在 HITL 完全解決（_hitlContext=null）時才重新啟用輸入
        // 若後端再次 interrupt（Q&A 循環），_hitlContext 已被恢復，保持禁用
        if (_hitlContext === null) {
            isAnalyzing = false;
            if (input) {
                input.disabled = false;
                input.classList.remove('opacity-50');
                input.focus();
            }
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
    }
};
// ── End HITL ─────────────────────────────────────────────────────────────────
