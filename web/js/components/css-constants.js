// ========================================
// css-constants.js - CSS class constants for component templates
// Auto-generated from components.js split (lines 5-99)
// ========================================

// Define all CSS class constants (original order preserved for inter-references)
const SHELL_SCROLL_ATTR = 'data-shell-scroll data-shell-scroll-extra="1rem"';
const SHELL_SCROLLBAR_CLASS = 'overflow-y-auto custom-scrollbar';
const SHELL_MODAL_SCROLL_ATTR = 'data-shell-scroll data-shell-scroll-extra="2rem"';
const TAB_SHELL_CLASS = 'h-full flex flex-col px-4 md:px-6 pt-6 md:pt-8';
const TAB_HEADER_CLASS = 'flex items-center justify-between mb-4 pr-12 md:pr-16';
const TAB_SWITCHER_CLASS =
    'flex gap-1 p-1 bg-background/50 border border-white/5 rounded-xl mb-6';
const TAB_CONTENT_AREA_CLASS = 'flex-1 overflow-visible relative';
const MODAL_OVERLAY_CLASS =
    'fixed inset-0 bg-background/90 backdrop-blur-sm z-[70] hidden flex items-center justify-center p-4';
const MODAL_PANEL_CLASS =
    'bg-surface w-full max-w-lg max-h-[85vh] flex flex-col rounded-[2rem] border border-white/5 shadow-2xl';
const MODAL_HEADER_CLASS = 'p-6 border-b border-white/5 flex justify-between items-center shrink-0';
const FEATURE_MODAL_STAGE_CLASS =
    'absolute inset-0 flex items-center justify-center p-4 pointer-events-none';
const FEATURE_MODAL_PANEL_CLASS =
    'feature-menu-content bg-surface rounded-3xl border border-white/5 shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col pointer-events-auto transform transition-all duration-300 scale-95 opacity-0';
const SUB_TAB_BUTTON_BASE_CLASS =
    'flex-1 py-2 px-4 rounded-lg font-bold text-sm transition flex items-center justify-center gap-2';
const SUB_TAB_BUTTON_ACTIVE_CLASS = 'bg-primary text-background shadow-md';
const SUB_TAB_BUTTON_INACTIVE_CLASS = 'text-textMuted hover:text-textMain hover:bg-white/5';
const MODAL_CLOSE_BUTTON_CLASS =
    'w-8 h-8 rounded-full bg-background flex items-center justify-center text-textMuted hover:text-secondary transition';
const GOV_TAB_BUTTON_BASE_CLASS =
    'gov-tab-btn px-3 py-2 text-xs font-bold rounded-t-lg border-b-2 transition';
const GOV_TAB_BUTTON_ACTIVE_CLASS = 'border-primary text-primary';
const GOV_TAB_BUTTON_INACTIVE_CLASS = 'border-transparent text-textMuted hover:text-secondary';
const ICON_ACTION_BUTTON_CLASS = 'p-2 hover:bg-white/5 rounded-full text-textMuted transition';
const FILTER_TRIGGER_BUTTON_CLASS =
    'flex items-center gap-2 px-3 py-1.5 bg-surface hover:bg-surfaceHighlight rounded-lg text-textMuted hover:text-primary transition border border-white/5';
const SECTION_HEADER_ROW_CLASS = 'flex items-center gap-3 mb-4 px-1';
const SECTION_TOGGLE_ROW_CLASS = 'flex items-center gap-2 mb-4 px-1';
const SECTION_TITLE_CLASS =
    'text-[10px] font-black uppercase tracking-[0.25em] whitespace-nowrap flex items-center gap-1.5';
