"""
Tests for telegram_bot.rate_limiter module.
"""

import time

import pytest

from telegram_bot.rate_limiter import (
    MAX_PER_DAY,
    MAX_PER_MINUTE,
    MINUTE_WINDOW,
    TelegramRateLimiter,
)


@pytest.fixture
def limiter() -> TelegramRateLimiter:
    """Provide a fresh limiter per test."""
    return TelegramRateLimiter()


class TestTelegramRateLimiter:
    """Unit tests for TelegramRateLimiter."""

    def test_allows_first_message(self, limiter: TelegramRateLimiter) -> None:
        allowed, reason = limiter.is_allowed(12345)
        assert allowed is True
        assert reason == ""

    def test_minute_limit_blocks_after_threshold(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 1001
        # Send MAX_PER_MINUTE messages — all should succeed
        for i in range(MAX_PER_MINUTE):
            allowed, reason = limiter.is_allowed(user_id)
            assert allowed is True, f"Message {i + 1} should be allowed"

        # Next message should be blocked
        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert "每分鐘" in reason
        assert str(MAX_PER_MINUTE) in reason

    def test_minute_limit_resets_after_window(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 1002
        # Fill up minute quota
        for _ in range(MAX_PER_MINUTE):
            limiter.is_allowed(user_id)

        # Blocked
        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is False

        # Fast-forward past the minute window
        limiter._store[user_id]["timestamps"] = [  # type: ignore[index]
            t - MINUTE_WINDOW - 1
            for t in limiter._store[user_id]["timestamps"]  # type: ignore[index]
        ]

        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is True

    def test_daily_limit_blocks_after_threshold(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 2001
        # Send MAX_PER_DAY messages, clearing minute timestamps each batch
        # to avoid per-minute limit interfering with the daily limit test
        for i in range(MAX_PER_DAY):
            if i > 0 and i % MAX_PER_MINUTE == 0:
                bucket = limiter._store[user_id]
                bucket["timestamps"] = []  # type: ignore[index]
            allowed, reason = limiter.is_allowed(user_id)
            assert allowed is True, f"Message {i + 1} should be allowed"

        # Next message should be blocked by daily limit
        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert "今天" in reason
        assert str(MAX_PER_DAY) in reason

    def test_daily_limit_message_includes_cooldown(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 2002
        # Fill daily quota, clearing minute timestamps each batch
        for i in range(MAX_PER_DAY):
            if i > 0 and i % MAX_PER_MINUTE == 0:
                bucket = limiter._store[user_id]
                bucket["timestamps"] = []  # type: ignore[index]
            limiter.is_allowed(user_id)

        # Check the blocked message contains time info
        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert "分" in reason  # should contain minutes/seconds breakdown

    def test_daily_limit_resets_after_window(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 2003
        for i in range(MAX_PER_DAY):
            if i > 0 and i % MAX_PER_MINUTE == 0:
                bucket = limiter._store[user_id]
                bucket["timestamps"] = []  # type: ignore[index]
            limiter.is_allowed(user_id)

        # Blocked
        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is False

        # Force daily reset by moving the window
        limiter._store[user_id]["daily_reset"] = time.time() - 1  # type: ignore[index]
        # Also clear minute timestamps so they don't block
        limiter._store[user_id]["timestamps"] = []  # type: ignore[index]
        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is True

    def test_independent_users(self, limiter: TelegramRateLimiter) -> None:
        user_a = 3001
        user_b = 3002

        # Fill user A's minute quota
        for _ in range(MAX_PER_MINUTE):
            limiter.is_allowed(user_a)

        # User A should be blocked
        allowed_a, _ = limiter.is_allowed(user_a)
        assert allowed_a is False

        # User B should still be allowed
        allowed_b, _ = limiter.is_allowed(user_b)
        assert allowed_b is True

    def test_get_remaining(self, limiter: TelegramRateLimiter) -> None:
        user_id = 4001
        # Send 3 messages
        for _ in range(3):
            limiter.is_allowed(user_id)

        remaining = limiter.get_remaining(user_id)
        assert remaining["minute_remaining"] == MAX_PER_MINUTE - 3
        assert remaining["day_remaining"] == MAX_PER_DAY - 3

    def test_reset_user(self, limiter: TelegramRateLimiter) -> None:
        user_id = 5001
        for _ in range(MAX_PER_MINUTE):
            limiter.is_allowed(user_id)

        # Blocked
        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is False

        # Reset
        limiter.reset_user(user_id)

        # Should be allowed again
        allowed, _ = limiter.is_allowed(user_id)
        assert allowed is True

    def test_cleanup_removes_expired_buckets(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_a = 6001
        user_b = 6002
        limiter.is_allowed(user_a)
        limiter.is_allowed(user_b)

        assert len(limiter._store) == 2

        # Expire both buckets
        for bucket in limiter._store.values():
            bucket["daily_reset"] = time.time() - 1

        limiter._cleanup(time.time())
        assert len(limiter._store) == 0

    def test_blocked_reason_mentions_wait_time(
        self, limiter: TelegramRateLimiter
    ) -> None:
        user_id = 7001
        for _ in range(MAX_PER_MINUTE):
            limiter.is_allowed(user_id)

        allowed, reason = limiter.is_allowed(user_id)
        assert allowed is False
        assert "秒後再試" in reason
