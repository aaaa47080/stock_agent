import hashlib
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError

from core.orm.repositories import _normalize_membership_tier, user_repo

load_dotenv()
logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


class CurrentUser(TypedDict, total=False):
    user_id: str
    username: str
    pi_uid: str
    is_premium: bool
    membership_tier: str
    created_at: str
    is_active: bool
    role: str


# Configuration
# 🔒 Security: JWT_SECRET_KEY must be set via environment variable
# Generate a secure key: openssl rand -hex 32
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days for refresh tokens
_COOKIE_SECURE = os.getenv("ENVIRONMENT", "development").lower() in (
    "production",
    "prod",
)
_COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
_COOKIE_SAME_SITE = "Lax"

# Security check: require fallback secret unless key rotation is explicitly enabled.
if not SECRET_KEY and os.getenv("USE_KEY_ROTATION", "false").lower() != "true":
    raise ValueError(
        "🚨 SECURITY ERROR: JWT_SECRET_KEY environment variable is required.\n"
        "Generate a strong key using: openssl rand -hex 32\n"
        "Then set it in your .env file: JWT_SECRET_KEY=<your-key>\n"
        "Alternatively, enable key rotation with: USE_KEY_ROTATION=true"
    )
if SECRET_KEY and len(SECRET_KEY) < 32:
    raise ValueError(
        "🚨 SECURITY ERROR: JWT_SECRET_KEY must be at least 32 characters long.\n"
        f"Current length: {len(SECRET_KEY)} characters.\n"
        "Generate a stronger key using: openssl rand -hex 32"
    )

_key_manager = None


def _use_key_rotation() -> bool:
    """Read rotation switch dynamically so tests/runtime toggles stay consistent."""
    return os.getenv("USE_KEY_ROTATION", "false").lower() == "true"


def _get_key_manager():
    """Lazy-load key manager to avoid module import-time coupling."""
    global _key_manager
    if _key_manager is None:
        from core.key_rotation import get_key_manager

        _key_manager = get_key_manager()
    return _key_manager


# === Refresh Token Blacklist (in-memory, DB-backed for persistence) ===
_revoked_tokens: dict[str, datetime] = {}  # token_hash -> expiry
_revoked_tokens_lock = threading.Lock()


