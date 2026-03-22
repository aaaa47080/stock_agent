// ========================================
// chat-analysis.js - 核心分析與訊息發送
// 職責：sendMessage、stopAnalysis、renderStoredBotMessage、流式輸出處理
// 依賴：chat-state.js, chat-sessions.js, chat-hitl.js
// ========================================


// ── Global Helper for Button Cleanup ─────────────────────────────────────────
// ── Global Helper for Button Cleanup ─────────────────────────────────────────
function cleanupStaleButtons() {
    // Target ALL buttons within the chat container to ensure thorough cleanup
    const chatBtns = document.querySelectorAll('#chat-messages button');
    chatBtns.forEach((btn) => {
        // If the button is inside a bordered action bar (common in our cards), remove the bar.
        // Otherwise just remove the button.
        const parent = btn.closest('.flex');
        if (parent && parent.className.includes('border-t')) {
            parent.remove();
        } else {
            btn.remove();
        }
    });
}
window.cleanupStaleButtons = cleanupStaleButtons;

function getSelectedAnalysisMode() {
    const select = document.getElementById('analysis-mode-select');
    return select?.value || 'quick';
}

async function refreshAnalysisModeSelector() {
    const select = document.getElementById('analysis-mode-select');
    if (!select) {
        return;
    }

    if (window.PiEnvironment?.shouldBlockProtectedRequests()) {
        Array.from(select.options).forEach((option) => {
            const allowed = option.value === 'quick';
            option.disabled = !allowed;
            option.dataset.locked = allowed ? 'false' : 'true';
            if (option.value === 'verified') {
                option.textContent = '已驗證（Premium）';
            } else if (option.value === 'research') {
                option.textContent = '深度研究（Premium）';
            }
        });
        select.dataset.allowedModes = 'quick';
        select.dataset.membershipTier = 'free';
        select.value = 'quick';
        return;
    }

    try {
        const data = await AppAPI.get('/api/analyze/modes');
        const allowedModes = Array.isArray(data.allowed_modes) ? data.allowed_modes : ['quick'];
        const defaultMode = typeof data.default_mode === 'string' ? data.default_mode : allowedModes[0] || 'quick';
        const tier = typeof data.current_tier === 'string' ? data.current_tier : 'free';

        Array.from(select.options).forEach((option) => {
            const allowed = allowedModes.includes(option.value);
            option.disabled = !allowed;
            option.dataset.locked = allowed ? 'false' : 'true';
            if (option.value === 'verified') {
                option.textContent = allowed ? '已驗證' : '已驗證（Premium）';
            } else if (option.value === 'research') {
                option.textContent = allowed ? '深度研究' : '深度研究（Premium）';
            }
        });

        select.dataset.allowedModes = allowedModes.join(',');
        select.dataset.membershipTier = tier;

        if (!allowedModes.includes(select.value)) {
            select.value = defaultMode;
        }
    } catch (error) {
        console.warn('Failed to refresh analysis modes:', error);
    }
}

window.getSelectedAnalysisMode = getSelectedAnalysisMode;
window.refreshAnalysisModeSelector = refreshAnalysisModeSelector;

function renderResponseMetadata(metadata = {}) {
    const mode = metadata.analysis_mode || 'quick';
    const verificationStatus = metadata.verification_status || mode;
    const usedTools = Array.isArray(metadata.used_tools) ? metadata.used_tools : [];
    const parts = [
        `<span>模式: ${escapeHtml(mode)}</span>`,
        `<span>驗證: ${escapeHtml(verificationStatus)}</span>`,
    ];

    if (metadata.data_as_of) {
        parts.push(`<span>資料時間: ${escapeHtml(String(metadata.data_as_of))}</span>`);
    }
    if (metadata.query_type) {
        parts.push(`<span>查詢類型: ${escapeHtml(String(metadata.query_type))}</span>`);
    }
    if (metadata.resolved_market) {
        parts.push(`<span>市場: ${escapeHtml(String(metadata.resolved_market))}</span>`);
    }
    if (metadata.policy_path) {
        parts.push(`<span>路徑: ${escapeHtml(String(metadata.policy_path))}</span>`);
    }
    if (usedTools.length) {
        parts.push(`<span>工具: ${escapeHtml(usedTools.join(', '))}</span>`);
    }
    if (metadata.quality_fail_reason) {
        parts.push(`<span class="text-danger">原因: ${escapeHtml(metadata.quality_fail_reason)}</span>`);
    }

    return `<div class="mt-3 flex flex-wrap gap-2 text-[11px] text-textMuted/70 font-mono">${parts.map((part) => `<span class="px-2 py-1 rounded-full bg-white/5 border border-white/10">${part}</span>`).join('')}</div>`;
}
window.renderResponseMetadata = renderResponseMetadata;

