"""Page Object Model for E2E tests."""

from tests.e2e.pages.base_page import BasePage
from tests.e2e.pages.chat_page import ChatPage
from tests.e2e.pages.settings_page import SettingsPage

__all__ = ["BasePage", "ChatPage", "SettingsPage"]
