// ========================================
// market-ws.js - WebSocket + Auto-Refresh + Cleanup
// ========================================

// ========================================
// WebSocket 即時更新功能
// ========================================

function getWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/klines`;
}

function connectWebSocket() {
    if (klineWebSocket && klineWebSocket.readyState === WebSocket.OPEN) {
        return;
    }

    const wsUrl = getWebSocketUrl();
    console.log('連接 WebSocket:', wsUrl);

    try {
        klineWebSocket = new WebSocket(wsUrl);

        klineWebSocket.onopen = () => {
            console.log('WebSocket 連接成功');
            wsConnected = true;
            updateWsStatus(true);
            // Reset reconnect attempts on successful connection
            reconnectAttempts = 0;

            // 如果已經有訂閱，重新訂閱
            if (currentChartSymbol && autoRefreshEnabled) {
                subscribeKline(currentChartSymbol, currentChartInterval);
            }

            // Start live time updates when WebSocket is connected and auto-refresh is enabled
            if (autoRefreshEnabled) {
                startLiveTimeUpdates();
            }
        };

        klineWebSocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error('WebSocket 消息解析錯誤:', e);
            }
        };

        klineWebSocket.onclose = (event) => {
            console.log('WebSocket 連接關閉:', event.code, event.reason);
            wsConnected = false;
            updateWsStatus(false);
            stopLiveTimeUpdates(); // Stop live time updates when disconnected

            // 自動重連 - 限制最大重連次數
            if (autoRefreshEnabled && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(
                    `嘗試重新連接 WebSocket... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`
                );
                wsReconnectTimer = setTimeout(() => {
                    connectWebSocket();
                }, 3000);
            } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                console.error('WebSocket 重連次數達到上限，停止重連');
                autoRefreshEnabled = false;
                updateAutoRefreshButton();
            }
        };

        klineWebSocket.onerror = (error) => {
            console.error('WebSocket 錯誤:', error);
            wsConnected = false;
            updateWsStatus(false);
        };
    } catch (e) {
        console.error('WebSocket 連接失敗:', e);
        wsConnected = false;
        updateWsStatus(false);
        if (typeof showToast === 'function') showToast('即時連線失敗，將使用輪詢更新', 'warning');
    }
}

function disconnectWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    if (klineWebSocket) {
        klineWebSocket.close();
        klineWebSocket = null;
    }
    wsConnected = false;
}

function subscribeKline(symbol, interval) {
    if (!klineWebSocket || klineWebSocket.readyState !== WebSocket.OPEN) {
        console.warn('WebSocket 未連接，無法訂閱');
        return;
    }

    klineWebSocket.send(
        JSON.stringify({
            action: 'subscribe',
            symbol: symbol,
            interval: interval,
        })
    );
    console.log(`訂閱: ${symbol} ${interval}`);
}

function unsubscribeKline() {
    if (!klineWebSocket || klineWebSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    klineWebSocket.send(JSON.stringify({ action: 'unsubscribe' }));
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'kline':
            updateChartWithKline(message.data);
            break;
        case 'subscribed':
            console.log(`已訂閱: ${message.symbol} ${message.interval}`);
            break;
        case 'unsubscribed':
            console.log('已取消訂閱');
            break;
        case 'pong':
            // 心跳回應
            break;
        case 'error':
            console.error('WebSocket 錯誤:', message.message);
            break;
    }
}

function updateChartWithKline(kline) {
    if (!chart || !candleSeries) return;

    // 更新或添加 K 線
    const klineData = {
        time: kline.time,
        open: kline.open,
        high: kline.high,
        low: kline.low,
        close: kline.close,
    };

    // 使用 update 方法更新最新 K 線
    candleSeries.update(klineData);

    // 更新成交量
    if (volumeSeries && kline.volume !== undefined) {
        volumeSeries.update({
            time: kline.time,
            value: kline.volume,
            color: kline.close >= kline.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
        });
    }

    // 更新大尺寸當前價格顯示
    const currentPriceDisplay = document.getElementById('current-price-display');
    if (currentPriceDisplay) {
        const priceDecimals = getPriceDecimals(kline.close);
        const formattedPrice = kline.close.toFixed(priceDecimals);
        const isUp = kline.close >= kline.open;
        currentPriceDisplay.textContent = `$${formattedPrice}`;
        currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
    }

    // 更新時間顯示
    const updatedEl = document.getElementById('chart-updated');
    if (updatedEl) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
        updatedEl.textContent = `即時 ${timeStr}`;
    }

    // 更新 OHLCV 顯示 (僅在圖表未被懸停時)
    if (!isChartHovered) {
        const priceDecimals = getPriceDecimals(kline.close);
        updateOHLCVDisplay(
            kline,
            document.getElementById('info-open'),
            document.getElementById('info-high'),
            document.getElementById('info-low'),
            document.getElementById('info-close'),
            document.getElementById('info-volume'),
            priceDecimals
        );
    }

    // 更新存儲的 K 線數據，以便在未懸停時顯示最新數據
    if (window.currentChartKlines && window.currentChartKlines.length > 0) {
        // 更新最後一根 K 線
        const lastIdx = window.currentChartKlines.length - 1;
        if (window.currentChartKlines[lastIdx].time === kline.time) {
            window.currentChartKlines[lastIdx] = kline;
        } else {
            // 如果是新時間的 K 線，添加到末尾
            window.currentChartKlines.push(kline);
            // 保持最多 200 根 K 線
            if (window.currentChartKlines.length > 200) {
                window.currentChartKlines.shift();
            }
        }
    }
}

function updateWsStatus(connected) {
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');

    if (connected && autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-success', 'bg-success/10');
            btn.classList.remove('text-primary', 'bg-primary/10', 'text-textMuted');
        }
        if (status) status.textContent = 'LIVE';
    } else if (autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-warning', 'bg-warning/10');
            btn.classList.remove('text-success', 'bg-success/10', 'text-textMuted');
        }
        if (status) status.textContent = '...';
    }
}

function updateAutoRefreshButton() {
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');

    if (!autoRefreshEnabled) {
        if (btn) {
            btn.classList.remove(
                'text-success',
                'bg-success/10',
                'text-primary',
                'bg-primary/10',
                'text-warning',
                'bg-warning/10'
            );
            btn.classList.add('text-textMuted');
        }
        if (status) status.textContent = 'OFF';
    } else if (wsConnected) {
        updateWsStatus(true);
    } else {
        updateWsStatus(false);
    }
}

// Timer for updating live time display
let liveTimeUpdateTimer = null;

function startLiveTimeUpdates() {
    if (liveTimeUpdateTimer) {
        clearInterval(liveTimeUpdateTimer);
    }

    liveTimeUpdateTimer = setInterval(() => {
        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl && wsConnected && autoRefreshEnabled) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            });
            updatedEl.textContent = `即時 ${timeStr}`;
        }
    }, 1000); // Update every second
}

function stopLiveTimeUpdates() {
    if (liveTimeUpdateTimer) {
        clearInterval(liveTimeUpdateTimer);
        liveTimeUpdateTimer = null;
    }
}

// 自動更新功能（使用 WebSocket）
function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');

    if (autoRefreshEnabled) {
        btn.classList.add('text-primary', 'bg-primary/10');
        btn.classList.remove('text-textMuted');
        status.textContent = '連接中...';
        startAutoRefresh();
    } else {
        btn.classList.remove(
            'text-primary',
            'bg-primary/10',
            'text-success',
            'bg-success/10',
            'text-warning',
            'bg-warning/10'
        );
        btn.classList.add('text-textMuted');
        status.textContent = 'OFF';
        stopAutoRefresh();
    }
}

function startAutoRefresh() {
    // 連接 WebSocket
    connectWebSocket();

    // 訂閱當前幣種
    if (currentChartSymbol) {
        // Clear any existing connection check timer
        if (wsConnectionCheckTimer) {
            clearInterval(wsConnectionCheckTimer);
            wsConnectionCheckTimer = null;
        }

        // 等待連接建立後訂閱
        wsConnectionCheckTimer = setInterval(() => {
            if (wsConnected) {
                subscribeKline(currentChartSymbol, currentChartInterval);
                clearInterval(wsConnectionCheckTimer);
                wsConnectionCheckTimer = null;
                // Start live time updates when connection is established
                startLiveTimeUpdates();
            }
        }, 100);

        // 5秒後停止檢查
        setTimeout(() => {
            if (wsConnectionCheckTimer) {
                clearInterval(wsConnectionCheckTimer);
                wsConnectionCheckTimer = null;
            }
        }, 5000);
    }
}

function stopAutoRefresh() {
    unsubscribeKline();
    disconnectWebSocket();
    stopLiveTimeUpdates(); // Stop live time updates when auto-refresh stops

    autoRefreshEnabled = false;
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');
    if (btn) {
        btn.classList.remove(
            'text-primary',
            'bg-primary/10',
            'text-success',
            'bg-success/10',
            'text-warning',
            'bg-warning/10'
        );
        btn.classList.add('text-textMuted');
    }
    if (status) status.textContent = 'OFF';
}

// 保留輪詢作為備用方案
async function refreshChartData() {
    if (!currentChartSymbol || !chart || !candleSeries) return;

    try {
        const res = await fetch('/api/klines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol: currentChartSymbol,
                interval: currentChartInterval,
                limit: 200,
            }),
        });
        const data = await res.json();

        if (!data.klines || data.klines.length === 0) return;

        candleSeries.setData(data.klines);
        chartKlinesData = data.klines;

        if (volumeSeries) {
            const volumeData = data.klines.map((k) => ({
                time: k.time,
                value: k.volume || 0,
                color: k.close >= k.open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
            }));
            volumeSeries.setData(volumeData);
        }

        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            });
            updatedEl.textContent = `更新: ${timeStr}`;
        }

        const lastKline = data.klines[data.klines.length - 1];
        if (lastKline) {
            const priceDecimals = getPriceDecimals(lastKline.close);
            // 更新 OHLCV 顯示 (僅在圖表未被懸停時)
            if (!isChartHovered) {
                updateOHLCVDisplay(
                    lastKline,
                    document.getElementById('info-open'),
                    document.getElementById('info-high'),
                    document.getElementById('info-low'),
                    document.getElementById('info-close'),
                    document.getElementById('info-volume'),
                    priceDecimals
                );

                // 更新大尺寸當前價格顯示 (僅在圖表未被懸停時)
                const currentPriceDisplay = document.getElementById('current-price-display');
                if (currentPriceDisplay) {
                    const formattedPrice = lastKline.close.toFixed(priceDecimals);
                    const isUp = lastKline.close >= lastKline.open;
                    currentPriceDisplay.textContent = `$${formattedPrice}`;
                    currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                }
            }
        }
    } catch (err) {
        console.error('[Market] refreshChartData failed:', err);
        if (typeof showToast === 'function') showToast('圖表數據更新失敗', 'error');
    }
}

// ========================================
// Market Watch Ticker WebSocket
// ========================================

function getTickerWebSocketUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/tickers`;
}

