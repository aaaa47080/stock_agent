import asyncio
import contextlib
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8766


class StaticAppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            return str((WEB_DIR / rel).resolve())
        if path in ("/", "/index.html"):
            return str((WEB_DIR / "index.html").resolve())
        return str((WEB_DIR / path.lstrip("/")).resolve())

    def log_message(self, fmt: str, *args) -> None:
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


async def run_verified_mode_market_flow_test():
    from playwright.async_api import async_playwright

    analyze_requests: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 960})

        await page.add_init_script(
            """
            localStorage.setItem("pi_user", JSON.stringify({
                uid: "premium-user-001",
                user_id: "premium-user-001",
                username: "PremiumUser",
                accessToken: "token-premium",
                accessTokenExpiry: Date.now() + 3600 * 1000,
                membership_tier: "premium"
            }));
            localStorage.setItem("user_selected_provider", "openai");
            localStorage.setItem("user_openai_selected_model", "gpt-4o-mini");
            """
        )

        async def handle_route(route):
            url = route.request.url

            if url.endswith("/api/config"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"test_mode": False, "current_settings": {}}),
                )
                return

            if url.endswith("/api/model-config"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"model_config": {}}),
                )
                return

            if url.endswith("/api/user/api-keys"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "keys": {
                                "openai": {
                                    "has_key": True,
                                    "masked_key": "sk-***test",
                                    "model": "gpt-4o-mini",
                                }
                            }
                        }
                    ),
                )
                return

            if url.endswith("/api/user/api-keys/openai/full"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"key": "sk-test-openai"}),
                )
                return

            if url.endswith("/api/analyze/modes"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "current_tier": "premium",
                            "allowed_modes": ["quick", "verified"],
                            "default_mode": "verified",
                        }
                    ),
                )
                return

            if "/api/chat/sessions" in url and route.request.method == "GET":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"sessions": []}),
                )
                return

            if "/api/chat/sessions" in url and route.request.method == "POST":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"session_id": "sess-e2e-001", "title": "New Chat"}),
                )
                return

            if url.endswith("/api/analyze") and route.request.method == "POST":
                raw_payload = route.request.post_data or "{}"
                analyze_requests.append(json.loads(raw_payload))
                await route.fulfill(
                    status=200,
                    headers={"Content-Type": "text/event-stream"},
                    body=(
                        'data: {"content":"TSM 最新價格已取得。"}\n\n'
                        'data: {"type":"response_metadata","data":{"analysis_mode":"verified","verification_status":"verified","used_tools":["web_search","us_stock_price"],"data_as_of":"2026-03-13T12:00:00Z","query_type":"price_lookup","resolved_market":"us","policy_path":"discovery_lookup"}}\n\n'
                        'data: {"done":true}\n\n'
                    ),
                )
                return

            if "/api/" in url:
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({}),
                )
                return

            await route.continue_()

        await page.route("**/*", handle_route)
        await page.goto(f"http://{HOST}:{PORT}/static/index.html#chat", wait_until="domcontentloaded")

        await page.wait_for_function(
            """
            () => {
                const select = document.getElementById('analysis-mode-select');
                const input = document.getElementById('user-input');
                return !!select && !!input && !input.disabled;
            }
            """
        )

        selector = page.locator("#analysis-mode-select")
        verified_option_disabled = await page.locator('#analysis-mode-select option[value="verified"]').evaluate(
            "(node) => node.disabled"
        )
        research_option_disabled = await page.locator('#analysis-mode-select option[value="research"]').evaluate(
            "(node) => node.disabled"
        )

        assert await selector.input_value() == "quick"
        assert verified_option_disabled is False
        assert research_option_disabled is True

        await selector.select_option("verified")
        await page.fill("#user-input", "tsm 現在多少？")
        await page.click("#send-btn")

        await page.wait_for_function(
            """
            () => {
                const body = document.body.innerText || '';
                return body.includes('TSM 最新價格已取得。') &&
                    body.includes('查詢類型: price_lookup') &&
                    body.includes('市場: us') &&
                    body.includes('路徑: discovery_lookup') &&
                    body.includes('工具: web_search, us_stock_price');
            }
            """
        )

        assert analyze_requests, "expected /api/analyze to be called"
        assert analyze_requests[0]["analysis_mode"] == "verified"
        assert analyze_requests[0]["message"] == "tsm 現在多少？"

        await browser.close()