const PRIMARY_DIVIDER_LEFT_CLASS = 'h-px flex-1 bg-gradient-to-r from-primary/40 to-transparent';
const PRIMARY_DIVIDER_RIGHT_CLASS = 'h-px flex-1 bg-gradient-to-l from-primary/40 to-transparent';
const WARNING_DIVIDER_LEFT_CLASS = 'h-px flex-1 bg-gradient-to-r from-yellow-500/40 to-transparent';
const WARNING_DIVIDER_RIGHT_CLASS = 'h-px flex-1 bg-gradient-to-l from-yellow-500/40 to-transparent';
const SUCCESS_DIVIDER_LEFT_CLASS = 'h-px flex-1 bg-gradient-to-r from-success/40 to-transparent';
const SUCCESS_DIVIDER_RIGHT_CLASS = 'h-px flex-1 bg-gradient-to-l from-success/40 to-transparent';
const ACCENT_DIVIDER_LEFT_CLASS = 'h-px flex-1 bg-gradient-to-r from-accent/40 to-transparent';
const ACCENT_DIVIDER_RIGHT_CLASS = 'h-px flex-1 bg-gradient-to-l from-accent/40 to-transparent';
const SECTION_TOGGLE_BUTTON_CLASS = 'flex items-center gap-1.5 group';
const SECTION_CHEVRON_BASE_CLASS = 'w-3.5 h-3.5 transition-transform duration-200';
const PRIMARY_CHEVRON_CLASS =
    `${SECTION_CHEVRON_BASE_CLASS} text-primary/60 group-hover:text-primary`;
const WARNING_CHEVRON_CLASS =
    `${SECTION_CHEVRON_BASE_CLASS} text-yellow-400/60 group-hover:text-yellow-400`;
const SUCCESS_CHEVRON_CLASS =
    `${SECTION_CHEVRON_BASE_CLASS} text-success/60 group-hover:text-success`;
const ACCENT_CHEVRON_CLASS =
    `${SECTION_CHEVRON_BASE_CLASS} text-accent/60 group-hover:text-accent`;
const LOADER_BLOCK_CLASS = 'hidden py-6 flex items-center justify-center';
const LARGE_LOADER_BLOCK_CLASS = 'hidden items-center justify-center py-10 flex';
const LOADING_PLACEHOLDER_CLASS = 'text-center text-textMuted py-8';
const LOADING_PLACEHOLDER_SMALL_CLASS = 'text-center text-textMuted py-8 text-sm';
const PRIMARY_SPINNER_CLASS = 'animate-spin rounded-full h-5 w-5 border-b-2 border-primary';
const WARNING_SPINNER_CLASS = 'animate-spin rounded-full h-5 w-5 border-b-2 border-yellow-400';
const SUCCESS_SPINNER_CLASS = 'animate-spin rounded-full h-5 w-5 border-b-2 border-success';
const ACCENT_SPINNER_CLASS = 'animate-spin rounded-full h-5 w-5 border-b-2 border-accent';
const PRIMARY_LARGE_SPINNER_CLASS = 'animate-spin rounded-full h-8 w-8 border-b-2 border-primary';
const PRIMARY_RING_SPINNER_CLASS =
    'animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full';
const WARNING_RING_SPINNER_CLASS =
    'animate-spin w-5 h-5 border-2 border-yellow-400 border-t-transparent rounded-full';
const LOADER_ICON_CLASS = 'w-6 h-6 animate-spin mx-auto mb-2';
const MODAL_FOOTER_CLASS = 'p-6 border-t border-white/5 shrink-0';
const MODAL_ACTION_ROW_CLASS = 'flex gap-3';
const SUCCESS_ACTION_BUTTON_CLASS =
    'flex-1 py-3 bg-success/10 hover:bg-success/20 text-success font-bold rounded-xl transition flex items-center justify-center gap-2';
const DANGER_ACTION_BUTTON_CLASS =
    'flex-1 py-3 bg-danger/10 hover:bg-danger/20 text-danger font-bold rounded-xl transition flex items-center justify-center gap-2';
const GOV_FILTER_ROW_CLASS = 'flex gap-2 mb-4 overflow-x-auto pb-1';
const GOV_FILTER_BUTTON_BASE_CLASS =
    'gov-filter-btn px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5';
const GOV_FILTER_BUTTON_ACTIVE_CLASS = 'text-primary border border-primary/20';
const GOV_FILTER_BUTTON_INACTIVE_CLASS = 'text-textMuted border border-white/5';
const LOADING_PLACEHOLDER_TIGHT_CLASS = 'text-center text-textMuted py-4 text-sm';
const SEARCH_SHELL_GLOW_CLASS =
    'absolute inset-0 bg-gradient-to-r from-primary/10 via-accent/5 to-transparent rounded-3xl blur-2xl opacity-50';
const SEARCH_SHELL_PANEL_CLASS =
    'relative flex items-center gap-3 bg-surface/60 backdrop-blur-xl border border-white/10 p-2 rounded-2xl shadow-xl';