function connectTickerWebSocket() {
    if (marketWebSocket && marketWebSocket.readyState === WebSocket.OPEN) {
        return;
    }

    const wsUrl = getTickerWebSocketUrl();
    console.log('連接 Ticker WebSocket:', wsUrl);

    try {
        marketWebSocket = new WebSocket(wsUrl);

        marketWebSocket.onopen = () => {
            console.log('Ticker WebSocket 連接成功');
            marketWsConnected = true;
            updateTickerWsStatus(true);
            // Reset reconnect attempts on successful connection
            tickerReconnectAttempts = 0;

            // 訂閱等待中的 symbols
            if (pendingTickerSymbols.size > 0) {
                const symbols = Array.from(pendingTickerSymbols);
                pendingTickerSymbols.clear();
                subscribeTickerSymbols(symbols);
            }

            // 重新訂閱之前的 symbols
            if (subscribedTickerSymbols.size > 0) {
                const symbols = Array.from(subscribedTickerSymbols);
                subscribedTickerSymbols.clear(); // 清空以便重新添加
                subscribeTickerSymbols(symbols);
            }
        };

        marketWebSocket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleTickerMessage(message);
            } catch (e) {
                console.error('Ticker WebSocket 消息解析錯誤:', e);
            }
        };

        marketWebSocket.onclose = (event) => {
            console.log('Ticker WebSocket 連接關閉:', event.code);
            marketWsConnected = false;
            updateTickerWsStatus(false);

            // 自動重連 - 限制最大重連次數
            if (tickerReconnectAttempts < MAX_TICKET_RECONNECT_ATTEMPTS) {
                tickerReconnectAttempts++;
                console.log(
                    `嘗試重新連接 Ticker WebSocket... (${tickerReconnectAttempts}/${MAX_TICKET_RECONNECT_ATTEMPTS})`
                );
                tickerReconnectTimer = setTimeout(() => {
                    connectTickerWebSocket();
                }, 3000);
            } else {
                console.error('Ticker WebSocket 重連次數達到上限，停止重連');
            }
        };

        marketWebSocket.onerror = (error) => {
            console.error('Ticker WebSocket 錯誤:', error);
            marketWsConnected = false;
            updateTickerWsStatus(false);
        };
    } catch (e) {
        console.error('Ticker WebSocket 連接失敗:', e);
        marketWsConnected = false;
        updateTickerWsStatus(false);
        if (typeof showToast === 'function') showToast('行情即時連線失敗', 'warning');
    }
}