async function sendMessage() {
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const text = input.value.trim();
    if (!text && !isAnalyzing) return; // Allow empty text if we are just stopping? No, stop is a separate click.

    // ── Global Cleanup ──
    // Force remove old buttons on any new interaction
    cleanupStaleButtons();

    // ── Input State Management for "Stop" capability ─────────────────────
    if (isAnalyzing) {
        // If we are in HITL pause (waiting for input), allow typing
        // But isAnalyzing is technically false during HITL pause (set in finally block)
        // Wait, in my previous edit, I set isAnalyzing = false in finally if hitlPaused.
        // So this block only runs if isAnalyzing is TRUE (streaming).
        // So clicking button here means STOP.

        // However, if the user hits ENTER in the input box...
        // If input is enabled (which it shouldn't be during streaming, but IS during HITL pause),
        // we need to check if we are actually in HITL mode.

        // Wait, if isAnalyzing is true, input SHOULD be disabled.
        // If isAnalyzing is false (HITL pause), we fall through to Start Analysis logic below.

        stopAnalysis();
        return;
    }

    // ── HITL Input Routing ───────────────────────────────────────────────
    // If we have a pending HITL context, this input is an answer/negotiation
    if (_hitlContext && _hitlContext.sessionId === currentSessionId) {
        const hitlType = _hitlContext.hitlType;

        // Clear input immediately
        input.value = '';

        // If it's a plan confirmation or pre_research, send the user's raw text
        // and let the backend's LLM determine if it's a question, modification, or confirmation.
        if (hitlType === 'confirm_plan' || hitlType === 'pre_research') {
            appendMessage('user', text);
            window.submitHITLAnswer(text);
            return;
        }

        // For other HITL types (e.g. simple clarification), send raw text
        appendMessage('user', text);
        window.submitHITLAnswer(text);
        return;
    }

    if (!text) return;

    // ── Start Analysis ───────────────────────────────────────────────────
    isAnalyzing = true;

    // Change Send button to Stop button
    sendBtn.classList.remove('bg-primary', 'hover:brightness-110');
    sendBtn.classList.add('bg-red-500', 'hover:bg-red-600', 'text-white');
    sendBtn.innerHTML = '<i data-lucide="square" class="w-4 h-4 fill-current"></i>'; // Stop icon
    if (window.lucide) lucide.createIcons({ nodes: [sendBtn] });

    // Disable Input but keep Button enabled (as Stop)
    input.disabled = true;
    input.classList.add('opacity-50');
    // sendBtn.disabled = true; // Don't disable, we need it for Stop

    // 檢查用戶是否有設置 API key（使用快取，避免每次發送都打後端）
    const userKey = await getCachedUserKey();

    if (!userKey) {
        resetChatUI(); // Helper to reset UI state
        showAlert({
            title: '未設置 API Key',
            message:
                '請先在系統設定中輸入您的 API Key 才能使用分析功能。\n\n您需要 OpenAI、Google Gemini 或 OpenRouter API Key。',
            type: 'warning',
            confirmText: '前往設定',
        }).then(() => {
            if (typeof switchTab === 'function') switchTab('settings');
        });
        return;
    }

    // Enable UI for sending (transition to analysis state)
    sendBtn.disabled = false;
    input.classList.remove('opacity-50');
    sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');

    const _sendIcon = sendBtn.querySelector('i[data-lucide]');
    // Note: We changed icon to Stop square earlier, so we don't want to reset it to arrow-up yet!
    // The previous code block was copy-pasted wrong.
    // We already set it to square icon at the top of function.

    // Remove the redundant error check block that was here.

    // Lazy Creation: 如果沒有 currentSessionId，先建立新的 Session
    if (!currentSessionId) {
        try {
            const userId = AuthManager.currentUser.user_id;

            // 這裡可以傳遞 title (e.g., text.substring(0, 20)) 但後端通常會預設為 New Chat 或由第一條訊息生成
            const createData = await AppAPI.post(
                `/api/chat/sessions?user_id=${encodeURIComponent(userId)}`,
            );
            currentSessionId = createData.session_id;

            // 刷新列表以顯示新對話
            // loadSessions();
        } catch (e) {
            console.error('Failed to create lazy session:', e);
            appendMessage('bot', '❌ 無法建立對話 Session，請稍後再試。');
            return;
        }
    }

    const userSelectedModel = window.APIKeyManager.getModelForProvider(userKey.provider);
    const checkboxes = document.querySelectorAll('.analysis-checkbox:checked');
    const selection = Array.from(checkboxes).map((cb) => cb.value);
    const marketType = 'spot';
    const autoExecute = false;
    const analysisMode = getSelectedAnalysisMode();

    input.value = '';
    appendMessage('user', text);

    const botMsgDiv = appendMessage('bot', '');
    const startTime = Date.now();
    let timerInterval;

    // 重置分析過程面板的展開狀態
    AppStore.set('lastProcessOpenState', false);
    window.lastProcessOpenState = false;

    // Initial "Proto-Process" UI to match the final analysis UI for seamless transition
    botMsgDiv.innerHTML = `
        <div class="process-container" style="border-style: dashed; opacity: 0.7;">
            <div class="flex items-center gap-2 px-4 py-3">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin text-primary"></i>
                <span class="font-medium text-sm text-textMuted">正在思考...</span>
                <span id="loading-timer" class="ml-auto text-xs font-mono text-textMuted/50">0.0s</span>
            </div>
        </div>
    `;

    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        window.ChatStreamUI.updateTimers(botMsgDiv, elapsed);
    }, 100);

    const ANALYSIS_REQUEST_TIMEOUT_MS = 300000;  // 5分鐘總超時
    const ANALYSIS_STREAM_IDLE_TIMEOUT_MS = 180000;  // 3分鐘閒置超時（避免慢速API被中斷）

