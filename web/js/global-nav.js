/**
 * Global Navigation Module
 * Provides shared bottom navigation across all pages (main app and forum)
 *
 * This module dynamically injects the draggable bottom navigation
 * and controls its visibility based on page type.
 */

const GlobalNav = {
    // DOM IDs
    CONTAINER_ID: 'global-nav-container',
    NAV_ID: 'draggable-nav',

    // Pages that should NOT show the bottom navigation
    HIDDEN_PAGES: ['post', 'create', 'profile', 'messages', 'wallet', 'premium'],

    /**
     * Initialize the global navigation
     * Determines whether to show nav based on current page type
     */
    init() {
        const pageType = document.body.dataset.page;
        const shouldShow = pageType && !this.HIDDEN_PAGES.includes(pageType);

        if (shouldShow) {
            this.injectNav();
        }
    },

    /**
     * Inject the navigation HTML into the page
     */
    injectNav() {
        // Skip if already injected
        if (document.getElementById(this.CONTAINER_ID)) return;

        const navHTML = this.getNavTemplate();
        document.body.insertAdjacentHTML('beforeend', navHTML);

        // Initialize language switcher and draggable first
        this.initLanguageSwitcher();
        this.initDraggable();
        this.restoreNavState();

        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }

        // Wait for I18n to be ready before rendering buttons
        // Check if I18n is fully initialized (not just function exists), otherwise wait for it
        if (window.I18n && window.I18n.isReady && window.I18n.isReady()) {
            // I18n is fully initialized, render immediately
            this.renderNavButtons();
        } else {
            // Wait for I18n to be initialized with timeout
            let attempts = 0;
            const maxAttempts = 50; // 5 seconds max (50 * 100ms)
            const checkI18n = setInterval(() => {
                attempts++;
                if (window.I18n && window.I18n.isReady && window.I18n.isReady()) {
                    clearInterval(checkI18n);
                    this.renderNavButtons();
                } else if (attempts >= maxAttempts) {
                    // Timeout: render with fallback labels
                    console.warn('[GlobalNav] I18n init timeout, using fallback labels');
                    clearInterval(checkI18n);
                    this.renderNavButtons();
                }
            }, 100);
        }
    },

    /**
     * Get the navigation HTML template
     * @returns {string} HTML string for navigation
     */
    getNavTemplate() {
        return `
            <div id="${this.CONTAINER_ID}" class="fixed bottom-24 left-1/2 z-50" style="transform: translateX(-50%);">
                <nav id="${this.NAV_ID}"
                    class="bg-surface/95 backdrop-blur-xl border border-white/10 rounded-full p-1.5 flex items-center gap-1 shadow-2xl shadow-black/40 select-none transition-all duration-300">
                    <!-- Collapse/Expand Toggle -->
                    <button id="nav-toggle" onclick="GlobalNav.toggleCollapse()"
                        class="w-10 h-10 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-textMuted hover:text-primary transition-all duration-200"
                        title="收縮/展開">
                        <i data-lucide="chevrons-left" class="w-4 h-4 transition-transform duration-300"
                            id="nav-toggle-icon"></i>
                    </button>

                    <!-- Navigation Buttons (Scrollable) -->
                    <div id="nav-buttons"
                        class="flex items-center gap-1 overflow-x-auto max-w-[160px] md:max-w-none transition-all duration-300 px-1 pb-1"
                        style="scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.2) transparent;">
                        <style>
                            #nav-buttons::-webkit-scrollbar {
                                height: 3px;
                            }
                            #nav-buttons::-webkit-scrollbar-track {
                                background: transparent;
                            }
                            #nav-buttons::-webkit-scrollbar-thumb {
                                background-color: rgba(255, 255, 255, 0.2);
                                border-radius: 9999px;
                            }
                        </style>
                        <!-- Navigation buttons will be dynamically rendered here -->
                    </div>

                    <!-- Language Switcher Container -->
                    <div class="lang-switcher-container"></div>

                    <!-- Drag Handle -->
                    <div
                        class="drag-handle w-8 h-10 flex items-center justify-center rounded-full hover:bg-white/10 text-textMuted/50 hover:text-textMuted cursor-grab active:cursor-grabbing transition-all duration-200 ml-0.5">
                        <i data-lucide="grip-vertical" class="w-4 h-4"></i>
                    </div>
                </nav>
            </div>
        `;
    },

    /**
     * Render navigation buttons based on user preferences
     */
    renderNavButtons() {
        if (!window.NavPreferences) {
            console.warn('NavPreferences not loaded yet, deferring button rendering');
            // Retry after a short delay
            setTimeout(() => this.renderNavButtons(), 100);
            return;
        }

        const container = document.getElementById('nav-buttons');
        if (!container) return;

        const enabledItems = NavPreferences.getEnabledItems();
        const pageType = document.body.dataset.page;

        // Clear existing buttons
        container.innerHTML = '';

        enabledItems.forEach(item => {
            const button = document.createElement('button');
            const isActive = pageType === item.id || (pageType === 'index' && item.id === 'forum');

            // Use i18n key if available, otherwise fall back to label
            let labelText = item.label; // Default fallback
            if (item.i18nKey && window.I18n && window.I18n.isReady && window.I18n.isReady()) {
                try {
                    const translated = window.I18n.t(item.i18nKey);
                    // Only use translation if it's different from the key (translation succeeded)
                    if (translated !== item.i18nKey) {
                        labelText = translated;
                    }
                } catch (e) {
                    console.warn('Translation error for key:', item.i18nKey, e);
                    // labelText already set to item.label above
                }
            }

            button.className = `nav-btn shrink-0 w-12 h-12 flex flex-col items-center justify-center rounded-full hover:bg-white/10 transition-all duration-200 gap-0.5 nav-item-enter ${isActive ? 'text-primary bg-white/5' : 'text-textMuted hover:text-primary'}`;
            button.title = labelText;
            button.dataset.tab = item.id;

            // Set click handler
            if (item.id === 'forum') {
                button.onclick = function () { GlobalNav.navigateToForum(); };
            } else {
                button.onclick = function () { GlobalNav.navigateToTab(item.id); };
            }

            button.innerHTML = `
                <i data-lucide="${item.icon}" class="w-5 h-5 ${isActive ? 'text-primary' : 'text-textMuted'}"></i>
                <span class="text-[9px] font-medium opacity-80">${labelText}</span>
            `;

            container.appendChild(button);
        });

        // Re-initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }
    },

    /**
     * Navigate to a main app tab
     * @param {string} tabId - The tab ID to navigate to
     */
    navigateToTab(tabId) {
        // Save current page info for potential return
        const currentPage = document.body.dataset.page;
        if (currentPage) {
            sessionStorage.setItem('lastForumPage', currentPage);
        }

        // Navigate to main app with tab
        window.location.href = `/static/index.html#${tabId}`;
    },

    /**
     * Navigate to forum
     */
    navigateToForum() {
        // Save current tab for return navigation
        const hash = window.location.hash;
        if (hash) {
            localStorage.setItem('lastActiveTab', hash.substring(1));
        }

        window.location.href = '/static/forum/index.html';
    },

    /**
     * Toggle navigation collapse/expand state
     */
    toggleCollapse() {
        const navButtons = document.getElementById('nav-buttons');
        const toggleIcon = document.getElementById('nav-toggle-icon');
        const nav = document.getElementById(this.NAV_ID);

        if (!navButtons || !toggleIcon || !nav) return;

        const currentState = localStorage.getItem('navCollapsed') === 'true';
        const newState = !currentState;

        if (newState) {
            // Collapse
            navButtons.style.width = '0';
            navButtons.style.opacity = '0';
            navButtons.style.pointerEvents = 'none';
            toggleIcon.style.transform = 'rotate(180deg)';
            nav.style.borderRadius = '9999px';
        } else {
            // Expand
            navButtons.style.width = '';
            navButtons.style.opacity = '1';
            navButtons.style.pointerEvents = 'auto';
            toggleIcon.style.transform = 'rotate(0deg)';
            nav.style.borderRadius = '9999px';
        }

        // Save state
        localStorage.setItem('navCollapsed', newState);
    },

    /**
     * Restore saved navigation state (position and collapse)
     */
    restoreNavState() {
        // Restore collapse state
        const savedCollapsed = localStorage.getItem('navCollapsed');
        if (savedCollapsed === 'true') {
            // Need to wait a tick for DOM to be ready
            setTimeout(() => this.toggleCollapse(), 0);
        }

        // Position is restored by initDraggable()
    },

    /**
     * Initialize the draggable functionality
     * This replicates the drag logic from app.js
     */
    initDraggable() {
        const container = document.getElementById(this.CONTAINER_ID);
        const nav = document.getElementById(this.NAV_ID);
        if (!container || !nav) return;

        // State Variables
        let isDragging = false;
        let currentX = 0, currentY = 0;
        let initialX, initialY;
        let xOffset = 0, yOffset = 0;
        let animationFrameId = null;

        // Load saved position
        const savedPos = localStorage.getItem('navPosition');
        if (savedPos) {
            const { x, y } = JSON.parse(savedPos);
            xOffset = x;
            yOffset = y;
            this.setTranslate(xOffset, yOffset, container);
        }

        const dragHandle = nav.querySelector('.drag-handle');
        if (!dragHandle) return;

        // Mobile Optimization: Prevent default touch actions
        dragHandle.style.touchAction = 'none';

        // Event Listeners
        dragHandle.addEventListener('mousedown', dragStart);
        dragHandle.addEventListener('touchstart', dragStart, { passive: false });

        document.addEventListener('mouseup', dragEnd);
        document.addEventListener('touchend', dragEnd);

        document.addEventListener('mousemove', drag);
        document.addEventListener('touchmove', drag, { passive: false });

        const self = this;

        function dragStart(e) {
            if (e.target.closest('button:not(.drag-handle)')) return;

            if (e.type === 'touchstart') {
                initialX = e.touches[0].clientX - xOffset;
                initialY = e.touches[0].clientY - yOffset;
            } else {
                initialX = e.clientX - xOffset;
                initialY = e.clientY - yOffset;
            }

            isDragging = true;

            container.style.willChange = 'transform';
            container.style.transition = 'none';
            nav.style.transition = 'none';

            dragHandle.style.cursor = 'grabbing';
        }

        function dragEnd(e) {
            if (!isDragging) return;

            initialX = currentX;
            initialY = currentY;

            isDragging = false;
            cancelAnimationFrame(animationFrameId);

            // Snap to bounds
            const viewW = window.innerWidth;
            const viewH = window.innerHeight;
            const navRect = nav.getBoundingClientRect();
            const navWidth = navRect.width;
            const navHeight = navRect.height;
            const padding = 10;

            const minX = -(viewW / 2) + (navWidth / 2) + padding;
            const maxX = (viewW / 2) - (navWidth / 2) - padding;

            // Reset transition for smooth snap
            container.style.transition = 'transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)';

            let targetX = currentX;
            let targetY = currentY;

            // Clamp X
            if (targetX < minX) targetX = minX;
            if (targetX > maxX) targetX = maxX;

            // Clamp Y
            const maxUp = -(viewH - 150);
            const maxDown = 80;

            if (targetY < maxUp) targetY = maxUp;
            if (targetY > maxDown) targetY = maxDown;

            xOffset = targetX;
            yOffset = targetY;

            self.setTranslate(targetX, targetY, container);

            // Cleanup
            setTimeout(() => {
                container.style.willChange = 'auto';
                container.style.transition = '';
                nav.style.transition = 'all 0.3s ease';
            }, 300);

            dragHandle.style.cursor = 'grab';

            // Save position
            localStorage.setItem('navPosition', JSON.stringify({ x: targetX, y: targetY }));
        }

        function drag(e) {
            if (!isDragging) return;

            e.preventDefault();

            let clientX, clientY;
            if (e.type === 'touchmove') {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else {
                clientX = e.clientX;
                clientY = e.clientY;
            }

            currentX = clientX - initialX;
            currentY = clientY - initialY;

            if (!animationFrameId) {
                animationFrameId = requestAnimationFrame(() => {
                    self.setTranslate(currentX, currentY, container);
                    animationFrameId = null;
                });
            }
        }
    },

    /**
     * Set translate transform on element
     * @param {number} xPos - X translation
     * @param {number} yPos - Y translation
     * @param {HTMLElement} el - Element to transform
     */
    setTranslate(xPos, yPos, el) {
        el.style.transform = `translateX(-50%) translate3d(${xPos}px, ${yPos}px, 0)`;
    },

    /**
     * Initialize language switcher component
     */
    initLanguageSwitcher() {
        const container = document.querySelector('.lang-switcher-container');
        if (!container) return;

        // Check if LanguageSwitcher module is available
        if (window.LanguageSwitcher && typeof window.LanguageSwitcher.init === 'function') {
            window.LanguageSwitcher.init(container);
        } else if (window.Components && window.Components.languageSwitcher) {
            // Fallback to component-based initialization
            container.innerHTML = window.Components.languageSwitcher;
            if (window.LanguageSwitcher && typeof window.LanguageSwitcher.init === 'function') {
                window.LanguageSwitcher.init(container);
            }
        }
    },

    /**
     * Re-render buttons (called when preferences change)
     */
    refreshButtons() {
        this.renderNavButtons();
    }
};

// Listen for language changes and re-render buttons
window.addEventListener('languageChanged', () => {
    if (document.getElementById('nav-buttons')) {
        GlobalNav.renderNavButtons();
    }
});

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => GlobalNav.init());
} else {
    GlobalNav.init();
}

// Export for use in other modules
window.GlobalNav = GlobalNav;
