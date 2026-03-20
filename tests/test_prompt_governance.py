import re
from pathlib import Path

PROMPT_SOURCE_PATHS = [
    *Path("core/agents/prompts").glob("*.yaml"),
    *Path("core/agents/descriptions").glob("*.md"),
]

MODEL_FACING_RUNTIME_PATHS = [
    Path("core/agents/tools.py"),
    Path("core/tools/tw_symbol_resolver.py"),
    Path("core/tools/tw_stock_tools.py"),
    Path("core/tools/us_stock_tools.py"),
    Path("core/tools/us_data_provider.py"),
    Path("core/tools/schemas.py"),
    Path("core/tools/universal_resolver.py"),
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


def test_bootstrap_agent_metadata_does_not_hardcode_specific_equities():
    bootstrap = Path("core/agents/bootstrap.py").read_text(encoding="utf-8")
    banned_equity_examples = [
        r"\bAAPL\b",
        r"\bTSM\b",
        r"\bNVDA\b",
        r"\bMSFT\b",
        r"\bGOOGL\b",
        r"\bAMZN\b",
        r"\bMETA\b",
        r"\bSMCI\b",
        r"\bAMD\b",
        r"台積電",
        r"鴻海",
        r"聯發科",
    ]
    violations = [
        pattern for pattern in banned_equity_examples if re.search(pattern, bootstrap)
    ]
    assert not violations, (
        "Found hardcoded equity examples in bootstrap metadata: "
        + ", ".join(violations)
    )


def test_model_facing_runtime_sources_do_not_hardcode_specific_equity_examples():
    banned_equity_examples = [
        r"\bAAPL\b",
        r"\bTSLA\b",
        r"\bNVDA\b",
        r"\bMSFT\b",
        r"\bGOOGL\b",
        r"\bAMZN\b",
        r"\bMETA\b",
        r"\bTSM\b",
        r"\b2330\b",
        r"\b2317\b",
        r"\b2454\b",
        r"台積電",
        r"鴻海",
        r"聯發科",
        r"蘋果",
        r"特斯拉",
    ]
    violations = []
    for path in MODEL_FACING_RUNTIME_PATHS:
        content = path.read_text(encoding="utf-8")
        for pattern in banned_equity_examples:
            if re.search(pattern, content):
                violations.append(f"{path}: {pattern}")

    assert not violations, (
        "Found hardcoded equity examples in model-facing runtime sources:\n"
        + "\n".join(violations)
    )
