// ========================================
// assets.js - 資產管理功能
// ========================================

async function refreshAssets() {
    const totalEl = document.getElementById('total-equity');
    const spotList = document.getElementById('spot-assets-list');
    const posTable = document.getElementById('positions-table-body');
    const summaryEl = document.getElementById('positions-summary');

    // Loading state
    totalEl.classList.add('animate-pulse');

    try {
        // ✅ 檢查是否有 OKX API 金鑰（BYOK 模式）
        const okxKeyManager = window.OKXKeyManager;
        if (!okxKeyManager || !okxKeyManager.hasCredentials()) {
            throw new Error("NO_OKX_KEY");
        }

        // ✅ 獲取認證頭
        const authHeaders = okxKeyManager.getAuthHeaders();

        // 1. Fetch Assets (帶上認證頭)
        const resAssets = await fetch('/api/account/assets', {
            headers: authHeaders
        });

        if (!resAssets.ok) {
            // 如果是 401 錯誤，說明金鑰無效或缺失
            if (resAssets.status === 401) {
                throw new Error("INVALID_OKX_KEY");
            }
            throw new Error("API_ERROR");
        }

        const assetsData = await resAssets.json();

        totalEl.innerText = assetsData.total_equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        totalEl.classList.remove('animate-pulse');
        document.getElementById('asset-update-time').innerText = new Date(assetsData.update_time).toLocaleTimeString();

        spotList.innerHTML = '';
        if (assetsData.details && assetsData.details.length > 0) {
            assetsData.details.slice(0, 5).forEach(asset => {
                const div = document.createElement('div');
                div.className = 'flex justify-between items-center text-sm';
                div.innerHTML = `
                    <div class="flex items-center gap-2">
                        <span class="font-bold text-white">${asset.currency}</span>
                        <span class="text-xs text-slate-500">${asset.available.toFixed(4)} 可用</span>
                    </div>
                    <div class="text-slate-300">$${asset.usd_value.toFixed(2)}</div>
                `;
                spotList.appendChild(div);
            });
        } else {
            spotList.innerHTML = '<div class="text-slate-500 text-xs">無資產餘額</div>';
        }

        // 2. Fetch Positions (帶上認證頭)
        const resPos = await fetch('/api/account/positions', {
            headers: authHeaders
        });
        if (!resPos.ok) {
            if (resPos.status === 401) {
                throw new Error("INVALID_OKX_KEY");
            }
            throw new Error("API_ERROR");
        }

        const posData = await resPos.json();

        posTable.innerHTML = '';
        summaryEl.innerHTML = '';

        if (posData.positions && posData.positions.length > 0) {
            let totalPnl = 0;

            posData.positions.forEach(pos => {
                const isLong = pos.side === 'long' || pos.size > 0;
                const pnlClass = pos.pnl >= 0 ? 'text-green-400' : 'text-red-400';
                const sideClass = isLong ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400';
                const sideText = pos.side === 'net' ? (pos.size > 0 ? '多' : '空') : (pos.side === 'long' ? '多' : '空');

                totalPnl += pos.pnl;

                const tr = document.createElement('tr');
                tr.className = 'border-b border-slate-700/50 hover:bg-slate-800/30 transition';
                tr.innerHTML = `
                    <td class="px-4 py-3 font-medium text-white">${pos.symbol}</td>
                    <td class="px-4 py-3">
                        <span class="text-[10px] px-1.5 py-0.5 rounded ${sideClass} border border-white/10 mr-1">${sideText}</span>
                        <span class="text-xs text-slate-400">${pos.leverage}x</span>
                    </td>
                    <td class="px-4 py-3 text-right font-mono">${Math.abs(pos.size)}</td>
                    <td class="px-4 py-3 text-right font-mono text-xs">$${pos.avg_price.toLocaleString()}</td>
                    <td class="px-4 py-3 text-right font-mono text-xs">$${pos.mark_price.toLocaleString()}</td>
                    <td class="px-4 py-3 text-right font-mono font-bold ${pnlClass}">
                        ${pos.pnl > 0 ? '+' : ''}${pos.pnl.toFixed(2)}
                        <div class="text-[10px] opacity-70">${pos.pnl_ratio.toFixed(2)}%</div>
                    </td>
                `;
                posTable.appendChild(tr);
            });

            summaryEl.innerHTML = `
                <div class="flex justify-between items-center text-sm mb-2">
                    <span class="text-slate-400">持倉數量</span>
                    <span class="text-white font-bold">${posData.positions.length}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-slate-400">未實現總盈虧</span>
                    <span class="${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} font-bold">${totalPnl > 0 ? '+' : ''}${totalPnl.toFixed(2)} USDT</span>
                </div>
            `;

        } else {
            posTable.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">尚無持倉數據</td></tr>';
            summaryEl.innerHTML = '<div class="text-slate-500 text-xs">無持倉</div>';
        }

    } catch (e) {
        console.error("Failed to fetch assets", e);
        totalEl.classList.remove('animate-pulse');
        totalEl.innerText = "---";

        const noKeyHtml = `
            <div class="flex flex-col items-center justify-center py-8 text-center h-full">
                <div class="bg-slate-800 p-3 rounded-full mb-3">
                    <i data-lucide="lock" class="w-6 h-6 text-amber-400"></i>
                </div>
                <h4 class="text-sm font-bold text-slate-200 mb-1">尚未綁定交易所</h4>
                <p class="text-xs text-slate-500 max-w-[200px] mb-4">請設定 API 金鑰以查看即時資產數據。</p>
                <button onclick="openApiKeyModal()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition shadow-lg shadow-blue-900/20 flex items-center gap-2">
                    <i data-lucide="settings" class="w-3 h-3"></i> 立即設定
                </button>
            </div>
        `;

        spotList.innerHTML = noKeyHtml;
        summaryEl.innerHTML = '<div class="text-xs text-slate-500 text-center">需先連接 API</div>';
        posTable.innerHTML = `<tr><td colspan="6" class="p-0"><div class="p-8 flex justify-center text-slate-500">${noKeyHtml}</div></td></tr>`;

        lucide.createIcons();
    }
}

