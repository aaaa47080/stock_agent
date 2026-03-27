"""Helpers for resolving user-scoped LLM credentials on the server side."""

from typing import Optional

from api.utils import logger
from core.orm.user_api_keys_repo import SUPPORTED_PROVIDERS, user_api_keys_repo


async def resolve_user_llm_credentials(
    current_user: Optional[dict],
    preferred_provider: Optional[str] = None,
) -> Optional[dict]:
    """Resolve an authenticated user's LLM provider + decrypted API key."""
    if not current_user:
        return None

    user_id = current_user.get("user_id")
    if not user_id:
        return None

    providers: list[str] = []
    if preferred_provider:
        normalized = preferred_provider.strip().lower()
        if normalized in SUPPORTED_PROVIDERS:
            providers.append(normalized)
        else:
            logger.warning(
                "Ignoring unsupported preferred LLM provider: %s",
                preferred_provider,
            )

    for provider in SUPPORTED_PROVIDERS:
        if provider not in providers:
            providers.append(provider)

    for provider in providers:
        api_key = await user_api_keys_repo.get_user_api_key(user_id, provider)
        if api_key:
            return {"provider": provider, "api_key": api_key}

    return None