def _hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def revoke_token(token: str, expires_at: Optional[datetime] = None) -> None:
    """
    Revoke a refresh token by adding its hash to the blacklist.
    Thread-safe for concurrent access.
    """
    token_hash = _hash_token(token)
    with _revoked_tokens_lock:
        _revoked_tokens[token_hash] = expires_at or (
            datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
    logger.info(f"Token revoked: {token_hash[:16]}...")


def is_token_revoked(token: str) -> bool:
    """
    Check if a token has been revoked.
    Returns True if revoked, False otherwise.
    Also auto-cleans expired entries.
    """
    token_hash = _hash_token(token)
    with _revoked_tokens_lock:
        if token_hash in _revoked_tokens:
            expiry = _revoked_tokens[token_hash]
            if expiry and expiry < datetime.now(timezone.utc):
                # Token has expired, remove from blacklist
                del _revoked_tokens[token_hash]
                return False
            return True
    return False


def cleanup_expired_revoked_tokens() -> int:
    """Remove expired entries from the revoked tokens blacklist. Returns count removed."""
    removed = 0
    now = datetime.now(timezone.utc)
    with _revoked_tokens_lock:
        expired = [h for h, exp in _revoked_tokens.items() if exp and exp < now]
        for h in expired:
            del _revoked_tokens[h]
            removed += 1
    if removed:
        logger.info(f"Cleaned up {removed} expired revoked tokens")
    return removed


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login", auto_error=False)


def _is_expected_user_db_fallback_error(exc: Exception) -> bool:
    if isinstance(exc, ModuleNotFoundError):
        return True

    message = str(exc)
    return "async_generator" in message and "context manager" in message


def set_token_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set httpOnly cookies for JWT tokens."""
    kwargs: dict = {
        "secure": _COOKIE_SECURE,
        "httponly": True,
        "samesite": _COOKIE_SAME_SITE,
        "path": "/",
    }
    if _COOKIE_DOMAIN:
        kwargs["domain"] = _COOKIE_DOMAIN

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **kwargs,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **kwargs,
    )


def clear_token_cookies(response: Response) -> None:
    """Clear JWT cookies on logout."""
    kwargs: dict = {"path": "/"}
    if _COOKIE_DOMAIN:
        kwargs["domain"] = _COOKIE_DOMAIN
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **kwargs)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, **kwargs)


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract access token from httpOnly cookie, falling back to Bearer header."""
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token.

    Stage 3 Security: Uses key rotation manager when enabled.
    New tokens are signed with the current primary key.
    """
    to_encode = data.copy()
    to_encode["type"] = "access"
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    # Stage 3: Use key rotation if enabled
    if _use_key_rotation():
        key_manager = _get_key_manager()
        key = key_manager.get_current_key()
        # Include key ID in token for tracking
        to_encode["_kid"] = key_manager.get_primary_key_id()
        encoded_jwt = jwt.encode(to_encode, key, algorithm=ALGORITHM)
    else:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a new JWT refresh token with longer expiration.
    Refresh tokens are used to obtain new access tokens without re-authentication.
    """
    to_encode = data.copy()
    to_encode["type"] = "refresh"
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})

    if _use_key_rotation():
        key_manager = _get_key_manager()
        key = key_manager.get_current_key()
        to_encode["_kid"] = key_manager.get_primary_key_id()
        encoded_jwt = jwt.encode(to_encode, key, algorithm=ALGORITHM)
    else:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify the token and return the payload.
    Used for WebSocket authentication or where Depends() cannot be used.

    Stage 3 Security: Supports key rotation when enabled.
    Tries all active keys to validate tokens signed with old keys.
    """
    if _use_key_rotation():
        key_manager = _get_key_manager()
        payload = key_manager.verify_token_with_any_key(token, algorithms=[ALGORITHM])
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return payload
    else:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )


async def get_current_user_id(
    request: Request, token: str = Depends(oauth2_scheme)
) -> str:
    """
    Validate the token and return the user_id.
    Reads from httpOnly cookie first, falls back to Authorization header.

    Stage 3 Security: Supports key rotation when enabled.
    """
    resolved_token = token or get_token_from_cookie(request) or ""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not resolved_token:
        raise credentials_exception

    try:
        if _use_key_rotation():
            key_manager = _get_key_manager()
            payload = key_manager.verify_token_with_any_key(
                resolved_token, algorithms=[ALGORITHM]
            )
            if payload is None:
                raise credentials_exception
        else:
            payload = jwt.decode(resolved_token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except (InvalidTokenError, HTTPException):
        raise credentials_exception


async def get_current_user(
    request: Request, token: str = Depends(oauth2_scheme)
) -> CurrentUser:
    """
    Validate token and return full user dict.
    Reads from httpOnly cookie first, falls back to Authorization header.
    In TEST_MODE, automatically return test user without requiring valid token.
    """
    from core.config import TEST_MODE, TEST_USER

    # 安全檢查：禁止在生產環境啟用 TEST_MODE
    if TEST_MODE:
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ["production", "prod"]:
            raise ValueError(
                "🚨 SECURITY ALERT: TEST_MODE must not be enabled in production environment"
            )

    resolved_token = token or get_token_from_cookie(request) or ""
    user_id = None

    # If using regular authentication (not skipped via TEST_MODE without token)
    if resolved_token:
        if TEST_MODE and resolved_token.startswith("test-user-"):
            _allowed = {
                u.strip()
                for u in os.getenv("ALLOWED_TEST_USERS", "test-user-001").split(",")
                if u.strip()
            }
            if resolved_token in _allowed:
                user_id = resolved_token
            # Use mock user logic below
        else:
            try:
                # Normal mode: Validate JWT token
                payload: dict
                if _use_key_rotation():
                    key_manager = _get_key_manager()
                    payload = key_manager.verify_token_with_any_key(
                        resolved_token, algorithms=[ALGORITHM]
                    )
                    if payload is None:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials",
                        )
                else:
                    payload = jwt.decode(
                        resolved_token, SECRET_KEY, algorithms=[ALGORITHM]
                    )
                user_id = payload.get("sub")
                if not user_id:
                    if not TEST_MODE:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials",
                        )
            except ExpiredSignatureError:
                # Token expired - in TEST_MODE, allow expired tokens to fall through to test user
                if not TEST_MODE:
                    raise
                user_id = None
            except (InvalidTokenError, HTTPException):
                # Token is invalid (bad signature, malformed, etc.) - reject even in TEST_MODE
                if not TEST_MODE:
                    raise
                # Reject invalid tokens in TEST_MODE as well - only expired tokens are allowed
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                )

    # Fetch from DB for BOTH normal mode and test mode (if user_id is set)
    if user_id:
        try:
            user = await user_repo.get_by_id(user_id)

            if user:
                if not user.get("is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account has been suspended",
                    )
                return user
        except HTTPException:
            raise
        except Exception as exc:
            # DB fetch fails or user doesn't exist
            if _is_expected_user_db_fallback_error(exc):
                logger.warning(
                    "Failed to load current user from DB; falling back by mode: %s",
                    exc,
                )
            else:
                logger.warning(
                    "Failed to load current user from DB; falling back by mode",
                    exc_info=True,
                )

    # If we are in TEST_MODE, return mock test user when DB fetch fails or no token
    if TEST_MODE:
        if not user_id:
            user_id = TEST_USER.get("uid", "test-user-001")

        # 🔧 Test mode: Support membership tier switching for testing
        # IMPORTANT: Use os.environ.get() instead of os.getenv() to get current value
        # os.getenv() caches at process startup, but os.environ.get() reads current value
        test_tier = _normalize_membership_tier(
            os.environ.get("TEST_USER_TIER", "premium")
        )

        return {
            "user_id": user_id,
            "username": f"TestUser_{user_id[-3:]}",
            "pi_uid": user_id,
            "is_premium": test_tier == "premium",
            "membership_tier": test_tier,  # ✅ Add membership_tier for testing
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # If not in TEST_MODE and no valid user found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_current_user(
    request: Request, token: str = Depends(oauth2_scheme)
) -> Optional[CurrentUser]:
    """
    Best-effort user resolution for endpoints that may be viewed anonymously.

    Returns the authenticated user when credentials are valid, otherwise None.
    """
    resolved_token = token or get_token_from_cookie(request)
    if not isinstance(resolved_token, str) or not resolved_token:
        return None

    try:
        return await get_current_user(request, resolved_token)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Require admin role. Use as dependency on admin-only endpoints.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
        )
    return current_user