function disconnectTickerWebSocket() {
    if (tickerReconnectTimer) {
        clearTimeout(tickerReconnectTimer);
        tickerReconnectTimer = null;
    }

    if (marketWebSocket) {
        marketWebSocket.close();
        marketWebSocket = null;
    }
    marketWsConnected = false;
    subscribedTickerSymbols.clear();
}

function subscribeTickerSymbols(symbols) {
    // 過濾已訂閱的
    const newSymbols = symbols.filter((s) => !subscribedTickerSymbols.has(s.toUpperCase()));
    if (newSymbols.length === 0) return;

    if (!marketWebSocket || marketWebSocket.readyState !== WebSocket.OPEN) {
        // WebSocket 未連接，加入等待列表
        newSymbols.forEach((s) => pendingTickerSymbols.add(s.toUpperCase()));
        console.log(`Ticker WebSocket 未連接，已排隊等待: ${newSymbols.join(', ')}`);
        return;
    }

    marketWebSocket.send(
        JSON.stringify({
            action: 'subscribe',
            symbols: newSymbols,
        })
    );

    newSymbols.forEach((s) => subscribedTickerSymbols.add(s.toUpperCase()));
    console.log(`訂閱 Ticker: ${newSymbols.join(', ')}`);
}

function unsubscribeTickerSymbols(symbols) {
    if (!marketWebSocket || marketWebSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    marketWebSocket.send(
        JSON.stringify({
            action: 'unsubscribe',
            symbols: symbols,
        })
    );

    symbols.forEach((s) => subscribedTickerSymbols.delete(s.toUpperCase()));
}

function handleTickerMessage(message) {
    switch (message.type) {
        case 'ticker':
            // console.log(`收到 Ticker 更新: ${message.symbol}`, message.data);
            updateMarketWatchItem(message.symbol, message.data);
            break;
        case 'subscribed':
            console.log(`✅ 已訂閱 Ticker: ${message.symbols.join(', ')}`);
            break;
        case 'unsubscribed':
            console.log(`已取消訂閱 Ticker`);
            break;
        case 'unsubscribed_all':
            console.log(`已取消所有 Ticker 訂閱`);
            break;
        case 'pong':
            break;
        case 'error':
            console.error('Ticker WebSocket 錯誤:', message.message);
            break;
        default:
            console.log('未知 Ticker 消息:', message);
    }
}

function updateMarketWatchItem(symbol, ticker) {
    // 尋找所有顯示該 symbol 的元素並更新價格
    // symbol 可能是 "BTC-USDT", "BTC", "BTCUSDT" 等格式
    // 統一處理為不帶後綴的格式
    const normalizedSymbol = symbol
        .toUpperCase()
        .replace('-USDT', '')
        .replace('USDT', '')
        .replace('-', '');

    // 更新所有列表中的價格
    const containers = ['top-list', 'oversold-list', 'overbought-list'];
    containers.forEach((containerId) => {
        const container = document.getElementById(containerId);
        if (!container) return;

        // 查找包含該 symbol 的卡片
        const cards = container.querySelectorAll('[data-symbol]');

        cards.forEach((card) => {
            const cardSymbol = (card.dataset.symbol || '')
                .toUpperCase()
                .replace('-USDT', '')
                .replace('USDT', '')
                .replace('-', '');

            if (cardSymbol && cardSymbol === normalizedSymbol) {
                // 更新價格
                const priceEl = card.querySelector('.ticker-price');
                if (priceEl && ticker.last) {
                    const oldPrice = priceEl.textContent;
                    const newPrice = `$${formatPrice(ticker.last)}`;

                    if (oldPrice !== newPrice) {
                        priceEl.textContent = newPrice;
                        // 閃爍效果
                        priceEl.classList.add('price-flash');
                        setTimeout(() => priceEl.classList.remove('price-flash'), 300);
                    }
                }

                // 更新 24h 漲跌幅
                const changeEl = card.querySelector('.ticker-change');
                if (changeEl && ticker.change24h !== undefined) {
                    const change = ticker.change24h;
                    const isUp = change >= 0;
                    changeEl.textContent = `${isUp ? '+' : ''}${change.toFixed(2)}%`;
                    changeEl.className = `text-base font-black ticker-change ${isUp ? 'text-success' : 'text-danger'}`;
                }
            }
        });
    });
}

function updateTickerWsStatus(connected) {
    const indicator = document.getElementById('ticker-ws-indicator');
    if (indicator) {
        if (connected) {
            indicator.classList.add('bg-success');
            indicator.classList.remove('bg-gray-500');
            indicator.title = '即時更新已連接';
        } else {
            indicator.classList.remove('bg-success');
            indicator.classList.add('bg-gray-500');
            indicator.title = '即時更新已斷開';
        }
    }
}

// 自動啟動 Ticker WebSocket (當頁面在 Market Watch 標籤時)
function initTickerWebSocket() {
    // 延遲啟動，等待頁面載入
    setTimeout(() => {
        connectTickerWebSocket();
    }, 1000);
}

// Make globally accessible
window.showChart = showChart;
window.changeChartInterval = changeChartInterval;
window.closeChart = closeChart;
window.toggleAutoRefresh = toggleAutoRefresh;
window.connectTickerWebSocket = connectTickerWebSocket;
window.disconnectTickerWebSocket = disconnectTickerWebSocket;
window.subscribeTickerSymbols = subscribeTickerSymbols;
// 處理瀏覽器分頁切換 (Visibility Change)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('[Market] Tab hidden, pausing updates to save resources.');
        // Optionally clear interval if we wanted to be very strict,
        // but app.js handles the main interval.
        // We just note it here.
    } else {
        console.log('[Market] Tab visible, checking for stale data...');
        // 如果當前在 Market Watch 頁面，且數據可能過期，則刷新
        // 檢查是否在前台
        const marketTab = document.getElementById('market-content');
        if (marketTab && !marketTab.classList.contains('hidden')) {
            // 延遲一點點確保網路恢復
            setTimeout(() => {
                console.log('[Market] Resuming updates, forcing refresh...');
                refreshScreener(false, true); // Silent refresh, force update
            }, 500);
        }
    }
});

