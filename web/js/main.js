// ========================================
// main.js - Application Entry Point
// ========================================
// Loaded via <script type="module"> in index.html.
// Import order matters: dependencies first, then consumers.
//
// Side-effect-only modules (no exports needed):
//   logger.js, pi-auth.js, i18n.js
//
// Simple modules (already converted to ES module format):
//   store.js, utils.js, api-client.js, security-utils.js, ui-shell.js,
//   legal.js, filter.js, testMode.js, wallet.js, alerts.js
//
// Complex modules (NOT yet converted internally — imported for side-effects only):
//   app.js, apiKeyManager.js, auth.js, friends.js, messages.js,
//   forum-app.js, admin.js, spa.js, components/*, chat-*.js, etc.
// ========================================

// ─── Phase 1: Core utilities (MUST load first) ───────────────────────────
import './store.js';           // AppStore (pub/sub state)

AppStore.restore();

window.addEventListener('unhandledrejection', (event) => {
    console.error('[Unhandled Rejection]', event.reason);
    if (typeof showToast === 'function') {
        showToast('發生未預期的錯誤', 'error');
    }
});

window.addEventListener('error', (event) => {
    console.error('[Global Error]', event.error);
});

import './utils.js';           // AppUtils (shared helpers)
import './api-client.js';      // AppAPI (HTTP client)

// ─── Phase 2: Side-effect-only modules ────────────────────────────────────
// Note: pi-auth.js is loaded in <head> via a regular <script> tag
//        and cannot be re-imported as a module. It runs before everything.
//        logger.js must run early to capture console output.

// ─── Phase 3: UI shell & layout ───────────────────────────────────────────
import './ui-shell.js';        // UIShell, showToast

// ─── Phase 4: Security & utilities ────────────────────────────────────────
import './security-utils.js';  // SecurityUtils (XSS, CSP)

// ─── Phase 5: App core ────────────────────────────────────────────────────
import './app.js';             // Main app logic
import './apiKeyManager.js';   // API key management
import './auth.js';            // AuthManager

// ─── Phase 6: Components system (load order matters) ──────────────────────
import './components/css-constants.js';
import './components/tab-crypto.js';
import './components/tab-twstock.js';
import './components/tab-usstock.js';
import './components/tab-friends.js';
import './components/tab-settings.js';
import './components/tab-safety.js';
import './components/tab-forum.js';
import './components/tab-admin.js';
import './components/core.js';

// ─── Phase 7: Notifications ───────────────────────────────────────────────
import './notification-service.js';
import './components/NotificationBell.js';
import './components/NotificationPanel.js';

// ─── Phase 8: Settings & tools ────────────────────────────────────────────
import './llmSettings.js';
import './testMode.js';
import './toolSettings.js';
import './filter.js';

// ─── Phase 9: Chat system ─────────────────────────────────────────────────
import './chat-state.js';
import './chat-sessions.js';
import './chat-stream-ui.js';
import './chat-hitl.js';
import './chat-analysis.js';
import './chat-history.js';
import './chat-init.js';

// ─── Phase 10: Social features ────────────────────────────────────────────
import './friends.js';
import './messages.js';

// ─── Phase 11: Navigation ─────────────────────────────────────────────────
import './nav-config.js';
import './global-nav.js';

// ─── Phase 12: Market data ────────────────────────────────────────────────
import './market-status.js';
import './twstock.js';
import './usstock.js';
import './market-screener.js';
import './market-chart.js';
import './market-ws.js';
import './pulse.js';
import './commodity.js';
import './forex.js';

// ─── Phase 13: Forum ──────────────────────────────────────────────────────
import './forum-config.js';
import './forum-api.js';
import './forum-app.js';

// ─── Phase 14: Wallet & alerts ────────────────────────────────────────────
import './wallet.js';
import './alerts.js';

// ─── Phase 15: Safety & admin ─────────────────────────────────────────────
import './safetyTab.js';
import './admin.js';
import './admin-stats.js';

// ─── Phase 16: SPA & modals ───────────────────────────────────────────────
import './spa.js';
import './modals.js';
import './legal.js';

// ─── Phase 17: Internationalization (last — translates everything) ────────
import './i18n.js';
import './components/LanguageSwitcher.js';
