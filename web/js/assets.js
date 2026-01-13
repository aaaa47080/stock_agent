// ========================================
// assets.js - 資產管理功能
// ========================================

async function refreshAssets() {
    const totalEl = document.getElementById('total-equity');
    const spotList = document.getElementById('spot-assets-list');
    const posTable = document.getElementById('positions-table-body');
    const summaryEl = document.getElementById('positions-summary');
    const noKeyOverlay = document.getElementById('no-okx-key-overlay');
    const assetsContent = document.getElementById('assets-content');

    // ✅ 檢查是否有 OKX API 金鑰（BYOK 模式）
    const okxKeyManager = window.OKXKeyManager;
    if (!okxKeyManager || !okxKeyManager.hasCredentials()) {
        // 沒有金鑰：顯示 overlay，隱藏內容
        if (noKeyOverlay) noKeyOverlay.classList.remove('hidden');
        if (assetsContent) assetsContent.classList.add('hidden');
        lucide.createIcons();
        return;
    }

    // 有金鑰：隱藏 overlay，顯示內容
    if (noKeyOverlay) noKeyOverlay.classList.add('hidden');
    if (assetsContent) assetsContent.classList.remove('hidden');

    // Loading state
    totalEl.classList.add('animate-pulse');

    try {

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
                        <span class="font-bold text-secondary">${asset.currency}</span>
                        <span class="text-xs text-textMuted">${asset.available.toFixed(4)} 可用</span>
                    </div>
                    <div class="text-textMuted">$${asset.usd_value.toFixed(2)}</div>
                `;
                spotList.appendChild(div);
            });
        } else {
            spotList.innerHTML = '<div class="text-textMuted text-xs">無資產餘額</div>';
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
                const pnlClass = pos.pnl >= 0 ? 'text-success' : 'text-danger';
                const sideClass = isLong ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger';
                const sideText = pos.side === 'net' ? (pos.size > 0 ? '多' : '空') : (pos.side === 'long' ? '多' : '空');

                totalPnl += pos.pnl;

                const tr = document.createElement('tr');
                tr.className = 'border-b border-white/5 hover:bg-surfaceHighlight transition';
                tr.innerHTML = `
                    <td class="px-4 py-3 font-medium text-secondary">${pos.symbol}</td>
                    <td class="px-4 py-3">
                        <span class="text-[10px] px-1.5 py-0.5 rounded ${sideClass} border border-white/10 mr-1">${sideText}</span>
                        <span class="text-xs text-textMuted">${pos.leverage}x</span>
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
                    <span class="text-textMuted">持倉數量</span>
                    <span class="text-secondary font-bold">${posData.positions.length}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-textMuted">未實現總盈虧</span>
                    <span class="${totalPnl >= 0 ? 'text-success' : 'text-danger'} font-bold">${totalPnl > 0 ? '+' : ''}${totalPnl.toFixed(2)} USDT</span>
                </div>
            `;

        } else {
            posTable.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-textMuted">尚無持倉數據</td></tr>';
            summaryEl.innerHTML = '<div class="text-textMuted text-xs">無持倉</div>';
        }

    } catch (e) {
        console.error("Failed to fetch assets", e);
        totalEl.classList.remove('animate-pulse');
        totalEl.innerText = "---";

        // 如果是金鑰無效，顯示 overlay
        if (e.message === "INVALID_OKX_KEY") {
            if (noKeyOverlay) noKeyOverlay.classList.remove('hidden');
            if (assetsContent) assetsContent.classList.add('hidden');
            lucide.createIcons();
            return;
        }

        // 其他 API 錯誤
        const errorHtml = `
            <div class="flex flex-col items-center justify-center py-6 text-center">
                <div class="bg-danger/10 p-3 rounded-full mb-3">
                    <i data-lucide="alert-circle" class="w-5 h-5 text-danger"></i>
                </div>
                <p class="text-xs text-textMuted">無法載入資料，請稍後重試</p>
            </div>
        `;

        spotList.innerHTML = errorHtml;
        summaryEl.innerHTML = '';
        posTable.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-textMuted text-xs">載入失敗</td></tr>`;

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
    const form = event.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;

    const apiKey = document.getElementById('input-api-key').value.trim();
    const secretKey = document.getElementById('input-secret-key').value.trim();
    const passphrase = document.getElementById('input-passphrase').value.trim();

    if (!apiKey || !secretKey || !passphrase) {
        showToast('請填寫所有欄位', 'warning');
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
            showToast('驗證失敗: ' + validation.message, 'error');
            return;
        }

        // ✅ 驗證成功，保存到 localStorage（BYOK 模式）
        okxKeyManager.saveCredentials({
            api_key: apiKey,
            secret_key: secretKey,
            passphrase: passphrase
        });

        showToast('OKX API 金鑰已保存\n金鑰僅存儲在您的瀏覽器中', 'success', 4000);

        // 清空輸入框
        document.getElementById('input-api-key').value = '';
        document.getElementById('input-secret-key').value = '';
        document.getElementById('input-passphrase').value = '';

        closeApiKeyModal();
        refreshAssets();

        // 更新 Settings 頁面的連接狀態
        if (typeof updateOKXStatusUI === 'function') {
            updateOKXStatusUI();
        }

    } catch (e) {
        showToast('系統錯誤: ' + e.message, 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
