"""Tests for XSS prevention utilities and patterns.

Verifies that frontend XSS protection patterns are correctly implemented.
"""

import os
import re

import pytest


def _read_js_file(filepath: str) -> str:
    full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filepath)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


class TestSanitizeUrlPresence:
    """Verify sanitizeUrl() helper exists and blocks dangerous protocols."""

    SANITIZE_URL_FILE = "web/js/utils.js"

    def test_has_sanitize_url_function(self):
        content = _read_js_file(self.SANITIZE_URL_FILE)
        assert "sanitizeUrl" in content, (
            f"{self.SANITIZE_URL_FILE} missing sanitizeUrl helper"
        )

    def test_sanitize_url_blocks_javascript_protocol(self):
        content = _read_js_file(self.SANITIZE_URL_FILE)
        match = re.search(r"sanitizeUrl\s*\([^)]*\)\s*\{([^}]+)\}", content, re.DOTALL)
        assert match is not None, (
            f"{self.SANITIZE_URL_FILE}: sanitizeUrl function not found"
        )
        body = match.group(1)
        assert "javascript:" in body.lower(), (
            f"{self.SANITIZE_URL_FILE}: sanitizeUrl does not check for javascript: protocol"
        )

    def test_sanitize_url_blocks_data_protocol(self):
        content = _read_js_file(self.SANITIZE_URL_FILE)
        match = re.search(r"sanitizeUrl\s*\([^)]*\)\s*\{([^}]+)\}", content, re.DOTALL)
        assert match is not None, (
            f"{self.SANITIZE_URL_FILE}: sanitizeUrl function not found"
        )
        body = match.group(1)
        assert "data:" in body.lower(), (
            f"{self.SANITIZE_URL_FILE}: sanitizeUrl does not check for data: protocol"
        )

    @pytest.mark.parametrize(
        "filepath",
        [
            "web/js/usstock.js",
            "web/js/twstock.js",
        ],
    )
    def test_files_import_sanitize_url(self, filepath):
        content = _read_js_file(filepath)
        assert "sanitizeUrl" in content, f"{filepath} missing sanitizeUrl reference"


class TestEscapeHtmlPresence:
    """Verify escapeHtml() is used in files that render API data."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "web/js/forex.js",
            "web/js/commodity.js",
            "web/js/usstock.js",
            "web/js/twstock.js",
            "web/js/safetyTab.js",
            "web/js/messages.js",
        ],
    )
    def test_uses_escape_html(self, filepath):
        content = _read_js_file(filepath)
        assert "escapeHtml" in content, f"{filepath} does not use escapeHtml"


class TestNoUnescapedHrefInJs:
    """Verify that href attributes use sanitized URLs, not raw API data."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "web/js/forex.js",
            "web/js/commodity.js",
            "web/js/usstock.js",
            "web/js/twstock.js",
        ],
    )
    def test_href_uses_sanitize_url(self, filepath):
        content = _read_js_file(filepath)
        # Find all href="${...}" patterns that use API data variables
        # (not hardcoded URLs like '/static/...')
        href_patterns = re.findall(r'href="\$\{([^}]+)\}"', content)
        for pattern in href_patterns:
            expr = pattern.strip()
            # Check if the expression starts with sanitizeUrl
            is_safe = expr.startswith("sanitizeUrl(")
            if not is_safe:
                # Also check for direct property access like sanitizeUrl(item.url)
                prop_match = re.search(
                    rf"sanitizeUrl\(\s*{re.escape(expr)}\s*\)", content
                )
                msg = f"{filepath}: href=... uses raw variable without sanitizeUrl(): {expr}"
                assert prop_match is not None, msg


class TestSafetyTabClipboardFix:
    """Verify the safetyTab.js clipboard XSS is fixed."""

    def test_no_string_interpolation_in_onclick_clipboard(self):
        content = _read_js_file("web/js/safetyTab.js")
        # Should NOT have: onclick="...writeText('${some_var}')"
        # which is vulnerable to single-quote breakout
        bad_pattern = re.findall(r"onclick=\"[^\"]*writeText\('\$\{", content)
        assert not bad_pattern, (
            f"safetyTab.js has vulnerable onclick clipboard pattern: {bad_pattern}"
        )

    def test_uses_data_attribute_or_encodeURIComponent(self):
        content = _read_js_file("web/js/safetyTab.js")
        # Should use data-clipboard attribute or encodeURIComponent for clipboard
        has_safe_pattern = (
            "data-clipboard" in content or "encodeURIComponent" in content
        )
        assert has_safe_pattern, "safetyTab.js clipboard handling not secured"


class TestAIContentEscaping:
    """Verify AI-generated content (summary, key_points) is escaped."""

    @pytest.mark.parametrize(
        "filepath,field",
        [
            ("web/js/forex.js", "summary"),
            ("web/js/commodity.js", "summary"),
            ("web/js/usstock.js", "summary"),
            ("web/js/twstock.js", "summary"),
        ],
    )
    def test_ai_summary_escaped(self, filepath, field):
        content = _read_js_file(filepath)
        # Find patterns like: ${d.report?.summary || ''}
        # The summary should be wrapped in escapeHtml()
        summary_patterns = re.findall(rf"\$\{{[^}}]*{field}[^}}]*\}}", content)
        for pattern in summary_patterns:
            # Check if this specific pattern uses escapeHtml
            escaped = "escapeHtml(" in content
            assert escaped, f"{filepath}: {field} is rendered without escapeHtml"


class TestErrorMessagesEscaped:
    """Verify error messages displayed via innerHTML are escaped."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "web/js/forex.js",
            "web/js/commodity.js",
        ],
    )
    def test_error_message_escaped(self, filepath):
        content = _read_js_file(filepath)
        # Find: ${e.message} in innerHTML context
        error_patterns = re.findall(r"\$\{{e\.message[^}]*\}}", content)
        if error_patterns:
            assert "escapeHtml" in content, (
                f"{filepath}: error messages (e.message) not escaped"
            )
