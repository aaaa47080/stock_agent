// ========================================
// trade.js - 交易功能
// ========================================

function showProposalModal(data) {
    currentProposal = data;
    const modal = document.getElementById('proposal-modal');

    document.getElementById('prop-symbol').innerText = data.symbol;

    const sideEl = document.getElementById('prop-side');
    sideEl.innerText = data.side.toUpperCase();
    sideEl.className = `font-bold uppercase px-2 py-0.5 rounded text-xs ${['buy', 'long'].includes(data.side) ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`;

    document.getElementById('prop-market').innerText = `${data.market_type === 'spot' ? '現貨' : '合約'} ${data.leverage > 1 ? '(' + data.leverage + 'x)' : ''}`;

    const amountInput = document.getElementById('prop-amount');

    // Reset styles
    amountInput.classList.remove("border-yellow-500", "border-red-500", "border-white/10");
    amountInput.classList.add("border-white/10");

    let warningMsg = "";

    if (data.balance_status === "unknown") {
        amountInput.value = "";
        amountInput.placeholder = "請輸入金額";
        amountInput.classList.replace("border-white/10", "border-primary/50");
        warningMsg = "⚠️ 未連結錢包/未獲取餘額，請手動輸入";
    } else if (data.balance_status === "zero") {
        amountInput.value = "0";
        amountInput.classList.replace("border-white/10", "border-danger/50");
        warningMsg = "⚠️ 帳戶餘額為 0";
    } else {
        amountInput.value = data.amount;
        if (data.amount <= 0) {
            warningMsg = "⚠️ 建議倉位過小";
        }
    }

    // Update or insert warning message
    let warnEl = document.getElementById('prop-warning');
    if (!warnEl) {
        warnEl = document.createElement('div');
        warnEl.id = 'prop-warning';
        warnEl.className = 'text-[10px] mt-1 font-bold';
        amountInput.parentNode.appendChild(warnEl);
    }

    if (warningMsg) {
        warnEl.innerText = warningMsg;
        warnEl.className = 'text-[10px] mt-1 font-bold ' + (data.balance_status === 'zero' ? 'text-danger' : 'text-primary');
        warnEl.style.display = 'block';
        setTimeout(() => amountInput.focus(), 100);
    } else {
        warnEl.style.display = 'none';
    }

    document.getElementById('prop-sl').value = data.stop_loss || '';
    document.getElementById('prop-tp').value = data.take_profit || '';

    modal.classList.remove('hidden');
}

function closeProposalModal() {
    document.getElementById('proposal-modal').classList.add('hidden');
}

