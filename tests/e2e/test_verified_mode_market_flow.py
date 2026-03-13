import asyncio
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "pw_test" / "test_verified_mode_market_flow.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("pw_verified_mode_market_flow", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load E2E script: {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.e2e
def test_verified_mode_market_flow():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")

    module = _load_script_module()

    with module.run_static_server():
        asyncio.run(module.run_verified_mode_market_flow_test())


@pytest.mark.e2e
def test_free_mode_guardrail():
    if importlib.util.find_spec("playwright") is None:
        pytest.skip("playwright is not installed")

    module = _load_script_module()

    with module.run_static_server():
        asyncio.run(module.run_free_mode_guardrail_test())