async def run_free_mode_guardrail_test():
    from playwright.async_api import async_playwright

    analyze_requests: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 960})

        await page.add_init_script(
            """
            localStorage.setItem("pi_user", JSON.stringify({
                uid: "free-user-001",
                user_id: "free-user-001",
                username: "FreeUser",
                accessToken: "token-free",
                accessTokenExpiry: Date.now() + 3600 * 1000,
                membership_tier: "free"
            }));
            localStorage.setItem("user_selected_provider", "openai");
            localStorage.setItem("user_openai_selected_model", "gpt-4o-mini");
            """
        )

        async def handle_route(route):
            url = route.request.url

            if url.endswith("/api/config"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"test_mode": False, "current_settings": {}}),
                )
                return

            if url.endswith("/api/model-config"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"model_config": {}}),
                )
                return

            if url.endswith("/api/user/api-keys"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "keys": {
                                "openai": {
                                    "has_key": True,
                                    "masked_key": "sk-***test",
                                    "model": "gpt-4o-mini",
                                }
                            }
                        }
                    ),
                )
                return

            if url.endswith("/api/user/api-keys/openai/full"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"key": "sk-test-openai"}),
                )
                return

            if url.endswith("/api/analyze/modes"):
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "current_tier": "free",
                            "allowed_modes": ["quick"],
                            "default_mode": "quick",
                        }
                    ),
                )
                return

            if "/api/chat/sessions" in url and route.request.method == "GET":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"sessions": []}),
                )
                return

            if "/api/chat/sessions" in url and route.request.method == "POST":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"session_id": "sess-free-001", "title": "New Chat"}),
                )
                return

            if url.endswith("/api/analyze") and route.request.method == "POST":
                raw_payload = route.request.post_data or "{}"
                analyze_requests.append(json.loads(raw_payload))
                await route.fulfill(
                    status=200,
                    headers={"Content-Type": "text/event-stream"},
                    body=(
                        'data: {"content":"這是 quick 模式回應。"}\n\n'
                        'data: {"type":"response_metadata","data":{"analysis_mode":"quick","verification_status":"standard","used_tools":[],"query_type":"general","resolved_market":null,"policy_path":null}}\n\n'
                        'data: {"done":true}\n\n'
                    ),
                )
                return

            if "/api/" in url:
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({}),
                )
                return

            await route.continue_()

        await page.route("**/*", handle_route)
        await page.goto(f"http://{HOST}:{PORT}/static/index.html#chat", wait_until="domcontentloaded")

        await page.wait_for_function(
            """
            () => {
                const select = document.getElementById('analysis-mode-select');
                const input = document.getElementById('user-input');
                return !!select && !!input && !input.disabled;
            }
            """
        )

        selector = page.locator("#analysis-mode-select")
        verified_option_disabled = await page.locator('#analysis-mode-select option[value="verified"]').evaluate(
            "(node) => node.disabled"
        )

        assert await selector.input_value() == "quick"
        assert verified_option_disabled is True

        await page.fill("#user-input", "幫我看一下台積電")
        await page.click("#send-btn")

        await page.wait_for_function(
            """
            () => {
                const body = document.body.innerText || '';
                return body.includes('這是 quick 模式回應。') &&
                    body.includes('模式: quick');
            }
            """
        )

        assert analyze_requests, "expected /api/analyze to be called"
        assert analyze_requests[0]["analysis_mode"] == "quick"
        assert analyze_requests[0]["message"] == "幫我看一下台積電"

        await browser.close()


if __name__ == "__main__":
    with run_static_server():
        asyncio.run(run_verified_mode_market_flow_test())
