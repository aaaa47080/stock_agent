/**
 * Centralized State Store (Pub/Sub)
 *
 * Replaces scattered window.* global variables with a single store.
 * Supports get/set/subscribe patterns for reactive state management.
 *
 * Usage:
 *   AppStore.set('activeTab', 'crypto');
 *   AppStore.get('activeTab'); // 'crypto'
 *   AppStore.subscribe('activeTab', (newVal, oldVal) => { ... });
 *   AppStore.setMany({ activeTab: 'chat', isAnalyzing: false });
 */
var _state = {};
var _subscribers = {};

function get(key) {
    return _state[key];
}

function set(key, value) {
    var oldValue = _state[key];
    _state[key] = value;
    if (_subscribers[key]) {
        _subscribers[key].forEach(function (fn) {
            try {
                fn(value, oldValue);
            } catch (e) {
                if (typeof _console !== 'undefined') {
                    _console.error('[AppStore] subscriber error for "' + key + '":', e);
                }
            }
        });
    }
}

function setMany(obj) {
    Object.keys(obj).forEach(function (key) {
        set(key, obj[key]);
    });
}

function subscribe(key, fn) {
    if (!_subscribers[key]) {
        _subscribers[key] = [];
    }
    _subscribers[key].push(fn);
    return function () {
        _subscribers[key] = _subscribers[key].filter(function (f) {
            return f !== fn;
        });
    };
}

function unsubscribe(key, fn) {
    if (!_subscribers[key]) return;
    _subscribers[key] = _subscribers[key].filter(function (f) {
        return f !== fn;
    });
}

function has(key) {
    return key in _state;
}

function keys() {
    return Object.keys(_state);
}

function snapshot() {
    return JSON.parse(JSON.stringify(_state));
}

var _PERSIST_KEY = '__appstore_state__';

var _RESTORABLE = new Set([
    'activeTab', 'isAnalyzing', 'currentSessionId', 'chatInitialized',
    'currentPulseData', 'forceGuestLandingTab',
    'settingsConfigCache', 'lastApiKeyCheck', 'lastProcessOpenState',
]);

function persist() {
    try {
        var data = {};
        _RESTORABLE.forEach(function (k) {
            if (k in _state) data[k] = _state[k];
        });
        sessionStorage.setItem(_PERSIST_KEY, JSON.stringify(data));
    } catch (e) { /* quota exceeded — ignore */ }
}

function restore() {
    try {
        var raw = sessionStorage.getItem(_PERSIST_KEY);
        if (!raw) return false;
        var data = JSON.parse(raw);
        if (typeof data !== 'object' || data === null) return false;
        Object.keys(data).forEach(function (k) {
            if (_RESTORABLE.has(k)) set(k, data[k]);
        });
        sessionStorage.removeItem(_PERSIST_KEY);
        return true;
    } catch (e) { return false; }
}

document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') persist();
});

window.addEventListener('pagehide', persist);

const AppStore = {
    get: get,
    set: set,
    setMany: setMany,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    has: has,
    keys: keys,
    snapshot: snapshot,
    persist: persist,
    restore: restore,
};

window.AppStore = AppStore;
export { AppStore };
