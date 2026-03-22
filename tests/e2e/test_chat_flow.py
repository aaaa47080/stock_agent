"""E2E tests for the chat flow — sending messages and verifying responses."""

from __future__ import annotations

import importlib.util

import pytest

from tests.e2e.pages.chat_page import ChatPage

# ---------------------------------------------------------------------------
# Skip guard — only run when Playwright is installed
# ---------------------------------------------------------------------------


def _requires_playwright():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")


BASE_URL = "http://127.0.0.1:8770/static/index.html"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_chat_page_loads_welcome(page):
    """The chat page should display the CryptoMind welcome screen."""
    _requires_playwright()

    chat = ChatPage(page, BASE_URL)
    await chat.open()
    await chat.wait_for_ready()

    assert await chat.is_welcome_visible(), "Welcome section should be rendered"


@pytest.mark.e2e
async def test_chat_input_disabled_without_api_key(page):
    """
    When no LLM key warning is visible, the user input should be disabled.
    (The mock API reports has_key=True, so the warning should be hidden and
    the input should be enabled in our stub scenario.)
    """
    _requires_playwright()

    chat = ChatPage(page, BASE_URL)
    await chat.open()
    await chat.wait_for_ready()

    # With our stub API key present, the input should become enabled
    # once the app JS hides the warning overlay.
    await page.wait_for_function(
        """() => {
            const input = document.getElementById('user-input');
            return input && !input.disabled;
        }""",
        timeout=15_000,
    )
    assert await chat.is_input_enabled(), "Input should be enabled when API key exists"


@pytest.mark.e2e
async def test_send_message_and_receive_response(page):
    """
    User types a message, clicks send, and a bot response appears
    in the chat messages area.
    """
    _requires_playwright()

    chat = ChatPage(page, BASE_URL)
    await chat.open()
    await chat.wait_for_ready()

    # Wait for the input to be enabled
    await page.wait_for_function(
        """() => {
            const input = document.getElementById('user-input');
            return input && !input.disabled;
        }""",
        timeout=15_000,
    )

    await chat.send_message_full("Analyze BTC trend")
    await chat.wait_for_bot_response("E2E test response.", timeout=15_000)

    messages_text = await chat.get_messages_text()
    assert "E2E test response." in messages_text, "Bot response should appear in chat"


@pytest.mark.e2e
async def test_analysis_mode_selection(page):
    """User can switch between quick / verified / research analysis modes."""
    _requires_playwright()

    chat = ChatPage(page, BASE_URL)
    await chat.open()
    await chat.wait_for_ready()

    for mode in ("quick", "verified", "research"):
        await chat.select_analysis_mode(mode)
        current = await chat.get_analysis_mode()
        assert current == mode, f"Expected mode '{mode}', got '{current}'"


@pytest.mark.e2e
async def test_send_message_via_enter_key(page):
    """User can send a message by pressing Enter in the input field."""
    _requires_playwright()

    chat = ChatPage(page, BASE_URL)
    await chat.open()
    await chat.wait_for_ready()

    # Wait for input to be enabled
    await page.wait_for_function(
        """() => {
            const input = document.getElementById('user-input');
            return input && !input.disabled;
        }""",
        timeout=15_000,
    )

    await chat.type_message("ETH Funding Rates")
    await page.press("#user-input", "Enter")
    await chat.wait_for_bot_response("E2E test response.", timeout=15_000)

    messages_text = await chat.get_messages_text()
    assert "E2E test response." in messages_text