AppStore.set('currentAnalysisController', new AbortController());
window.currentAnalysisController = AppStore.get('currentAnalysisController');
    let requestTimeoutId = null;
    let streamIdleTimeoutId = null;

    const clearAnalysisTimeouts = () => {
        if (requestTimeoutId) {
            clearTimeout(requestTimeoutId);
            requestTimeoutId = null;
        }
        if (streamIdleTimeoutId) {
            clearTimeout(streamIdleTimeoutId);
            streamIdleTimeoutId = null;
        }
    };

        const armStreamIdleTimeout = () => {
        if (streamIdleTimeoutId) clearTimeout(streamIdleTimeoutId);
        streamIdleTimeoutId = setTimeout(() => {
            if (AppStore.get('currentAnalysisController')) {
                AppStore.get('currentAnalysisController').abort(
                    new Error('STREAM_IDLE_TIMEOUT')
                );
            }
        }, ANALYSIS_STREAM_IDLE_TIMEOUT_MS);
    };

    // Pre-build HITL resume context (used if server sends hitl_question)
    const _hitlResumeContext = {
        originalMessage: text,
        sessionId: currentSessionId,
        userKey,
        userSelectedModel,
        botMsgDiv,
        startTime,
    };

    // Declared OUTSIDE try so finally can read it
    let hitlPaused = false;

    try {
        const token = AuthManager.currentUser.accessToken;
        requestTimeoutId = setTimeout(() => {
            if (AppStore.get('currentAnalysisController')) {
                AppStore.get('currentAnalysisController').abort(new Error('ANALYSIS_TIMEOUT'));
            }
        }, ANALYSIS_REQUEST_TIMEOUT_MS);

        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
                message: text,
                analysis_mode: analysisMode,
                manual_selection: selection,
                market_type: marketType,
                auto_execute: autoExecute,
                user_api_key: userKey.key,
                user_provider: userKey.provider,
                user_model: userSelectedModel,
                session_id: currentSessionId,
                language: window.I18n?.getLanguage() || 'zh-TW',
            }),
            signal: AppStore.get('currentAnalysisController').signal,
        });

        if (!response.ok) {
            let errorMsg = `Server Error (${response.status})`;
            try {
                const errorData = await response.json();
                if (errorData.detail) errorMsg = errorData.detail;
            } catch (e) {
                // If not JSON, try text
                const text = await response.text();
                if (text) errorMsg = text.substring(0, 100);
            }
            throw new Error(errorMsg);
        }

        // Backend 已經保存了用戶訊息並更新了標題，立即刷新列表以顯示新標題
        loadSessions();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let responseMetadata = null;
        let pendingBuffer = '';

        armStreamIdleTimeout();

        while (true) {
            const { value, done } = await reader.read();
            if (done || hitlPaused) break;

            armStreamIdleTimeout();
            const chunk = decoder.decode(value, { stream: true });
            const parsed = window.ChatStreamUI.consumeChunk(pendingBuffer, chunk);
            const lines = parsed.lines;
            pendingBuffer = parsed.pending;
            const currentElapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    let data;
                    try {
                        data = JSON.parse(line.substring(6));
                    } catch {
                        continue;
                    }

                    // ── HITL: server needs user input ──────────────────────
                    if (data.type === 'hitl_question') {
                        clearInterval(timerInterval);
                        clearAnalysisTimeouts();
                        _hitlContext = _hitlResumeContext;
                        const idata = data.data || {};
                        // Store HITL type for sendMessage routing
                        _hitlContext.hitlType = idata.type;

                        if (idata.type === 'pre_research') {
                            renderPreResearchCard(idata, botMsgDiv);
                        } else if (idata.type === 'confirm_plan') {
                            renderPlanCard(idata, botMsgDiv);
                        } else {
                            // Render clarification question inline (clear spinner, show question)
                            const question = idata.question || '請問您具體想了解什麼？';
                            botMsgDiv.innerHTML = `
                                <div class="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                                    <div class="px-5 py-4 flex items-start gap-3">
                                        <i data-lucide="help-circle" class="w-4 h-4 text-primary mt-0.5 flex-shrink-0"></i>
                                        <div>
                                            <p class="text-sm text-secondary">${question}</p>
                                            <p class="text-xs text-textMuted mt-1.5">請在下方輸入框回覆</p>
                                        </div>
                                    </div>
                                </div>`;
                            if (window.lucide) lucide.createIcons({ nodes: [botMsgDiv] });
                        }
                    }
                    if (data.waiting) {
                        hitlPaused = true;
                        break;
                    }

                    // ── Meta Update (Codebook ID) ───────────────────────────
                    if (data.type === 'meta') {
                        if (data.codebook_id) {
                            botMsgDiv.dataset.codebookId = data.codebook_id;
                        }
                    }

                    // ── Progress Update (Parallel Execution) ────────────────
                    if (data.type === 'progress') {
                        window.ChatStreamUI.applyProgress(botMsgDiv, data.data || {});
                    }

                    if (data.type === 'response_metadata') {
                        responseMetadata = data.data || null;
                    }

                    if (data.content) {
                        fullContent += data.content;
                        // 實時更新內容，傳入 isStreaming=true 和當前耗時
                        botMsgDiv.innerHTML = renderStoredBotMessage(
                            fullContent,
                            true,
                            currentElapsed
                        );
                    }

                    if (data.done) {
                        clearInterval(timerInterval);
                        clearAnalysisTimeouts();
                        isAnalyzing = false;
                        const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);

                        // Final render，傳入 isStreaming=false
                        botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, false, totalTime);
                        if (responseMetadata) {
                            botMsgDiv.insertAdjacentHTML('beforeend', renderResponseMetadata(responseMetadata));
                        }

                        const timeBadge = document.createElement('div');
                        timeBadge.className =
                            'mt-4 flex items-center justify-between text-xs text-textMuted/60 font-mono';

                        let feedbackHtml = '';
                        const codebookId = botMsgDiv.dataset.codebookId;
                        if (codebookId) {
                            feedbackHtml = `
                                <div class="flex items-center gap-2">
                                    <span class="opacity-50">分析品質回饋：</span>
                                    <button onclick="submitFeedback('${codebookId}', 1, this)" class="p-1 hover:text-success transition" title="有幫助">
                                        <i data-lucide="thumbs-up" class="w-3.5 h-3.5"></i>
                                    </button>
                                    <button onclick="submitFeedback('${codebookId}', -1, this)" class="p-1 hover:text-danger transition" title="需改進">
                                        <i data-lucide="thumbs-down" class="w-3.5 h-3.5"></i>
                                    </button>
                                </div>
                            `;
                        }

                        timeBadge.innerHTML = `<span>分析完成，耗時 ${totalTime}s</span>${feedbackHtml}`;
                        botMsgDiv.appendChild(timeBadge);
                        if (window.lucide) {
                            lucide.createIcons({ nodes: [botMsgDiv] });
                        }

                        // Refresh sessions list (to update title if it was new)
                        loadSessions();
                    }

                    if (data.error) {
                        clearInterval(timerInterval);
                        clearAnalysisTimeouts();
                        botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${escapeHtml(data.error)}</span>`;
                        isAnalyzing = false;
                    }
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            const abortReason = AppStore.get('currentAnalysisController')?.signal?.reason;
            if (abortReason instanceof Error && abortReason.message === 'ANALYSIS_TIMEOUT') {
                botMsgDiv.innerHTML =
                    '<span class="text-red-400">分析逾時，請縮小問題範圍後再試。</span>';
            } else if (
                abortReason instanceof Error &&
                abortReason.message === 'STREAM_IDLE_TIMEOUT'
            ) {
                botMsgDiv.innerHTML =
                    '<span class="text-red-400">分析流程中斷過久，已自動停止，請重試。</span>';
            } else {
                console.log('Analysis aborted by user');
                botMsgDiv.innerHTML = '<span class="text-orange-400">已取消分析。</span>';
            }
        } else {
            console.error(err);
            botMsgDiv.innerHTML = `<span class="text-red-400">${escapeHtml(err.message || '連線失敗，請檢查後端伺服器。')}</span>`;
        }
        clearInterval(timerInterval);
        clearAnalysisTimeouts();
        isAnalyzing = false;
    } finally {
        clearInterval(timerInterval);
        clearAnalysisTimeouts();

        if (hitlPaused) {
            // HITL paused: Unlock input so user can type negotiation/answer
            // But keep "Stop" button hidden or converted back to Send?
            // If we unlock input, user can type and hit Send.
            // sendMessage needs to handle this state.

            isAnalyzing = false; // Logically not "analyzing" (streaming), but waiting.
            const input = document.getElementById('user-input');
            const sendBtn = document.getElementById('send-btn');

            if (input) {
                input.disabled = false;
                input.classList.remove('opacity-50');
                input.focus();
                input.placeholder = '輸入回應或是調整計畫...';
            }
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove(
                    'opacity-50',
                    'cursor-not-allowed',
                    'bg-red-500',
                    'hover:bg-red-600',
                    'text-white'
                );
                sendBtn.classList.add('bg-primary', 'hover:brightness-110');
                sendBtn.innerHTML = '<i data-lucide="arrow-up" class="w-5 h-5"></i>'; // use Send icon
                if (window.lucide) lucide.createIcons({ nodes: [sendBtn] });
            }
        } else {
            // Normal finish or Abort
            resetChatUI();
        }
    }
}
window.sendMessage = sendMessage;

function stopAnalysis() {
    if (AppStore.get('currentAnalysisController')) {
        AppStore.get('currentAnalysisController').abort();
        AppStore.set('currentAnalysisController', null);
        window.currentAnalysisController = null;
    }

    // IMPORTANT: Clear HITL context so subsequent messages are treated as new queries
    window._hitlContext = null;

    // Append "Stopped" message
    const chatContainer = document.getElementById('chat-messages');
    if (chatContainer) {
        const stopMsg = document.createElement('div');
        stopMsg.className = 'flex justify-center my-4 opacity-0 animate-fade-in-up';
        stopMsg.style.animationFillMode = 'forwards';
        stopMsg.innerHTML =
            '<span class="px-3 py-1 rounded-full bg-red-500/10 text-red-500 text-xs font-mono border border-red-500/20">⛔ 分析已終止</span>';
        chatContainer.appendChild(stopMsg);
        setTimeout(() => (chatContainer.scrollTop = chatContainer.scrollHeight), 100);
    }

    resetChatUI();
}
window.stopAnalysis = stopAnalysis;

function resetChatUI() {
    isAnalyzing = false;
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    if (AppStore.get('currentAnalysisController')) {
        // If called directly (not via stopAnalysis), ensure we nullify
        // But usually stopAnalysis does the aborting.
    }

    if (input) {
        input.disabled = false;
        input.classList.remove('opacity-50');
        input.focus();
    }
    if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.classList.remove(
            'opacity-50',
            'cursor-not-allowed',
            'bg-red-500',
            'hover:bg-red-600',
            'text-white'
        );
        sendBtn.classList.add('bg-primary', 'hover:brightness-110');
        sendBtn.innerHTML = '<i data-lucide="arrow-up" class="w-5 h-5"></i>';
    }
    if (window.lucide) createIconsIn(sendBtn);
}
window.resetChatUI = resetChatUI;

// Reuse the renderStoredBotMessage function from previous step
function renderStoredBotMessage(fullContent, isStreaming = false, elapsedTime = null) {
    let processContent = '';
    let resultContent = '';
    let hasProcessContent = false;

    const contentLines = fullContent.split('\n');
    let currentMode = 'normal';

    for (const cLine of contentLines) {
        if (cLine.includes('[PROCESS_START]')) {
            currentMode = 'process';
            hasProcessContent = true;
            continue;
        }
        if (cLine.includes('[PROCESS_END]')) {
            currentMode = 'normal';
            continue;
        }
        if (cLine.includes('[RESULT]')) {
            currentMode = 'result';
            continue;
        }
        if (cLine.startsWith('[PROCESS]')) {
            processContent += cLine.substring(9) + '\n';
            hasProcessContent = true;
        } else if (currentMode === 'process') {
            processContent += cLine + '\n';
        } else if (currentMode === 'result') {
            resultContent += cLine + '\n';
        } else {
            resultContent += cLine + '\n';
        }
    }

    let html = '';
    if (hasProcessContent && processContent.trim()) {
        const stepCount = (processContent.match(/✅|📊|⚔️|👨‍⚖️|⚖️|🛡️|💰|🚀|🔍|⏳/g) || []).length;
        const processLines = processContent
            .trim()
            .split('\n')
            .filter((l) => l.trim());
        let stepsHtml = '';
        let hasTimeInfo = false;

        processLines.forEach((line, index) => {
            const trimmed = line.trim();
            const isLastLine = index === processLines.length - 1;

            // Determine content
            let lineContent = '';
            if (trimmed.startsWith('---') || trimmed.startsWith('###')) {
                lineContent = `<div class="mt-3 mb-2 text-accent font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
            } else if (
                trimmed.startsWith('**🐂') ||
                trimmed.startsWith('**🐻') ||
                trimmed.startsWith('**⚖️')
            ) {
                lineContent = `<div class="mt-2 font-medium text-secondary">${md.renderInline(trimmed)}</div>`;
            } else if (trimmed.startsWith('>')) {
                lineContent = `<div class="pl-3 border-l-2 border-white/10 text-textMuted text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
            } else if (trimmed.startsWith('→')) {
                lineContent = `<div class="pl-4 text-textMuted/60 text-xs">${trimmed}</div>`;
            } else if (trimmed.includes('⏱️ **分析完成**: 總耗時')) {
                hasTimeInfo = true;
                const timeMatch = trimmed.match(/⏱️ \*\*分析完成\*\*: 總耗時 ([\d.]+) 秒/);
                if (timeMatch) {
                    lineContent = `<div class="mt-2 p-3 rounded-xl bg-surface border border-white/10 flex items-center gap-2">
                                    <span class="text-primary">⏱️</span>
                                    <span class="text-textMuted">總耗時: <span class="text-secondary font-mono">${timeMatch[1]} 秒</span></span>
                                  </div>`;
                }
            } else {
                lineContent = `<div class="process-step-item py-1">${md.renderInline(trimmed)}</div>`;
            }

            // Append Loading Spinner to the last line if streaming
            if (isStreaming && isLastLine && !trimmed.includes('分析完成')) {
                const spinnerSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-loader-2 animate-spin inline-block ml-2 text-primary"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;

                // Check if it's a div wrapper (standard lines) or just text
                if (lineContent.includes('<div')) {
                    // Insert before the closing div
                    lineContent = lineContent.replace('</div>', ` ${spinnerSvg}</div>`);
                } else {
                    lineContent += ` ${spinnerSvg}`;
                }
            }
            stepsHtml += lineContent;
        });

        // 使用全局變量來跟蹤展開狀態
        const isCurrentlyOpen =
            AppStore.get('lastProcessOpenState') !== undefined ? AppStore.get('lastProcessOpenState') : true; // Default to open during analysis

        // 如果在步驟中沒有找到時間信息，則檢查完整內容
        let timeInfo = '';
        let timerHeader = '';

        if (!hasTimeInfo) {
            const timeMatch = fullContent.match(
                /\[PROCESS\]⏱️ \*\*分析完成\*\*: 總耗時 ([\d.]+) 秒/
            );
            if (timeMatch) {
                timeInfo = `<div class="mt-2 p-3 rounded-xl bg-surface border border-white/10 flex items-center gap-2">
                              <span class="text-primary">⏱️</span>
                              <span class="text-textMuted">總耗時: <span class="text-secondary font-mono">${timeMatch[1]} 秒</span></span>
                            </div>`;
            } else if (isStreaming && elapsedTime) {
                // Live Timer in Header - Reuses the ID so the interval keeps updating it
                timerHeader = `<span class="ml-2 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-mono flex items-center gap-1">
                                <i data-lucide="clock" class="w-3 h-3"></i> 
                                <span id="loading-timer">${elapsedTime}s</span>
                               </span>`;
            }
        }

        html += `
            <details class="process-container" ${isCurrentlyOpen ? 'open' : ''}>
                <summary onclick="toggleProcessState(this)">
                    <div class="flex items-center gap-2">
                        <i data-lucide="chevron-right" class="w-4 h-4 chevron"></i>
                        ${isStreaming ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-loader animate-spin text-primary"><path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/><path d="m16.2 16.2 2.9 2.9"/><path d="M12 18v4"/><path d="m4.9 19.1 2.9-2.9"/><path d="M2 12h4"/><path d="m4.9 4.9 2.9 2.9"/></svg>' : '<i data-lucide="check-circle" class="w-4 h-4 text-green-500"></i>'}
                        <span class="font-medium">分析過程</span>
                        ${timerHeader}
                    </div>
                    <span class="ml-auto text-xs text-textMuted/50">${stepCount} 個步驟</span>
                </summary>
                <div class="process-content custom-scrollbar pl-6 border-l border-white/5 ml-2 mt-2 space-y-1">
                    ${stepsHtml}
                </div>
                ${timeInfo}
            </details>
        `;
    }

    const renderMd = (text) => (md ? md.render(text) : `<pre>${text.replace(/</g, '&lt;')}</pre>`);

    if (resultContent.trim()) {
        html += `<div class="result-container prose mt-4">${renderMd(resultContent)}</div>`;
    } else if (!hasProcessContent) {
        let timerHtml = '';
        if (isStreaming && elapsedTime) {
            timerHtml = `<div class="flex items-center gap-2 mb-2 text-xs text-textMuted/50 font-mono">
                            <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>
                            <span id="loading-timer">${elapsedTime}s</span>
                          </div>`;
        }
        html = timerHtml + renderMd(fullContent);
    }

    const proposalMatch = fullContent.match(
        /<!-- TRADE_PROPOSAL_START (.*?) TRADE_PROPOSAL_END -->/
    );
    if (proposalMatch) {
        try {
            const proposalJson = proposalMatch[1];
            const pData = JSON.parse(proposalJson);
            html = html.replace(proposalMatch[0], '');
            const infoHtml = `
                <div class="mt-6 p-5 bg-surface rounded-2xl border border-white/10">
                    <h4 class="text-sm font-bold text-primary flex items-center gap-2">
                        <i data-lucide="lightbulb" class="w-4 h-4"></i>
                        AI 交易建議
                    </h4>
                    <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
                        <div class="bg-surfaceHighlight rounded-lg p-3">
                            <div class="text-textMuted">標的</div>
                            <div class="text-secondary font-bold font-mono">${pData.symbol}</div>
                        </div>
                        <div class="bg-surfaceHighlight rounded-lg p-3">
                            <div class="text-textMuted">方向</div>
                            <div class="font-bold ${pData.side === 'buy' || pData.side === 'long' ? 'text-success' : 'text-danger'}">${pData.side.toUpperCase()}</div>
                        </div>
                        ${pData.stop_loss ? `
                        <div class="bg-surfaceHighlight rounded-lg p-3">
                            <div class="text-textMuted">建議止損</div>
                            <div class="text-danger font-mono">${pData.stop_loss}</div>
                        </div>
                        ` : ''}
                        ${pData.take_profit ? `
                        <div class="bg-surfaceHighlight rounded-lg p-3">
                            <div class="text-textMuted">建議止盈</div>
                            <div class="text-success font-mono">${pData.take_profit}</div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="mt-3 text-xs text-textMuted">
                        ⚠️ 此僅為 AI 分析建議，不構成投資建議。實際交易請自行評估風險。
                    </div>
                </div>
            `;
            html += infoHtml;
        } catch (e) {
            console.error('Error parsing proposal', e);
        }
    }

    // Wrap <table> elements for proper overflow + border styling
    if (html.includes('<table')) {
        const temp = document.createElement('div');
        temp.innerHTML = html;
        temp.querySelectorAll('table').forEach((table) => {
            if (!table.parentElement.classList.contains('table-wrapper')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-wrapper';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
        html = temp.innerHTML;
    }

    return html;
}
window.renderStoredBotMessage = renderStoredBotMessage;

// 保存展開狀態的函數
function toggleProcessState(summaryElement) {
    // 獲取對應的 details 元素
    const detailsElement = summaryElement.parentElement;
    // 延遲執行以確保狀態已更新
    setTimeout(() => {
        // 更新狀態標記
        AppStore.set('lastProcessOpenState', detailsElement.open);
        window.lastProcessOpenState = AppStore.get('lastProcessOpenState');
    }, 0);
}
window.toggleProcessState = toggleProcessState;

export {
    cleanupStaleButtons,
    getSelectedAnalysisMode,
    refreshAnalysisModeSelector,
    renderResponseMetadata,
    sendMessage,
    stopAnalysis,
    resetChatUI,
    renderStoredBotMessage,
    toggleProcessState,
};
