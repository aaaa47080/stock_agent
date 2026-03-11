from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
I18N_DIR = WEB / "js" / "i18n"


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    items: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(flatten(value, full_key))
        else:
            items[full_key] = value
    return items


def load_translations(name: str) -> dict[str, str]:
    payload = json.loads((I18N_DIR / name).read_text(encoding="utf-8"))
    return flatten(payload)


def collect_i18n_keys() -> set[str]:
    keys: set[str] = set()
    html_pattern = re.compile(r'data-i18n="([^"]+)"')
    js_pattern = re.compile(r"""I18n\.t\(\s*['"]([^'"]+)['"]""")

    for path in list(WEB.rglob("*.html")) + list((WEB / "js").rglob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        keys.update(html_pattern.findall(text))
        keys.update(js_pattern.findall(text))

    return keys


def test_translation_files_parse_and_match():
    zh = load_translations("zh-TW.json")
    en = load_translations("en.json")
    assert set(zh) == set(en)


def test_all_referenced_i18n_keys_exist():
    zh = load_translations("zh-TW.json")
    en = load_translations("en.json")
    used = collect_i18n_keys()
    assert used - set(zh) == set()
    assert used - set(en) == set()


def test_scam_tracker_pages_load_i18n_assets():
    pages = [
        WEB / "scam-tracker" / "index.html",
        WEB / "scam-tracker" / "detail.html",
        WEB / "scam-tracker" / "submit.html",
    ]
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert "/static/js/i18n.js" in text
        assert "/static/scam-tracker/js/scam-tracker-i18n.js" in text
        assert "lang-toggle-label" in text
