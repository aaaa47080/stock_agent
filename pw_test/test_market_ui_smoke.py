import asyncio
import contextlib
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8769


class StaticAppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean_path = urlsplit(path).path
        if clean_path.startswith("/static/"):
            rel = clean_path[len("/static/"):]
            return str((WEB_DIR / rel).resolve())
        if clean_path in ("/", "/index.html"):
            return str((WEB_DIR / "index.html").resolve())
        return str((WEB_DIR / clean_path.lstrip("/")).resolve())

    def log_message(self, format: str, *args) -> None:
        return


@contextlib.contextmanager
def run_static_server():
    server = ThreadingHTTPServer((HOST, PORT), StaticAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


async def run_market_ui_smoke_test():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def seed_context(context):
            await context.add_init_script(
                """
                localStorage.setItem("pi_user", JSON.stringify({
                    uid: "e2e-user-001",
                    user_id: "e2e-user-001",
                    username: "E2ETester",
                    authMethod: "password",
                    accessToken: "token-e2e",
                    accessTokenExpiry: Date.now() + 3600 * 1000,
                    membership_tier: "premium"
                }));
                localStorage.setItem("selectedLanguage", "zh-TW");
                localStorage.setItem("activeTab", "crypto");
                """
            )

        async def mock_api_routes(route):
            parsed = urlsplit(route.request.url)
            path = parsed.path
            method = route.request.method

            if path == "/api/config":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"test_mode": True, "current_settings": {}}),
                )
                return

            if path == "/api/crypto/market":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "top_performers": [
                            {"symbol": "BTC", "name": "Bitcoin", "price": 65000, "changePercent": 2.5},
                            {"symbol": "ETH", "name": "Ethereum", "price": 3400, "changePercent": -1.2},
                        ],
                        "last_updated": "2026-03-20T15:00:00",
                    }),
                )
                return

            if path == "/api/forex/market":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "pairs": [
                            {"symbol": "USD/TWD", "name": "USD/TWD", "rate": 32.5, "changePercent": 0.1},
                            {"symbol": "EUR/USD", "name": "EUR/USD", "rate": 1.08, "changePercent": -0.05},
                        ],
                        "last_updated": "2026-03-20T15:00:00",
                    }),
                )
                return

            if path == "/api/commodity/market":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "commodities": [
                            {"symbol": "XAU", "name": "Gold", "price": 2150, "changePercent": 0.8, "unit": "oz"},
                            {"symbol": "WTI", "name": "WTI Crude", "price": 72.5, "changePercent": -1.5, "unit": "bbl"},
                        ],
                        "last_updated": "2026-03-20T15:00:00",
                    }),
                )
                return

            if path == "/api/twstock/market":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "top_performers": [
                            {"Symbol": "2330", "Name": "TSMC", "Close": 850, "Change": 15, "ChangePercent": 1.79},
                            {"Symbol": "2317", "Name": "Hon Hai", "Close": 120, "Change": -2, "ChangePercent": -1.64},
                        ],
                        "last_updated": "2026-03-20T15:00:00",
                    }),
                )
                return

            if path == "/api/usstock/market":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "stocks": [
                            {"symbol": "AAPL", "name": "Apple", "price": 195, "change": 3, "changePercent": 1.56},
                            {"symbol": "TSLA", "name": "Tesla", "price": 250, "change": -5, "changePercent": -1.96},
                        ],
                        "last_updated": "2026-03-20T15:00:00",
                    }),
                )
                return

            if path.startswith("/api/"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({}),
                )
                return

            await route.continue_()

        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        await seed_context(context)
        page = await context.new_page()
        await page.route("**/*", mock_api_routes)

        await page.goto(
            f"http://{HOST}:{PORT}/static/index.html#crypto",
            wait_until="domcontentloaded",
        )

        await page.wait_for_timeout(3000)

        sidebar = await page.query_selector("#chat-sidebar")
        sidebar_display = await sidebar.evaluate("el => getComputedStyle(el).display") if sidebar else "not_found"
        assert sidebar_display == "none", f"Sidebar should be hidden on crypto page, got: {sidebar_display}"

        crypto_tab = await page.query_selector("#crypto-tab")
        assert crypto_tab is not None, "Crypto tab should exist"
        crypto_hidden = await crypto_tab.evaluate("el => el.classList.contains('hidden')")
        assert not crypto_hidden, "Crypto tab should be visible"

        sidebar = await page.query_selector("#chat-sidebar")
        sidebar_display = await sidebar.evaluate("el => getComputedStyle(el).display") if sidebar else "not_found"
        assert sidebar_display == "none", f"Sidebar should be hidden on crypto page, got: {sidebar_display}"

        commodity_h2 = await page.query_selector("#commodity-market-section h2")
        if commodity_h2:
            commodity_title = await commodity_h2.inner_text()
            assert "大宗商品" in commodity_title, f"Commodity title should contain Chinese, got: {commodity_title}"

        await page.goto(
            f"http://{HOST}:{PORT}/static/index.html#forex",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(3000)

        i18n_ready = await page.evaluate("() => window.I18n ? window.I18n.isReady() : false")
        if i18n_ready:
            await page.evaluate("""
                () => {
                    if (window.I18n) {
                        window.I18n.changeLanguage('en');
                    }
                }
            """)
            await page.wait_for_timeout(2000)

        commodity_h2 = await page.query_selector("#commodity-market-section h2")
        if commodity_h2:
            commodity_title_en = await commodity_h2.inner_text()
            assert "Commodity" in commodity_title_en, f"Commodity title should be English after switch, got: {commodity_title_en}"

        forex_h2 = await page.query_selector("#forex-market-section h2")
        if forex_h2:
            forex_title_en = await forex_h2.inner_text()
            assert "Forex" in forex_title_en, f"Forex title should be English after switch, got: {forex_title_en}"

        last_updated_el = await page.query_selector("#forex-last-updated")
        if last_updated_el:
            last_updated_text = await last_updated_el.inner_text()
            assert "Last Updated" in last_updated_text, \
                f"Last updated should be translated to English, got: {last_updated_text}"

        await page.evaluate("window.location.hash = '#twstock'")
        await page.wait_for_timeout(1000)

        sidebar = await page.query_selector("#chat-sidebar")
        if sidebar:
            sidebar_display = await sidebar.evaluate("el => getComputedStyle(el).display")
            assert sidebar_display == "none", f"Sidebar should be hidden on twstock page, got: {sidebar_display}"

        status_badge = await page.query_selector("#twstock-market-status-badge")
        if status_badge:
            badge_text = await status_badge.inner_text()
            assert badge_text, "TW Stock status badge should have text"

        await page.evaluate("window.location.hash = '#usstock'")
        await page.wait_for_timeout(1000)

        sidebar = await page.query_selector("#chat-sidebar")
        if sidebar:
            sidebar_display = await sidebar.evaluate("el => getComputedStyle(el).display")
            assert sidebar_display == "none", f"Sidebar should be hidden on usstock page, got: {sidebar_display}"

        await page.evaluate("window.location.hash = '#chat'")
        await page.wait_for_timeout(1000)

        sidebar = await page.query_selector("#chat-sidebar")
        if sidebar:
            sidebar_display = await sidebar.evaluate("el => getComputedStyle(el).display")
            assert sidebar_display != "none", f"Sidebar should be visible on chat page, got: {sidebar_display}"

        await context.close()
        await browser.close()


if __name__ == "__main__":
    with run_static_server():
        asyncio.run(run_market_ui_smoke_test())
