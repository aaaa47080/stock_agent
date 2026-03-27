"""
Async ORM repository for User API Key operations.

Provides async equivalents of the functions in core.database.user_api_keys,
using SQLAlchemy 2.0 select/update with the UserApiKey model.

Usage::

    from core.orm.user_api_keys_repo import user_api_keys_repo

    result = await user_api_keys_repo.save_user_api_key("user-1", "openai", "sk-...")
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from utils.encryption import decrypt_api_key, encrypt_api_key, mask_api_key

from .models import UserApiKey
from .session import using_session

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = [
    "openai",
    "google_gemini",
    "anthropic",
    "groq",
    "openrouter",
]


class UserApiKeysRepository:
    """Async ORM repository for user API key management."""

    async def save_user_api_key(
        self,
        user_id: str,
        provider: str,
        api_key: str,
        model: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Save (upsert) a user's API key (encrypted)."""
        if provider not in SUPPORTED_PROVIDERS:
            return {"success": False, "error": f"Unsupported provider: {provider}"}

        if not api_key or not api_key.strip():
            return {"success": False, "error": "API key cannot be empty"}

        encrypted_key = encrypt_api_key(api_key.strip())
        now = datetime.now(timezone.utc)

        stmt = (
            pg_insert(UserApiKey)
            .values(
                user_id=user_id,
                provider=provider,
                encrypted_key=encrypted_key,
                model_selection=model,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "provider"],
                set_={
                    "encrypted_key": pg_insert.excluded.encrypted_key,
                    "model_selection": pg_insert.excluded.model_selection,
                    "updated_at": now,
                },
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

        return {"success": True}

    async def get_user_api_key(
        self,
        user_id: str,
        provider: str,
        session: AsyncSession | None = None,
    ) -> Optional[str]:
        """Get the decrypted API key for a user + provider, or None."""
        stmt = select(UserApiKey.encrypted_key).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            decrypted = decrypt_api_key(row)
            return decrypted or None

    async def get_user_api_key_masked(
        self,
        user_id: str,
        provider: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Get a masked version of the API key for frontend display."""
        stmt = select(
            UserApiKey.encrypted_key,
            UserApiKey.model_selection,
            UserApiKey.updated_at,
        ).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            row = result.fetchone()
            if not row:
                return {
                    "has_key": False,
                    "masked_key": None,
                    "model": None,
                    "updated_at": None,
                }

            decrypted = decrypt_api_key(row[0])
            masked = mask_api_key(decrypted) if decrypted else None

            return {
                "has_key": bool(decrypted),
                "masked_key": masked,
                "model": row[1],
                "updated_at": row[2].isoformat() if row[2] else None,
                "corrupted": not bool(decrypted),
            }

    async def get_all_user_api_keys(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Get masked versions of all API keys for a user."""
        stmt = select(
            UserApiKey.provider,
            UserApiKey.encrypted_key,
            UserApiKey.model_selection,
            UserApiKey.updated_at,
        ).where(UserApiKey.user_id == user_id)

        async with using_session(session) as s:
            result = await s.execute(stmt)
            rows = result.fetchall()
            result_map: Dict[str, Dict[str, Any]] = {}

            for row in rows:
                provider = row[0]
                decrypted = decrypt_api_key(row[1])
                masked = mask_api_key(decrypted) if decrypted else None

                result_map[provider] = {
                    "has_key": bool(decrypted),
                    "masked_key": masked,
                    "model": row[2],
                    "updated_at": row[3].isoformat() if row[3] else None,
                    "corrupted": not bool(decrypted),
                }

            # Ensure all supported providers have an entry
            for provider in SUPPORTED_PROVIDERS:
                if provider not in result_map:
                    result_map[provider] = {
                        "has_key": False,
                        "masked_key": None,
                        "model": None,
                        "updated_at": None,
                    }

            return result_map

    async def delete_user_api_key(
        self,
        user_id: str,
        provider: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Delete a user's API key for a specific provider."""
        stmt = delete(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        )

        async with using_session(session) as s:
            await s.execute(stmt)

        return {"success": True}

    async def delete_all_user_api_keys(
        self,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Delete all API keys for a user (used on account deletion)."""
        stmt = delete(UserApiKey).where(UserApiKey.user_id == user_id)

        async with using_session(session) as s:
            await s.execute(stmt)

        return {"success": True}

    async def save_user_model_selection(
        self,
        user_id: str,
        provider: str,
        model: str,
        session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """Save user's model selection without changing the API key."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(UserApiKey)
            .where(
                UserApiKey.user_id == user_id,
                UserApiKey.provider == provider,
            )
            .values(model_selection=model, updated_at=now)
        )

        async with using_session(session) as s:
            result = await s.execute(stmt)
            if result.rowcount == 0:
                return {"success": False, "error": "No API key found for this provider"}

        return {"success": True}


user_api_keys_repo = UserApiKeysRepository()
