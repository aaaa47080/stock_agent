// ========================================
// market-status.js - Market schedule and refresh UX helpers
// ========================================

(function () {
    const MARKET_CONFIG = {
        forex: {
            label: 'Forex',
            refreshSeconds: 15,
            timezone: 'Asia/Taipei',
        },
        commodity: {
            label: 'Commodity',
            refreshSeconds: 30,
            timezone: 'America/Chicago',
        },
        twstock: {
            label: 'TW Stock',
            refreshSeconds: 30,
            timezone: 'Asia/Taipei',
        },
        usstock: {
            label: 'US Stock',
            refreshSeconds: 30,
            timezone: 'America/New_York',
        },
    };

    function getZonedParts(date, timeZone) {
        const formatter = new Intl.DateTimeFormat('en-CA', {
            timeZone,
            hour12: false,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            weekday: 'short',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
        const parts = formatter.formatToParts(date);
        const map = {};
        for (const part of parts) {
            if (part.type !== 'literal') {
                map[part.type] = part.value;
            }
        }
        return {
            year: Number(map.year),
            month: Number(map.month),
            day: Number(map.day),
            hour: Number(map.hour),
            minute: Number(map.minute),
            second: Number(map.second),
            weekday: map.weekday,
        };
    }

    function minutesSinceMidnight(parts) {
        return parts.hour * 60 + parts.minute;
    }

    function isWeekday(parts) {
        return !['Sat', 'Sun'].includes(parts.weekday);
    }

    function getMarketState(marketType, now = new Date()) {
        const config = MARKET_CONFIG[marketType];
        if (!config) {
            return {
                isOpen: false,
                summary: 'Unknown market',
                detail: 'No schedule configured',
                refreshLabel: 'Manual refresh',
                statusTone: 'muted',
            };
        }

        const parts = getZonedParts(now, config.timezone);
        const minute = minutesSinceMidnight(parts);
        let isOpen = false;
        let summary = 'Closed';
        let detail = 'Updates paused';
        let statusTone = 'muted';

        if (marketType === 'forex') {
            isOpen = parts.weekday !== 'Sat';
            if (parts.weekday === 'Sun') {
                isOpen = minute >= 5 * 60;
            }
            if (parts.weekday === 'Fri' && minute >= 5 * 60) {
                isOpen = false;
            }
            summary = isOpen ? 'Market Open' : 'Weekend Closed';
            detail = isOpen ? 'Auto-updating while global FX market is active' : 'Weekend pause';
            statusTone = isOpen ? 'open' : 'closed';
        } else if (marketType === 'commodity') {
            const inSession = minute < 16 * 60 || minute >= 17 * 60;
            isOpen = isWeekday(parts) && inSession;
            if (parts.weekday === 'Sun') {
                isOpen = minute >= 17 * 60;
            }
            if (parts.weekday === 'Fri' && minute >= 16 * 60) {
                isOpen = false;
            }
            summary = isOpen ? 'Electronic Session Open' : 'Session Break / Closed';
            detail = isOpen
                ? 'CME-style electronic session assumed'
                : 'Daily break or weekly close';
            statusTone = isOpen ? 'open' : 'closed';
        } else if (marketType === 'twstock') {
            isOpen = isWeekday(parts) && minute >= 9 * 60 && minute < 13 * 60 + 30;
            summary = isOpen ? 'Regular Session Open' : 'Market Closed';
            detail = isOpen ? 'Taiwan regular trading hours' : 'Outside 09:00-13:30';
            statusTone = isOpen ? 'open' : 'closed';
        } else if (marketType === 'usstock') {
            isOpen = isWeekday(parts) && minute >= 9 * 60 + 30 && minute < 16 * 60;
            summary = isOpen ? 'Regular Session Open' : 'Market Closed';
            detail = isOpen ? 'US regular trading hours' : 'Outside 09:30-16:00 ET';
            statusTone = isOpen ? 'open' : 'closed';
        }

        const refreshLabel = isOpen
            ? `Auto refresh every ${config.refreshSeconds}s`
            : 'Auto refresh paused outside market hours';

        return {
            ...config,
            isOpen,
            summary,
            detail,
            refreshLabel,
            statusTone,
        };
    }

    function getToneClasses(tone) {
        if (tone === 'open') {
            return 'bg-success/10 text-success border-success/20';
        }
        if (tone === 'closed') {
            return 'bg-white/5 text-textMuted border-white/10';
        }
        return 'bg-white/5 text-textMuted border-white/10';
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function updateMarketStatusBar(marketType, lastUpdated) {
        const state = getMarketState(marketType);
        const badge = document.getElementById(`${marketType}-market-status-badge`);
        if (badge) {
            badge.className =
                `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold ${getToneClasses(state.statusTone)}`;
            badge.textContent = state.summary;
        }

        setText(`${marketType}-market-refresh-note`, state.refreshLabel);
        setText(`${marketType}-market-session-note`, state.detail);

        if (lastUpdated) {
            const dt = new Date(lastUpdated);
            const label = Number.isNaN(dt.getTime())
                ? String(lastUpdated)
                : dt.toLocaleTimeString('zh-TW', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                  });
            setText(`${marketType}-last-updated`, `上次更新 ${label}`);
        } else if (!state.isOpen) {
            setText(`${marketType}-last-updated`, '休市中，等待下次開市');
        }

        return state;
    }

    const statusTimers = {};
    const refreshControllers = {};

    function bindStatusAutoRefresh(marketType, getLastUpdated) {
        if (statusTimers[marketType]) {
            clearInterval(statusTimers[marketType]);
        }

        const refresh = () => {
            const lastUpdated =
                typeof getLastUpdated === 'function' ? getLastUpdated() : undefined;
            updateMarketStatusBar(marketType, lastUpdated);
        };

        refresh();
        statusTimers[marketType] = setInterval(refresh, 1000 * 30);
    }

    function startMarketAutoRefresh(marketType, onRefresh, getLastUpdated) {
        if (refreshControllers[marketType]) {
            clearInterval(refreshControllers[marketType]);
        }

        bindStatusAutoRefresh(marketType, getLastUpdated);

        let lastRunAt = 0;
        const tick = async () => {
            const state = getMarketState(marketType);
            if (!state.isOpen || typeof onRefresh !== 'function') {
                return;
            }

            const intervalMs = state.refreshSeconds * 1000;
            if (Date.now() - lastRunAt < intervalMs) {
                return;
            }

            lastRunAt = Date.now();
            try {
                await onRefresh();
            } catch (error) {
                console.warn(`[MarketStatus] ${marketType} auto refresh failed:`, error);
            }
        };

        refreshControllers[marketType] = setInterval(tick, 5000);
    }

    window.MarketStatus = {
        MARKET_CONFIG,
        getMarketState,
        updateMarketStatusBar,
        bindStatusAutoRefresh,
        startMarketAutoRefresh,
    };
})();
