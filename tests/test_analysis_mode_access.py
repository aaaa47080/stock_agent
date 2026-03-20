import os

os.environ["REDIS_URL"] = "memory://"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.routers.analysis import router as analysis_router
from core.agents.analysis_policy import AnalysisPolicyResolver


def test_analysis_policy_returns_tier_mode_access():
    resolver = AnalysisPolicyResolver()

    free_policy = resolver.get_mode_access_policy("free")
    premium_policy = resolver.get_mode_access_policy("premium")
    legacy_policy = resolver.get_mode_access_policy("pro")

    assert free_policy.allowed_modes == ("quick",)
    assert free_policy.default_mode == "quick"
    assert premium_policy.allowed_modes == ("quick", "verified", "research")
    assert premium_policy.default_mode == "verified"
    assert legacy_policy.allowed_modes == ("quick", "verified", "research")


def test_analysis_policy_normalizes_disallowed_mode_to_default():
    resolver = AnalysisPolicyResolver()

    assert resolver.ensure_allowed_mode("free", "verified") == "quick"
    assert resolver.ensure_allowed_mode("free", "research") == "quick"
    assert resolver.ensure_allowed_mode("premium", "verified") == "verified"
    assert resolver.ensure_allowed_mode("premium", "research") == "research"


def test_analyze_modes_endpoint_returns_allowed_modes():
    app = FastAPI()
    app.include_router(analysis_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-1",
        "membership_tier": "premium",
    }

    with TestClient(app) as client:
        response = client.get("/api/analyze/modes")

    assert response.status_code == 200
    assert response.json() == {
        "current_tier": "premium",
        "allowed_modes": ["quick", "verified", "research"],
        "default_mode": "verified",
    }


def test_analyze_modes_endpoint_returns_free_defaults():
    app = FastAPI()
    app.include_router(analysis_router)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-2",
        "membership_tier": "free",
    }

    with TestClient(app) as client:
        response = client.get("/api/analyze/modes")

    assert response.status_code == 200
    assert response.json()["allowed_modes"] == ["quick"]
    assert response.json()["default_mode"] == "quick"
