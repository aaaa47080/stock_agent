from pathlib import Path
import re


PROMPT_SOURCE_PATHS = [
    *Path("core/agents/prompts").glob("*.yaml"),
    *Path("core/agents/descriptions").glob("*.md"),
]

# Guardrail: runtime prompt/design sources should express market boundaries,
# not hardcode specific assets.
BANNED_PATTERNS = [
    r"\bAAPL\b",
    r"\bTSM\b",
    r"\bBTC\b",
    r"\bETH\b",
    r"\bSOL\b",
    r"\bPI\b",
    r"\bINTC\b",
    r"\bNVDA\b",
    r"\bSMCI\b",
    r"\bAMD\b",
    r"\bGOOGL\b",
    r"\bMETA\b",
    r"台積電",
    r"聯發科",
    r"鴻海",
    r"蘋果",
    r"特斯拉",
    r"比特幣",
    r"以太坊",
    r"2330",
]


def test_prompt_sources_do_not_hardcode_specific_assets():
    violations = []
    for path in PROMPT_SOURCE_PATHS:
        content = path.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, content):
                violations.append(f"{path}: {pattern}")
    assert not violations, "Found hardcoded asset examples:\n" + "\n".join(violations)


def test_manager_does_not_inline_multiline_prompt_templates():
    manager_py = Path("core/agents/manager.py").read_text(encoding="utf-8")
    assert 'prompt = f"""' not in manager_py
