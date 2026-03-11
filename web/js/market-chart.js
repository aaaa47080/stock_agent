// ========================================
// market-chart.js - TradingView K-Line Chart
// ========================================

var historyChartInstance = null;

function renderHistoryChart(historyData) {
    const ctx = document.getElementById('fundingHistoryChart').getContext('2d');

    if (historyChartInstance) {
        historyChartInstance.destroy();
    }

    const labels = historyData.map((d) => {
        const date = new Date(parseInt(d.time));
        return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
    });

    const rates = historyData.map((d) => d.rate);
    const colors = rates.map((r) => (r >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)'));
    const borders = rates.map((r) => (r >= 0 ? 'rgba(34, 197, 94, 1)' : 'rgba(239, 68, 68, 1)'));

    historyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '資金費率 (%)',
                    data: rates,
                    backgroundColor: colors,
                    borderColor: borders,
                    borderWidth: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: { color: '#94a3b8' },
                    beginAtZero: false,
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        display: true,
                        color: '#64748b',
                        maxTicksLimit: 10,
                    },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#e2e8f0',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: function (context) {
                            return `費率: ${context.raw.toFixed(4)}%`;
                        },
                    },
                },
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'xy',
                    },
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true,
                        },
                        mode: 'xy',
                    },
                },
            },
        },
    });
}

// ========================================
// Chart Functionality (Moved from Watchlist)
// ========================================

// 根據價格大小決定小數位
function getPriceDecimals(price) {
    const p = Math.abs(price);
    if (p >= 1000) return 2;
    if (p >= 1) return 2;
    if (p >= 0.01) return 4;
    if (p >= 0.0001) return 6;
    return 8;
}

// 格式化價格顯示
function formatChartPrice(price, decimals) {
    return price.toFixed(decimals);
}

// 格式化成交量顯示
function formatVolume(vol) {
    if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
    if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
    if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
    return vol.toFixed(2);
}

// 更新 OHLCV 顯示
function updateOHLCVDisplay(kline, openEl, highEl, lowEl, closeEl, volEl, decimals) {
    if (!kline) return;

    const isUp = kline.close >= kline.open;
    const color = isUp ? 'text-success' : 'text-danger';

    if (openEl) openEl.textContent = formatChartPrice(kline.open, decimals);
    if (highEl) highEl.textContent = formatChartPrice(kline.high, decimals);
    if (lowEl) lowEl.textContent = formatChartPrice(kline.low, decimals);
    if (closeEl) {
        closeEl.textContent = formatChartPrice(kline.close, decimals);
        closeEl.className = color;
    }
    if (volEl && kline.volume !== undefined) {
        volEl.textContent = formatVolume(kline.volume);
    }
}

