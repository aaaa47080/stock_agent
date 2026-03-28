"""
JWT Key Rotation System — DB-backed storage with in-memory cache.

Keys are stored encrypted in PostgreSQL (jwt_keys table).
Encryption uses JWT_MASTER_KEY env var (Fernet/PBKDF2).

Design:
- Primary Key: Signs new tokens
- Deprecated Key: Validates old tokens until they expire (24h max)
- Auto-rotation: every KEY_ROTATION_INTERVAL_DAYS (default: 30)
- Bootstrap: first startup auto-generates key and saves to DB

Required env vars when USE_KEY_ROTATION=true:
  JWT_MASTER_KEY  — master encryption key for key values in DB
                    generate with: openssl rand -hex 32
"""

import base64
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from api.utils import logger

# ── Encryption helpers ─────────────────────────────────────────────────────────

_fernet_cache: Optional[Fernet] = None


def _get_master_fernet() -> Fernet:
    """Derive Fernet instance from JWT_MASTER_KEY env var (cached)."""
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache

    master = os.getenv("JWT_MASTER_KEY")
    if not master:
        raise RuntimeError(
            "JWT_MASTER_KEY environment variable is required when USE_KEY_ROTATION=true. "
            "Generate with: openssl rand -hex 32"
        )
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"PiCryptoMind_JWT_Key_DB_v1",
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master.encode()))
    _fernet_cache = Fernet(key)
    return _fernet_cache


def _encrypt_key_value(value: str) -> str:
    return _get_master_fernet().encrypt(value.encode()).decode()


def _decrypt_key_value(encrypted: str) -> str:
    return _get_master_fernet().decrypt(encrypted.encode()).decode()


# ── KeyRotationManager ─────────────────────────────────────────────────────────


