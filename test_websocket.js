// Test WebSocket connections and real-time updates
console.log("Testing WebSocket connections...");

// Check if WebSocket functions are available
if (typeof connectTickerWebSocket === 'function') {
    console.log("✓ Ticker WebSocket connection function available");
} else {
    console.error("✗ Ticker WebSocket connection function NOT available");
}

if (typeof connectWebSocket === 'function') {
    console.log("✓ K-line WebSocket connection function available");
} else {
    console.error("✗ K-line WebSocket connection function NOT available");
}

if (typeof subscribeTickerSymbols === 'function') {
    console.log("✓ Subscribe ticker symbols function available");
} else {
    console.error("✗ Subscribe ticker symbols function NOT available");
}

// Test WebSocket connection status
function testWebSocketConnections() {
    console.log("\n--- Testing WebSocket Connections ---");
    
    // Check connection status
    console.log("K-line WebSocket connected:", window.wsConnected || false);
    console.log("Ticker WebSocket connected:", window.marketWsConnected || false);
    
    // Check WebSocket objects
    console.log("K-line WebSocket object:", window.klineWebSocket ? 'Exists' : 'Not found');
    console.log("Ticker WebSocket object:", window.marketWebSocket ? 'Exists' : 'Not found');
    
    // Check auto-refresh status
    console.log("Auto-refresh enabled:", window.autoRefreshEnabled || false);
}

// Run initial test
testWebSocketConnections();

// Wait a bit and test again to see if connections establish
setTimeout(() => {
    console.log("\n--- Re-testing after delay ---");
    testWebSocketConnections();
}, 3000);

// Function to test subscribing to symbols
function testSubscribeSymbols() {
    if (typeof subscribeTickerSymbols === 'function') {
        console.log("\n--- Testing Symbol Subscription ---");
        const testSymbols = ['BTC', 'ETH', 'SOL'];
        console.log("Attempting to subscribe to:", testSymbols);
        subscribeTickerSymbols(testSymbols);
    }
}

// Add event listeners to monitor WebSocket events
function setupMonitoring() {
    console.log("\n--- Setting up WebSocket Monitoring ---");
    
    // Monitor WebSocket connection changes
    const originalSet = window.__lookupSetter__('wsConnected') || (() => {});
    const originalMarketSet = window.__lookupSetter__('marketWsConnected') || (() => {});
    
    // We can't easily intercept the variables, so we'll just log periodically
    setInterval(() => {
        if (window.wsConnected !== undefined) {
            // Connection status changed - could be logged
        }
    }, 1000);
}

setupMonitoring();

// Export test function for manual testing
window.runWebSocketTest = testWebSocketConnections;
window.testSubscribe = testSubscribeSymbols;

console.log("\nTo run tests manually:");
console.log("- runWebSocketTest() - Test WebSocket connections");
console.log("- testSubscribe() - Test subscribing to symbols");