async function showChart(symbol, interval = null) {
    const symbolChanged = symbol && symbol !== currentChartSymbol;
    const intervalChanged = interval && interval !== currentChartInterval;

    if (symbol) currentChartSymbol = symbol;
    if (interval) currentChartInterval = interval;

    // 如果 WebSocket 已連接且幣種或週期改變，重新訂閱
    if (autoRefreshEnabled && wsConnected && (symbolChanged || intervalChanged)) {
        unsubscribeKline();
        setTimeout(() => subscribeKline(currentChartSymbol, currentChartInterval), 100);
    }

    // 自動啟動即時更新（如果預設開啟但尚未連接）
    if (autoRefreshEnabled && !wsConnected) {
        startAutoRefresh();
    }

    // 確保按鈕狀態正確更新
    updateWsStatus(wsConnected);

    // 更新時間顯示
    const updatedEl = document.getElementById('chart-updated');
    if (updatedEl) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
        // Only update if it's not already showing LIVE status
        if (!updatedEl.textContent.includes('即時')) {
            updatedEl.textContent = `更新: ${timeStr}`;
        }
    }

    // Update active button state
    document.querySelectorAll('.chart-interval-btn').forEach((btn) => {
        if (btn.dataset.interval === currentChartInterval) {
            btn.classList.add('bg-white/10', 'text-primary');
            btn.classList.remove('text-textMuted');
        } else {
            btn.classList.remove('bg-white/10', 'text-primary');
            btn.classList.add('text-textMuted');
        }
    });

    const chartSection = document.getElementById('chart-section');
    const chartContainer = document.getElementById('chart-container');
    const volumeContainer = document.getElementById('volume-container');

    if (!chartSection || !chartContainer) {
        console.error('Chart DOM elements missing');
        return;
    }

    chartSection.classList.remove('hidden');
    lucide.createIcons();

    const titleEl = document.getElementById('chart-title');
    if (titleEl)
        titleEl.textContent = `${currentChartSymbol} (${currentChartInterval.toUpperCase()})`;

    // 更新自動更新按鈕狀態
    const btn = document.getElementById('auto-refresh-btn');
    const status = document.getElementById('auto-refresh-status');
    if (autoRefreshEnabled) {
        if (btn) {
            btn.classList.add('text-primary', 'bg-primary/10');
            btn.classList.remove('text-textMuted');
        }
        if (status) status.textContent = wsConnected ? 'LIVE' : '連接中...';
    }

    chartContainer.innerHTML =
        '<div class="animate-pulse text-textMuted h-full flex items-center justify-center">載入數據中...</div>';
    if (volumeContainer) {
        volumeContainer.innerHTML = '';
        volumeContainer.style.display = '';
    }

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

        if (!data.klines || data.klines.length === 0) {
            chartContainer.innerHTML =
                '<div class="text-danger h-full flex items-center justify-center">無法載入數據</div>';
            return;
        }

        // 更新時間顯示
        const updatedEl = document.getElementById('chart-updated');
        if (updatedEl && data.updated_at) {
            const date = new Date(data.updated_at);
            const timeStr = date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            });
            updatedEl.textContent = `更新: ${timeStr}`;
        }

        // 計算價格精度
        const samplePrice = data.klines[data.klines.length - 1]?.close || 1;
        const priceDecimals = getPriceDecimals(samplePrice);

        chartContainer.innerHTML = '';
        if (chart) chart.remove();

        // chart-container has CSS h-[52vh], read actual rendered height with fallback
        const chartHeight = chartContainer.clientHeight || Math.floor(window.innerHeight * 0.52);

        chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartHeight,
            layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#94a3b8' },
            grid: {
                vertLines: { color: 'rgba(51, 65, 85, 0.3)' },
                horzLines: { color: 'rgba(51, 65, 85, 0.3)' },
            },
            timeScale: { borderColor: '#334155', timeVisible: true },
            rightPriceScale: { autoScale: true, scaleMargins: { top: 0.1, bottom: 0.1 } },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
                horzTouchDrag: true,
                vertTouchDrag: true,
            },
            handleScale: {
                axisPressedMouseMove: { time: true, price: true },
                axisDoubleClickReset: { time: true, price: true },
                mouseWheel: true,
                pinch: true,
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        });

        candleSeries = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            borderDownColor: '#ef4444',
            priceFormat: {
                type: 'price',
                precision: priceDecimals,
                minMove: Math.pow(10, -priceDecimals),
            },
        });
        candleSeries.setData(data.klines);

        // 儲存 klines 數據以便 crosshair 查詢
        const klinesMap = {};
        data.klines.forEach((k) => {
            klinesMap[k.time] = k;
        });

        // Remove old volume chart reference
        if (window.volumeChart) {
            window.volumeChart.remove();
            window.volumeChart = null;
        }

        // Populate volume data
        const volumeData = data.klines.map((k) => ({
            time: k.time,
            value: k.volume || 0,
            color: k.close >= k.open ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)',
        }));

        // Create separate volume chart
        if (volumeContainer) {
            window.volumeChart = LightweightCharts.createChart(volumeContainer, {
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#94a3b8',
                },
                grid: {
                    vertLines: { color: 'rgba(51, 65, 85, 0.2)' },
                    horzLines: { color: 'rgba(51, 65, 85, 0.1)' },
                },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: {
                    borderColor: '#334155',
                    scaleMargins: { top: 0.1, bottom: 0.05 },
                },
                timeScale: { visible: false },
                handleScroll: {
                    mouseWheel: false,
                    pressedMouseMove: false,
                    horzTouchDrag: false,
                    vertTouchDrag: false,
                },
                handleScale: { mouseWheel: false, pinchScale: false },
            });
            volumeSeries = window.volumeChart.addHistogramSeries({
                priceFormat: { type: 'volume' },
            });
            volumeSeries.setData(volumeData);
            // Sync time scales
            let _syncingRange = false;
            chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (_syncingRange || !range || !window.volumeChart) return;
                _syncingRange = true;
                window.volumeChart.timeScale().setVisibleLogicalRange(range);
                _syncingRange = false;
            });
            window.volumeChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
                if (_syncingRange || !range || !chart) return;
                _syncingRange = true;
                chart.timeScale().setVisibleLogicalRange(range);
                _syncingRange = false;
            });
        }

        chart.timeScale().fitContent();

        // 監聽 Resize 事件以動態調整佈局 (使用 requestAnimationFrame 優化性能)
        let resizeFrame = null;
        const adaptiveResizeHandler = () => {
            if (resizeFrame) cancelAnimationFrame(resizeFrame);

            resizeFrame = requestAnimationFrame(() => {
                if (!chart || !chartContainer) return;
                chart.applyOptions({ width: chartContainer.clientWidth });
                if (window.volumeChart && volumeContainer) {
                    window.volumeChart.applyOptions({ width: volumeContainer.clientWidth });
                }
            });
        };

        // Remove old listeners to prevent duplicates
        if (window._marketResizeHandler) {
            window.removeEventListener('resize', window._marketResizeHandler);
        }
        window._marketResizeHandler = adaptiveResizeHandler;
        window.addEventListener('resize', adaptiveResizeHandler);

        // Crosshair 移動時更新 OHLCV 資訊
        chart.subscribeCrosshairMove((param) => {
            const infoOpen = document.getElementById('info-open');
            const infoHigh = document.getElementById('info-high');
            const infoLow = document.getElementById('info-low');
            const infoClose = document.getElementById('info-close');
            const infoVolume = document.getElementById('info-volume');
            const currentPriceDisplay = document.getElementById('current-price-display');

            if (!param.time || !param.seriesData) {
                // 滑鼠離開圖表，顯示最新數據
                isChartHovered = false;
                const lastKline = data.klines[data.klines.length - 1];
                if (lastKline) {
                    updateOHLCVDisplay(
                        lastKline,
                        infoOpen,
                        infoHigh,
                        infoLow,
                        infoClose,
                        infoVolume,
                        priceDecimals
                    );

                    // 恢復顯示最新價格
                    if (currentPriceDisplay) {
                        const formattedPrice = lastKline.close.toFixed(priceDecimals);
                        const isUp = lastKline.close >= lastKline.open;
                        currentPriceDisplay.textContent = `$${formattedPrice}`;
                        currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                    }
                }
                if (window.volumeChart) window.volumeChart.clearCrosshairPosition();
                return;
            }

            // 滑鼠在圖表上，顯示懸停位置的數據
            isChartHovered = true;
            const kline = klinesMap[param.time];
            if (kline) {
                updateOHLCVDisplay(
                    kline,
                    infoOpen,
                    infoHigh,
                    infoLow,
                    infoClose,
                    infoVolume,
                    priceDecimals
                );

                // 顯示懸停位置的價格
                if (currentPriceDisplay) {
                    const formattedPrice = kline.close.toFixed(priceDecimals);
                    const isUp = kline.close >= kline.open;
                    currentPriceDisplay.textContent = `$${formattedPrice}`;
                    currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
                }
                // Sync crosshair to volume chart
                if (window.volumeChart && volumeSeries && kline.volume != null) {
                    window.volumeChart.setCrosshairPosition(kline.volume, param.time, volumeSeries);
                }
            }
        });

        // Store the latest kline for reference when not hovering
        const latestKline = data.klines[data.klines.length - 1];
        if (latestKline) {
            // Store for later use when WebSocket updates come in
            window.currentChartKlines = data.klines; // Keep track of current klines
            window.currentChartPriceDecimals = priceDecimals; // Keep track of current decimals
        }

        // 初始顯示最新 K 線數據
        const lastKline = data.klines[data.klines.length - 1];
        if (lastKline) {
            updateOHLCVDisplay(
                lastKline,
                document.getElementById('info-open'),
                document.getElementById('info-high'),
                document.getElementById('info-low'),
                document.getElementById('info-close'),
                document.getElementById('info-volume'),
                priceDecimals
            );

            // 顯示大尺寸當前價格
            const currentPriceDisplay = document.getElementById('current-price-display');
            if (currentPriceDisplay) {
                const formattedPrice = lastKline.close.toFixed(priceDecimals);
                const isUp = lastKline.close >= lastKline.open;
                currentPriceDisplay.textContent = `$${formattedPrice}`;
                currentPriceDisplay.className = `text-center text-2xl font-bold font-mono ${isUp ? 'text-success' : 'text-danger'}`;
            }
        }

        // 追蹤當前價格軸邊距
        let currentMargins = { top: 0.1, bottom: 0.1 };

        // 自定義滾輪行為
        chartContainer.addEventListener(
            'wheel',
            (e) => {
                e.preventDefault();
                const rect = chartContainer.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const chartWidth = rect.width;
                const chartHeight = rect.height;
                const priceScaleWidth = 70;
                const timeScaleHeight = 30;

                const zoomIn = e.deltaY < 0;
                const factor = zoomIn ? 0.9 : 1.1;

                if (x > chartWidth - priceScaleWidth) {
                    chart.priceScale('right').applyOptions({ autoScale: false });
                    const adjustment = zoomIn ? -0.03 : 0.03;
                    currentMargins.top = Math.max(
                        0.02,
                        Math.min(0.4, currentMargins.top + adjustment)
                    );
                    currentMargins.bottom = Math.max(
                        0.02,
                        Math.min(0.4, currentMargins.bottom + adjustment)
                    );
                    chart.priceScale('right').applyOptions({
                        scaleMargins: { top: currentMargins.top, bottom: currentMargins.bottom },
                    });
                } else if (y > chartHeight - timeScaleHeight) {
                    const timeScale = chart.timeScale();
                    const range = timeScale.getVisibleLogicalRange();
                    if (range) {
                        const center = (range.from + range.to) / 2;
                        const halfRange = ((range.to - range.from) / 2) * factor;
                        timeScale.setVisibleLogicalRange({
                            from: center - halfRange,
                            to: center + halfRange,
                        });
                    }
                } else {
                    chart.priceScale('right').applyOptions({ autoScale: true });
                    currentMargins = { top: 0.1, bottom: 0.1 };
                    const timeScale = chart.timeScale();
                    const range = timeScale.getVisibleLogicalRange();
                    if (range) {
                        const center = (range.from + range.to) / 2;
                        const halfRange = ((range.to - range.from) / 2) * factor;
                        timeScale.setVisibleLogicalRange({
                            from: center - halfRange,
                            to: center + halfRange,
                        });
                    }
                }
            },
            { passive: false }
        );

        // 雙擊重置
        chartContainer.addEventListener('dblclick', () => {
            chart.priceScale('right').applyOptions({ autoScale: true });
            currentMargins = { top: 0.1, bottom: 0.1 };
            chart.timeScale().fitContent();
        });

        // Auto-resize handler is now managed inside showChart for adaptive logic
        /* 
        const resizeHandler = () => { ... } 
        window.addEventListener('resize', resizeHandler);
        */
    } catch (err) {
        console.error('[Market] showChart failed:', err);
        if (chartContainer) {
            chartContainer.innerHTML =
                '<div class="text-danger h-full flex items-center justify-center">連線錯誤</div>';
        }
        if (typeof showToast === 'function') showToast('圖表載入失敗，請稍後再試', 'error');
    }
}

// 關閉圖表
function closeChart() {
    const chartSection = document.getElementById('chart-section');
    if (chartSection) {
        chartSection.classList.add('hidden');
    }
    // 停止自動更新
    stopAutoRefresh();
    // 清理圖表資源
    if (window.volumeChart) {
        window.volumeChart.remove();
        window.volumeChart = null;
    }
}

function changeChartInterval(interval) {
    if (!currentChartSymbol) return;

    // 如果 WebSocket 已連接，重新訂閱新的時間週期
    if (autoRefreshEnabled && wsConnected) {
        unsubscribeKline();
        currentChartInterval = interval;
        subscribeKline(currentChartSymbol, interval);
    }

    showChart(currentChartSymbol, interval);
}

// Export chart functions
window.showChart = showChart;
window.closeChart = closeChart;
window.changeChartInterval = changeChartInterval;