async function confirmTradeExecution() {
    if (!currentProposal) return;

    const btn = document.getElementById('btn-confirm-trade');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner w-4 h-4 border-2"></div> 執行中...';

    try {
        // ✅ 檢查是否有 OKX API 金鑰
        const okxKeyManager = window.OKXKeyManager;
        if (!okxKeyManager || !okxKeyManager.hasCredentials()) {
            alert('⚠️ 請先設置 OKX API 金鑰');
            btn.disabled = false;
            btn.innerHTML = originalText;
            return;
        }

        // Update proposal with user edits
        currentProposal.amount = parseFloat(document.getElementById('prop-amount').value);
        currentProposal.stop_loss = parseFloat(document.getElementById('prop-sl').value) || null;
        currentProposal.take_profit = parseFloat(document.getElementById('prop-tp').value) || null;

        // ✅ 獲取認證頭
        const authHeaders = okxKeyManager.getAuthHeaders();

        const res = await fetch('/api/trade/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authHeaders
            },
            body: JSON.stringify(currentProposal)
        });

        const data = await res.json();

        if (data.status === 'success') {
            alert(`✅ 交易成功！\n訂單ID: ${data.details.data ? data.details.data[0].ordId : 'Unknown'}`);
            closeProposalModal();
            refreshAssets();
        } else {
            alert(`❌ 交易失敗: ${data.error || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert('❌ 連線錯誤');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ========================================
// Backtest & Debate Functions
// ========================================

function openBacktestModal() {
    document.getElementById('backtest-modal').classList.remove('hidden');
}

async function runBacktest() {
    const symbol = document.getElementById('bt-symbol').value;
    const strategy = document.getElementById('bt-strategy').value;
    const resultDiv = document.getElementById('bt-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<div class="animate-pulse">回測中...</div>';
    try {
        const res = await fetch('/api/backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: symbol, signal_type: strategy, interval: '1h' }) });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const isProfitable = data.return_pct > 0;
        resultDiv.innerHTML = `<div class="flex justify-between items-center mb-2"><span class="font-bold text-secondary">${symbol} (${strategy})</span><span class="${isProfitable ? 'text-success' : 'text-danger'} font-bold">${data.return_pct.toFixed(2)}%</span></div><div class="grid grid-cols-2 gap-2 text-xs text-textMuted"><div>勝率: <span class="text-secondary">${data.win_rate.toFixed(1)}%</span></div><div>交易次數: <span class="text-secondary">${data.total_trades}</span></div><div>最大回撤: <span class="text-danger">${data.max_drawdown.toFixed(2)}%</span></div><div>淨利: <span class="${isProfitable ? 'text-success' : 'text-danger'}">$${(data.final_capital - data.initial_capital).toFixed(2)}</span></div></div>`;
    } catch (e) {
        resultDiv.innerHTML = `<span class="text-danger">回測失敗: ${e.message}</span>`;
    }
}

async function showDebate(symbol) {
    const modal = document.getElementById('debate-modal');
    const bullArg = document.getElementById('bull-arg');
    const bearArg = document.getElementById('bear-arg');
    const verdict = document.getElementById('judge-verdict');
    modal.classList.remove('hidden');
    document.getElementById('debate-symbol').textContent = symbol;
    bullArg.innerHTML = '<div class="animate-pulse">分析中...</div>';
    bearArg.innerHTML = '<div class="animate-pulse">分析中...</div>';
    verdict.innerHTML = '裁判審核中...';
    try {
        const res = await fetch(`/api/debate/${symbol}`);
        const data = await res.json();
        const bullScore = data.debate_judgment.bull_score;
        const bearScore = data.debate_judgment.bear_score;
        const bullPct = (bullScore / (bullScore + bearScore)) * 100;
        document.getElementById('score-bull').style.width = `${bullPct}%`;
        document.getElementById('score-bear').style.width = `${100 - bullPct}%`;
        document.getElementById('score-val-bull').textContent = bullScore;
        document.getElementById('score-val-bear').textContent = bearScore;
        const winnerBadge = document.getElementById('winner-badge');
        if (data.debate_judgment.winning_stance === 'Bull') {
            winnerBadge.textContent = '多頭勝出 🐂';
            winnerBadge.className = 'px-3 py-1 bg-success/20 text-success rounded-lg text-sm border border-success/30';
        }
        else if (data.debate_judgment.winning_stance === 'Bear') {
            winnerBadge.textContent = '空頭勝出 🐻';
            winnerBadge.className = 'px-3 py-1 bg-danger/20 text-danger rounded-lg text-sm border border-danger/30';
        }
        else {
            winnerBadge.textContent = '平局 ⚖️';
            winnerBadge.className = 'px-3 py-1 bg-surfaceHighlight text-textMuted rounded-lg text-sm border border-white/10';
        }
        bullArg.innerHTML = md.render(data.bull_argument.argument);
        bearArg.innerHTML = md.render(data.bear_argument.argument);
        verdict.innerHTML = md.render(data.debate_judgment.judge_rationale);
    } catch (e) { console.error(e); }
}

function closeDebate() {
    document.getElementById('debate-modal').classList.add('hidden');
}

// Export showDebate to window for global access
window.showDebate = showDebate;