class KeyRotationManager:
    """
    DB-backed JWT key rotation manager with in-memory cache.

    Lifecycle:
        manager = get_key_manager()       # sync, no DB access
        await manager.initialize()        # async, loads keys from DB
        key = manager.get_current_key()   # sync, reads from cache

    The background task (key_rotation_task) owns initialization and
    periodic rotation. Routes read from the cache without awaiting.
    """

    def __init__(self) -> None:
        # key_id -> {"value": str, "status": str, "is_primary": bool, "expires_at": datetime}
        self._cache: Dict[str, dict] = {}
        self._primary_key_id: Optional[str] = None
        self._initialized: bool = False

    # ── Public sync interface (cache reads) ────────────────────────────────────

    def get_current_key(self) -> str:
        """Return primary signing key value (sync, from cache)."""
        self._require_initialized()
        entry = self._cache.get(self._primary_key_id or "")
        if not entry:
            raise RuntimeError("Primary JWT key not found in cache")
        return entry["value"]

    def get_primary_key_id(self) -> str:
        """Return primary key ID (sync, from cache)."""
        self._require_initialized()
        return self._primary_key_id  # type: ignore[return-value]

    def get_all_active_keys(self) -> Dict[str, str]:
        """Return all active+deprecated key values for token validation (sync, from cache)."""
        self._require_initialized()
        return {
            kid: e["value"]
            for kid, e in self._cache.items()
            if e["status"] in ("active", "deprecated")
        }

    def verify_token_with_any_key(
        self, token: str, algorithms: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Try all active/deprecated keys; return decoded payload or None."""
        if algorithms is None:
            algorithms = ["HS256"]
        for key_id, key_value in self.get_all_active_keys().items():
            try:
                payload = jwt.decode(
                    token,
                    key_value,
                    algorithms=algorithms,
                    options={"verify_exp": True},
                )
                payload["_key_id"] = key_id
                return payload
            except Exception:
                continue
        return None

    def should_rotate(self, rotation_interval_days: int = 30) -> bool:
        """True if the primary key is older than rotation_interval_days."""
        self._require_initialized()
        entry = self._cache.get(self._primary_key_id or "")
        if not entry:
            return True
        expires_at = entry["expires_at"]
        if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        # Keys are created with 90-day expiry; derive creation time
        created_approx = expires_at - timedelta(days=90)
        return datetime.now(UTC) >= created_approx + timedelta(days=rotation_interval_days)

    def get_keys_status(self) -> Dict:
        """Admin view — key values are NOT included."""
        return {
            "primary_key_id": self._primary_key_id,
            "initialized": self._initialized,
            "total_keys": len(self._cache),
            "active_keys": sum(
                1 for e in self._cache.values() if e["status"] == "active"
            ),
            "deprecated_keys": sum(
                1 for e in self._cache.values() if e["status"] == "deprecated"
            ),
        }

    # ── Async DB operations ────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Load (or bootstrap) keys from DB and populate in-memory cache.

        Self-healing: if the jwt_keys table doesn't exist yet (e.g. Alembic
        migration hasn't run), creates it inline before bootstrapping.
        """
        from core.orm.models import JWTKey
        from core.orm.session import get_session_factory
        from sqlalchemy import select, text

        factory = get_session_factory()
        async with factory() as session:
            try:
                result = await session.execute(
                    select(JWTKey).where(JWTKey.status.in_(["active", "deprecated"]))
                )
                rows = result.scalars().all()
            except Exception as exc:
                err = str(exc).lower()
                if "jwt_keys" in err or "does not exist" in err or "undefined" in err:
                    logger.warning(
                        "jwt_keys table missing — creating inline as Alembic fallback"
                    )
                    await session.rollback()
                    await session.execute(text("""
                        CREATE TABLE IF NOT EXISTS jwt_keys (
                            id TEXT PRIMARY KEY,
                            value_encrypted TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'active',
                            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            expires_at TIMESTAMPTZ NOT NULL,
                            deprecated_at TIMESTAMPTZ
                        )
                    """))
                    await session.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_jwt_keys_status ON jwt_keys(status)"
                    ))
                    await session.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_jwt_keys_is_primary ON jwt_keys(is_primary)"
                    ))
                    await session.commit()
                    rows = []
                else:
                    raise

            if not rows:
                await self._bootstrap(session)
                result = await session.execute(
                    select(JWTKey).where(JWTKey.status.in_(["active", "deprecated"]))
                )
                rows = result.scalars().all()

        self._cache = {}
        self._primary_key_id = None

        for row in rows:
            try:
                value = _decrypt_key_value(row.value_encrypted)
            except Exception as exc:
                logger.error(f"Failed to decrypt JWT key {row.id}: {exc}")
                continue
            self._cache[row.id] = {
                "value": value,
                "status": row.status,
                "is_primary": row.is_primary,
                "expires_at": row.expires_at,
            }
            if row.is_primary:
                self._primary_key_id = row.id

        if not self._primary_key_id:
            raise RuntimeError("No primary JWT key found after initialization")

        self._initialized = True
        logger.info(
            f"🔑 JWT KeyRotationManager initialized ({len(self._cache)} key(s) loaded)"
        )

    async def rotate_key(self) -> Dict:
        """Demote current primary → deprecated; generate and promote new primary."""
        from core.orm.models import JWTKey
        from core.orm.session import get_session_factory
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(JWTKey).where(JWTKey.is_primary.is_(True))
            )
            old_primary = result.scalar_one_or_none()
            if not old_primary:
                raise RuntimeError("No primary key found in DB for rotation")

            old_key_id = old_primary.id
            now = datetime.now(UTC)

            old_primary.is_primary = False
            old_primary.status = "deprecated"
            old_primary.deprecated_at = now

            new_id, new_value = _generate_key_pair()
            new_key = JWTKey(
                id=new_id,
                value_encrypted=_encrypt_key_value(new_value),
                status="active",
                is_primary=True,
                created_at=now,
                expires_at=now + timedelta(days=90),
            )
            session.add(new_key)
            await session.commit()

        # Refresh cache after rotation
        await self.initialize()

        result = {
            "old_key_id": old_key_id,
            "new_key_id": new_id,
            "rotated_at": now.isoformat(),
        }
        logger.info(
            f"🔑 Key rotation completed: {old_key_id[:8]}... → {new_id[:8]}..."
        )
        return result

    async def cleanup_expired_keys(self) -> int:
        """Delete deprecated keys whose expiry has passed."""
        from core.orm.models import JWTKey
        from core.orm.session import get_session_factory
        from sqlalchemy import delete, select

        now = datetime.now(UTC)
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(JWTKey.id).where(
                    JWTKey.status == "deprecated",
                    JWTKey.expires_at < now,
                    JWTKey.is_primary.is_(False),
                )
            )
            expired_ids = [row[0] for row in result.fetchall()]

            if expired_ids:
                await session.execute(
                    delete(JWTKey).where(JWTKey.id.in_(expired_ids))
                )
                await session.commit()
                logger.info(f"🧹 Cleaned up {len(expired_ids)} expired JWT key(s)")

        return len(expired_ids)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "JWT KeyRotationManager not yet initialized. "
                "The key_rotation_task must complete initialization before handling requests."
            )

    @staticmethod
    async def _bootstrap(session) -> None:
        """Insert the first key on a fresh DB."""
        from core.orm.models import JWTKey

        key_id, key_value = _generate_key_pair()
        now = datetime.now(UTC)
        session.add(
            JWTKey(
                id=key_id,
                value_encrypted=_encrypt_key_value(key_value),
                status="active",
                is_primary=True,
                created_at=now,
                expires_at=now + timedelta(days=90),
            )
        )
        await session.commit()
        logger.info(f"🔑 Bootstrap: generated initial JWT key {key_id[:8]}...")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _generate_key_pair() -> tuple[str, str]:
    """Return (key_id, key_value) — both cryptographically random."""
    key_id = hashlib.sha256(secrets.token_bytes(16)).hexdigest()[:16]
    key_value = secrets.token_urlsafe(32)
    return key_id, key_value


