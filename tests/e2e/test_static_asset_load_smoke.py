import asyncio
import contextlib
import importlib.util
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8767

PAGES_TO_CHECK = [
    "/static/index.html#chat",
    "/static/forum/index.html",
    "/static/forum/dashboard.html",
    "/static/forum/create.html",
    "/static/forum/post.html?id=1",
    "/static/forum/premium.html",
    "/static/forum/profile.html",
    "/static/forum/messages.html",
    "/static/scam-tracker/index.html",
    "/static/scam-tracker/detail.html?id=1",
    "/static/scam-tracker/submit.html",
    "/static/governance/index.html",
    "/static/legal/terms-of-service.html",
    "/static/legal/privacy-policy.html",
    "/static/legal/community-guidelines.html",
]


class StaticAppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean_path = urlsplit(path).path
        if clean_path.startswith("/static/"):
            rel = clean_path[len("/static/") :]
            return str((WEB_DIR / rel).resolve())
        if clean_path in ("/", "/index.html"):
            return str((WEB_DIR / "index.html").resolve())
        return str((WEB_DIR / clean_path.lstrip("/")).resolve())

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


def build_api_stub(path: str, method: str):
    if path == "/api/config":
        return {"test_mode": False, "current_settings": {}}
    if path == "/api/model-config":
        return {"model_config": {}}
    if path == "/api/config/prices":
        return {}
    if path == "/api/config/limits":
        return {}
    if path == "/api/analyze/modes":
        return {
            "current_tier": "premium",
            "allowed_modes": ["quick", "verified", "research"],
            "default_mode": "verified",
        }
    if path == "/api/user/api-keys":
        return {
            "keys": {
                "openai": {
                    "has_key": True,
                    "masked_key": "sk-***test",
                    "model": "gpt-4o-mini",
                }
            }
        }
    if path == "/api/user/tools":
        return {"tools": []}
    if path == "/api/test-mode/current-tier":
        return {"tier": "premium"}
    if path.startswith("/api/chat/sessions"):
        if method == "GET":
            return {"sessions": []}
        return {"session_id": "sess-smoke-001", "title": "Smoke"}
    if path.startswith("/api/forum/boards"):
        return {"boards": []}
    if path.startswith("/api/forum/posts/"):
        return {
            "post": {
                "id": 1,
                "title": "Smoke Post",
                "category": "General",
                "user_id": "smoke-user-001",
                "username": "SmokeUser",
                "created_at": "2026-03-14T00:00:00Z",
                "content": "Smoke post content",
                "tags": "[]",
                "push_count": 0,
                "boo_count": 0,
                "tips_total": 0,
                "viewer_vote": None,
            }
        }
    if path.startswith("/api/forum/posts"):
        return {"posts": [], "total": 0, "has_more": False}
    if path.startswith("/api/forum/tags/trending"):
        return {"tags": []}
    if path.startswith("/api/scam-tracker/reports/config"):
        return {"scam_types": []}
    if path.startswith("/api/scam-tracker/reports/search"):
        return {"reports": []}
    if path.startswith("/api/scam-tracker/reports/"):
        return {
            "report": {
                "id": "1",
                "scam_wallet_address": "PTEST123",
                "scam_type": "other",
                "description": "smoke-test",
                "verification_status": "pending",
                "created_at": "2026-03-14T00:00:00Z",
                "reporter_wallet_masked": "PTEST***",
                "transaction_hash": "",
                "view_count": 0,
                "approve_count": 0,
                "reject_count": 0,
                "comment_count": 0,
                "viewer_vote": None,
            }
        }
    if path.startswith("/api/scam-tracker/reports"):
        return {"reports": [], "total": 0}
    if path.startswith("/api/scam-tracker/comments/"):
        return {"comments": []}
    return {}


async def run_static_asset_load_smoke():
    from playwright.async_api import async_playwright

    static_failures: list[tuple[str, int, str]] = []
    page_errors: list[tuple[str, str]] = []
    console_errors: list[tuple[str, str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 960})

        for page_path in PAGES_TO_CHECK:
            page = await context.new_page()

            await page.add_init_script(
                """
                localStorage.setItem("pi_user", JSON.stringify({
                    uid: "smoke-user-001",
                    user_id: "smoke-user-001",
                    username: "SmokeUser",
                    authMethod: "password",
                    accessToken: "token-smoke",
                    accessTokenExpiry: Date.now() + 3600 * 1000,
                    membership_tier: "premium"
                }));

                class SmokeWebSocket {
                    static CONNECTING = 0;
                    static OPEN = 1;
                    static CLOSING = 2;
                    static CLOSED = 3;

                    constructor(url) {
                        this.url = url;
                        this.readyState = SmokeWebSocket.OPEN;
                        this.onopen = null;
                        this.onmessage = null;
                        this.onclose = null;
                        this.onerror = null;
                        setTimeout(() => {
                            if (this.onopen) this.onopen({ type: "open" });
                        }, 0);
                    }

                    send() {}

                    close() {
                        this.readyState = SmokeWebSocket.CLOSED;
                        if (this.onclose) this.onclose({ type: "close", code: 1000 });
                    }

                    addEventListener(type, handler) {
                        if (type === "open") this.onopen = handler;
                        if (type === "message") this.onmessage = handler;
                        if (type === "close") this.onclose = handler;
                        if (type === "error") this.onerror = handler;
                    }
                }

                window.WebSocket = SmokeWebSocket;
                """
            )

            async def handle_route(route):
                url = route.request.url
                if "/api/" in url:
                    parsed = urlsplit(url)
                    body = build_api_stub(parsed.path, route.request.method)
                    await route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(body),
                    )
                    return
                await route.continue_()

            def on_response(resp):
                url = resp.url
                if f"http://{HOST}:{PORT}/static/" in url and resp.status >= 400:
                    static_failures.append((page_path, resp.status, url))

            def on_pageerror(err):
                page_errors.append((page_path, str(err)))

            def on_console(msg):
                if msg.type != "error":
                    return
                loc = msg.location or {}
                url = loc.get("url", "")
                # Focus on errors emitted by our local static scripts.
                if f"http://{HOST}:{PORT}/static/" in url:
                    console_errors.append((page_path, url, msg.text))

            await page.route("**/*", handle_route)
            page.on("response", on_response)
            page.on("pageerror", on_pageerror)
            page.on("console", on_console)

            await page.goto(
                f"http://{HOST}:{PORT}{page_path}",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await page.wait_for_timeout(1200)
            await page.close()

        await browser.close()

    assert not static_failures, "static assets failed to load:\n" + "\n".join(
        f"{path} -> {status} {url}" for path, status, url in static_failures
    )
    assert not page_errors, "uncaught frontend errors detected:\n" + "\n".join(
        f"{path} -> {message}" for path, message in page_errors
    )
    assert not console_errors, "frontend console errors detected:\n" + "\n".join(
        f"{path} -> {url} :: {message}" for path, url, message in console_errors
    )


@pytest.mark.e2e
def test_static_asset_load_smoke():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")

    with run_static_server():
        asyncio.run(run_static_asset_load_smoke())
