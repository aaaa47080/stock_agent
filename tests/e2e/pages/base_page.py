"""Base page object with shared helpers for all E2E pages."""

from __future__ import annotations

from typing import Optional

from playwright.async_api import Page


class BasePage:
    """Common operations shared across all page objects."""

    # ------------------------------------------------------------------
    # Selectors
    # ------------------------------------------------------------------
    SIDEBAR = "#chat-sidebar"
    SIDEBAR_BACKDROP = "#sidebar-backdrop"
    TOAST_CONTAINER = "#toast-container"
    DRAGGABLE_NAV = "#draggable-nav"

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    async def goto(self, path: str = "", fragment: str = "") -> None:
        """Navigate to a page path and optional hash fragment."""
        url = f"{self.base_url}{path}"
        if fragment:
            url += f"#{fragment}"
        await self.page.goto(url, wait_until="domcontentloaded", timeout=15_000)

    async def wait_for_timeout(self, ms: int) -> None:
        """Wait for a fixed duration (use sparingly)."""
        await self.page.wait_for_timeout(ms)

    # ------------------------------------------------------------------
    # Generic element interactions
    # ------------------------------------------------------------------
    async def click(self, selector: str) -> None:
        """Click an element matching *selector*."""
        await self.page.click(selector)

    async def fill(self, selector: str, value: str) -> None:
        """Fill an input element with *value*."""
        await self.page.fill(selector, value)

    async def select_option(self, selector: str, value: str) -> None:
        """Select an option in a <select> element."""
        await self.page.select_option(selector, value)

    async def is_visible(self, selector: str) -> bool:
        """Return whether the matched element is visible."""
        return await self.page.is_visible(selector)

    async def is_hidden(self, selector: str) -> bool:
        """Return whether the matched element is hidden."""
        return await self.page.is_hidden(selector)

    async def get_text(self, selector: str) -> str:
        """Return the inner text of the first matched element."""
        el = await self.page.query_selector(selector)
        return await el.inner_text() if el else ""

    async def get_attribute(self, selector: str, attr: str) -> Optional[str]:
        """Return an attribute value or ``None`` if element not found."""
        el = await self.page.query_selector(selector)
        return await el.get_attribute(attr) if el else None

    async def wait_for_selector_visible(
        self, selector: str, timeout: int = 10_000
    ) -> None:
        """Wait until the matched element is visible."""
        await self.page.wait_for_selector(selector, state="visible", timeout=timeout)

    async def wait_for_selector_hidden(
        self, selector: str, timeout: int = 10_000
    ) -> None:
        """Wait until the matched element is hidden."""
        await self.page.wait_for_selector(selector, state="hidden", timeout=timeout)

    async def wait_for_text(
        self, selector: str, text: str, timeout: int = 10_000
    ) -> None:
        """Wait until the element's inner text contains *text*."""
        await self.page.wait_for_function(
            """(sel, txt) => {
                const el = document.querySelector(sel);
                return el ? el.innerText.includes(txt) : false;
            }""",
            arg=selector,
            arg1=text,
            timeout=timeout,
        )

    async def evaluate(self, expression: str) -> None:
        """Execute raw JavaScript on the page."""
        await self.page.evaluate(expression)

    # ------------------------------------------------------------------
    # Toast / notification helpers
    # ------------------------------------------------------------------
    async def has_toast_with_text(self, text: str, timeout: int = 5_000) -> bool:
        """Return True if a toast containing *text* appears within *timeout*."""
        try:
            await self.wait_for_text(self.TOAST_CONTAINER, text, timeout=timeout)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sidebar helpers
    # ------------------------------------------------------------------
    async def is_sidebar_visible(self) -> bool:
        """Check whether the chat sidebar is displayed."""
        sidebar = await self.page.query_selector(self.SIDEBAR)
        if not sidebar:
            return False
        display = await sidebar.evaluate("el => getComputedStyle(el).display")
        return display != "none"

    async def toggle_sidebar(self) -> None:
        """Open or close the mobile sidebar."""
        await self.click("#chat-sidebar button[aria-label='關閉側邊欄']")

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------
    async def switch_tab(self, tab_name: str) -> None:
        """Switch to a SPA tab via ``switchTab()`` JS function."""
        await self.evaluate(f"window.switchTab('{tab_name}')")

    async def is_tab_visible(self, tab_id: str) -> bool:
        """Return True if the tab element is visible (not hidden)."""
        el = await self.page.query_selector(f"#{tab_id}")
        if not el:
            return False
        return not await el.evaluate("el => el.classList.contains('hidden')")