window.refreshScreener = refreshScreener; // CRITICAL: Export for index.html to call
window.showFundingHistory = showFundingHistory;
window.closeFundingHistory = closeFundingHistory;

// ========================================
// Cleanup function for memory leak prevention
// ========================================
function cleanupMarketResources() {
    console.log('[Market] Cleaning up resources...');

    // Clear live time update timer
    if (liveTimeUpdateTimer) {
        clearInterval(liveTimeUpdateTimer);
        liveTimeUpdateTimer = null;
    }

    // Clear WebSocket reconnect timers
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    if (wsConnectionCheckTimer) {
        clearInterval(wsConnectionCheckTimer);
        wsConnectionCheckTimer = null;
    }

    if (tickerReconnectTimer) {
        clearTimeout(tickerReconnectTimer);
        tickerReconnectTimer = null;
    }

    // Remove resize event listener
    if (window._marketResizeHandler) {
        window.removeEventListener('resize', window._marketResizeHandler);
        window._marketResizeHandler = null;
    }

    // Close WebSocket connections
    if (klineWebSocket) {
        klineWebSocket.close();
        klineWebSocket = null;
    }

    if (marketWebSocket) {
        marketWebSocket.close();
        marketWebSocket = null;
    }

    // Reset reconnect attempts
    reconnectAttempts = 0;
    tickerReconnectAttempts = 0;

    console.log('[Market] Resources cleaned up');
}

// Register cleanup on page unload
window.addEventListener('beforeunload', cleanupMarketResources);

// Also cleanup on visibility change when leaving the page
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
        // Optional: cleanup when tab becomes hidden
        // cleanupMarketResources();
    }
});
