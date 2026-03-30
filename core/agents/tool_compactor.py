"""
Tool result compaction helpers.

Wrap large LangChain tool outputs to avoid flooding LangGraph message state.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional

import orjson
from langchain_core.tools import BaseTool

from core.memory_scope import build_scope, scope_namespace

logger = logging.getLogger(__name__)

THRESHOLD = 2_000
PREVIEW_LEN = 500
REDIS_TTL = 3_600
_KEY_PREFIX = "tr:"
MAX_LOCAL_STORE_SIZE = 1000

_local_store: dict[str, str] = {}
_redis_client: Optional[Any] = None
_redis_init_attempted = False
_wrapped_tool_ids: set[int] = set()
_tool_stats: dict[int, Optional[dict]] = {}


def _serialize_record(
    data: str,
    owner_id: Optional[str],
    workspace_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    owner_scope = None
    if owner_id is not None:
        owner_scope = scope_namespace(
            build_scope(owner_id, session_id=session_id, workspace_id=workspace_id)
        )
    return orjson.dumps(
        {
            "data": data,
            "owner_id": owner_id,
            "owner_scope": owner_scope,
        }
    ).decode()


def _deserialize_record(raw: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if raw is None:
        return None, None, None

    if isinstance(raw, bytes):
        raw = raw.decode()

    if not isinstance(raw, str):
        return None, None, str(raw)

    try:
        decoded = orjson.loads(raw)
    except Exception:
        return None, None, raw

    if isinstance(decoded, dict) and "data" in decoded:
        owner_id = decoded.get("owner_id")
        if owner_id is not None:
            owner_id = str(owner_id)
        owner_scope = decoded.get("owner_scope")
        if owner_scope is not None:
            owner_scope = str(owner_scope)
        return owner_id, owner_scope, str(decoded["data"])

    return None, None, raw


def _get_redis_sync() -> Optional[Any]:
    """Return a synchronous Redis client or None when unavailable."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client

    _redis_init_attempted = True
    try:
        import redis as _r

        from core.redis_url import resolve_redis_url

        url, _ = resolve_redis_url()
        if not url:
            return None

        client = _r.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info("[ToolCompactor] Redis sync client connected")
    except Exception as exc:
        logger.warning(
            "[ToolCompactor] Redis unavailable, using local fallback: %s", exc
        )
        _redis_client = None
    return _redis_client


def _to_str(output: Any) -> str:
    if isinstance(output, str):
        return output
    try:
        return orjson.dumps(output).decode()
    except Exception:
        return json.dumps(output, ensure_ascii=False, default=str)


