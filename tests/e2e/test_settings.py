"""E2E tests for Settings tab — language switching, theme, API key modal."""

from __future__ import annotations

import importlib.util

import pytest

from tests.e2e.pages.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------


def _requires_playwright():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")


BASE_URL = "http://127.0.0.1:8770/static/index.html"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_settings_tab_opens(page):
    """Navigating to #settings should show the settings tab."""
    _requires_playwright()

    settings = SettingsPage(page, BASE_URL)
    await settings.open()
    await settings.wait_for_ready()

    assert await settings.is_tab_visible("settings-tab"), (
        "Settings tab should be visible"
    )


@pytest.mark.e2e
async def test_language_switch_zh_tw_to_en(page):
    """
    Switching language from zh-TW to en should update visible text
    via the i18n system.
    """
    _requires_playwright()

    settings = SettingsPage(page, BASE_URL)
    await settings.open()
    await settings.wait_for_ready()

    # Ensure we start in Chinese
    assert await settings.get_current_language() in ("zh-TW", None)

    # Switch to English
    await settings.set_language_via_js("en")
    await page.wait_for_timeout(2000)

    # Verify localStorage was updated
    lang = await settings.get_current_language()
    assert lang == "en", f"Expected language 'en', got '{lang}'"


@pytest.mark.e2e
async def test_language_persists_after_reload(page):
    """Language preference should survive a page reload."""
    _requires_playwright()

    settings = SettingsPage(page, BASE_URL)
    await settings.open()
    await settings.wait_for_ready()

    # Set language
    await settings.set_language_via_js("en")
    await page.wait_for_timeout(1000)

    # Reload
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    lang = await settings.get_current_language()
    assert lang == "en", "Language should persist after reload"


@pytest.mark.e2e
async def test_dark_theme_is_default(page):
    """The page should load with the 'dark' class on <html>."""
    _requires_playwright()

    settings = SettingsPage(page, BASE_URL)
    await settings.open()
    await page.wait_for_timeout(2000)

    assert await settings.is_dark_theme(), "Page should load with dark theme by default"


@pytest.mark.e2e
async def test_api_key_modal_open_and_close(page):
    """The API key modal should open and close without errors."""
    _requires_playwright()

    settings = SettingsPage(page, BASE_URL)
    await settings.open()
    await settings.wait_for_ready()

    # Open modal
    await settings.open_api_key_modal()
    await page.wait_for_timeout(500)
    assert await settings.is_api_key_modal_open(), "API key modal should be open"

    # Close modal
    await settings.close_api_key_modal()
    await page.wait_for_timeout(500)
    assert not await settings.is_api_key_modal_open(), "API key modal should be closed"
