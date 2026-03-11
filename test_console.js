const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({
        headless: 'new',
    });
    const page = await browser.newPage();

    page.on('console', msg => {
        // We only care about our [App] logs and maybe errors
        if (msg.text().includes('[App]') || msg.type() === 'error' || msg.type() === 'warning') {
            console.log(`[Browser ${msg.type().toUpperCase()}] ${msg.text()}`);
        }
    });

    try {
        console.log('Navigating to http://localhost:8080...');
        await page.goto('http://localhost:8080', { waitUntil: 'networkidle0' });

        // Wait for our UI initialization to possibly finish
        await page.waitForTimeout(3000);
        console.log('Done waiting, closing browser.');
    } catch (e) {
        console.error('Puppeteer error:', e);
    } finally {
        await browser.close();
    }
})();