const SEARCH_ICON_WRAP_CLASS = 'pl-4 flex-shrink-0';
const SEARCH_INPUT_CLASS =
    'flex-1 bg-transparent border-none outline-none text-textMain placeholder-textMuted/50 text-base font-mono tracking-wider focus:ring-0 w-full min-w-0';
const SEARCH_ACTION_BUTTON_CLASS =
    'bg-primary/20 hover:bg-primary text-primary hover:text-background border border-primary/30 hover:border-primary transition-all duration-300 px-6 py-3 rounded-xl font-bold tracking-[0.1em] text-sm flex items-center gap-2 flex-shrink-0';
const HERO_TITLE_CLASS = 'font-serif text-2xl md:text-3xl text-secondary flex items-center gap-3';
const HERO_ICON_BOX_CLASS = 'w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center';
const CARD_HEADER_ROW_CLASS = 'flex items-center gap-3';
const STATUS_BADGE_CLASS = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium';
const STATUS_BADGE_MUTED_CLASS = `${STATUS_BADGE_CLASS} bg-white/5 text-textMuted`;
const INFO_PANEL_CLASS = 'bg-background/50 rounded-xl p-4 border border-white/5';
const WARNING_BANNER_CLASS = 'hidden mx-6 mt-4 p-3 bg-warning/10 border border-warning/20 rounded-xl';
const WARNING_BANNER_ROW_CLASS = 'flex items-start gap-2';