# ── Singleton ──────────────────────────────────────────────────────────────────

_global_manager: Optional[KeyRotationManager] = None


def get_key_manager() -> KeyRotationManager:
    """Return the global KeyRotationManager singleton (lazy creation, no DB access)."""
    global _global_manager
    if _global_manager is None:
        _global_manager = KeyRotationManager()
    return _global_manager


# ── Background task ────────────────────────────────────────────────────────────


async def key_rotation_task() -> None:
    """
    Wait for DB, initialize key manager (with retry), then check rotation every hour.

    Started by api/lifespan.py when USE_KEY_ROTATION=true.
    """
    import asyncio

    from core.db_ready import wait_for_db_ready

    rotation_interval_days = int(os.getenv("KEY_ROTATION_INTERVAL_DAYS", "30"))
    manager = get_key_manager()

    await wait_for_db_ready()

    # Initialize with exponential backoff retry
    retry_delay = 5
    while not manager._initialized:
        try:
            await manager.initialize()
        except Exception as exc:
            logger.error(
                f"❌ JWT key manager init failed (retry in {retry_delay}s): {exc}"
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 120)

    logger.info(
        f"🔑 Key rotation task running (interval: {rotation_interval_days} days)"
    )

    while True:
        await asyncio.sleep(3600)  # check every hour
        try:
            if manager.should_rotate(rotation_interval_days):
                logger.info("🔑 JWT key rotation due, rotating...")
                result = await manager.rotate_key()
                logger.info(
                    f"✅ Key rotation: {result['old_key_id'][:8]}... → {result['new_key_id'][:8]}..."
                )
                try:
                    from core.audit import audit_log

                    audit_log(action="key_rotation_automatic", metadata={"type": "jwt", **result})
                except ImportError:
                    pass

            await manager.cleanup_expired_keys()

        except Exception as exc:
            logger.error(f"❌ Key rotation task error: {exc}")
