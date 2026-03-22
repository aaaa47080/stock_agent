"""Page Object Model for the Chat tab."""

from __future__ import annotations

from typing import Optional

from playwright.async_api import Page

from tests.e2e.pages.base_page import BasePage


class ChatPage(BasePage):
    """Encapsulates interactions on the Chat (home) tab."""

    # ------------------------------------------------------------------
    # Selectors
    # ------------------------------------------------------------------
    CHAT_TAB = "#chat-tab"
    CHAT_MESSAGES = "#chat-messages"
    USER_INPUT = "#user-input"
    SEND_BTN = "#send-btn"
    ANALYSIS_MODE_SELECT = "#analysis-mode-select"
    NO_LLM_WARNING = "#no-llm-key-warning"
    SESSION_LIST = "#chat-session-list"
    NEW_CHAT_BTN = "button[onclick='createNewChat()']"

    def __init__(self, page: Page, base_url: str) -> None:
        super().__init__(page, base_url)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    async def open(self) -> None:
        """Navigate to the chat tab."""
        await self.goto(fragment="chat")

    async def wait_for_ready(self, timeout: int = 15_000) -> None:
        """Wait until the chat tab is fully loaded and interactive."""
        await self.page.wait_for_function(
            """() => {
                const select = document.getElementById('analysis-mode-select');
                const input = document.getElementById('user-input');
                return !!select && !!input;
            }""",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Chat interactions
    # ------------------------------------------------------------------
    async def is_input_enabled(self) -> bool:
        """Check whether the user input field is enabled (not disabled)."""
        disabled = await self.page.get_attribute(self.USER_INPUT, "disabled")
        return disabled is None

    async def get_input_placeholder(self) -> str:
        """Return the placeholder text of the input field."""
        return await self.get_attribute(self.USER_INPUT, "placeholder") or ""

    async def type_message(self, message: str) -> None:
        """Type a message into the chat input (does not send)."""
        await self.fill(self.USER_INPUT, message)

    async def send_message(self) -> None:
        """Click the send button."""
        await self.click(self.SEND_BTN)

    async def send_message_full(self, message: str) -> None:
        """Type a message and click send."""
        await self.type_message(message)
        await self.send_message()

    async def select_analysis_mode(self, mode: str) -> None:
        """Choose an analysis mode (quick / verified / research)."""
        await self.select_option(self.ANALYSIS_MODE_SELECT, mode)

    async def get_analysis_mode(self) -> Optional[str]:
        """Return the currently selected analysis mode value."""
        return await self.page.input_value(self.ANALYSIS_MODE_SELECT)

    # ------------------------------------------------------------------
    # Message verification
    # ------------------------------------------------------------------
    async def wait_for_bot_response(self, text: str, timeout: int = 15_000) -> None:
        """Wait until the chat messages area contains *text*."""
        await self.wait_for_text(self.CHAT_MESSAGES, text, timeout=timeout)

    async def get_messages_text(self) -> str:
        """Return the full inner text of the messages area."""
        return await self.get_text(self.CHAT_MESSAGES)

    # ------------------------------------------------------------------
    # Warning overlay
    # ------------------------------------------------------------------
    async def is_no_key_warning_visible(self) -> bool:
        """Return True when the 'no LLM key' warning overlay is shown."""
        return await self.is_visible(self.NO_LLM_WARNING)

    # ------------------------------------------------------------------
    # Session history sidebar
    # ------------------------------------------------------------------
    async def get_session_list_text(self) -> str:
        """Return the inner text of the session list in the sidebar."""
        return await self.get_text(self.SESSION_LIST)

    async def has_session(self, title: str) -> bool:
        """Check if a session with the given title appears in the list."""
        text = await self.get_session_list_text()
        return title in text

    async def click_new_chat(self) -> None:
        """Click the 'New Chat' button in the sidebar."""
        await self.click(self.NEW_CHAT_BTN)

    # ------------------------------------------------------------------
    # Quick-ask buttons
    # ------------------------------------------------------------------
    async def click_quick_ask(self, label: str) -> None:
        """Click one of the quick-ask suggestion buttons by visible text."""
        await self.page.click(f"button:has-text('{label}')")

    # ------------------------------------------------------------------
    # Welcome screen
    # ------------------------------------------------------------------
    async def is_welcome_visible(self) -> bool:
        """Return True if the welcome section is rendered."""
        return await self.page.evaluate(
            """() => {
                const h1 = document.querySelector('#chat-messages h1');
                return h1 ? h1.innerText.includes('CryptoMind') : false;
            }"""
        )
