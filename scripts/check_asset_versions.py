#!/usr/bin/env python3
"""Enforce cache-busting version consistency for shared /static assets.

Checks that each versioned static asset uses the same ?v= value across
all HTML files. No hardcoded expected versions — the source of truth is
whatever version index.html declares.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

# index.html is the canonical version source
CANONICAL_HTML = WEB_DIR / "index.html"

STATIC_REF_RE = re.compile(r"""(?:src|href)=["'](/static/[^"'#?]+)\?v=(\d+)["']""")


def extract_versions(html: Path) -> dict[str, str]:
    text = html.read_text(encoding="utf-8", errors="ignore")
    return {asset: v for asset, v in STATIC_REF_RE.findall(text)}


def iter_html_files(root: Path):
    for path in root.rglob("*.html"):
        if path.name == "index.copy.html" or path == CANONICAL_HTML:
            continue
        yield path


def main() -> int:
    canonical = extract_versions(CANONICAL_HTML)
    errors: list[str] = []
    checked = 0

    for html in iter_html_files(WEB_DIR):
        versions = extract_versions(html)
        for asset, v in versions.items():
            if asset not in canonical:
                continue
            checked += 1
            expected = canonical[asset]
            if v != expected:
                errors.append(
                    f"{html.relative_to(ROOT)}: {asset} expected v={expected}, got v={v}"
                )

    print(f"checked_versioned_refs={checked}")
    if not errors:
        print("version_mismatch=0")
        return 0

    print(f"version_mismatch={len(errors)}")
    for msg in errors:
        print(msg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
