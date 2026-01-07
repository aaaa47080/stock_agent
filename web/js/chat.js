// ========================================
// chat.js - 聊天功能
// ========================================

function appendMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message-bubble ${role === 'user' ? 'user-message' : 'bot-message prose'}`;

    if (role === 'bot') {
        div.innerHTML = md.render(content);
        const match = content.match(/\b([A-Z]{2,5})\b/);
        if (match && !content.includes('載入中') && !content.includes('Error')) {
            const symbol = match[1];
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'flex gap-2 mt-4 pt-4 border-t border-white/5';
            actionsDiv.innerHTML = `
                <button onclick="showDebate('${symbol}')" class="text-xs bg-accent/10 text-accent px-3 py-1.5 rounded-full hover:bg-accent/20 border border-accent/20 transition flex items-center gap-1.5">
                    <i data-lucide="swords" class="w-3 h-3"></i> Debate
                </button>
                <button onclick="showChart('${symbol}'); switchTab('watchlist');" class="text-xs bg-primary/10 text-primary px-3 py-1.5 rounded-full hover:bg-primary/20 border border-primary/20 transition flex items-center gap-1.5">
                    <i data-lucide="bar-chart" class="w-3 h-3"></i> Chart
                </button>
            `;
            div.appendChild(actionsDiv);
            setTimeout(() => lucide.createIcons(), 0);
        }
    } else {
        div.textContent = content;
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function toggleOptions() {
    const panel = document.getElementById('analysis-options-panel');
    panel.classList.toggle('hidden');
    lucide.createIcons();
}

async function clearChat() {
    if (!confirm("確定要清除所有對話紀錄嗎？")) return;

    try {
        await fetch('/api/chat/clear', { method: 'POST' });
        const container = document.getElementById('chat-messages');

        container.innerHTML = `
        <div class="bot-message opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; animation-fill-mode: forwards;">
            <p class="font-serif text-2xl md:text-3xl leading-tight text-secondary mb-4">
                Chat cleared. <br>
                Ready for new analysis.
            </p>
            <p class="text-textMuted text-lg font-light leading-relaxed">
                What would you like to analyze today?
            </p>
            <div class="flex flex-wrap gap-3 mt-8">
                <button onclick="quickAsk('Analyze BTC trend')" class="px-5 py-2.5 rounded-full bg-surface hover:bg-surfaceHighlight border border-white/5 text-sm text-textMuted hover:text-primary transition shadow-sm">
                    Bitcoin Trend
                </button>
                <button onclick="quickAsk('ETH Funding Rates')" class="px-5 py-2.5 rounded-full bg-surface hover:bg-surfaceHighlight border border-white/5 text-sm text-textMuted hover:text-primary transition shadow-sm">
                    ETH Rates
                </button>
            </div>
        </div>`;

        lucide.createIcons();
    } catch (e) {
        console.error(e);
        alert("清除失敗");
    }
}

async function sendMessage() {
    const input = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const text = input.value.trim();
    if (!text || isAnalyzing) return;

    // 檢查用戶是否有設置 API key（從 localStorage）
    const userKey = window.APIKeyManager?.getCurrentKey();

    if (!userKey) {
        const providerName = '任何 LLM API';
        alert(`❌ 未設置 API Key\n\n請先在系統設定中輸入您的 ${providerName} Key 才能使用分析功能。\n\n您需要自己的 OpenAI、Google Gemini 或 OpenRouter API Key。`);

        // 自動開啟設定面板
        if (typeof openSettings === 'function') {
            openSettings();
        }
        return;
    }

    const checkboxes = document.querySelectorAll('.analysis-checkbox:checked');
    const selection = Array.from(checkboxes).map(cb => cb.value);

    // Default execution options (simplified UI)
    const marketType = 'spot';
    const autoExecute = false;

    input.value = '';
    appendMessage('user', text);
    isAnalyzing = true;

    input.disabled = true;
    sendBtn.disabled = true;
    input.classList.add('opacity-50');
    sendBtn.classList.add('opacity-50', 'cursor-not-allowed');

    const botMsgDiv = appendMessage('bot', '');
    const startTime = Date.now();
    let timerInterval;

    botMsgDiv.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dots flex gap-1">
                <span></span><span></span><span></span>
            </div>
            <span class="text-sm text-textMuted ml-2">Thinking...</span>
            <span id="loading-timer" class="text-xs font-mono text-textMuted/50 ml-auto">0.0s</span>
        </div>
    `;

    const timerSpan = botMsgDiv.querySelector('#loading-timer');
    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        timerSpan.textContent = `${elapsed}s`;
    }, 100);

    // Create AbortController
    window.currentAnalysisController = new AbortController();

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                manual_selection: selection,
                market_type: marketType,
                auto_execute: autoExecute,
                // 傳送用戶的 API key
                user_api_key: userKey.key,
                user_provider: userKey.provider
            }),
            signal: window.currentAnalysisController.signal
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let processContent = '';
        let resultContent = '';
        let hasProcessContent = false;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));
                    console.log('[DEBUG] Received:', data); // 調試輸出
                    if (data.content) {
                        fullContent += data.content;
                        console.log('[DEBUG] fullContent length:', fullContent.length); // 調試輸出
                        processContent = '';
                        resultContent = '';
                        hasProcessContent = false;

                        const contentLines = fullContent.split('\n');
                        let currentMode = 'normal';

                        for (const cLine of contentLines) {
                            if (cLine.includes('[PROCESS_START]')) { currentMode = 'process'; hasProcessContent = true; continue; }
                            if (cLine.includes('[PROCESS_END]')) { currentMode = 'normal'; continue; }
                            if (cLine.includes('[RESULT]')) { currentMode = 'result'; continue; }
                            if (cLine.startsWith('[PROCESS]')) { processContent += cLine.substring(9) + '\n'; hasProcessContent = true; }
                            else if (currentMode === 'process') { processContent += cLine + '\n'; }
                            else if (currentMode === 'result') { resultContent += cLine + '\n'; }
                            else { resultContent += cLine + '\n'; }
                        }

                        let html = '';
                        const isStillProcessing = !fullContent.includes('[RESULT]');
                        console.log('[DEBUG] hasProcessContent:', hasProcessContent, 'processContent length:', processContent.length); // 調試輸出

                        if (hasProcessContent && processContent.trim()) {
                            const stepCount = (processContent.match(/✅|📊|⚔️|👨‍⚖️|⚖️|🛡️|💰|🚀|🔍|⏳/g) || []).length;
                            const openAttr = isStillProcessing ? 'open' : '';
                            const processLines = processContent.trim().split('\n').filter(l => l.trim());
                            let stepsHtml = '';
                            for (const line of processLines) {
                                const trimmed = line.trim();
                                if (trimmed.startsWith('---') || trimmed.startsWith('###')) {
                                    stepsHtml += `<div class="mt-3 mb-2 text-accent font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
                                } else if (trimmed.startsWith('**🐂') || trimmed.startsWith('**🐻') || trimmed.startsWith('**⚖️')) {
                                    stepsHtml += `<div class="mt-2 font-medium text-secondary">${md.renderInline(trimmed)}</div>`;
                                } else if (trimmed.startsWith('>')) {
                                    stepsHtml += `<div class="pl-3 border-l-2 border-white/10 text-textMuted text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
                                } else if (trimmed.startsWith('→')) {
                                    stepsHtml += `<div class="pl-4 text-textMuted/60 text-xs">${trimmed}</div>`;
                                } else {
                                    stepsHtml += `<div class="process-step-item py-1">${md.renderInline(trimmed)}</div>`;
                                }
                            }

                            html += `
                                <details class="process-container" ${openAttr}>
                                    <summary>
                                        <i data-lucide="chevron-right" class="w-4 h-4 chevron"></i>
                                        ${isStillProcessing ? '<div class="spinner" style="width:14px;height:14px;border-width:2px;"></div>' : '<i data-lucide="check-circle" class="w-4 h-4 text-green-500"></i>'}
                                        分析過程 (${stepCount} 個步驟)${isStillProcessing ? ' - 進行中...' : ' - 已完成'}
                                        <span class="ml-auto text-xs text-slate-500">點擊展開/收起</span>
                                    </summary>
                                    <div class="process-content custom-scrollbar">${stepsHtml}</div>
                                </details>
                            `;
                        }

                        if (resultContent.trim()) {
                            html += `<div class="result-container prose">${md.render(resultContent)}</div>`;
                        } else if (!hasProcessContent) {
                            html = md.render(fullContent);
                        } else if (isStillProcessing) {
                            html += `<div class="text-textMuted text-sm animate-pulse mt-4">⏳ Generating report...</div>`;
                        }

                        botMsgDiv.innerHTML = html;
                        lucide.createIcons();
                        document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
                    }
                    if (data.done) {
                        clearInterval(timerInterval);
                        isAnalyzing = false;
                        const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);

                        processContent = '';
                        resultContent = '';
                        hasProcessContent = false;
                        const contentLines = fullContent.split('\n');
                        let currentMode = 'normal';
                        for (const cLine of contentLines) {
                            if (cLine.includes('[PROCESS_START]')) { currentMode = 'process'; hasProcessContent = true; continue; }
                            if (cLine.includes('[PROCESS_END]')) { currentMode = 'normal'; continue; }
                            if (cLine.includes('[RESULT]')) { currentMode = 'result'; continue; }
                            if (cLine.startsWith('[PROCESS]')) { processContent += cLine.substring(9) + '\n'; hasProcessContent = true; }
                            else if (currentMode === 'process') { processContent += cLine + '\n'; }
                            else if (currentMode === 'result') { resultContent += cLine + '\n'; }
                            else { resultContent += cLine + '\n'; }
                        }

                        let finalHtml = '';
                        if (hasProcessContent && processContent.trim()) {
                            const stepCount = (processContent.match(/✅|📊|⚔️|👨‍⚖️|⚖️|🛡️|💰|🚀|🔍|⏳/g) || []).length;
                            const processLines = processContent.trim().split('\n').filter(l => l.trim());
                            let stepsHtml = '';
                            for (const line of processLines) {
                                const trimmed = line.trim();
                                if (trimmed.startsWith('---') || trimmed.startsWith('###')) {
                                    stepsHtml += `<div class="mt-3 mb-2 text-accent font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
                                } else if (trimmed.startsWith('**🐂') || trimmed.startsWith('**🐻') || trimmed.startsWith('**⚖️')) {
                                    stepsHtml += `<div class="mt-2 font-medium text-secondary">${md.renderInline(trimmed)}</div>`;
                                } else if (trimmed.startsWith('>')) {
                                    stepsHtml += `<div class="pl-3 border-l-2 border-white/10 text-textMuted text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
                                } else if (trimmed.startsWith('→')) {
                                    stepsHtml += `<div class="pl-4 text-textMuted/60 text-xs">${trimmed}</div>`;
                                } else {
                                    stepsHtml += `<div class="process-step-item py-1">${md.renderInline(trimmed)}</div>`;
                                }
                            }

                            finalHtml += `
                                <details class="process-container">
                                    <summary>
                                        <i data-lucide="chevron-right" class="w-4 h-4 chevron"></i>
                                        <i data-lucide="check-circle" class="w-4 h-4 text-green-500"></i>
                                        分析過程 (${stepCount} 個步驟) - 已完成
                                        <span class="ml-auto text-xs text-slate-500">點擊展開/收起</span>
                                    </summary>
                                    <div class="process-content custom-scrollbar">${stepsHtml}</div>
                                </details>
                            `;
                        }
                        if (resultContent.trim()) {
                            finalHtml += `<div class="result-container prose">${md.render(resultContent)}</div>`;
                        } else if (!hasProcessContent) {
                            finalHtml = md.render(fullContent);
                        }

                        // Check for embedded trade proposal
                        const proposalMatch = fullContent.match(/<!-- TRADE_PROPOSAL_START (.*?) TRADE_PROPOSAL_END -->/);
                        if (proposalMatch) {
                            try {
                                const proposalJson = proposalMatch[1];
                                const pData = JSON.parse(proposalJson);
                                finalHtml = finalHtml.replace(proposalMatch[0], '');
                                const btnHtml = `
                                    <div class="mt-6 p-5 bg-surface rounded-2xl border border-primary/20 flex items-center justify-between">
                                        <div>
                                            <h4 class="text-sm font-bold text-primary">Trade Opportunity</h4>
                                            <p class="text-xs text-textMuted mt-1">AI Suggests: <span class="text-secondary font-mono">${pData.side.toUpperCase()} ${pData.symbol}</span></p>
                                        </div>
                                        <button onclick='showProposalModal(${proposalJson})' class="px-4 py-2.5 bg-primary hover:brightness-110 text-background text-sm font-bold rounded-xl shadow-lg shadow-primary/20 transition flex items-center gap-2">
                                            <i data-lucide="zap" class="w-4 h-4"></i> Execute
                                        </button>
                                    </div>
                                `;
                                finalHtml += btnHtml;
                            } catch (e) { console.error("Error parsing proposal", e); }
                        }

                        botMsgDiv.innerHTML = finalHtml;

                        const timeBadge = document.createElement('div');
                        timeBadge.className = 'mt-4 text-xs text-textMuted/60 font-mono';
                        timeBadge.innerHTML = `Completed in ${totalTime}s`;
                        botMsgDiv.appendChild(timeBadge);

                        const disclaimer = document.createElement('div');
                        disclaimer.className = 'mt-4 pt-4 border-t border-white/5 text-[10px] text-textMuted/40 italic';
                        disclaimer.innerHTML = 'Disclaimer: AI-generated analysis for reference only. Not financial advice.';
                        botMsgDiv.appendChild(disclaimer);
                        lucide.createIcons();
                    }
                    if (data.error) {
                        clearInterval(timerInterval);
                        botMsgDiv.innerHTML = `<span class="text-red-400">Error: ${data.error}</span>`;
                        isAnalyzing = false;
                    }
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') {
            console.log('Analysis aborted by user');
            botMsgDiv.innerHTML = '<span class="text-orange-400">已取消分析。</span>';
        } else {
            console.error(err);
            botMsgDiv.innerHTML = '<span class="text-red-400">連線失敗，請檢查後端伺服器。</span>';
        }
        clearInterval(timerInterval);
        isAnalyzing = false;
    } finally {
        window.currentAnalysisController = null;
        clearInterval(timerInterval);
        input.disabled = false;
        sendBtn.disabled = false;
        input.classList.remove('opacity-50');
        sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        input.focus();
    }
}