def _store_sync(
    data: str,
    owner_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    uid = str(uuid.uuid4())
    record = _serialize_record(
        data, owner_id, workspace_id=workspace_id, session_id=session_id
    )
    redis_client = _get_redis_sync()
    if redis_client is not None:
        try:
            redis_client.setex(_KEY_PREFIX + uid, REDIS_TTL, record)
            return uid
        except Exception as exc:
            logger.debug("[ToolCompactor] Redis store failed: %s", exc)
    if len(_local_store) >= MAX_LOCAL_STORE_SIZE:
        keys_to_remove = list(_local_store.keys())[: MAX_LOCAL_STORE_SIZE // 5]
        for k in keys_to_remove:
            del _local_store[k]
    _local_store[uid] = record
    return uid


def _retrieve_sync(uid: str) -> Optional[tuple[Optional[str], Optional[str], str]]:
    redis_client = _get_redis_sync()
    if redis_client is not None:
        try:
            value = redis_client.get(_KEY_PREFIX + uid)
            if value is not None:
                owner_id, owner_scope, data = _deserialize_record(value)
                if data is not None:
                    return owner_id, owner_scope, data
        except Exception as exc:
            logger.debug("[ToolCompactor] Redis retrieve failed: %s", exc)
    value = _local_store.get(uid)
    if value is None:
        return None
    owner_id, owner_scope, data = _deserialize_record(value)
    if data is None:
        return None
    return owner_id, owner_scope, data


def _is_compactor_wrapped(tool: Any) -> bool:
    if id(tool) in _wrapped_tool_ids:
        return True
    # Use getattr with explicit bool check to avoid MagicMock returning truthy auto-created attrs
    val = getattr(tool, "_compactor_wrapped", None)
    return val is True


def _set_last_stat(tool: Any, stat: Optional[dict]) -> None:
    _tool_stats[id(tool)] = stat


def _get_last_stat(tool: Any) -> Optional[dict]:
    return _tool_stats.get(id(tool))


if not isinstance(getattr(BaseTool, "last_stat", None), property):
    BaseTool.last_stat = property(_get_last_stat, _set_last_stat)


class _CompactingToolWrapper(BaseTool):
    """
    Proxy that compacts large `invoke()` outputs without mutating the original tool.

    Inherits from BaseTool so that isinstance(wrapper, BaseTool) returns True.
    This prevents LangGraph's internal tool() decorator from trying to re-wrap it.
    """

    name: str = ""
    description: str = ""

    # Internal state
    _original: Any = None
    _owner_id: Optional[str] = None
    _workspace_id: Optional[str] = None
    _session_id: Optional[str] = None
    _last_stat: Optional[dict] = None

    def __init__(
        self,
        original: Any,
        owner_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # Delegate name/description from original tool
        # Use str() to handle MagicMock/other non-string types gracefully
        name = getattr(original, "name", None)
        desc = getattr(original, "description", None)
        kwargs["name"] = str(name) if name else "unknown"
        kwargs["description"] = str(desc) if desc else ""
        super().__init__(**kwargs)
        object.__setattr__(self, "_original", original)
        object.__setattr__(self, "_owner_id", owner_id)
        object.__setattr__(self, "_workspace_id", workspace_id)
        object.__setattr__(self, "_session_id", session_id)
        object.__setattr__(self, "_last_stat", None)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._original, item)

    @property
    def last_stat(self) -> Optional[dict]:
        return self._last_stat

    @last_stat.setter
    def last_stat(self, value: Optional[dict]) -> None:
        object.__setattr__(self, "_last_stat", value)

    def invoke(self, input: Any, **kwargs: Any) -> Any:  # noqa: A002
        start = time.monotonic()
        try:
            raw = self._original.invoke(input, **kwargs)
            text = _to_str(raw)
            latency_ms = int((time.monotonic() - start) * 1000)
            object.__setattr__(self, "_last_stat", {
                "tool_name": getattr(self._original, "name", "unknown"),
                "success": True,
                "latency_ms": latency_ms,
                "output_chars": len(text),
                "error_type": None,
            })
            if len(text) <= THRESHOLD:
                return raw
            uid = _store_sync(
                text,
                owner_id=self._owner_id,
                workspace_id=self._workspace_id,
                session_id=self._session_id,
            )
            preview = text[:PREVIEW_LEN]
            return (
                f"[COMPACTED:{uid}]\n"
                f"{preview}...\n"
                f"[{len(text):,} chars total. Retrieve full data with key: {uid}]"
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            object.__setattr__(self, "_last_stat", {
                "tool_name": getattr(self._original, "name", "unknown"),
                "success": False,
                "latency_ms": latency_ms,
                "output_chars": 0,
                "error_type": type(exc).__name__,
            })
            raise

    def _run(self, *args: Any, **kwargs: Any) -> Any:  # noqa: A002
        """Sync wrapper for invoke(). Required by BaseTool abstract method."""
        return self.invoke(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:  # noqa: A002
        """Async wrapper for ainvoke(). Delegates to _original's ainvoke or invoke."""
        ainvoke = getattr(self._original, "ainvoke", None)
        if ainvoke is not None:
            return await ainvoke(*args, **kwargs)
        return self.invoke(*args, **kwargs)


def _compact_output(
    raw: Any,
    *,
    owner_id: Optional[str],
    workspace_id: Optional[str],
    session_id: Optional[str],
) -> Any:
    text = _to_str(raw)
    if len(text) <= THRESHOLD:
        return raw
    uid = _store_sync(
        text,
        owner_id=owner_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )
    preview = text[:PREVIEW_LEN]
    return (
        f"[COMPACTED:{uid}]\n"
        f"{preview}...\n"
        f"[{len(text):,} chars total. Retrieve full data with key: {uid}]"
    )


def wrap_tool(
    tool: Any,
    owner_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    """Return a non-mutating wrapper for LangChain tools that expose `invoke()`."""
    if not hasattr(tool, "invoke"):
        return tool
    if _is_compactor_wrapped(tool):
        return tool
    return _CompactingToolWrapper(
        tool,
        owner_id=owner_id,
        workspace_id=workspace_id,
        session_id=session_id,
    )


def retrieve_tool_result(
    uid: str,
    requester_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    record = _retrieve_sync(uid)
    if record is None:
        return f"[ERROR] Tool result '{uid}' not found or expired."
    owner_id, owner_scope, data = record
    requester_scope = None
    if requester_id is not None:
        requester_scope = scope_namespace(
            build_scope(requester_id, session_id=session_id, workspace_id=workspace_id)
        )
    if (
        requester_scope is not None
        and owner_scope is not None
        and requester_scope != owner_scope
    ):
        return f"[ERROR] Tool result '{uid}' is not available for this user."
    if (
        requester_scope is None
        and requester_id is not None
        and owner_id is not None
        and requester_id != owner_id
    ):
        return f"[ERROR] Tool result '{uid}' is not available for this user."
    return data


def _reset_for_testing() -> None:
    """Reset module-level state used by tests."""
    global _redis_client, _redis_init_attempted
    _redis_client = None
    _redis_init_attempted = False
    _local_store.clear()
    _wrapped_tool_ids.clear()
    _tool_stats.clear()
