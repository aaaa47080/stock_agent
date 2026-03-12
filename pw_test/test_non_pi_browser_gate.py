import asyncio
import contextlib
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765


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


async def main():
    protected_hits: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 390, "height": 844})

        await page.add_init_script(
            """
            localStorage.setItem("pi_user", JSON.stringify({
                uid: "user-001",
                username: "SavedUser",
                accessToken: "token-123",
                accessTokenExpiry: Date.now() + 3600 * 1000
            }));
            localStorage.setItem("activeTab", "settings");
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
            if "/api/user/tools" in url or "/api/test-mode/current-tier" in url:
                protected_hits.append(url)
                await route.fulfill(
                    status=401,
                    content_type="application/json",
                    body=json.dumps({"detail": "unauthorized"}),
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
        await page.goto(f"http://{HOST}:{PORT}/static/index.html#settings", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        modal = page.locator("#login-modal")
        not_pi = page.locator("#not-pi-browser-msg")
        active_chat = page.locator("#chat-tab")

        assert await modal.is_visible(), "login modal should be visible immediately"
        assert await not_pi.is_visible(), "non-Pi Browser warning should be visible"
        assert "chat" in page.url, f"expected landing to be locked to chat, got {page.url}"
        assert await active_chat.is_visible(), "chat tab should remain the active landing tab"
        assert not protected_hits, f"protected endpoints should not be called anonymously: {protected_hits}"

        await browser.close()


if __name__ == "__main__":
    with run_static_server():
        asyncio.run(main())
