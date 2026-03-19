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

    const HOLIDAY_CALENDAR = {
        twstock: {
            '2026-01-01': 'New Year Holiday',
            '2026-02-12': 'Lunar New Year Break',
            '2026-02-13': 'Lunar New Year Break',
            '2026-02-16': 'Lunar New Year Break',
            '2026-02-17': 'Lunar New Year Break',
            '2026-02-18': 'Lunar New Year Break',
            '2026-02-19': 'Lunar New Year Break',
            '2026-02-20': 'Lunar New Year Observed',
            '2026-02-27': 'Peace Memorial Day Observed',
            '2026-04-03': 'Children and Tomb Sweeping Day Observed',
            '2026-04-06': 'Tomb Sweeping Day Observed',
            '2026-05-01': 'Labor Day',
            '2026-06-19': 'Dragon Boat Festival',
            '2026-09-25': 'Mid-Autumn Festival Observed',
            '2026-09-28': 'Confucius Birthday',
            '2026-10-09': 'National Day Observed',
            '2026-10-26': 'Taiwan Retrocession Day Observed',
            '2026-12-25': 'Constitution Day',
        },
        usstock: {
            '2026-01-01': 'New Year\'s Day',
            '2026-01-19': 'Martin Luther King Jr. Day',
            '2026-02-16': 'Washington\'s Birthday',
            '2026-04-03': 'Good Friday',
            '2026-05-25': 'Memorial Day',
            '2026-06-19': 'Juneteenth',
            '2026-07-03': 'Independence Day Observed',
            '2026-09-07': 'Labor Day',
            '2026-11-26': 'Thanksgiving Day',
            '2026-12-25': 'Christmas Day',
        },
    };

    const SPECIAL_SESSIONS = {
        usstock: {
            '2026-11-27': {
                regularCloseMinutes: 13 * 60,
                afterHoursCloseMinutes: 17 * 60,
                label: 'Early Close',
                detail: 'NYSE early close day',
            },
            '2026-12-24': {
                regularCloseMinutes: 13 * 60,
                afterHoursCloseMinutes: 17 * 60,
                label: 'Early Close',
                detail: 'NYSE early close day',
            },
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

    function getDateKey(parts) {
        return [
            String(parts.year).padStart(4, '0'),
            String(parts.month).padStart(2, '0'),
            String(parts.day).padStart(2, '0'),
        ].join('-');
    }

    function getHolidayName(marketType, dateKey) {
        return HOLIDAY_CALENDAR[marketType]?.[dateKey] || null;
    }

    function getSpecialSession(marketType, dateKey) {
        return SPECIAL_SESSIONS[marketType]?.[dateKey] || null;
    }

    function createState(config, overrides = {}) {
        return {
            ...config,
            isOpen: false,
            summary: 'Market Closed',
            detail: 'Auto refresh paused outside market hours',
            refreshLabel: 'Auto refresh paused outside market hours',
            statusTone: 'closed',
            sessionType: 'closed',
            ...overrides,
        };
    }

    function getForexState(config, parts) {
        const minute = minutesSinceMidnight(parts);
        let isOpen = parts.weekday !== 'Sat';

        if (parts.weekday === 'Sun') {
            isOpen = minute >= 5 * 60;
        }
        if (parts.weekday === 'Fri' && minute >= 5 * 60) {
            isOpen = false;
        }

        return createState(config, {
            isOpen,
            summary: isOpen ? 'FX Market Open' : 'Weekend Closed',
            detail: isOpen
                ? 'Auto refresh is active while the global FX market is trading'
                : 'Auto refresh resumes when the market reopens on Monday',
            refreshLabel: isOpen
                ? `Auto refresh every ${config.refreshSeconds}s`
                : 'Auto refresh paused for weekend close',
            statusTone: isOpen ? 'open' : 'closed',
            sessionType: isOpen ? 'regular' : 'closed',
        });
    }

    function getCommodityState(config, parts) {
        const minute = minutesSinceMidnight(parts);
        const inDailyBreak = minute >= 16 * 60 && minute < 17 * 60;
        let isOpen = isWeekday(parts) && !inDailyBreak;

        if (parts.weekday === 'Sun') {
            isOpen = minute >= 17 * 60;
        }
        if (parts.weekday === 'Fri' && minute >= 16 * 60) {
            isOpen = false;
        }

        let summary = 'Electronic Session Closed';
        let detail = 'Auto refresh resumes when the next electronic session opens';
        let refreshLabel = 'Auto refresh paused outside market hours';

        if (isOpen) {
            summary = 'Electronic Session Open';
            detail = 'CME-style electronic session with daily maintenance break';
            refreshLabel = `Auto refresh every ${config.refreshSeconds}s`;
        } else if (inDailyBreak && parts.weekday !== 'Sat') {
            summary = 'Session Break';
            detail = 'Daily maintenance break 16:00-17:00 CT';
        }

        return createState(config, {
            isOpen,
            summary,
            detail,
            refreshLabel,
            statusTone: isOpen ? 'open' : 'closed',
            sessionType: isOpen ? 'regular' : 'closed',
        });
    }

    function getTWStockState(config, parts) {
        const dateKey = getDateKey(parts);
        const minute = minutesSinceMidnight(parts);
        const holidayName = getHolidayName('twstock', dateKey);

        if (holidayName) {
            return createState(config, {
                summary: 'TW Market Holiday',
                detail: `${holidayName}. Auto refresh is paused today`,
                sessionType: 'holiday',
            });
        }

        if (!isWeekday(parts)) {
            return createState(config, {
                summary: 'Weekend Closed',
                detail: 'Taiwan stock market is closed on weekends',
            });
        }

        if (minute >= 9 * 60 && minute < 13 * 60 + 30) {
            return createState(config, {
                isOpen: true,
                summary: 'Regular Session Open',
                detail: 'Regular trading hours 09:00-13:30 Taipei time',
                refreshLabel: `Auto refresh every ${config.refreshSeconds}s`,
                statusTone: 'open',
                sessionType: 'regular',
            });
        }

        if (minute >= 8 * 60 + 30 && minute < 9 * 60) {
            return createState(config, {
                summary: 'Pre-Open',
                detail: 'Order collection period before the regular session',
                sessionType: 'preopen',
            });
        }

        return createState(config, {
            summary: 'Market Closed',
            detail: 'Outside Taiwan regular trading hours',
        });
    }

    function getUSStockState(config, parts) {
        const dateKey = getDateKey(parts);
        const minute = minutesSinceMidnight(parts);
        const holidayName = getHolidayName('usstock', dateKey);
        const specialSession = getSpecialSession('usstock', dateKey);
        const regularCloseMinutes = specialSession?.regularCloseMinutes ?? 16 * 60;
        const afterHoursCloseMinutes = specialSession?.afterHoursCloseMinutes ?? 20 * 60;

        if (holidayName) {
            return createState(config, {
                summary: 'US Market Holiday',
                detail: `${holidayName}. Auto refresh is paused today`,
                sessionType: 'holiday',
            });
        }

        if (!isWeekday(parts)) {
            return createState(config, {
                summary: 'Weekend Closed',
                detail: 'US stock market is closed on weekends',
            });
        }

        // Use America/New_York local time so DST is handled by the platform.
        if (minute >= 4 * 60 && minute < 9 * 60 + 30) {
            return createState(config, {
                isOpen: true,
                summary: 'Pre-Market',
                detail: specialSession
                    ? `${specialSession.label}: extended trading before the early close`
                    : 'Extended trading session before the regular open',
                refreshLabel: `Auto refresh every ${config.refreshSeconds}s`,
                statusTone: 'extended',
                sessionType: 'pre_market',
            });
        }

        if (minute >= 9 * 60 + 30 && minute < regularCloseMinutes) {
            return createState(config, {
                isOpen: true,
                summary:
                    regularCloseMinutes < 16 * 60 ? 'Early-Close Session' : 'Regular Session Open',
                detail:
                    regularCloseMinutes < 16 * 60
                        ? `Regular trading until ${formatMinuteLabel(regularCloseMinutes)} ET`
                        : 'Regular trading hours 09:30-16:00 ET',
                refreshLabel: `Auto refresh every ${config.refreshSeconds}s`,
                statusTone: 'open',
                sessionType: 'regular',
            });
        }

        if (minute >= regularCloseMinutes && minute < afterHoursCloseMinutes) {
            return createState(config, {
                isOpen: true,
                summary: 'After-Hours',
                detail:
                    regularCloseMinutes < 16 * 60
                        ? `${specialSession.detail} with extended trading until ${formatMinuteLabel(afterHoursCloseMinutes)} ET`
                        : 'Extended trading session after the regular close',
                refreshLabel: `Auto refresh every ${config.refreshSeconds}s`,
                statusTone: 'extended',
                sessionType: 'after_hours',
            });
        }

        return createState(config, {
            summary: 'Market Closed',
            detail:
                regularCloseMinutes < 16 * 60
                    ? `Early-close schedule finished at ${formatMinuteLabel(afterHoursCloseMinutes)} ET`
                    : 'Outside US trading hours',
        });
    }

    function formatMinuteLabel(totalMinutes) {
        const hour = Math.floor(totalMinutes / 60);
        const minute = totalMinutes % 60;
        return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    }

    function getMarketState(marketType, now = new Date()) {
        const config = MARKET_CONFIG[marketType];
        if (!config) {
            return createState(
                {
                    label: 'Unknown',
                    refreshSeconds: 0,
                    timezone: 'UTC',
                },
                {
                    summary: 'Unknown market',
                    detail: 'No schedule configured',
                    refreshLabel: 'Manual refresh only',
                    statusTone: 'muted',
                }
            );
        }

        const parts = getZonedParts(now, config.timezone);

        if (marketType === 'forex') {
            return getForexState(config, parts);
        }
        if (marketType === 'commodity') {
            return getCommodityState(config, parts);
        }
        if (marketType === 'twstock') {
            return getTWStockState(config, parts);
        }
        if (marketType === 'usstock') {
            return getUSStockState(config, parts);
        }

        return createState(config);
    }

    function getToneClasses(tone) {
        if (tone === 'open') {
            return 'bg-success/10 text-success border-success/20';
        }
        if (tone === 'extended') {
            return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20';
        }
        if (tone === 'closed') {
            return 'bg-white/5 text-textMuted border-white/10';
        }
        return 'bg-white/5 text-textMuted border-white/10';
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = text;
        }
    }

    function formatLastUpdatedLabel(lastUpdated) {
        if (!lastUpdated) {
            return null;
        }

        const dt = new Date(lastUpdated);
        if (Number.isNaN(dt.getTime())) {
            return String(lastUpdated);
        }

        return dt.toLocaleTimeString('zh-TW', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    }

    function updateMarketStatusBar(marketType, lastUpdated) {
        const state = getMarketState(marketType);
        const badge = document.getElementById(`${marketType}-market-status-badge`);

        if (badge) {
            badge.className = `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold ${getToneClasses(state.statusTone)}`;
            badge.textContent = state.summary;
        }

        setText(`${marketType}-market-refresh-note`, state.refreshLabel);
        setText(`${marketType}-market-session-note`, state.detail);

        const lastUpdatedLabel = formatLastUpdatedLabel(lastUpdated);
        if (lastUpdatedLabel) {
            setText(`${marketType}-last-updated`, `上次更新：${lastUpdatedLabel}`);
        } else if (!state.isOpen) {
            setText(`${marketType}-last-updated`, '上次更新：休市中');
        } else {
            setText(`${marketType}-last-updated`, '上次更新：等待首次同步');
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
        statusTimers[marketType] = setInterval(refresh, 30 * 1000);
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
