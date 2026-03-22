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

const AppStore = {
    get: get,
    set: set,
    setMany: setMany,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    has: has,
    keys: keys,
    snapshot: snapshot,
};

window.AppStore = AppStore;
export { AppStore };
