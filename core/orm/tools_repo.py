"""
Async ORM repository for Tool system operations.

Provides async equivalents of the functions in core.database.tools,
using SQLAlchemy 2.0 select/update with ToolsCatalog, AgentToolPermission,
UserToolPreference, and ToolUsageLog models.

Usage::

    from core.orm.tools_repo import tools_repo

    allowed = await tools_repo.get_allowed_tools("crypto", "premium", "user-1")
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AgentToolPermission, ToolsCatalog, ToolUsageLog, UserToolPreference
from .session import using_session

logger = logging.getLogger(__name__)

TIER_HIERARCHY = {"free": 0, "premium": 1}

_TIER_ALIASES = {
    "free": "free",
    "premium": "premium",
    "plus": "premium",
    "pro": "premium",
}

_AGENT_DEFAULT_TOOLS: Dict[str, List[str]] = {
    "crypto": [
        "get_current_time_taipei",
        "technical_analysis",
        "get_crypto_price",
        "google_news",
        "aggregate_news",
        "web_search",
        "get_fear_and_greed_index",
        "get_trending_tokens",
        "get_crypto_market_cap",
        "get_economic_calendar",
        "get_futures_data",
        "get_defillama_tvl",
        "get_crypto_categories_and_gainers",
        "get_token_unlocks",
        "get_token_supply",
        "get_dex_volume",
        "get_whale_alerts",
    ],
    "tw_stock": [
        "get_current_time_taipei",
        "tw_stock_price",
        "tw_technical_analysis",
        "tw_fundamentals",
        "tw_institutional",
        "tw_news",
        "tw_major_news",
        "tw_pe_ratio",
        "tw_monthly_revenue",
        "tw_dividend",
        "tw_foreign_top20",
        "web_search",
    ],
    "us_stock": [
        "us_stock_price",
        "us_technical_analysis",
        "us_fundamentals",
        "us_earnings",
        "us_news",
        "us_institutional_holders",
        "us_insider_transactions",
        "get_current_time_taipei",
    ],
    "chat": [
        "get_current_time_taipei",
        "get_crypto_price",
        "web_search",
    ],
}

# Tier-level mapping from the seed data (tool_id -> tier_required)
_TOOLS_TIER_MAP: Dict[str, str] = {
    "get_crypto_price": "free",
    "get_current_time_taipei": "free",
    "get_fear_and_greed_index": "free",
    "get_trending_tokens": "free",
    "get_crypto_market_cap": "free",
    "get_economic_calendar": "free",
    "technical_analysis": "free",
    "google_news": "free",
    "aggregate_news": "free",
    "web_search": "free",
    "get_futures_data": "premium",
    "get_defillama_tvl": "premium",
    "get_crypto_categories_and_gainers": "premium",
    "get_token_supply": "premium",
    "get_dex_volume": "premium",
    "get_token_unlocks": "premium",
    "get_whale_alerts": "premium",
    "tw_stock_price": "free",
    "tw_technical_analysis": "free",
    "tw_news": "free",
    "tw_major_news": "free",
    "tw_fundamentals": "premium",
    "tw_institutional": "premium",
    "tw_pe_ratio": "premium",
    "tw_monthly_revenue": "premium",
    "tw_dividend": "premium",
    "tw_foreign_top20": "premium",
    "us_stock_price": "free",
    "us_technical_analysis": "free",
    "us_news": "free",
    "us_fundamentals": "premium",
    "us_earnings": "premium",
    "us_institutional_holders": "premium",
    "us_insider_transactions": "premium",
}


def _normalize_tier(tier: Optional[str]) -> str:
    """Normalize legacy membership names to tool-system tiers."""
    return _TIER_ALIASES.get((tier or "free").strip().lower(), "free")


def _get_tier_level(tier: str) -> int:
    """Return numeric level for a tier string."""
    return TIER_HIERARCHY.get(_normalize_tier(tier), 0)


def _get_fallback_tools(agent_id: str, user_tier: str) -> List[str]:
    """Hardcode fallback when DB is not yet seeded."""
    user_tier = _normalize_tier(user_tier)
    all_tools = _AGENT_DEFAULT_TOOLS.get(agent_id, [])
    user_tier_level = _get_tier_level(user_tier)

    allowed = []
    for t in _TOOLS_TIER_MAP:
        if _get_tier_level(_TOOLS_TIER_MAP[t]) <= user_tier_level and t in all_tools:
            allowed.append(t)
    return allowed


class ToolsRepository:
    """Async ORM repository for tool catalog, permissions, preferences, and usage."""

    async def get_allowed_tools(
        self,
        agent_id: str,
        user_tier: str = "free",
        user_id: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> List[str]:
        """Return tool IDs available to *agent_id* for the given *user_tier*."""
        user_tier = _normalize_tier(user_tier)
        user_tier_level = _get_tier_level(user_tier)
        allowed_tiers = [
            tier for tier, level in TIER_HIERARCHY.items() if level <= user_tier_level
        ]

        async with using_session(session) as s:
            # Base query: catalog JOIN agent permissions
            stmt = (
                select(ToolsCatalog.tool_id)
                .join(
                    AgentToolPermission,
                    and_(
                        ToolsCatalog.tool_id == AgentToolPermission.tool_id,
                        AgentToolPermission.agent_id == agent_id,
                    ),
                )
                .where(
                    ToolsCatalog.is_active.is_(True),
                    AgentToolPermission.is_enabled.is_(True),
                    ToolsCatalog.tier_required.in_(allowed_tiers),
                )
            )

            # Exclude user-disabled tools for premium users
            if user_id and user_tier == "premium":
                stmt = stmt.outerjoin(
                    UserToolPreference,
                    and_(
                        ToolsCatalog.tool_id == UserToolPreference.tool_id,
                        UserToolPreference.user_id == user_id,
                    ),
                ).where(
                    or_(
                        UserToolPreference.is_enabled.is_(None),
                        UserToolPreference.is_enabled.is_(True),
                    ),
                )

            result = await s.execute(stmt)
            rows = result.fetchall()
            tools = [r[0] for r in rows]

            if not tools:
                # Check if catalog/permissions exist at all
                check_stmt = (
                    select(func.count())
                    .select_from(AgentToolPermission)
                    .join(
                        ToolsCatalog,
                        ToolsCatalog.tool_id == AgentToolPermission.tool_id,
                    )
                    .where(AgentToolPermission.agent_id == agent_id)
                    .limit(1)
                )
                check_result = await s.execute(check_stmt)
                seeded = (check_result.scalar_one() or 0) > 0
                if seeded:
                    return []
                return _get_fallback_tools(agent_id, user_tier)

            return tools

    async def check_and_increment_tool_quota(
        self,
        user_id: str,
        tool_id: str,
        user_tier: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Atomically check tool quota and increment usage in a single transaction.

        Returns True if the tool can be used (quota available), False if limit reached.
        """
        user_tier = _normalize_tier(user_tier)

        async with using_session(session) as s:
            stmt = select(
                ToolsCatalog.quota_type,
                ToolsCatalog.daily_limit_free,
                ToolsCatalog.daily_limit_plus,
                ToolsCatalog.daily_limit_prem,
            ).where(ToolsCatalog.tool_id == tool_id, ToolsCatalog.is_active.is_(True))

            result = await s.execute(stmt)
            row = result.fetchone()

            if not row:
                return True

            quota_type, limit_free, limit_plus, limit_prem = row

            if quota_type == "unlimited":
                return True

            if user_tier == "premium":
                limit = limit_prem if limit_prem is not None else limit_plus
            else:
                limit = limit_free

            if limit is None:
                return True
            if limit == 0:
                return False

            today = date.today()
            # Upsert tool_usage_log and get new call_count
            upsert_stmt = (
                pg_insert(ToolUsageLog)
                .values(
                    user_id=user_id,
                    tool_id=tool_id,
                    used_date=today,
                    call_count=1,
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "tool_id", "used_date"],
                    set_={"call_count": ToolUsageLog.call_count + 1},
                )
                .returning(ToolUsageLog.call_count)
            )
            upsert_result = await s.execute(upsert_stmt)
            used = upsert_result.scalar_one() or 1

            return used <= limit

    async def check_tool_quota(
        self,
        user_id: str,
        tool_id: str,
        user_tier: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Check if the user has remaining quota for *tool_id* today (no side-effects)."""
        user_tier = _normalize_tier(user_tier)

        async with using_session(session) as s:
            stmt = select(
                ToolsCatalog.quota_type,
                ToolsCatalog.daily_limit_free,
                ToolsCatalog.daily_limit_plus,
                ToolsCatalog.daily_limit_prem,
            ).where(ToolsCatalog.tool_id == tool_id, ToolsCatalog.is_active.is_(True))

            result = await s.execute(stmt)
            row = result.fetchone()

            if not row:
                return True

            quota_type, limit_free, limit_plus, limit_prem = row

            if quota_type == "unlimited":
                return True

            if user_tier == "premium":
                limit = limit_prem if limit_prem is not None else limit_plus
            else:
                limit = limit_free

            if limit is None:
                return True
            if limit == 0:
                return False

            today = date.today()
            usage_stmt = select(ToolUsageLog.call_count).where(
                ToolUsageLog.user_id == user_id,
                ToolUsageLog.tool_id == tool_id,
                ToolUsageLog.used_date == today,
            )
            usage_result = await s.execute(usage_stmt)
            used = usage_result.scalar_one_or_none() or 0

            return used < limit

    async def increment_tool_usage(
        self,
        user_id: str,
        tool_id: str,
        session: AsyncSession | None = None,
    ) -> None:
        """Record one tool invocation (upsert)."""
        today = date.today()
        stmt = (
            pg_insert(ToolUsageLog)
            .values(
                user_id=user_id,
                tool_id=tool_id,
                used_date=today,
                call_count=1,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "tool_id", "used_date"],
                set_={"call_count": ToolUsageLog.call_count + 1},
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)

    async def get_tools_for_frontend(
        self,
        user_tier: str,
        user_id: Optional[str] = None,
        session: AsyncSession | None = None,
    ) -> List[Dict[str, Any]]:
        """Return the tool list needed by the frontend settings page."""
        user_tier = _normalize_tier(user_tier)
        user_tier_level = _get_tier_level(user_tier)

        async with using_session(session) as s:
            if user_id and user_tier == "premium":
                stmt = (
                    select(
                        ToolsCatalog.tool_id,
                        ToolsCatalog.display_name,
                        ToolsCatalog.description,
                        ToolsCatalog.category,
                        ToolsCatalog.tier_required,
                        ToolsCatalog.quota_type,
                        func.coalesce(UserToolPreference.is_enabled, True).label(
                            "is_enabled"
                        ),
                    )
                    .outerjoin(
                        UserToolPreference,
                        and_(
                            ToolsCatalog.tool_id == UserToolPreference.tool_id,
                            UserToolPreference.user_id == user_id,
                        ),
                    )
                    .where(ToolsCatalog.is_active.is_(True))
                    .order_by(
                        ToolsCatalog.category,
                        ToolsCatalog.tier_required,
                        ToolsCatalog.tool_id,
                    )
                )
            else:
                stmt = (
                    select(
                        ToolsCatalog.tool_id,
                        ToolsCatalog.display_name,
                        ToolsCatalog.description,
                        ToolsCatalog.category,
                        ToolsCatalog.tier_required,
                        ToolsCatalog.quota_type,
                        literal(True).label("is_enabled"),
                    )
                    .where(ToolsCatalog.is_active.is_(True))
                    .order_by(
                        ToolsCatalog.category,
                        ToolsCatalog.tier_required,
                        ToolsCatalog.tool_id,
                    )
                )

            result = await s.execute(stmt)
            rows = result.fetchall()

            return [
                {
                    "tool_id": r[0],
                    "display_name": r[1],
                    "description": r[2],
                    "category": r[3],
                    "tier_required": r[4],
                    "quota_type": r[5],
                    "is_enabled": r[6],
                    "locked": _get_tier_level(r[4]) > user_tier_level,
                }
                for r in rows
            ]

    async def update_user_tool_preference(
        self,
        user_id: str,
        tool_id: str,
        is_enabled: bool,
        session: AsyncSession | None = None,
    ) -> None:
        """Update a user's personal preference for a tool (Premium only)."""
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(UserToolPreference)
            .values(
                user_id=user_id,
                tool_id=tool_id,
                is_enabled=is_enabled,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "tool_id"],
                set_={
                    "is_enabled": pg_insert.excluded.is_enabled,
                    "updated_at": now,
                },
            )
        )

        async with using_session(session) as s:
            await s.execute(stmt)


tools_repo = ToolsRepository()
