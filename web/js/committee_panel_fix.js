// Expose to global for HTML callbacks
window.CommitteeManager = CommitteeManager;
window.toggleCommitteePanel = (checkbox) => {
    console.log('[Global] toggleCommitteePanel called with:', checkbox);
    if (checkbox && typeof checkbox === 'object' && 'checked' in checkbox) {
        // Called from inline handler with checkbox element
        console.log('[Global] Calling togglePanel with checked:', checkbox.checked);
        CommitteeManager.togglePanel(checkbox.checked);
    } else {
        // Fallback: read directly from DOM
        const cb = document.getElementById('set-committee-mode');
        console.log('[Global] Fallback to DOM, checkbox:', cb, 'checked:', cb?.checked);
        if (cb) CommitteeManager.togglePanel(cb.checked);
    }
};
window.updateCommitteeModels = () => CommitteeManager.handleProviderChange();
window.addModelToCommittee = (team) => CommitteeManager.addMember(team);
