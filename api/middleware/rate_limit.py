"""
API Rate Limiting Middleware

Implements per-IP and per-user rate limiting to prevent API abuse and DDoS attacks.

Stage 2 Security: Added persistent rate limiting that survives server restarts.
"""
import json
import time
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from typing import Callable, Optional

def get_user_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting
    - Use user_id from JWT if authenticated
    - Fallback to IP address for unauthenticated requests
    """
    # Try to get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        user_id = user.get('user_id', 'unknown')
        return f"user:{user_id}"
    
    # Fallback to IP address for unauthenticated requests
    ip = get_remote_address(request)
    return f"ip:{ip}"


# Initialize rate limiter
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["1000/hour", "100/minute"],  # Global default limits
    storage_uri="memory://",  # Use in-memory storage (or redis:// for distributed systems)
    strategy="fixed-window"  # Fixed window strategy
)


# Custom rate limits for different endpoint types
RATE_LIMITS = {
    # Authentication endpoints (very strict to prevent brute force)
    "auth": "5/minute",

    # Write operations (stricter)
    "write": "30/minute",

    # Payment operations (strict to prevent abuse)
    "payment": "10/minute",

    # Read operations (more lenient)
    "read": "100/minute",

    # Admin operations (moderate)
    "admin": "50/hour",

    # Public endpoints (lenient)
    "public": "200/minute",

    # Community Governance endpoints
    "governance_report": "10/hour",  # Report submission (strict)
    "governance_vote": "30/hour",    # Voting (PRO members only)
    "governance_read": "100/hour",   # Reading governance data
}


def get_rate_limit_for_route(request: Request) -> str:
    """
    Determine appropriate rate limit based on route and method
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limit string (e.g., "30/minute")
    """
    method = request.method.lower()
    path = request.url.path.lower()
    
    # Authentication endpoints
    if any(x in path for x in ['/login', '/pi-sync', '/dev-login']):
        return RATE_LIMITS["auth"]
    
    # Payment endpoints
    if '/payment' in path or '/tip' in path:
        return RATE_LIMITS["payment"]
    
    # Admin endpoints
    if '/admin' in path:
        return RATE_LIMITS["admin"]
    
    # Write operations
    if method in ['post', 'put', 'patch', 'delete']:
        return RATE_LIMITS["write"]
    
    # Public read endpoints (forum, market data)
    if any(x in path for x in ['/forum/posts', '/forum/boards', '/market', '/agents/']):
        return RATE_LIMITS["public"]

    # Community Governance endpoints
    if '/governance' in path:
        if '/reports' in path and method == 'post':
            return RATE_LIMITS["governance_report"]
        elif '/vote' in path and method == 'post':
            return RATE_LIMITS["governance_vote"]
        else:
            return RATE_LIMITS["governance_read"]
    
    # Default read operations
    if method == 'get':
        return RATE_LIMITS["read"]
    
    # Default fallback
    return "100/minute"


# Exception handler for rate limit exceeded
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors
    
    Returns a JSON response with retry information
    """
    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down and try again later.",
            "retry_after": exc.retry_after,
            "limit": str(exc.limit),
        },
        headers={
            "Retry-After": str(exc.retry_after),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
        }
    )


# ============================================================================
# Stage 2 Security: Persistent Rate Limiting
# ============================================================================

class PersistentRateLimiter:
    """
    File-based persistent rate limiter that survives server restarts.

    This provides a fallback for environments without Redis.
    Rate limits are stored in a JSON file and loaded on startup.

    Usage:
        # Initialize
        limiter = PersistentRateLimiter("data/rate_limits.json")

        # Check limit
        if limiter.check_limit("user:123", limit=100, window=3600):
            # Allow request
        else:
            # Rate limit exceeded
    """

    def __init__(self, storage_path: str = "data/rate_limits.json"):
        """
        Initialize the persistent rate limiter.

        Args:
            storage_path: Path to the JSON file for storing rate limit state
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.state: dict = {}
        self._load_state()

    def _load_state(self):
        """Load rate limit state from file."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    self.state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            # If file is corrupted, start fresh
            self.state = {}

    def _save_state(self):
        """Save rate limit state to file."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.state, f)
        except IOError:
            # Fail silently - rate limiting is a protection, not a requirement
            pass

    def check_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> bool:
        """
        Check if a request should be rate limited.

        Args:
            key: Unique identifier (e.g., "user:123" or "ip:192.168.1.1")
            limit: Maximum number of requests allowed
            window: Time window in seconds

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = int(time.time())
        window_start = now - window

        # Initialize key if not exists
        if key not in self.state:
            self.state[key] = []

        # Remove timestamps outside the current window
        self.state[key] = [t for t in self.state[key] if t > window_start]

        # Check if limit exceeded
        if len(self.state[key]) >= limit:
            return False

        # Add current request timestamp
        self.state[key].append(now)
        self._save_state()
        return True

    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """
        Get remaining requests for a key.

        Args:
            key: Unique identifier
            limit: Maximum number of requests
            window: Time window in seconds

        Returns:
            Number of remaining requests
        """
        now = int(time.time())
        window_start = now - window

        if key not in self.state:
            return limit

        # Count requests within window
        recent_count = sum(1 for t in self.state[key] if t > window_start)
        return max(0, limit - recent_count)

    def reset_key(self, key: str):
        """
        Reset rate limit for a specific key.

        Args:
            key: Unique identifier to reset
        """
        if key in self.state:
            del self.state[key]
            self._save_state()

    def cleanup_old_entries(self, older_than_seconds: int = 86400):
        """
        Remove old entries to prevent file growth.

        Args:
            older_than_seconds: Remove entries older than this (default: 24 hours)
        """
        now = int(time.time())
        cutoff = now - older_than_seconds

        keys_to_remove = []
        for key, timestamps in self.state.items():
            # Remove old timestamps
            self.state[key] = [t for t in timestamps if t > cutoff]
            # Mark empty keys for removal
            if not self.state[key]:
                keys_to_remove.append(key)

        # Remove empty keys
        for key in keys_to_remove:
            del self.state[key]

        if keys_to_remove or any(timestamps for timestamps in self.state.values()):
            self._save_state()


# Global persistent rate limiter instance
persistent_limiter: Optional[PersistentRateLimiter] = None

def get_persistent_limiter() -> PersistentRateLimiter:
    """
    Get or create the global persistent rate limiter.

    Returns:
        PersistentRateLimiter instance
    """
    global persistent_limiter
    if persistent_limiter is None:
        persistent_limiter = PersistentRateLimiter()
    return persistent_limiter
