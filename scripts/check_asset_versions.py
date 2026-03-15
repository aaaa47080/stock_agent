#!/usr/bin/env python3
"""Enforce cache-busting version consistency for shared /static assets."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

# Only enforce versions for high-impact shared assets that are reused across pages.
EXPECTED_VERSIONS = {
    "/static/styles.css": "4",
    "/static/js/pi-auth.js": "4",
    "/static/js/app.js": "54",
    "/static/js/auth.js": "58",
    "/static/js/spa.js": "6",
    "/static/js/filter.js": "49",
    "/static/js/market-screener.js": "2",
    "/static/js/pulse.js": "53",
    "/static/js/premium.js": "40",
    "/static/js/i18n.js": "8",
    "/static/js/apiKeyManager.js": "48",
    "/static/js/nav-config.js": "7",
    "/static/js/global-nav.js": "2",
    "/static/js/components/LanguageSwitcher.js": "3",
    "/static/js/friends.js": "5",
    "/static/js/messages.js": "5",
    "/static/scam-tracker/js/scam-tracker.js": "48",
}

STATIC_REF_RE = re.compile(r"""(?:src|href)=["'](/static/[^"'#?]+)(?:\?([^"']*))?["']""")


def iter_html_files(root: Path):
    for path in root.rglob("*.html"):
        if path.name == "index.copy.html":
            continue
        yield path


def extract_v_param(query: str | None) -> str | None:
    if not query:
        return None
    for item in query.split("&"):
        if item.startswith("v="):
            return item[2:]
    return None


def main() -> int:
    errors: list[tuple[Path, str, str, str | None]] = []
    checked = 0

    for html in iter_html_files(WEB_DIR):
        text = html.read_text(encoding="utf-8", errors="ignore")
        for asset_path, query in STATIC_REF_RE.findall(text):
            expected_v = EXPECTED_VERSIONS.get(asset_path)
            if expected_v is None:
                continue
            checked += 1
            actual_v = extract_v_param(query)
            if actual_v != expected_v:
                errors.append((html.relative_to(ROOT), asset_path, expected_v, actual_v))

    print(f"checked_versioned_refs={checked}")
    if not errors:
        print("version_mismatch=0")
        return 0

    print(f"version_mismatch={len(errors)}")
    for html, asset_path, expected, actual in errors:
        actual_label = actual if actual is not None else "<missing>"
        print(f"{html}: {asset_path} expected v={expected}, got v={actual_label}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
