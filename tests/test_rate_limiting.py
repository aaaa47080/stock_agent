"""Tests for per-route rate limiting configuration.

Verifies that sensitive endpoints have @limiter.limit decorators
with appropriate rate limits applied via SlowAPI's internal registry.
"""

import pytest

RATE_LIMITED_ENDPOINTS = {
    "api.routers.user.dev_login": "5 per 1 minute",
    "api.routers.user.sync_pi_user": "5 per 1 minute",
    "api.routers.user.refresh_token": "5 per 1 minute",
    "api.routers.user.refresh_access_token": "10 per 1 minute",
    "api.routers.user.approve_payment": "10 per 1 minute",
    "api.routers.user.complete_payment": "10 per 1 minute",
    "api.routers.user.get_user_api_key_full_endpoint": "10 per 1 minute",
    "api.routers.premium.upgrade_to_premium": "10 per 1 minute",
    "api.routers.forum.posts.create_new_post": "20 per 1 minute",
    "api.routers.forum.comments.add_new_comment": "30 per 1 minute",
    "api.routers.forum.comments.push_post": "30 per 1 minute",
    "api.routers.forum.comments.boo_post": "30 per 1 minute",
    "api.routers.forum.tips.tip_post": "10 per 1 minute",
    "api.routers.messages.send_message_endpoint": "30 per 1 minute",
    "api.routers.messages.send_greeting_endpoint": "5 per 1 minute",
    "api.routers.governance.submit_report": "10 per 1 hour",
    "api.routers.governance.vote_on_pending_report": "30 per 1 hour",
    "api.routers.analysis.analyze_crypto": "10 per 1 minute",
    "api.routers.system.update_user_settings": "10 per 1 minute",
    "api.routers.system.validate_key": "10 per 1 minute",
}


@pytest.fixture(scope="module")
def route_limits():
    # Import router modules for side effects (rate limit registration)
    import api.routers.analysis  # noqa: F401
    import api.routers.forum.comments  # noqa: F401
    import api.routers.forum.posts  # noqa: F401
    import api.routers.forum.tips  # noqa: F401
    import api.routers.governance  # noqa: F401
    import api.routers.messages  # noqa: F401
    import api.routers.premium  # noqa: F401
    import api.routers.system  # noqa: F401
    import api.routers.user  # noqa: F401
    from api.middleware.rate_limit import limiter

    return limiter._route_limits


class TestAuthRateLimits:
    def test_dev_login_5_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.dev_login", [])
        assert len(limits) >= 1
        assert "5 per 1 minute" in [str(r.limit) for r in limits]

    def test_pi_sync_5_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.sync_pi_user", [])
        assert len(limits) >= 1
        assert "5 per 1 minute" in [str(r.limit) for r in limits]

    def test_refresh_token_5_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.refresh_token", [])
        assert len(limits) >= 1
        assert "5 per 1 minute" in [str(r.limit) for r in limits]


class TestPaymentRateLimits:
    def test_premium_upgrade_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.premium.upgrade_to_premium", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]

    def test_payment_approve_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.approve_payment", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]

    def test_payment_complete_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.complete_payment", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]

    def test_tip_post_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.forum.tips.tip_post", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]


class TestApiKeyRateLimits:
    def test_api_key_full_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.user.get_user_api_key_full_endpoint", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]


class TestMessageRateLimits:
    def test_send_message_30_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.messages.send_message_endpoint", [])
        assert len(limits) >= 1
        assert "30 per 1 minute" in [str(r.limit) for r in limits]

    def test_greeting_5_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.messages.send_greeting_endpoint", [])
        assert len(limits) >= 1
        assert "5 per 1 minute" in [str(r.limit) for r in limits]


class TestForumRateLimits:
    def test_create_post_20_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.forum.posts.create_new_post", [])
        assert len(limits) >= 1
        assert "20 per 1 minute" in [str(r.limit) for r in limits]

    def test_add_comment_30_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.forum.comments.add_new_comment", [])
        assert len(limits) >= 1
        assert "30 per 1 minute" in [str(r.limit) for r in limits]

    def test_push_post_30_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.forum.comments.push_post", [])
        assert len(limits) >= 1
        assert "30 per 1 minute" in [str(r.limit) for r in limits]

    def test_boo_post_30_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.forum.comments.boo_post", [])
        assert len(limits) >= 1
        assert "30 per 1 minute" in [str(r.limit) for r in limits]


class TestGovernanceRateLimits:
    def test_report_10_per_hour(self, route_limits):
        limits = route_limits.get("api.routers.governance.submit_report", [])
        assert len(limits) >= 1
        assert "10 per 1 hour" in [str(r.limit) for r in limits]

    def test_vote_30_per_hour(self, route_limits):
        limits = route_limits.get("api.routers.governance.vote_on_pending_report", [])
        assert len(limits) >= 1
        assert "30 per 1 hour" in [str(r.limit) for r in limits]


class TestAnalysisRateLimit:
    def test_analyze_10_per_minute(self, route_limits):
        limits = route_limits.get("api.routers.analysis.analyze_crypto", [])
        assert len(limits) >= 1
        assert "10 per 1 minute" in [str(r.limit) for r in limits]


class TestTotalRateLimitedEndpoints:
    def test_all_expected_endpoints_are_limited(self, route_limits):
        expected = set(RATE_LIMITED_ENDPOINTS.keys())
        actual = set(route_limits.keys())
        missing = expected - actual
        assert not missing, f"Missing rate limits for: {missing}"

    def test_no_unexpected_endpoints(self, route_limits):
        expected = set(RATE_LIMITED_ENDPOINTS.keys())
        actual = set(route_limits.keys())
        extra = actual - expected
        assert not extra, f"Unexpected rate-limited endpoints: {extra}"