// Export each constant to global scope (for template literal ${VAR} references in tab files)
window.SHELL_SCROLL_ATTR = SHELL_SCROLL_ATTR;
window.SHELL_SCROLLBAR_CLASS = SHELL_SCROLLBAR_CLASS;
window.SHELL_MODAL_SCROLL_ATTR = SHELL_MODAL_SCROLL_ATTR;
window.TAB_SHELL_CLASS = TAB_SHELL_CLASS;
window.TAB_HEADER_CLASS = TAB_HEADER_CLASS;
window.TAB_SWITCHER_CLASS = TAB_SWITCHER_CLASS;
window.TAB_CONTENT_AREA_CLASS = TAB_CONTENT_AREA_CLASS;
window.MODAL_OVERLAY_CLASS = MODAL_OVERLAY_CLASS;
window.MODAL_PANEL_CLASS = MODAL_PANEL_CLASS;
window.MODAL_HEADER_CLASS = MODAL_HEADER_CLASS;
window.FEATURE_MODAL_STAGE_CLASS = FEATURE_MODAL_STAGE_CLASS;
window.FEATURE_MODAL_PANEL_CLASS = FEATURE_MODAL_PANEL_CLASS;
window.SUB_TAB_BUTTON_BASE_CLASS = SUB_TAB_BUTTON_BASE_CLASS;
window.SUB_TAB_BUTTON_ACTIVE_CLASS = SUB_TAB_BUTTON_ACTIVE_CLASS;
window.SUB_TAB_BUTTON_INACTIVE_CLASS = SUB_TAB_BUTTON_INACTIVE_CLASS;
window.MODAL_CLOSE_BUTTON_CLASS = MODAL_CLOSE_BUTTON_CLASS;
window.GOV_TAB_BUTTON_BASE_CLASS = GOV_TAB_BUTTON_BASE_CLASS;
window.GOV_TAB_BUTTON_ACTIVE_CLASS = GOV_TAB_BUTTON_ACTIVE_CLASS;
window.GOV_TAB_BUTTON_INACTIVE_CLASS = GOV_TAB_BUTTON_INACTIVE_CLASS;
window.ICON_ACTION_BUTTON_CLASS = ICON_ACTION_BUTTON_CLASS;
window.FILTER_TRIGGER_BUTTON_CLASS = FILTER_TRIGGER_BUTTON_CLASS;
window.SECTION_HEADER_ROW_CLASS = SECTION_HEADER_ROW_CLASS;
window.SECTION_TOGGLE_ROW_CLASS = SECTION_TOGGLE_ROW_CLASS;
window.SECTION_TITLE_CLASS = SECTION_TITLE_CLASS;
window.PRIMARY_DIVIDER_LEFT_CLASS = PRIMARY_DIVIDER_LEFT_CLASS;
window.PRIMARY_DIVIDER_RIGHT_CLASS = PRIMARY_DIVIDER_RIGHT_CLASS;
window.WARNING_DIVIDER_LEFT_CLASS = WARNING_DIVIDER_LEFT_CLASS;
window.WARNING_DIVIDER_RIGHT_CLASS = WARNING_DIVIDER_RIGHT_CLASS;
window.SUCCESS_DIVIDER_LEFT_CLASS = SUCCESS_DIVIDER_LEFT_CLASS;
window.SUCCESS_DIVIDER_RIGHT_CLASS = SUCCESS_DIVIDER_RIGHT_CLASS;
window.ACCENT_DIVIDER_LEFT_CLASS = ACCENT_DIVIDER_LEFT_CLASS;
window.ACCENT_DIVIDER_RIGHT_CLASS = ACCENT_DIVIDER_RIGHT_CLASS;
window.SECTION_TOGGLE_BUTTON_CLASS = SECTION_TOGGLE_BUTTON_CLASS;
window.SECTION_CHEVRON_BASE_CLASS = SECTION_CHEVRON_BASE_CLASS;
window.PRIMARY_CHEVRON_CLASS = PRIMARY_CHEVRON_CLASS;
window.WARNING_CHEVRON_CLASS = WARNING_CHEVRON_CLASS;
window.SUCCESS_CHEVRON_CLASS = SUCCESS_CHEVRON_CLASS;
window.ACCENT_CHEVRON_CLASS = ACCENT_CHEVRON_CLASS;
window.LOADER_BLOCK_CLASS = LOADER_BLOCK_CLASS;
window.LARGE_LOADER_BLOCK_CLASS = LARGE_LOADER_BLOCK_CLASS;
window.LOADING_PLACEHOLDER_CLASS = LOADING_PLACEHOLDER_CLASS;
window.LOADING_PLACEHOLDER_SMALL_CLASS = LOADING_PLACEHOLDER_SMALL_CLASS;
window.PRIMARY_SPINNER_CLASS = PRIMARY_SPINNER_CLASS;
window.WARNING_SPINNER_CLASS = WARNING_SPINNER_CLASS;
window.SUCCESS_SPINNER_CLASS = SUCCESS_SPINNER_CLASS;
window.ACCENT_SPINNER_CLASS = ACCENT_SPINNER_CLASS;
window.PRIMARY_LARGE_SPINNER_CLASS = PRIMARY_LARGE_SPINNER_CLASS;
window.PRIMARY_RING_SPINNER_CLASS = PRIMARY_RING_SPINNER_CLASS;
window.WARNING_RING_SPINNER_CLASS = WARNING_RING_SPINNER_CLASS;
window.LOADER_ICON_CLASS = LOADER_ICON_CLASS;
window.MODAL_FOOTER_CLASS = MODAL_FOOTER_CLASS;
window.MODAL_ACTION_ROW_CLASS = MODAL_ACTION_ROW_CLASS;
window.SUCCESS_ACTION_BUTTON_CLASS = SUCCESS_ACTION_BUTTON_CLASS;
window.DANGER_ACTION_BUTTON_CLASS = DANGER_ACTION_BUTTON_CLASS;
window.GOV_FILTER_ROW_CLASS = GOV_FILTER_ROW_CLASS;
window.GOV_FILTER_BUTTON_BASE_CLASS = GOV_FILTER_BUTTON_BASE_CLASS;
window.GOV_FILTER_BUTTON_ACTIVE_CLASS = GOV_FILTER_BUTTON_ACTIVE_CLASS;
window.GOV_FILTER_BUTTON_INACTIVE_CLASS = GOV_FILTER_BUTTON_INACTIVE_CLASS;
window.LOADING_PLACEHOLDER_TIGHT_CLASS = LOADING_PLACEHOLDER_TIGHT_CLASS;
window.SEARCH_SHELL_GLOW_CLASS = SEARCH_SHELL_GLOW_CLASS;
window.SEARCH_SHELL_PANEL_CLASS = SEARCH_SHELL_PANEL_CLASS;
window.SEARCH_ICON_WRAP_CLASS = SEARCH_ICON_WRAP_CLASS;
window.SEARCH_INPUT_CLASS = SEARCH_INPUT_CLASS;
window.SEARCH_ACTION_BUTTON_CLASS = SEARCH_ACTION_BUTTON_CLASS;
window.HERO_TITLE_CLASS = HERO_TITLE_CLASS;
window.HERO_ICON_BOX_CLASS = HERO_ICON_BOX_CLASS;
window.CARD_HEADER_ROW_CLASS = CARD_HEADER_ROW_CLASS;
window.STATUS_BADGE_CLASS = STATUS_BADGE_CLASS;
window.STATUS_BADGE_MUTED_CLASS = STATUS_BADGE_MUTED_CLASS;
window.INFO_PANEL_CLASS = INFO_PANEL_CLASS;
window.WARNING_BANNER_CLASS = WARNING_BANNER_CLASS;
window.WARNING_BANNER_ROW_CLASS = WARNING_BANNER_ROW_CLASS;

