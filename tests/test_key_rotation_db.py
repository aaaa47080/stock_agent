"""
Unit tests for DB-backed JWT key rotation (core/key_rotation.py).

All DB interactions are mocked — no real PostgreSQL connection required.
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

# Set required env vars before importing the module under test
os.environ.setdefault("JWT_MASTER_KEY", "test-master-key-32-chars-minimum-ok")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-1234567890")
os.environ.setdefault("USE_KEY_ROTATION", "true")


from core.key_rotation import (  # noqa: E402
    KeyRotationManager,
    _decrypt_key_value,
    _encrypt_key_value,
    _generate_key_pair,
    get_key_manager,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_db_key(key_id: str, value: str, status: str = "active", is_primary: bool = False):
    """Build a mock ORM JWTKey row."""
    row = MagicMock()
    row.id = key_id
    row.value_encrypted = _encrypt_key_value(value)
    row.status = status
    row.is_primary = is_primary
    row.created_at = datetime.now(UTC)
    row.expires_at = datetime.now(UTC) + timedelta(days=90)
    row.deprecated_at = None
    return row


def _manager_with_cache(primary_id: str, primary_value: str, extra_keys=None):
    """Return an already-initialized manager with a pre-populated cache."""
    manager = KeyRotationManager()
    manager._cache = {
        primary_id: {
            "value": primary_value,
            "status": "active",
            "is_primary": True,
            "expires_at": datetime.now(UTC) + timedelta(days=90),
        }
    }
    if extra_keys:
        manager._cache.update(extra_keys)
    manager._primary_key_id = primary_id
    manager._initialized = True
    return manager


# ── Encryption round-trip ──────────────────────────────────────────────────────


def test_encrypt_decrypt_round_trip():
    """Encrypted value can be decrypted back to the original."""
    original = "super-secret-jwt-signing-key-value"
    encrypted = _encrypt_key_value(original)
    assert encrypted != original
    assert _decrypt_key_value(encrypted) == original


def test_generate_key_pair_uniqueness():
    """Two key pairs must not share id or value."""
    id1, val1 = _generate_key_pair()
    id2, val2 = _generate_key_pair()
    assert id1 != id2
    assert val1 != val2
    assert len(id1) == 16


# ── Uninitialized guard ────────────────────────────────────────────────────────


def test_get_current_key_raises_before_init():
    manager = KeyRotationManager()
    with pytest.raises(RuntimeError, match="not yet initialized"):
        manager.get_current_key()


def test_get_all_active_keys_raises_before_init():
    manager = KeyRotationManager()
    with pytest.raises(RuntimeError, match="not yet initialized"):
        manager.get_all_active_keys()


# ── get_current_key / get_all_active_keys ─────────────────────────────────────


def test_get_current_key_returns_primary_value():
    manager = _manager_with_cache("key-abc", "my-signing-value")
    assert manager.get_current_key() == "my-signing-value"


def test_get_primary_key_id():
    manager = _manager_with_cache("key-abc", "my-signing-value")
    assert manager.get_primary_key_id() == "key-abc"


def test_get_all_active_keys_includes_deprecated():
    manager = _manager_with_cache("primary-id", "primary-val")
    manager._cache["old-id"] = {
        "value": "old-val",
        "status": "deprecated",
        "is_primary": False,
        "expires_at": datetime.now(UTC) + timedelta(hours=12),
    }
    keys = manager.get_all_active_keys()
    assert "primary-id" in keys
    assert "old-id" in keys
    assert len(keys) == 2


def test_get_all_active_keys_excludes_expired():
    manager = _manager_with_cache("primary-id", "primary-val")
    manager._cache["dead-id"] = {
        "value": "dead-val",
        "status": "expired",
        "is_primary": False,
        "expires_at": datetime.now(UTC) - timedelta(days=1),
    }
    keys = manager.get_all_active_keys()
    assert "dead-id" not in keys


# ── verify_token_with_any_key ──────────────────────────────────────────────────


def test_verify_token_with_valid_key():
    key_id, key_value = _generate_key_pair()
    manager = _manager_with_cache(key_id, key_value)

    token = jwt.encode(
        {"sub": "user123", "exp": datetime.now(UTC) + timedelta(hours=1)},
        key_value,
        algorithm="HS256",
    )
    payload = manager.verify_token_with_any_key(token)
    assert payload is not None
    assert payload["sub"] == "user123"
    assert payload["_key_id"] == key_id


def test_verify_token_with_deprecated_key():
    """Token signed with old (deprecated) key should still verify."""
    old_id, old_value = _generate_key_pair()
    new_id, new_value = _generate_key_pair()

    manager = _manager_with_cache(new_id, new_value)
    manager._cache[old_id] = {
        "value": old_value,
        "status": "deprecated",
        "is_primary": False,
        "expires_at": datetime.now(UTC) + timedelta(hours=12),
    }

    token = jwt.encode(
        {"sub": "user456", "exp": datetime.now(UTC) + timedelta(hours=1)},
        old_value,
        algorithm="HS256",
    )
    payload = manager.verify_token_with_any_key(token)
    assert payload is not None
    assert payload["_key_id"] == old_id


def test_verify_token_with_wrong_key_returns_none():
    key_id, key_value = _generate_key_pair()
    _, wrong_value = _generate_key_pair()
    manager = _manager_with_cache(key_id, key_value)

    token = jwt.encode(
        {"sub": "user789", "exp": datetime.now(UTC) + timedelta(hours=1)},
        wrong_value,
        algorithm="HS256",
    )
    assert manager.verify_token_with_any_key(token) is None


def test_verify_expired_token_returns_none():
    key_id, key_value = _generate_key_pair()
    manager = _manager_with_cache(key_id, key_value)

    token = jwt.encode(
        {"sub": "user000", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        key_value,
        algorithm="HS256",
    )
    assert manager.verify_token_with_any_key(token) is None


# ── should_rotate ──────────────────────────────────────────────────────────────


def test_should_rotate_false_when_key_is_new():
    manager = _manager_with_cache("kid", "val")
    # expires_at = now + 90 days → created ≈ now → no rotation needed
    assert manager.should_rotate(rotation_interval_days=30) is False


def test_should_rotate_true_when_key_is_old():
    manager = _manager_with_cache("kid", "val")
    # Simulate key created 31 days ago
    manager._cache["kid"]["expires_at"] = datetime.now(UTC) + timedelta(days=90 - 31)
    assert manager.should_rotate(rotation_interval_days=30) is True


# ── get_keys_status ────────────────────────────────────────────────────────────


def test_get_keys_status():
    manager = _manager_with_cache("primary-id", "primary-val")
    manager._cache["old-id"] = {
        "value": "old-val",
        "status": "deprecated",
        "is_primary": False,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    status = manager.get_keys_status()
    assert status["primary_key_id"] == "primary-id"
    assert status["initialized"] is True
    assert status["total_keys"] == 2
    assert status["active_keys"] == 1
    assert status["deprecated_keys"] == 1


# ── async initialize ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initialize_loads_keys_from_db():
    """initialize() populates cache from mocked DB rows."""
    key_id, key_value = _generate_key_pair()
    db_row = _make_db_key(key_id, key_value, status="active", is_primary=True)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [db_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("core.orm.session.get_session_factory", return_value=mock_factory):
        manager = KeyRotationManager()
        await manager.initialize()

    assert manager._initialized is True
    assert manager._primary_key_id == key_id
    assert manager.get_current_key() == key_value


@pytest.mark.asyncio
async def test_initialize_bootstraps_when_db_empty():
    """initialize() calls _bootstrap when no keys exist in DB."""
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []

    key_id, key_value = _generate_key_pair()
    db_row = _make_db_key(key_id, key_value, status="active", is_primary=True)
    populated_result = MagicMock()
    populated_result.scalars.return_value.all.return_value = [db_row]

    call_count = {"n": 0}

    async def mock_execute(_query):
        call_count["n"] += 1
        return empty_result if call_count["n"] == 1 else populated_result

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("core.orm.session.get_session_factory", return_value=mock_factory):
        manager = KeyRotationManager()
        await manager.initialize()

    assert manager._initialized is True


# ── async rotate_key ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rotate_key_demotes_old_and_creates_new():
    """rotate_key() demotes old primary and creates new one, then refreshes cache."""
    old_id, old_value = _generate_key_pair()
    old_row = _make_db_key(old_id, old_value, status="active", is_primary=True)

    new_id, new_value = _generate_key_pair()
    new_db_row = _make_db_key(new_id, new_value, status="active", is_primary=True)

    rotate_result = MagicMock()
    rotate_result.scalar_one_or_none.return_value = old_row

    init_result = MagicMock()
    init_result.scalars.return_value.all.return_value = [new_db_row]

    call_count = {"n": 0}

    async def mock_execute(_query):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return rotate_result  # select primary for rotation
        return init_result  # re-initialize

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("core.orm.session.get_session_factory", return_value=mock_factory):
        manager = _manager_with_cache(old_id, old_value)
        result = await manager.rotate_key()

    assert result["old_key_id"] == old_id
    assert "new_key_id" in result
    assert "rotated_at" in result
    # old primary was demoted
    assert old_row.is_primary is False
    assert old_row.status == "deprecated"


# ── async cleanup_expired_keys ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_expired_keys_deletes_old_deprecated():
    expired_id = "expired-key-id"

    select_result = MagicMock()
    select_result.fetchall.return_value = [(expired_id,)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("core.orm.session.get_session_factory", return_value=mock_factory):
        manager = _manager_with_cache("current-key", "current-value")
        removed = await manager.cleanup_expired_keys()

    assert removed == 1


@pytest.mark.asyncio
async def test_cleanup_expired_keys_returns_zero_when_nothing_to_clean():
    select_result = MagicMock()
    select_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=select_result)
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("core.orm.session.get_session_factory", return_value=mock_factory):
        manager = _manager_with_cache("current-key", "current-value")
        removed = await manager.cleanup_expired_keys()

    assert removed == 0


# ── singleton ──────────────────────────────────────────────────────────────────


def test_get_key_manager_returns_singleton():
    m1 = get_key_manager()
    m2 = get_key_manager()
    assert m1 is m2
