"""
Per-user rate limiter for Telegram Bot.

Uses in-memory dict with automatic cleanup of expired timestamps.
No external dependencies — standard library only.
"""

import logging
import time

logger = logging.getLogger(__name__)

# --- Configurable limits ---
MINUTE_WINDOW = 60  # seconds
MAX_PER_MINUTE = 10

DAILY_WINDOW = 86400  # seconds (24 hours)
MAX_PER_DAY = 100

# Cleanup threshold: run cleanup when store exceeds this many users
_CLEANUP_THRESHOLD = 500


class TelegramRateLimiter:
    """In-memory per-user rate limiter with minute and daily windows."""

    def __init__(self) -> None:
        # {user_id: {"timestamps": [float, ...], "daily_count": int, "daily_reset": float}}
        self._store: dict[int, dict[str, object]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, user_id: int) -> tuple[bool, str]:
        """
        Check whether *user_id* is within rate limits.

        Returns:
            (allowed, reason) — *reason* is empty string when allowed.
        """
        now = time.time()
        bucket = self._get_or_create_bucket(user_id, now)

        # --- Daily limit ---
        if now >= bucket["daily_reset"]:
            # Reset daily counter when the window expires
            bucket["daily_count"] = 0
            bucket["daily_reset"] = now + DAILY_WINDOW

        daily_count: int = bucket["daily_count"]  # type: ignore[assignment]
        if daily_count >= MAX_PER_DAY:
            daily_reset: float = bucket["daily_reset"]  # type: ignore[assignment]
            remaining = int(daily_reset - now)
            minutes, seconds = divmod(remaining, 60)
            return (
                False,
                f"您今天的訊息次數已達上限（{MAX_PER_DAY} 則）。"
                f"請在 {minutes} 分 {seconds} 秒後再試。",
            )

        # --- Per-minute limit ---
        timestamps: list[float] = bucket["timestamps"]  # type: ignore[assignment]
        # Remove timestamps older than the sliding window
        cutoff = now - MINUTE_WINDOW
        bucket["timestamps"] = [t for t in timestamps if t > cutoff]  # type: ignore[assignment]
        timestamps = bucket["timestamps"]  # type: ignore[assignment]

        if len(timestamps) >= MAX_PER_MINUTE:
            oldest = timestamps[0]
            wait = int(oldest - cutoff) + 1
            return (
                False,
                f"您發送訊息太頻繁了（每分鐘上限 {MAX_PER_MINUTE} 則）。"
                f"請在 {wait} 秒後再試。",
            )

        # --- Allowed — record the hit ---
        timestamps.append(now)
        bucket["timestamps"] = timestamps  # type: ignore[assignment]
        bucket["daily_count"] = daily_count + 1  # type: ignore[assignment]

        # Periodic cleanup
        if len(self._store) >= _CLEANUP_THRESHOLD:
            self._cleanup(now)

        return (True, "")

    def get_remaining(self, user_id: int) -> dict[str, int]:
        """Return remaining quotas for display purposes."""
        now = time.time()
        bucket = self._get_or_create_bucket(user_id, now)

        # Refresh daily if expired
        if now >= bucket["daily_reset"]:
            bucket["daily_count"] = 0
            bucket["daily_reset"] = now + DAILY_WINDOW

        timestamps: list[float] = bucket["timestamps"]  # type: ignore[assignment]
        cutoff = now - MINUTE_WINDOW
        recent = [t for t in timestamps if t > cutoff]

        daily_count: int = bucket["daily_count"]  # type: ignore[assignment]
        return {
            "minute_remaining": max(0, MAX_PER_MINUTE - len(recent)),
            "day_remaining": max(0, MAX_PER_DAY - daily_count),
        }

    def reset_user(self, user_id: int) -> None:
        """Remove all rate-limit data for a user (admin use)."""
        self._store.pop(user_id, None)
        logger.info("Rate limit reset for user %s", user_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_bucket(self, user_id: int, now: float) -> dict[str, object]:
        if user_id not in self._store:
            self._store[user_id] = {
                "timestamps": [],
                "daily_count": 0,
                "daily_reset": now + DAILY_WINDOW,
            }
        return self._store[user_id]

    def _cleanup(self, now: float) -> None:
        """Remove buckets whose daily window has expired."""
        expired = [
            uid
            for uid, bucket in self._store.items()
            if now >= bucket["daily_reset"]  # type: ignore[operator]
        ]
        for uid in expired:
            del self._store[uid]
        if expired:
            logger.debug(
                "Rate limiter cleanup: removed %d expired buckets", len(expired)
            )