// Export as organized namespace for backward compatibility
const ComponentCSS = {
    SHELL_SCROLL_ATTR,
    SHELL_SCROLLBAR_CLASS,
    SHELL_MODAL_SCROLL_ATTR,
    TAB_SHELL_CLASS,
    TAB_HEADER_CLASS,
    TAB_SWITCHER_CLASS,
    TAB_CONTENT_AREA_CLASS,
    MODAL_OVERLAY_CLASS,
    MODAL_PANEL_CLASS,
    MODAL_HEADER_CLASS,
    FEATURE_MODAL_STAGE_CLASS,
    FEATURE_MODAL_PANEL_CLASS,
    SUB_TAB_BUTTON_BASE_CLASS,
    SUB_TAB_BUTTON_ACTIVE_CLASS,
    SUB_TAB_BUTTON_INACTIVE_CLASS,
    MODAL_CLOSE_BUTTON_CLASS,
    GOV_TAB_BUTTON_BASE_CLASS,
    GOV_TAB_BUTTON_ACTIVE_CLASS,
    GOV_TAB_BUTTON_INACTIVE_CLASS,
    ICON_ACTION_BUTTON_CLASS,
    FILTER_TRIGGER_BUTTON_CLASS,
    SECTION_HEADER_ROW_CLASS,
    SECTION_TOGGLE_ROW_CLASS,
    SECTION_TITLE_CLASS,
    PRIMARY_DIVIDER_LEFT_CLASS,
    PRIMARY_DIVIDER_RIGHT_CLASS,
    WARNING_DIVIDER_LEFT_CLASS,
    WARNING_DIVIDER_RIGHT_CLASS,
    SUCCESS_DIVIDER_LEFT_CLASS,
    SUCCESS_DIVIDER_RIGHT_CLASS,
    ACCENT_DIVIDER_LEFT_CLASS,
    ACCENT_DIVIDER_RIGHT_CLASS,
    SECTION_TOGGLE_BUTTON_CLASS,
    SECTION_CHEVRON_BASE_CLASS,
    PRIMARY_CHEVRON_CLASS,
    WARNING_CHEVRON_CLASS,
    SUCCESS_CHEVRON_CLASS,
    ACCENT_CHEVRON_CLASS,
    LOADER_BLOCK_CLASS,
    LARGE_LOADER_BLOCK_CLASS,
    LOADING_PLACEHOLDER_CLASS,
    LOADING_PLACEHOLDER_SMALL_CLASS,
    PRIMARY_SPINNER_CLASS,
    WARNING_SPINNER_CLASS,
    SUCCESS_SPINNER_CLASS,
    ACCENT_SPINNER_CLASS,
    PRIMARY_LARGE_SPINNER_CLASS,
    PRIMARY_RING_SPINNER_CLASS,
    WARNING_RING_SPINNER_CLASS,
    LOADER_ICON_CLASS,
    MODAL_FOOTER_CLASS,
    MODAL_ACTION_ROW_CLASS,
    SUCCESS_ACTION_BUTTON_CLASS,
    DANGER_ACTION_BUTTON_CLASS,
    GOV_FILTER_ROW_CLASS,
    GOV_FILTER_BUTTON_BASE_CLASS,
    GOV_FILTER_BUTTON_ACTIVE_CLASS,
    GOV_FILTER_BUTTON_INACTIVE_CLASS,
    LOADING_PLACEHOLDER_TIGHT_CLASS,
    SEARCH_SHELL_GLOW_CLASS,
    SEARCH_SHELL_PANEL_CLASS,
    SEARCH_ICON_WRAP_CLASS,
    SEARCH_INPUT_CLASS,
    SEARCH_ACTION_BUTTON_CLASS,
    HERO_TITLE_CLASS,
    HERO_ICON_BOX_CLASS,
    CARD_HEADER_ROW_CLASS,
    STATUS_BADGE_CLASS,
    STATUS_BADGE_MUTED_CLASS,
    INFO_PANEL_CLASS,
    WARNING_BANNER_CLASS,
    WARNING_BANNER_ROW_CLASS,
};

