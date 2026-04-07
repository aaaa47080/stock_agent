/* Shared UI shell helpers for toast rendering and fixed-stack spacing. */

const DEFAULT_TOAST_DURATION = 3000;
const ROOT = document.documentElement;

function escapeText(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getFixedStackHeight() {
    const selectors = ['[data-shell-fixed-nav]', '[data-shell-fixed-input]'];

    return selectors.reduce(function (total, selector) {
        return total + Array.from(document.querySelectorAll(selector)).reduce(function (sum, element) {
            if (!element) {
                return sum;
            }
            const computedStyle = window.getComputedStyle(element);
            if (
                computedStyle.display === 'none' ||
                computedStyle.visibility === 'hidden' ||
                computedStyle.opacity === '0'
            ) {
                return sum;
            }

            if (
                selector === '[data-shell-fixed-input]' &&
                window.innerWidth >= 768 &&
                computedStyle.position !== 'fixed'
            ) {
                return sum;
            }

            return sum + element.getBoundingClientRect().height;
        }, 0);
    }, 0);
}

function getVisibleHeight(selector) {
    return Array.from(document.querySelectorAll(selector)).reduce(function (sum, element) {
        if (!element) {
            return sum;
        }
        const computedStyle = window.getComputedStyle(element);
        if (
            computedStyle.display === 'none' ||
            computedStyle.visibility === 'hidden' ||
            computedStyle.opacity === '0'
        ) {
            return sum;
        }
        if (
            selector === '[data-shell-fixed-nav]' &&
            ROOT.classList.contains('chat-keyboard-open')
        ) {
            return sum;
        }
        return sum + element.getBoundingClientRect().height;
    }, 0);
}

function applyScrollPadding() {
    document.querySelectorAll('[data-shell-scroll]').forEach(function (element) {
        const extra = element.getAttribute('data-shell-scroll-extra') || '0px';
        element.style.paddingBottom = 'calc(var(--shell-fixed-stack-offset, 0px) + ' + extra + ')';
    });
}

function syncLayout() {
    const fixedStackHeight = getFixedStackHeight();
    const navHeight = getVisibleHeight('[data-shell-fixed-nav]');
    const inputHeight = getVisibleHeight('[data-shell-fixed-input]');
    ROOT.style.setProperty('--shell-fixed-stack-offset', fixedStackHeight + 'px');
    ROOT.style.setProperty('--shell-fixed-nav-height', navHeight + 'px');
    ROOT.style.setProperty('--shell-fixed-input-height', inputHeight + 'px');
    ROOT.style.setProperty('--shell-toast-bottom', 'calc(' + fixedStackHeight + 'px + 1rem + env(safe-area-inset-bottom, 0px))');
    applyScrollPadding();
}

function ensureToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.setAttribute('role', 'status');
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        container.className = 'fixed z-[110] flex flex-col gap-3 pointer-events-none bottom-4 left-4 right-4 items-center md:bottom-auto md:top-24 md:left-auto md:right-4 md:items-end';
        document.body.appendChild(container);
    }
    return container;
}

function showToast(message, type, duration) {
    const container = ensureToastContainer();
    const tone = type || 'info';
    const timeout = typeof duration === 'number' ? duration : DEFAULT_TOAST_DURATION;

    const icons = {
        success: 'check-circle',
        error: 'x-circle',
        warning: 'alert-triangle',
        info: 'info',
    };

    const colors = {
        success: 'bg-success/20 border-success/30 text-success',
        error: 'bg-danger/20 border-danger/30 text-danger',
        warning: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
        info: 'bg-primary/20 border-primary/30 text-primary',
    };

    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border px-4 py-3 backdrop-blur-xl shadow-xl animate-fade-in-up ' + (colors[tone] || colors.info);
    toast.innerHTML = [
        '<i data-lucide="' + (icons[tone] || icons.info) + '" class="w-5 h-5 flex-shrink-0 mt-0.5"></i>',
        '<p class="text-sm leading-relaxed whitespace-pre-line flex-1">' + escapeText(message || '') + '</p>',
        '<button type="button" class="text-current opacity-60 hover:opacity-100 transition" aria-label="Close toast">',
        '<i data-lucide="x" class="w-4 h-4"></i>',
        '</button>',
    ].join('');

    const dismiss = function () {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'all 0.25s ease';
        window.setTimeout(function () {
            toast.remove();
        }, 250);
    };

    toast.querySelector('button').addEventListener('click', dismiss);
    container.appendChild(toast);

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }

    if (timeout > 0) {
        window.setTimeout(dismiss, timeout);
    }

    return toast;
}

function dismissToast(toast) {
    if (!toast || typeof toast.remove !== 'function') {
        return;
    }

    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.25s ease';
    window.setTimeout(function () {
        toast.remove();
    }, 250);
}

function clearToasts() {
    const container = document.getElementById('toast-container');
    if (!container) {
        return;
    }

    Array.from(container.children).forEach(function (toast) {
        dismissToast(toast);
    });
}

function initialize() {
    syncLayout();

    const fixedElements = document.querySelectorAll('[data-shell-fixed-nav], [data-shell-fixed-input]');

    if (typeof window.ResizeObserver === 'function') {
        const observer = new window.ResizeObserver(syncLayout);
        fixedElements.forEach(function (element) {
            observer.observe(element);
        });
    }

    if (typeof window.MutationObserver === 'function') {
        const mutationObserver = new window.MutationObserver(syncLayout);
        fixedElements.forEach(function (element) {
            mutationObserver.observe(element, {
                attributes: true,
                attributeFilter: ['class', 'style', 'hidden'],
            });
        });
    }

    window.addEventListener('resize', window.Utils ? window.Utils.debounce(syncLayout, 100) : syncLayout);
    window.addEventListener('orientationchange', window.Utils ? window.Utils.debounce(syncLayout, 100) : syncLayout);
}

const UIShell = {
    ensureToastContainer: ensureToastContainer,
    showToast: showToast,
    dismissToast: dismissToast,
    clearToasts: clearToasts,
    syncLayout: syncLayout,
    applyScrollPadding: applyScrollPadding,
    initialize: initialize,
};

window.UIShell = UIShell;
window.showToast = showToast;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

export { UIShell, showToast };
