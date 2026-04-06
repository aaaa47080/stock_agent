// ========================================
// market-status.js - Market schedule and refresh UX helpers
// ========================================

(function () {
    function t(key, opts) {
        return window.I18n ? window.I18n.t(key, opts) : key;
    }

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
        hkstock: {
            label: 'HK Stock',
            refreshSeconds: 30,
            timezone: 'Asia/Hong_Kong',
        },
        astock: {
            label: 'A Stock',
            refreshSeconds: 30,
            timezone: 'Asia/Shanghai',
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
            '2026-01-01': "New Year's Day",
            '2026-01-19': 'Martin Luther King Jr. Day',
            '2026-02-16': "Washington's Birthday",
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
            summary: 'Closed',
            detail: '休市中',
            refreshLabel: '休市中，暫停自動更新',
            nextEventLabel: '',
            statusTone: 'closed',
            sessionType: 'closed',
            ...overrides,
        };
    }

    function formatMinuteLabel(totalMinutes) {
        const hour = Math.floor(totalMinutes / 60);
        const minute = totalMinutes % 60;
        return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    }

    function formatEventTime(date, timeZone) {
        return new Intl.DateTimeFormat('zh-TW', {
            timeZone,
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
        }).format(date);
    }

    function createDateFromZoneParts(parts, minutes, timeZone) {
        const hour = Math.floor(minutes / 60);
        const minute = minutes % 60;
        const utcGuess = Date.UTC(parts.year, parts.month - 1, parts.day, hour, minute, 0);
        const zonedGuess = getZonedParts(new Date(utcGuess), timeZone);
        const desiredUtc = Date.UTC(parts.year, parts.month - 1, parts.day, hour, minute, 0);
        const actualUtc = Date.UTC(
            zonedGuess.year,
            zonedGuess.month - 1,
            zonedGuess.day,
            zonedGuess.hour,
            zonedGuess.minute,
            0
        );
        return new Date(utcGuess + (desiredUtc - actualUtc));
    }

    function addDaysFromParts(parts, days, timeZone) {
        const seed = new Date(Date.UTC(parts.year, parts.month - 1, parts.day, 12, 0, 0));
        seed.setUTCDate(seed.getUTCDate() + days);
        return getZonedParts(seed, timeZone);
    }

    function findNextTradingDay(marketType, parts, timeZone, startOffset) {
        for (let offset = startOffset; offset <= 14; offset += 1) {
            const candidate = addDaysFromParts(parts, offset, timeZone);
            const dateKey = getDateKey(candidate);
            if (isWeekday(candidate) && !getHolidayName(marketType, dateKey)) {
                return candidate;
            }
        }
        return null;
    }

    function getForexNextEvent(parts, isOpen) {
        const minute = minutesSinceMidnight(parts);

        if (isOpen) {
            if (parts.weekday === 'Sun') {
                return {
                    kind: 'close',
                    date: createDateFromZoneParts(
                        addDaysFromParts(parts, 5, 'Asia/Taipei'),
                        5 * 60,
                        'Asia/Taipei'
                    ),
                };
            }
            if (parts.weekday === 'Mon') {
                return {
                    kind: 'close',
                    date: createDateFromZoneParts(
                        addDaysFromParts(parts, 4, 'Asia/Taipei'),
                        5 * 60,
                        'Asia/Taipei'
                    ),
                };
            }
            if (parts.weekday === 'Tue') {
                return {
                    kind: 'close',
                    date: createDateFromZoneParts(
                        addDaysFromParts(parts, 3, 'Asia/Taipei'),
                        5 * 60,
                        'Asia/Taipei'
                    ),
                };
            }
            if (parts.weekday === 'Wed') {
                return {
                    kind: 'close',
                    date: createDateFromZoneParts(
                        addDaysFromParts(parts, 2, 'Asia/Taipei'),
                        5 * 60,
                        'Asia/Taipei'
                    ),
                };
            }
            return {
                kind: 'close',
                date: createDateFromZoneParts(
                    addDaysFromParts(parts, 1, 'Asia/Taipei'),
                    5 * 60,
                    'Asia/Taipei'
                ),
            };
        }

        let offset = 0;
        if (parts.weekday === 'Fri' && minute >= 5 * 60) {
            offset = 2;
        } else if (parts.weekday === 'Sat') {
            offset = 1;
        }
        return {
            kind: 'open',
            date: createDateFromZoneParts(
                addDaysFromParts(parts, offset, 'Asia/Taipei'),
                5 * 60,
                'Asia/Taipei'
            ),
        };
    }

    function getCommodityNextEvent(parts, isOpen) {
        const minute = minutesSinceMidnight(parts);

        if (isOpen) {
            if (parts.weekday === 'Fri') {
                return {
                    kind: 'close',
                    date: createDateFromZoneParts(parts, 16 * 60, 'America/Chicago'),
                };
            }
            return {
                kind: 'close',
                date: createDateFromZoneParts(parts, 16 * 60, 'America/Chicago'),
            };
        }

        if (parts.weekday === 'Sun' && minute < 17 * 60) {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 17 * 60, 'America/Chicago'),
            };
        }
        if (parts.weekday === 'Sat') {
            return {
                kind: 'open',
                date: createDateFromZoneParts(
                    addDaysFromParts(parts, 1, 'America/Chicago'),
                    17 * 60,
                    'America/Chicago'
                ),
            };
        }
        if (parts.weekday === 'Fri' && minute >= 16 * 60) {
            return {
                kind: 'open',
                date: createDateFromZoneParts(
                    addDaysFromParts(parts, 2, 'America/Chicago'),
                    17 * 60,
                    'America/Chicago'
                ),
            };
        }
        if (minute >= 16 * 60 && minute < 17 * 60) {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 17 * 60, 'America/Chicago'),
            };
        }
        return {
            kind: 'open',
            date: createDateFromZoneParts(parts, 17 * 60, 'America/Chicago'),
        };
    }

    function getTWStockNextEvent(parts, state) {
        const minute = minutesSinceMidnight(parts);

        if (state.sessionType === 'regular') {
            return {
                kind: 'close',
                date: createDateFromZoneParts(parts, 13 * 60 + 30, 'Asia/Taipei'),
            };
        }

        if (state.sessionType === 'preopen') {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 9 * 60, 'Asia/Taipei'),
            };
        }

        if (isWeekday(parts) && !getHolidayName('twstock', getDateKey(parts)) && minute < 8 * 60 + 30) {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 8 * 60 + 30, 'Asia/Taipei'),
            };
        }

        const nextTradingDay = findNextTradingDay(
            'twstock',
            parts,
            'Asia/Taipei',
            1
        );
        if (!nextTradingDay) {
            return null;
        }

        return {
            kind: 'open',
            date: createDateFromZoneParts(nextTradingDay, 8 * 60 + 30, 'Asia/Taipei'),
        };
    }

    function getUSStockNextEvent(parts, state, regularCloseMinutes, afterHoursCloseMinutes) {
        const minute = minutesSinceMidnight(parts);
        const todayIsTradingDay = isWeekday(parts) && !getHolidayName('usstock', getDateKey(parts));

        if (state.sessionType === 'pre_market') {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 9 * 60 + 30, 'America/New_York'),
            };
        }

        if (state.sessionType === 'regular') {
            return {
                kind: 'close',
                date: createDateFromZoneParts(parts, regularCloseMinutes, 'America/New_York'),
            };
        }

        if (state.sessionType === 'after_hours') {
            return {
                kind: 'close',
                date: createDateFromZoneParts(
                    parts,
                    afterHoursCloseMinutes,
                    'America/New_York'
                ),
            };
        }

        if (todayIsTradingDay && minute < 4 * 60) {
            return {
                kind: 'open',
                date: createDateFromZoneParts(parts, 4 * 60, 'America/New_York'),
            };
        }

        const nextTradingDay = findNextTradingDay(
            'usstock',
            parts,
            'America/New_York',
            1
        );
        if (!nextTradingDay) {
            return null;
        }

        return {
            kind: 'open',
            date: createDateFromZoneParts(nextTradingDay, 4 * 60, 'America/New_York'),
        };
    }

    function buildNextEventLabel(config, nextEvent) {
        if (!nextEvent || !nextEvent.date) {
            return '';
        }

        const prefix = nextEvent.kind === 'close' ? t('status.expectedClose') : t('status.nextOpen');
        return `${prefix}：${formatEventTime(nextEvent.date, config.timezone)}`;
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

        const nextEvent = getForexNextEvent(parts, isOpen);

        return createState(config, {
            isOpen,
            summary: isOpen ? t('status.fxOpen') : t('status.fxClosed'),
            detail: isOpen ? t('status.liveUpdate') : t('status.weekendPaused'),
            refreshLabel: isOpen
                ? t('status.autoUpdate', { seconds: config.refreshSeconds })
                : t('status.paused'),
            nextEventLabel: buildNextEventLabel(config, nextEvent),
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

        const nextEvent = getCommodityNextEvent(parts, isOpen);

        let summary = t('status.marketClosed');
        let detail = t('status.paused');
        let refreshLabel = t('status.paused');

        if (isOpen) {
            summary = t('status.electronicSession');
            detail = t('status.liveUpdate');
            refreshLabel = t('status.autoUpdate', { seconds: config.refreshSeconds });
        } else if (inDailyBreak && parts.weekday !== 'Sat') {
            summary = t('status.sessionBreak');
            detail = t('status.dailyBreak');
        }

        return createState(config, {
            isOpen,
            summary,
            detail,
            refreshLabel,
            nextEventLabel: buildNextEventLabel(config, nextEvent),
            statusTone: isOpen ? 'open' : 'closed',
            sessionType: isOpen ? 'regular' : 'closed',
        });
    }

    function getTWStockState(config, parts) {
        const dateKey = getDateKey(parts);
        const minute = minutesSinceMidnight(parts);
        const holidayName = getHolidayName('twstock', dateKey);
        let state;

        if (holidayName) {
            state = createState(config, {
                summary: t('status.twHoliday'),
                detail: `${holidayName}，${t('status.marketClosed')}`,
                sessionType: 'holiday',
            });
        } else if (!isWeekday(parts)) {
            state = createState(config, {
                summary: t('status.marketClosed'),
                detail: t('status.weekendPaused'),
            });
        } else if (minute >= 9 * 60 && minute < 13 * 60 + 30) {
            state = createState(config, {
                isOpen: true,
                summary: t('nav.twstock') + ' Open',
                detail: t('status.liveUpdate'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'open',
                sessionType: 'regular',
            });
        } else if (minute >= 8 * 60 + 30 && minute < 9 * 60) {
            state = createState(config, {
                summary: t('status.preMarket'),
                detail: t('status.preMarket'),
                sessionType: 'preopen',
            });
        } else {
            state = createState(config, {
                summary: t('status.marketClosed'),
                detail: t('status.paused'),
            });
        }

        return {
            ...state,
            nextEventLabel: buildNextEventLabel(config, getTWStockNextEvent(parts, state)),
        };
    }

    function getHKStockState(config, parts) {
        // HKEX: 9:30-12:00 morning, 13:00-16:00 afternoon (HKT)
        const minute = minutesSinceMidnight(parts);
        let state;
        if (!isWeekday(parts)) {
            state = createState(config, { summary: t('status.marketClosed'), detail: t('status.weekendPaused') });
        } else if ((minute >= 9 * 60 + 30 && minute < 12 * 60) || (minute >= 13 * 60 && minute < 16 * 60)) {
            state = createState(config, {
                isOpen: true,
                summary: '港股 Open',
                detail: t('status.liveUpdate'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'open',
                sessionType: 'regular',
            });
        } else if (minute >= 12 * 60 && minute < 13 * 60) {
            state = createState(config, { summary: '午間休市', detail: '13:00 恢復交易', sessionType: 'break' });
        } else if (minute >= 9 * 60 && minute < 9 * 60 + 30) {
            state = createState(config, { summary: t('status.preMarket'), detail: '9:30 開市', sessionType: 'preopen' });
        } else {
            state = createState(config, { summary: t('status.marketClosed'), detail: t('status.paused') });
        }
        return state;
    }

    function getAStockState(config, parts) {
        // A-Share: 9:30-11:30 morning, 13:00-15:00 afternoon (CST)
        const minute = minutesSinceMidnight(parts);
        let state;
        if (!isWeekday(parts)) {
            state = createState(config, { summary: t('status.marketClosed'), detail: t('status.weekendPaused') });
        } else if ((minute >= 9 * 60 + 30 && minute < 11 * 60 + 30) || (minute >= 13 * 60 && minute < 15 * 60)) {
            state = createState(config, {
                isOpen: true,
                summary: 'A股 Open',
                detail: t('status.liveUpdate'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'open',
                sessionType: 'regular',
            });
        } else if (minute >= 11 * 60 + 30 && minute < 13 * 60) {
            state = createState(config, { summary: '午間休市', detail: '13:00 恢復交易', sessionType: 'break' });
        } else if (minute >= 9 * 60 && minute < 9 * 60 + 30) {
            state = createState(config, { summary: t('status.preMarket'), detail: '9:30 開市', sessionType: 'preopen' });
        } else {
            state = createState(config, { summary: t('status.marketClosed'), detail: t('status.paused') });
        }
        return state;
    }

    function getUSStockState(config, parts) {
        const dateKey = getDateKey(parts);
        const minute = minutesSinceMidnight(parts);
        const holidayName = getHolidayName('usstock', dateKey);
        const specialSession = getSpecialSession('usstock', dateKey);
        const regularCloseMinutes = specialSession?.regularCloseMinutes ?? 16 * 60;
        const afterHoursCloseMinutes = specialSession?.afterHoursCloseMinutes ?? 20 * 60;
        let state;

        if (holidayName) {
            state = createState(config, {
                summary: t('status.marketClosed'),
                detail: `${holidayName}，${t('status.marketClosed')}`,
                sessionType: 'holiday',
            });
        } else if (!isWeekday(parts)) {
            state = createState(config, {
                summary: t('status.marketClosed'),
                detail: t('status.weekendPaused'),
            });
        } else if (minute >= 4 * 60 && minute < 9 * 60 + 30) {
            state = createState(config, {
                isOpen: true,
                summary: t('status.preMarket'),
                detail: specialSession
                    ? `${specialSession.label} ${t('status.preMarket')}`
                    : t('status.preMarket'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'extended',
                sessionType: 'pre_market',
            });
        } else if (minute >= 9 * 60 + 30 && minute < regularCloseMinutes) {
            state = createState(config, {
                isOpen: true,
                summary: regularCloseMinutes < 16 * 60 ? t('status.earlyClose') : t('status.regular'),
                detail: regularCloseMinutes < 16 * 60
                    ? `${t('status.earlyClose')} ${formatMinuteLabel(regularCloseMinutes)} ET`
                    : t('status.regular'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'open',
                sessionType: 'regular',
            });
        } else if (minute >= regularCloseMinutes && minute < afterHoursCloseMinutes) {
            state = createState(config, {
                isOpen: true,
                summary: t('status.afterHours'),
                detail: regularCloseMinutes < 16 * 60
                    ? `${specialSession.detail}，${t('status.afterHours')} ${formatMinuteLabel(afterHoursCloseMinutes)} ET`
                    : t('status.afterHours'),
                refreshLabel: t('status.autoUpdate', { seconds: config.refreshSeconds }),
                statusTone: 'extended',
                sessionType: 'after_hours',
            });
        } else {
            state = createState(config, {
                summary: t('status.marketClosed'),
                detail: regularCloseMinutes < 16 * 60
                    ? `${t('status.earlyClose')} - ${formatMinuteLabel(afterHoursCloseMinutes)} ET`
                    : t('status.paused'),
            });
        }

        return {
            ...state,
            nextEventLabel: buildNextEventLabel(
                config,
                getUSStockNextEvent(parts, state, regularCloseMinutes, afterHoursCloseMinutes)
            ),
        };
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
                    summary: 'Unknown',
                    detail: '未設定市場時段',
                    refreshLabel: '僅支援手動更新',
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
        if (marketType === 'hkstock') {
            return getHKStockState(config, parts);
        }
        if (marketType === 'astock') {
            return getAStockState(config, parts);
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
        setText(
            `${marketType}-market-session-note`,
            state.nextEventLabel ? `${state.detail} | ${state.nextEventLabel}` : state.detail
        );

        const lastUpdatedLabel = formatLastUpdatedLabel(lastUpdated);
        if (lastUpdatedLabel) {
            setText(`${marketType}-last-updated`, `${t('status.lastUpdated')}：${lastUpdatedLabel}`);
        } else if (!state.isOpen) {
            setText(`${marketType}-last-updated`, `${t('status.lastUpdated')}：${t('status.marketClosed')}`);
        } else {
            setText(`${marketType}-last-updated`, `${t('status.lastUpdated')}：${t('status.awaitingSync')}`);
        }

        return state;
    }

    const statusTimers = {};
    const refreshControllers = {};
    const _syncedMarkets = {};
    let _clockTimer = null;

    function markSynced(marketType) {
        _syncedMarkets[marketType] = true;
    }

    function _startGlobalClock() {
        if (_clockTimer) return;
        _clockTimer = setInterval(() => {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('zh-TW', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
            });

            for (const [mt, synced] of Object.entries(_syncedMarkets)) {
                if (!synced) continue;
                const el = document.getElementById(`${mt}-last-updated`);
                if (el) el.textContent = `${t('status.lastUpdated')}：${timeStr}`;
            }

            const screenerEl = document.getElementById('screener-last-updated');
            if (screenerEl && _syncedMarkets['screener']) {
                screenerEl.textContent = `LIVE (更新於: ${timeStr})`;
            }
        }, 1000);
    }

    function bindStatusAutoRefresh(marketType, getLastUpdated) {
        if (statusTimers[marketType]) {
            clearInterval(statusTimers[marketType]);
        }

        _startGlobalClock();

        const refresh = () => {
            const lastUpdated =
                typeof getLastUpdated === 'function' ? getLastUpdated() : undefined;
            if (lastUpdated) markSynced(marketType);
            const state = getMarketState(marketType);
            const badge = document.getElementById(`${marketType}-market-status-badge`);
            if (badge) {
                badge.className = `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold ${getToneClasses(state.statusTone)}`;
                badge.textContent = state.summary;
            }
            setText(`${marketType}-market-refresh-note`, state.refreshLabel);
            setText(
                `${marketType}-market-session-note`,
                state.nextEventLabel ? `${state.detail} | ${state.nextEventLabel}` : state.detail
            );
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
        markSynced,
    };
})();

// ES module re-export
export { }; // MarketStatus is already on window; importers should use window.MarketStatus