window.ComponentCSS = ComponentCSS;

export { SHELL_SCROLL_ATTR, SHELL_SCROLLBAR_CLASS, SHELL_MODAL_SCROLL_ATTR, TAB_SHELL_CLASS, TAB_HEADER_CLASS, TAB_SWITCHER_CLASS, TAB_CONTENT_AREA_CLASS, MODAL_OVERLAY_CLASS, MODAL_PANEL_CLASS, MODAL_HEADER_CLASS, FEATURE_MODAL_STAGE_CLASS, FEATURE_MODAL_PANEL_CLASS, SUB_TAB_BUTTON_BASE_CLASS, SUB_TAB_BUTTON_ACTIVE_CLASS, SUB_TAB_BUTTON_INACTIVE_CLASS, MODAL_CLOSE_BUTTON_CLASS, GOV_TAB_BUTTON_BASE_CLASS, GOV_TAB_BUTTON_ACTIVE_CLASS, GOV_TAB_BUTTON_INACTIVE_CLASS, ICON_ACTION_BUTTON_CLASS, FILTER_TRIGGER_BUTTON_CLASS, SECTION_HEADER_ROW_CLASS, SECTION_TOGGLE_ROW_CLASS, SECTION_TITLE_CLASS, PRIMARY_DIVIDER_LEFT_CLASS, PRIMARY_DIVIDER_RIGHT_CLASS, WARNING_DIVIDER_LEFT_CLASS, WARNING_DIVIDER_RIGHT_CLASS, SUCCESS_DIVIDER_LEFT_CLASS, SUCCESS_DIVIDER_RIGHT_CLASS, ACCENT_DIVIDER_LEFT_CLASS, ACCENT_DIVIDER_RIGHT_CLASS, SECTION_TOGGLE_BUTTON_CLASS, SECTION_CHEVRON_BASE_CLASS, PRIMARY_CHEVRON_CLASS, WARNING_CHEVRON_CLASS, SUCCESS_CHEVRON_CLASS, ACCENT_CHEVRON_CLASS, LOADER_BLOCK_CLASS, LARGE_LOADER_BLOCK_CLASS, LOADING_PLACEHOLDER_CLASS, LOADING_PLACEHOLDER_SMALL_CLASS, PRIMARY_SPINNER_CLASS, WARNING_SPINNER_CLASS, SUCCESS_SPINNER_CLASS, ACCENT_SPINNER_CLASS, PRIMARY_LARGE_SPINNER_CLASS, PRIMARY_RING_SPINNER_CLASS, WARNING_RING_SPINNER_CLASS, LOADER_ICON_CLASS, MODAL_FOOTER_CLASS, MODAL_ACTION_ROW_CLASS, SUCCESS_ACTION_BUTTON_CLASS, DANGER_ACTION_BUTTON_CLASS, GOV_FILTER_ROW_CLASS, GOV_FILTER_BUTTON_BASE_CLASS, GOV_FILTER_BUTTON_ACTIVE_CLASS, GOV_FILTER_BUTTON_INACTIVE_CLASS, LOADING_PLACEHOLDER_TIGHT_CLASS, SEARCH_SHELL_GLOW_CLASS, SEARCH_SHELL_PANEL_CLASS, SEARCH_ICON_WRAP_CLASS, SEARCH_INPUT_CLASS, SEARCH_ACTION_BUTTON_CLASS, HERO_TITLE_CLASS, HERO_ICON_BOX_CLASS, CARD_HEADER_ROW_CLASS, STATUS_BADGE_CLASS, STATUS_BADGE_MUTED_CLASS, INFO_PANEL_CLASS, WARNING_BANNER_CLASS, WARNING_BANNER_ROW_CLASS, ComponentCSS };
