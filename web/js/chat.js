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
            actionsDiv.className = 'flex gap-2 mt-3 pt-3 border-t border-slate-700/50';
            actionsDiv.innerHTML = `
                <button onclick="showDebate('${symbol}')" class="text-xs bg-purple-900/30 text-purple-400 px-2 py-1 rounded hover:bg-purple-900/50 border border-purple-500/30 transition flex items-center gap-1">
                    <i data-lucide="swords" class="w-3 h-3"></i> 觀看辯論
                </button>
                <button onclick="showChart('${symbol}'); switchTab('watchlist');" class="text-xs bg-blue-900/30 text-blue-400 px-2 py-1 rounded hover:bg-blue-900/50 border border-blue-500/30 transition flex items-center gap-1">
                    <i data-lucide="bar-chart" class="w-3 h-3"></i> K線圖
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
        <div class="bot-message message-bubble prose">
            <h3 class="flex items-center gap-2"><i data-lucide="bot" class="w-5 h-5"></i> 歡迎使用 Pi Crypto Insight</h3>
            <p>對話已重置。我是您的 AI 投資助手，請輸入加密貨幣代號（如 BTC, ETH, PI）開始分析。</p>
            <div class="flex wrap gap-2 mt-2">
                <button onclick="quickAsk('PIUSDT 可以投資嗎？')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs border border-slate-700 transition">Pi Network (PI) 分析</button>
                <button onclick="quickAsk('比特幣現在適合買入嗎？')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs border border-slate-700 transition">BTC 行情預測</button>
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

    // New: Get execution options
    const marketType = document.getElementById('select-market-type').value;
    const autoExecute = document.getElementById('toggle-auto-execute').checked;

    // Pre-check: If auto-execute is on, ensure we have some indicator of keys
    if (autoExecute) {
        const totalEquity = document.getElementById('total-equity').innerText;
        if (totalEquity === "---" || totalEquity === "0.00") {
            if (!confirm("偵測到您尚未設定 API Key 或餘額不足。自動交易將無法執行，是否仍要繼續僅進行分析？")) {
                return;
            }
        }
    }

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
        <div class="loading-container">
            <div class="spinner"></div>
            <span>AI 思考中...</span>
            <span id="loading-timer">⏱️ 0.0 秒</span>
        </div>
    `;

    const timerSpan = botMsgDiv.querySelector('#loading-timer');
    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        timerSpan.textContent = `⏱️ ${elapsed} 秒`;
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
                                    stepsHtml += `<div class="mt-3 mb-2 text-blue-400 font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
                                } else if (trimmed.startsWith('**🐂') || trimmed.startsWith('**🐻') || trimmed.startsWith('**⚖️')) {
                                    stepsHtml += `<div class="mt-2 font-medium text-slate-300">${md.renderInline(trimmed)}</div>`;
                                } else if (trimmed.startsWith('>')) {
                                    stepsHtml += `<div class="pl-3 border-l-2 border-slate-600 text-slate-400 text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
                                } else if (trimmed.startsWith('→')) {
                                    stepsHtml += `<div class="pl-4 text-slate-500 text-xs">${trimmed}</div>`;
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
                            html += `<div class="text-slate-500 text-sm animate-pulse mt-4">⏳ 正在生成分析報告...</div>`;
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
                                    stepsHtml += `<div class="mt-3 mb-2 text-blue-400 font-semibold text-sm">${md.renderInline(trimmed.replace(/^---\s*/, '').replace(/^###\s*/, ''))}</div>`;
                                } else if (trimmed.startsWith('**🐂') || trimmed.startsWith('**🐻') || trimmed.startsWith('**⚖️')) {
                                    stepsHtml += `<div class="mt-2 font-medium text-slate-300">${md.renderInline(trimmed)}</div>`;
                                } else if (trimmed.startsWith('>')) {
                                    stepsHtml += `<div class="pl-3 border-l-2 border-slate-600 text-slate-400 text-xs my-1">${md.renderInline(trimmed.substring(1).trim())}</div>`;
                                } else if (trimmed.startsWith('→')) {
                                    stepsHtml += `<div class="pl-4 text-slate-500 text-xs">${trimmed}</div>`;
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
                                    <div class="mt-6 p-4 bg-blue-900/20 border border-blue-500/30 rounded-xl flex items-center justify-between">
                                        <div>
                                            <h4 class="text-sm font-bold text-blue-400">交易機會識別</h4>
                                            <p class="text-xs text-slate-400 mt-1">AI 建議: <span class="text-white font-mono">${pData.side.toUpperCase()} ${pData.symbol}</span></p>
                                        </div>
                                        <button onclick='showProposalModal(${proposalJson})' class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-lg shadow-lg shadow-blue-600/20 transition flex items-center gap-2">
                                            <i data-lucide="zap" class="w-4 h-4"></i> 執行交易
                                        </button>
                                    </div>
                                `;
                                finalHtml += btnHtml;
                            } catch (e) { console.error("Error parsing proposal", e); }
                        }

                        botMsgDiv.innerHTML = finalHtml;

                        const timeBadge = document.createElement('div');
                        timeBadge.className = 'done-badge';
                        timeBadge.innerHTML = `✅ 完成 ⏱️ ${totalTime} 秒`;
                        botMsgDiv.appendChild(timeBadge);

                        const disclaimer = document.createElement('div');
                        disclaimer.className = 'mt-3 pt-3 border-t border-slate-700/50 text-[10px] text-slate-500 italic';
                        disclaimer.innerHTML = '⚠️ 免責聲明：以上分析由 AI 自動生成，僅供參考，不構成投資建議。投資決策請自行判斷，盈虧自負。';
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
