import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from core.orm.repositories import _normalize_membership_tier, user_repo

load_dotenv()
logger = logging.getLogger(__name__)


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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login", auto_error=False)


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


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Validate the token and return the user_id.
    This dependency can be used to protect endpoints.

    Stage 3 Security: Supports key rotation when enabled.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        if _use_key_rotation():
            key_manager = _get_key_manager()
            payload = key_manager.verify_token_with_any_key(
                token, algorithms=[ALGORITHM]
            )
            if payload is None:
                raise credentials_exception
        else:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except (InvalidTokenError, HTTPException):
        raise credentials_exception


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Validate token and return full user dict.
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

    user_id = None

    # If using regular authentication (not skipped via TEST_MODE without token)
    if token:
        if TEST_MODE and token.startswith("test-user-"):
            _allowed = {
                u.strip()
                for u in os.getenv("ALLOWED_TEST_USERS", "test-user-001").split(",")
                if u.strip()
            }
            if token in _allowed:
                user_id = token
            # Use mock user logic below
        else:
            try:
                # Normal mode: Validate JWT token
                user_id = await get_current_user_id(token)
            except HTTPException:
                if not TEST_MODE:
                    raise
                # Fallback to default test user if validation fails in TEST_MODE
                user_id = None

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
        except Exception:
            # DB fetch fails or user doesn't exist
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
