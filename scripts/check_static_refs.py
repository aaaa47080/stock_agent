#!/usr/bin/env python3
"""Validate that /static/* references in HTML map to real files under web/."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

# Capture local static href/src, ignore query/hash suffix.
STATIC_REF_RE = re.compile(r"""(?:src|href)=["'](/static/[^"'#?]+)(?:\?[^"']*)?["']""")


def iter_html_files(root: Path):
    for path in root.rglob("*.html"):
        # Keep backup artifact out of stability checks.
        if path.name == "index.copy.html":
            continue
        yield path


def main() -> int:
    missing: list[tuple[Path, str]] = []
    checked = 0

    for html in iter_html_files(WEB_DIR):
        text = html.read_text(encoding="utf-8", errors="ignore")
        for static_ref in STATIC_REF_RE.findall(text):
            checked += 1
            rel = static_ref[len("/static/") :]
            target = WEB_DIR / rel
            if not target.exists():
                missing.append((html.relative_to(ROOT), static_ref))

    print(f"checked_refs={checked}")
    if not missing:
        print("missing_refs=0")
        return 0

    print(f"missing_refs={len(missing)}")
    for html, ref in missing:
        print(f"{html}: {ref}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
