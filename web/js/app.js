// ========================================
// app.js - 核心應用邏輯與全局變量
// ========================================

// Initialize Lucide icons
lucide.createIcons();
const md = window.markdownit({ html: true, linkify: true });
let isAnalyzing = false;
let marketRefreshInterval = null;

// --- Global Filter Logic Variables ---
let allMarketSymbols = [];
let globalSelectedSymbols = []; // Unified selection
let selectedNewsSources = ['google', 'cryptocompare', 'cryptopanic', 'newsapi']; // Default all sources
let currentFilterExchange = 'okx';
let isFirstLoad = true;

// Watchlist & Chart Variables
let currentUserId = 'guest';
let chart = null;
let candleSeries = null;

// Pulse Data Cache
let currentPulseData = {};

// Trade Proposal
let currentProposal = null;

// Analysis Abort Controller
window.currentAnalysisController = null;

// Pi Network Initialization
const Pi = window.Pi;

// ========================================
// Tab Switching
// ========================================
function switchTab(tab) {
    ['chat', 'market', 'watchlist', 'settings', 'pulse', 'assets'].forEach(t => {
        const el = document.getElementById(t + '-tab');
        if (el) el.classList.add('hidden');
    });
    document.getElementById(tab + '-tab').classList.remove('hidden');

    // Update nav icon colors
    document.querySelectorAll('nav button').forEach(btn => btn.classList.replace('text-blue-500', 'text-slate-400'));

    // Abort pending analysis if leaving chat tab
    if (tab !== 'chat' && window.currentAnalysisController) {
        window.currentAnalysisController.abort();
        window.currentAnalysisController = null;
        isAnalyzing = false; // Reset analyzing state
        
        // Reset Chat UI if needed (optional, but good for UX)
        const input = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        if (input && sendBtn) {
            input.disabled = false;
            sendBtn.disabled = false;
            input.classList.remove('opacity-50');
            sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    if (marketRefreshInterval) {
        clearInterval(marketRefreshInterval);
        marketRefreshInterval = null;
    }
    if (window.pulseInterval) {
        clearInterval(window.pulseInterval);
        window.pulseInterval = null;
    }

    if (tab === 'market') {
        refreshScreener(true);
        marketRefreshInterval = setInterval(() => {
            refreshScreener(false);
        }, 1000);
    }

    if (tab === 'pulse') {
        checkMarketPulse(true);
        window.pulseInterval = setInterval(() => {
            checkMarketPulse(false);
        }, 30000);
    }

    if (window.assetsInterval) {
        clearInterval(window.assetsInterval);
        window.assetsInterval = null;
    }

    if (tab === 'watchlist') refreshWatchlist();

    if (tab === 'assets') {
        refreshAssets();
        window.assetsInterval = setInterval(refreshAssets, 10000);
    }

    lucide.createIcons();
}

// ========================================
// Utility Functions
// ========================================
function updateUserId(uid) { currentUserId = uid || 'guest'; }

function quickAsk(text) {
    document.getElementById('user-input').value = text;
    sendMessage();
}

// ========================================
// Pi Network Authentication
// ========================================
if (Pi) {
    Pi.init({ version: "2.0", sandbox: true });
    Pi.authenticate(['username'], (payment) => {}).then(auth => {
        const userEl = document.getElementById('pi-user');
        userEl.innerHTML = `<span class="text-blue-400 font-medium">@${auth.user.username}</span>`;
        userEl.classList.remove('hidden');
        const settingsUserEl = document.getElementById('settings-user');
        if (settingsUserEl) settingsUserEl.innerText = "@" + auth.user.username;
        updateUserId(auth.user.uid || auth.user.username);
    }).catch(err => console.error(err));
}
