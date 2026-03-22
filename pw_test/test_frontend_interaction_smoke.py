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
PORT = 8768


class StaticAppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean_path = urlsplit(path).path
        if clean_path.startswith("/static/"):
            rel = clean_path[len("/static/") :]
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


async def run_frontend_interaction_smoke_test():
    from playwright.async_api import async_playwright

    analyze_requests: list[dict] = []
    deleted_alert_ids: list[str] = []
    sent_messages: list[dict] = []
    session_records = [
        {"id": "sess-history-1", "title": "BTC history", "is_pinned": False},
        {"id": "sess-history-2", "title": "ETH setup", "is_pinned": True},
    ]
    alert_records = [
        {
            "id": "alert-1",
            "symbol": "TSM",
            "condition": "above",
            "target": 180,
            "repeat": False,
        }
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def seed_context(context):
            await context.add_init_script(
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
                localStorage.setItem("activeTab", "settings");
                localStorage.setItem("user_selected_provider", "openai");
                localStorage.setItem("user_openai_selected_model", "gpt-4o-mini");

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
            parsed = urlsplit(route.request.url)
            path = parsed.path
            method = route.request.method

            if path == "/api/config":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"test_mode": False, "current_settings": {}}),
                )
                return

            if path == "/api/model-config":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"model_config": {}}),
                )
                return

            if path == "/api/user/api-keys":
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

            if path == "/api/user/api-keys/openai/full":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"key": "sk-test-openai"}),
                )
                return

            if path == "/api/user/tools":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"tools": []}),
                )
                return

            if path == "/api/test-mode/current-tier":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"tier": "premium"}),
                )
                return

            if path == "/api/analyze/modes":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "current_tier": "premium",
                            "allowed_modes": ["quick", "verified", "research"],
                            "default_mode": "verified",
                        }
                    ),
                )
                return

            if path == "/api/chat/sessions" and method == "GET":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"sessions": session_records}),
                )
                return

            if path == "/api/chat/sessions" and method == "POST":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"session_id": "sess-smoke-002", "title": "Smoke"}),
                )
                return

            if path == "/api/analyze" and method == "POST":
                payload = json.loads(route.request.post_data or "{}")
                analyze_requests.append(payload)
                await route.fulfill(
                    status=200,
                    headers={"Content-Type": "text/event-stream"},
                    body=(
                        'data: {"content":"Smoke analysis complete."}\n\n'
                        'data: {"type":"response_metadata","data":{"analysis_mode":"verified","verification_status":"verified","used_tools":["web_search"],"query_type":"price_lookup","resolved_market":"us"}}\n\n'
                        'data: {"done":true}\n\n'
                    ),
                )
                return

            if path == "/api/chat/history":
                query_params = dict(
                    item.split("=", 1)
                    for item in parsed.query.split("&")
                    if "=" in item
                )
                session_id = query_params.get("session_id", "")
                history = []
                if session_id == "sess-history-1":
                    if query_params.get("before_timestamp"):
                        history = [
                            {
                                "role": "assistant",
                                "content": "Older BTC history loaded.",
                                "timestamp": "2026-03-18T09:00:00",
                            }
                        ]
                    else:
                        history = [
                            {
                                "role": "assistant",
                                "content": "Historical BTC session loaded.",
                                "timestamp": "2026-03-18T10:00:00",
                            }
                        ]
                elif session_id == "sess-history-2":
                    history = [
                        {
                            "role": "assistant",
                            "content": "ETH pinned session loaded.",
                            "timestamp": "2026-03-18T11:00:00",
                        }
                    ]
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "history": history,
                            "has_more": session_id == "sess-history-1"
                            and not query_params.get("before_timestamp"),
                        }
                    ),
                )
                return

            if path == "/api/chat/sessions/sess-history-1/pin" and method == "PUT":
                query_params = dict(
                    item.split("=", 1)
                    for item in parsed.query.split("&")
                    if "=" in item
                )
                is_pinned = query_params.get("is_pinned", "false") == "true"
                for session in session_records:
                    if session["id"] == "sess-history-1":
                        session["is_pinned"] = is_pinned
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/chat/sessions/sess-history-1" and method == "DELETE":
                session_records[:] = [
                    s for s in session_records if s["id"] != "sess-history-1"
                ]
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/alerts" and method == "POST":
                alert_records[:] = [
                    {
                        "id": "alert-1",
                        "symbol": "TSM",
                        "condition": "above",
                        "target": 180,
                        "repeat": False,
                    }
                ]
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/alerts" and method == "GET":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"alerts": alert_records}),
                )
                return

            if path == "/api/alerts/alert-1" and method == "DELETE":
                alert_records[:] = []
                deleted_alert_ids.append("alert-1")
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/messages/limits":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "is_premium": True,
                            "message_limit": {"used": 1, "limit": 20},
                            "max_length": 500,
                        }
                    ),
                )
                return

            if path == "/api/messages/conversations":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "conversations": [
                                {
                                    "id": 101,
                                    "other_user_id": "friend-001",
                                    "other_username": "Friend One",
                                    "other_membership_tier": "premium",
                                    "last_message": "最近怎麼樣？",
                                    "last_message_at": "2026-03-18T12:00:00Z",
                                    "unread_count": 1,
                                }
                            ]
                        }
                    ),
                )
                return

            if path == "/api/messages/with/friend-001":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "conversation": {
                                "id": 101,
                                "other_username": "Friend One",
                            },
                            "messages": [
                                {
                                    "id": 1,
                                    "from_user_id": "friend-001",
                                    "to_user_id": "smoke-user-001",
                                    "content": "嗨，這是 smoke test 對話。",
                                    "created_at": "2026-03-18T12:00:00Z",
                                    "message_type": "text",
                                    "is_read": False,
                                }
                            ],
                        }
                    ),
                )
                return

            if path == "/api/messages/conversation/101":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "messages": [
                                {
                                    "id": 1,
                                    "from_user_id": "friend-001",
                                    "to_user_id": "smoke-user-001",
                                    "content": "嗨，這是 smoke test 對話。",
                                    "created_at": "2026-03-18T12:00:00Z",
                                    "message_type": "text",
                                    "is_read": False,
                                }
                            ],
                            "has_more": False,
                        }
                    ),
                )
                return

            if path == "/api/messages/send" and method == "POST":
                payload = json.loads(route.request.post_data or "{}")
                sent_messages.append(payload)
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "success": True,
                            "message": {
                                "id": 2,
                                "from_user_id": "smoke-user-001",
                                "to_user_id": payload["to_user_id"],
                                "content": payload["content"],
                                "created_at": "2026-03-18T12:05:00Z",
                                "message_type": "text",
                                "is_read": False,
                            },
                        }
                    ),
                )
                return

            if path == "/api/messages/read":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/messages/2" and method == "DELETE":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True}),
                )
                return

            if path == "/api/messages/search":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "results": [
                                {
                                    "other_user_id": "friend-001",
                                    "other_username": "Friend One",
                                    "content": "Smoke search result",
                                    "created_at": "2026-03-18T12:03:00Z",
                                }
                            ]
                        }
                    ),
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

        context = await browser.new_context(viewport={"width": 390, "height": 844})
        await seed_context(context)
        page = await context.new_page()
        await page.route("**/*", handle_route)

        await page.goto(
            f"http://{HOST}:{PORT}/static/index.html#settings",
            wait_until="domcontentloaded",
        )
        await page.wait_for_function(
            """
            () => {
                const featureMenu = typeof window.FeatureMenu !== 'undefined';
                const legalPage = typeof window.showLegalPage === 'function';
                return featureMenu && legalPage;
            }
            """,
            timeout=60000,
        )
        await page.wait_for_function(
            """
            () => document.body.innerText.includes('About & Legal')
            """,
            timeout=10000,
        )

        await page.evaluate("window.FeatureMenu.open()")
        await page.wait_for_selector("#feature-menu-modal:not(.hidden)")
        await page.wait_for_function(
            """
            () => {
                const items = document.querySelectorAll('#feature-menu-items .feature-menu-item');
                return items.length > 0;
            }
            """
        )
        await page.evaluate("window.FeatureMenu.close()")
        await page.wait_for_function(
            """
            () => document.getElementById('feature-menu-modal')?.classList.contains('hidden')
            """
        )

        await page.evaluate("window.FeatureMenu.open()")
        await page.wait_for_selector("#feature-menu-modal:not(.hidden)")
        await page.evaluate(
            """
            () => {
                const items = Array.from(document.querySelectorAll('#feature-menu-items .feature-menu-item'));
                const keepIds = items.slice(0, 2).map((item) => item.dataset.itemId);
                window.FeatureMenu._tempPreferences = new Set(keepIds);
                const target = items.find((item) => keepIds.includes(item.dataset.itemId));
                if (target) {
                    window.FeatureMenu.toggleItem(target.dataset.itemId, target);
                }
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const banner = document.getElementById('feature-menu-warning');
                return banner && !banner.classList.contains('hidden');
            }
            """
        )
        await page.click('#feature-menu-modal button[onclick="FeatureMenu.save()"]')
        await page.wait_for_function(
            """
            () => {
                const toast = document.getElementById('toast-container');
                return toast && toast.innerText.includes('Navigation preferences saved');
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const raw = localStorage.getItem('userNavPreferences');
                if (!raw) return false;
                const prefs = JSON.parse(raw);
                return Array.isArray(prefs.enabledItems) && prefs.enabledItems.length === 2;
            }
            """
        )
        await page.evaluate("window.confirm = () => true")
        await page.evaluate("window.FeatureMenu.open()")
        await page.wait_for_selector("#feature-menu-modal:not(.hidden)")
        await page.evaluate("window.FeatureMenu.resetToDefaults()")
        await page.wait_for_function(
            """
            () => {
                const toast = document.getElementById('toast-container');
                return toast && toast.innerText.includes('Navigation reset to defaults');
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const raw = localStorage.getItem('userNavPreferences');
                if (!raw) return false;
                const prefs = JSON.parse(raw);
                return Array.isArray(prefs.enabledItems) && prefs.enabledItems.length > 2;
            }
            """
        )
        await page.evaluate("window.FeatureMenu.open()")
        await page.wait_for_selector("#feature-menu-modal:not(.hidden)")
        await page.wait_for_function(
            """
            () => {
                const raw = localStorage.getItem('userNavPreferences');
                const prefs = raw ? JSON.parse(raw) : null;
                const items = Array.from(document.querySelectorAll('#feature-menu-items .feature-menu-item'));
                if (!prefs || !Array.isArray(prefs.enabledItems) || items.length === 0) return false;
                return items.every((item) => {
                    const enabled = prefs.enabledItems.includes(item.dataset.itemId);
                    return enabled ? !item.classList.contains('disabled') : item.classList.contains('disabled');
                });
            }
            """
        )
        await page.evaluate("window.FeatureMenu.close()")

        await page.evaluate("window.showLegalPage('terms')")
        await page.wait_for_function(
            """
            () => {
                const modal = document.getElementById('legal-modal');
                return modal && !modal.classList.contains('hidden');
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const title = document.getElementById('legal-title')?.textContent || '';
                const content = document.getElementById('legal-content')?.innerText || '';
                return title.trim().length > 0 && content.trim().length > 50;
            }
            """
        )
        await page.evaluate(
            """
            () => {
                window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: 'zh-TW' } }));
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const back = document.getElementById('legal-back-text')?.textContent || '';
                const title = document.getElementById('legal-title')?.textContent || '';
                return back.includes('返回') && title.length > 0;
            }
            """
        )
        await page.evaluate("window.closeLegalModal()")
        await page.wait_for_function(
            """
            () => document.getElementById('legal-modal')?.classList.contains('hidden')
            """
        )
        await page.evaluate("window.openAlertModal('TSM', 'us_stock')")
        await page.wait_for_function(
            """
            () => {
                const modal = document.getElementById('alert-modal');
                const label = document.getElementById('alert-symbol-label')?.textContent || '';
                return modal && !modal.classList.contains('hidden') && label.includes('TSM');
            }
            """
        )
        await page.evaluate(
            """
            () => {
                document.getElementById('alert-target').value = '180';
                document.getElementById('alert-condition').value = 'above';
                document.getElementById('alert-repeat').checked = false;
                return window.submitAlert();
            }
            """
        )
        await page.wait_for_function(
            """
            () => {
                const toast = document.getElementById('toast-container');
                const modal = document.getElementById('alert-modal');
                return toast && toast.innerText.includes('✅') && modal && modal.classList.contains('hidden');
            }
            """
        )
        await page.evaluate("window.deleteUserAlert('alert-1')")
        await page.wait_for_timeout(150)

        chat_context = await browser.new_context(viewport={"width": 390, "height": 844})
        await seed_context(chat_context)
        chat_page = await chat_context.new_page()
        await chat_page.route("**/*", handle_route)

        await chat_page.goto(
            f"http://{HOST}:{PORT}/static/index.html#chat",
            wait_until="domcontentloaded",
        )
        await chat_page.wait_for_function(
            """
            () => {
                const select = document.getElementById('analysis-mode-select');
                const input = document.getElementById('user-input');
                return !!select && !!input && !input.disabled;
            }
            """,
            timeout=60000,
        )
        await chat_page.wait_for_function(
            """
            () => {
                const list = document.getElementById('chat-session-list');
                return list && list.innerText.includes('BTC history') && list.innerText.includes('ETH setup');
            }
            """
        )
        await chat_page.evaluate("window.switchSession('sess-history-1')")
        await chat_page.wait_for_function(
            """
            () => {
                const body = document.getElementById('chat-messages')?.innerText || '';
                return body.includes('Historical BTC session loaded.');
            }
            """
        )
        await chat_page.wait_for_function(
            """
            () => document.querySelector('[data-session-id="sess-history-1"]')?.classList.contains('text-primary')
            """
        )
        await chat_page.evaluate(
            """
            () => {
                const container = document.getElementById('chat-messages');
                container.scrollTop = 0;
                return window.loadMoreHistory();
            }
            """
        )
        await chat_page.wait_for_function(
            """
            () => {
                const body = document.getElementById('chat-messages')?.innerText || '';
                return body.includes('Older BTC history loaded.');
            }
            """
        )
        await chat_page.evaluate(
            """
            () => window.toggleStarSession({ stopPropagation() {} }, 'sess-history-1', true)
            """
        )
        await chat_page.wait_for_function(
            """
            () => {
                const item = document.querySelector('[data-session-id="sess-history-1"]');
                return item && item.querySelector('[data-lucide="star"]');
            }
            """
        )
        await chat_page.evaluate(
            """
            async () => {
                window.showConfirm = async () => true;
                const item = document.querySelector('[data-session-id="sess-history-1"]');
                const btn = item.querySelector('button[title="Delete Chat"]');
                await window.deleteSession({
                    stopPropagation() {},
                    currentTarget: btn,
                    target: btn,
                }, 'sess-history-1');
            }
            """
        )
        await chat_page.wait_for_function(
            """
            () => !document.querySelector('[data-session-id="sess-history-1"]')
            """
        )
        await chat_page.select_option("#analysis-mode-select", "verified")
        await chat_page.fill("#user-input", "Smoke verify TSM")
        await chat_page.click("#send-btn")
        await chat_page.wait_for_function(
            """
            () => {
                const body = document.body.innerText || '';
                return body.includes('Smoke analysis complete.') && body.includes('price_lookup');
            }
            """
        )

        messages_context = await browser.new_context(
            viewport={"width": 390, "height": 844}
        )
        await seed_context(messages_context)
        messages_page = await messages_context.new_page()
        await messages_page.route("**/*", handle_route)

        await messages_page.goto(
            f"http://{HOST}:{PORT}/static/forum/messages.html?with=friend-001&source=friends",
            wait_until="domcontentloaded",
        )
        await messages_page.wait_for_function(
            """
            () => {
                const chatSection = document.getElementById('chat-section');
                const input = document.getElementById('message-input');
                return !!chatSection && !!input && chatSection.classList.contains('flex') && !input.closest('#message-input-container').classList.contains('hidden');
            }
            """
        )
        await messages_page.fill("#message-input", "Smoke test message")
        await messages_page.click("#send-btn")
        await messages_page.wait_for_function(
            """
            () => (document.getElementById('messages-container')?.innerText || '').includes('Smoke test message')
            """
        )
        await messages_page.evaluate("window.MessagesPage.backToList()")
        await messages_page.wait_for_function(
            """
            () => {
                const sidebar = document.getElementById('conversation-sidebar');
                const chatSection = document.getElementById('chat-section');
                return sidebar && !sidebar.classList.contains('hidden') && chatSection && chatSection.classList.contains('hidden');
            }
            """
        )
        await messages_page.evaluate("window.MessagesPage.toggleSearch()")
        await messages_page.wait_for_function(
            """
            () => {
                const panel = document.getElementById('search-panel');
                return panel && !panel.classList.contains('hidden');
            }
            """
        )
        await messages_page.fill("#search-input", "smoke")
        await messages_page.wait_for_function(
            """
            () => (document.getElementById('search-results')?.innerText || '').includes('Smoke search result')
            """
        )
        await messages_page.evaluate("window.MessagesPage.toggleSearch()")
        await messages_page.evaluate("window.confirm = () => true")
        await messages_page.evaluate(
            """
            async () => {
                const container = document.getElementById('messages-container');
                const wrapper = document.createElement('div');
                wrapper.id = 'msg-2';
                wrapper.className = 'flex justify-end mb-4 group';
                wrapper.innerHTML = '<div class="text-xs text-textMuted">12:05</div>';
                container.appendChild(wrapper);
                const btn = document.createElement('button');
                await window.MessagesPage.recallMessage(2, btn);
            }
            """
        )
        await messages_page.wait_for_function(
            """
            () => (document.getElementById('msg-2')?.innerText || '').includes('你已收回訊息')
            """
        )

        assert analyze_requests, "expected main chat smoke test to hit /api/analyze"
        assert analyze_requests[0]["analysis_mode"] == "verified"
        assert "alert-1" in deleted_alert_ids
        assert sent_messages, "expected forum messages smoke test to send a message"
        assert sent_messages[0]["content"] == "Smoke test message"

        await chat_context.close()
        await messages_context.close()
        await context.close()
        await browser.close()


if __name__ == "__main__":
    with run_static_server():
        asyncio.run(run_frontend_interaction_smoke_test())
