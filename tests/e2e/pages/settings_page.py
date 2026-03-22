"""Page Object Model for the Settings tab."""

from __future__ import annotations

from playwright.async_api import Page

from tests.e2e.pages.base_page import BasePage


class SettingsPage(BasePage):
    """Encapsulates interactions on the Settings tab."""

    # ------------------------------------------------------------------
    # Selectors
    # ------------------------------------------------------------------
    SETTINGS_TAB = "#settings-tab"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    async def open(self) -> None:
        """Navigate to the settings tab."""
        await self.goto(fragment="settings")

    async def wait_for_ready(self, timeout: int = 15_000) -> None:
        """Wait until the settings tab is rendered and interactive."""
        await self.page.wait_for_function(
            """() => {
                const tab = document.getElementById('settings-tab');
                return tab && !tab.classList.contains('hidden') && tab.innerText.length > 0;
            }""",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    async def get_current_language(self) -> str:
        """Return the language stored in localStorage."""
        lang = await self.page.evaluate(
            "() => localStorage.getItem('selectedLanguage')"
        )
        return lang or "zh-TW"

    async def set_language_via_js(self, lang: str) -> None:
        """Change language by dispatching the i18n event (mirrors UI action)."""
        await self.page.evaluate(
            """(lang) => {
                window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
            }""",
            arg=lang,
        )

    async def click_language_switcher(self) -> None:
        """Click the language switcher button in the nav bar."""
        await self.page.click(".lang-switcher-container button")

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    async def get_html_class(self) -> str:
        """Return the current class on the <html> element (e.g. 'dark' or '')."""
        return await self.page.evaluate("() => document.documentElement.className")

    async def is_dark_theme(self) -> bool:
        """Return True when the dark theme class is present on <html>."""
        cls = await self.get_html_class()
        return "dark" in cls

    # ------------------------------------------------------------------
    # API Key configuration
    # ------------------------------------------------------------------
    async def is_api_key_modal_open(self) -> bool:
        """Return True when the API key modal is visible."""
        return await self.is_visible("#apikey-modal")

    async def open_api_key_modal(self) -> None:
        """Open the API key modal via JS."""
        await self.page.evaluate("window.openApiKeyModal()")

    async def close_api_key_modal(self) -> None:
        """Close the API key modal."""
        await self.page.evaluate("window.closeApiKeyModal()")

    # ------------------------------------------------------------------
    # General settings content
    # ------------------------------------------------------------------
    async def get_settings_content_text(self) -> str:
        """Return the inner text of the settings tab."""
        return await self.get_text(self.SETTINGS_TAB)

    async def has_section(self, text: str) -> bool:
        """Return True if a settings section containing *text* exists."""
        content = await self.get_settings_content_text()
        return text in content
