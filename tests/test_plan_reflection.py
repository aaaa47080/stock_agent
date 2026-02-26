"""Tests for Plan Reflection feature."""
import asyncio
import pytest
from core.config import PLAN_REFLECTION_MAX_RETRIES


def test_plan_reflection_max_retries_exists():
    assert isinstance(PLAN_REFLECTION_MAX_RETRIES, int)
    assert PLAN_REFLECTION_MAX_RETRIES >= 1