function openApiKeyModal() {
    document.getElementById('apikey-modal').classList.remove('hidden');
}

function closeApiKeyModal() {
    document.getElementById('apikey-modal').classList.add('hidden');
}

async function saveApiKeys(event) {
    event.preventDefault();
    const btn = document.getElementById('btn-save-keys');
    const originalText = btn.innerHTML;

    const apiKey = document.getElementById('input-api-key').value.trim();
    const secretKey = document.getElementById('input-secret-key').value.trim();
    const passphrase = document.getElementById('input-passphrase').value.trim();

    if (!apiKey || !secretKey || !passphrase) {
        alert('⚠️ 請填寫所有欄位');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<div class="spinner w-4 h-4 border-2"></div> 驗證中...';

    try {
        const okxKeyManager = window.OKXKeyManager;

        // ✅ 先驗證金鑰是否有效
        const validation = await okxKeyManager.validateCredentials({
            api_key: apiKey,
            secret_key: secretKey,
            passphrase: passphrase
        });

        if (!validation.valid) {
            alert('❌ 驗證失敗: ' + validation.message);
            return;
        }

        // ✅ 驗證成功，保存到 localStorage（BYOK 模式）
        okxKeyManager.saveCredentials({
            api_key: apiKey,
            secret_key: secretKey,
            passphrase: passphrase
        });

        alert('✅ OKX API 金鑰已保存到本地瀏覽器\n\n⚠️ 注意: 金鑰僅存儲在您的瀏覽器中，不會上傳到服務器。\n無痕視窗不會保存您的金鑰。');

        // 清空輸入框
        document.getElementById('input-api-key').value = '';
        document.getElementById('input-secret-key').value = '';
        document.getElementById('input-passphrase').value = '';

        closeApiKeyModal();
        refreshAssets();

    } catch (e) {
        alert('❌ 系統錯誤: ' + e.message);
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
