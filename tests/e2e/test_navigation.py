"""E2E tests for sidebar navigation, tab switching, and SPA routing."""

from __future__ import annotations

import importlib.util

import pytest

from tests.e2e.pages.base_page import BasePage

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------


def _requires_playwright():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")


BASE_URL = "http://127.0.0.1:8770/static/index.html"

# Tab IDs that exist in the SPA
SPA_TABS = [
    ("chat", "#chat-tab"),
    ("crypto", "#crypto-tab"),
    ("twstock", "#twstock-tab"),
    ("usstock", "#usstock-tab"),
    ("wallet", "#wallet-tab"),
    ("commodity", "#commodity-tab"),
    ("forex", "#forex-tab"),
    ("settings", "#settings-tab"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_sidebar_visible_on_chat_tab(page):
    """The chat sidebar should be visible when the chat tab is active."""
    _requires_playwright()

    base = BasePage(page, BASE_URL)
    await base.goto(fragment="chat")
    await page.wait_for_timeout(3000)

    assert await base.is_sidebar_visible(), "Sidebar should be visible on chat tab"


@pytest.mark.e2e
async def test_sidebar_hidden_on_market_tabs(page):
    """The chat sidebar should be hidden when a market tab (crypto/twstock/usstock) is active."""
    _requires_playwright()

    base = BasePage(page, BASE_URL)

    for tab_name in ("crypto", "twstock", "usstock"):
        await base.goto(fragment=tab_name)
        await page.wait_for_timeout(2000)
        assert not await base.is_sidebar_visible(), (
            f"Sidebar should be hidden on '{tab_name}' tab"
        )


@pytest.mark.e2e
async def test_sidebar_restored_when_returning_to_chat(page):
    """After navigating away from chat and back, the sidebar should reappear."""
    _requires_playwright()

    base = BasePage(page, BASE_URL)
    await base.goto(fragment="crypto")
    await page.wait_for_timeout(2000)
    assert not await base.is_sidebar_visible()

    await base.goto(fragment="chat")
    await page.wait_for_timeout(2000)
    assert await base.is_sidebar_visible(), "Sidebar should reappear on chat tab"


@pytest.mark.e2e
async def test_switch_tab_via_js_function(page):
    """switchTab('settings') should hide chat tab and show settings tab."""
    _requires_playwright()

    base = BasePage(page, BASE_URL)
    await base.goto(fragment="chat")
    await page.wait_for_timeout(2000)

    # Verify chat tab is visible initially
    assert await base.is_tab_visible("chat-tab"), "Chat tab should be visible"

    # Switch via JS
    await base.switch_tab("settings")
    await page.wait_for_timeout(1500)

    assert not await base.is_tab_visible("chat-tab"), "Chat tab should be hidden"
    assert await base.is_tab_visible("settings-tab"), "Settings tab should be visible"


@pytest.mark.e2e
async def test_all_spa_tabs_exist_in_dom(page):
    """All major SPA tabs should exist as DOM elements."""
    _requires_playwright()

    base = BasePage(page, BASE_URL)
    await base.goto(fragment="chat")
    await page.wait_for_timeout(2000)

    for tab_name, selector in SPA_TABS:
        el = await page.query_selector(selector)
        assert el is not None, f"Tab element '{selector}' should exist in DOM"
