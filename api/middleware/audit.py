"""
Audit Logging Middleware - Optimized Dual-Layer Architecture

**设计理念**：
- 普通API调用 → logging文件（轻量、快速）
- 安全敏感操作 → 数据库（持久化、合规）

这样既保留完整的调试能力，又避免数据库写入压力。
"""

import asyncio
import time
from typing import Optional

from fastapi import Request

from api.utils import logger
from core.audit import AuditLogger


async def _extract_user_from_request(request: Request) -> Optional[dict]:
    """
    Extract user information from request headers or state.

    This function tries to get user info from:
    1. request.state.user (if set by auth middleware)
    2. Authorization header (for TEST_MODE or JWT tokens)

    Returns:
        dict with user_id and username, or None if not authenticated
    """
    # Try request.state.user first
    user = getattr(request.state, "user", None)
    if user:
        return user

    # Try to extract from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix

        # Check if in TEST_MODE with raw test-user-XXX token
        try:
            from core.config import TEST_MODE

            if TEST_MODE and token.startswith("test-user-"):
                # Import get_user_by_id to fetch user from DB
                from core.orm.repositories import user_repo

                user_data = await user_repo.get_by_id(token)
                if user_data:
                    return user_data
                # Return mock user if not in DB
                return {
                    "user_id": token,
                    "username": f"TestUser_{token[-3:]}",
                }
        except Exception as e:
            logger.debug(f"Failed to extract test user from token: {e}")

    return None


async def audit_middleware(request: Request, call_next):
    """
    双层审计中间件：文件日志 + 数据库选择性记录

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in the chain

    Returns:
        Response from the next handler
    """
    path = request.url.path.lower()

    # 完全跳过的端点（连日志都不记录）
    SKIP_ALL = {
        "/health",
        "/ready",
        "/validation-key.txt",
        "/static/",
        "/js/",
        "/css/",
        "/images/",
        "/favicon.ico",
        "/ws/",
        "/api/debug-log",
    }

    if any(path.startswith(skip) or skip in path for skip in SKIP_ALL):
        return await call_next(request)

    start_time = time.time()

    # Extract user from request (with TEST_MODE support)
    user = await _extract_user_from_request(request)

    action = _determine_action(request)

    # Process the request
    response = await call_next(request)

    duration_ms = int((time.time() - start_time) * 1000)
    success = 200 <= response.status_code < 400

    # 判断是否需要写入数据库（只有安全敏感操作）
    needs_db = _is_sensitive_action(action, path, request.method)

    if needs_db:
        try:

            async def _log_async():
                AuditLogger.log(
                    action=action,
                    user_id=user.get("user_id") if user else None,
                    username=user.get("username") if user else None,
                    endpoint=str(request.url.path),
                    method=request.method,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    response_code=response.status_code,
                    success=success,
                    duration_ms=duration_ms,
                    metadata={
                        "source": "audit_middleware",
                        "path": str(request.url.path),
                    },
                )

            asyncio.get_running_loop().create_task(_log_async())
        except Exception as e:
            logger.error(f"Database audit logging failed: {e}")
    else:
        # 🟢 普通操作 → 只写入日志文件
        user_info = (
            f"{user.get('username', 'anonymous')}({user.get('user_id', 'N/A')})"
            if user
            else "anonymous"
        )
        status_icon = "✅" if success else "❌"
        logger.info(
            f"{status_icon} {request.method:6} {path:50} | "
            f"user={user_info:20} | {response.status_code} | {duration_ms}ms"
        )

    return response


def _is_sensitive_action(action: str, path: str, method: str) -> bool:
    """
    判断是否为安全敏感操作（需要写入数据库）

    Returns:
        True = 写入数据库, False = 只写日志文件
    """
    normalized_action = AuditLogger._normalize_action(action)

    if AuditLogger.is_sensitive_action(normalized_action):
        return True

    # 根据路径和方法判断
    # 所有 DELETE 操作都记录到数据库
    if method == "DELETE":
        return True

    # 所有论坛发文/评论都记录到数据库
    if method == "POST" and ("/forum/posts" in path or "/forum/comments" in path):
        return True

    # 所有支付相关都记录
    if "/payment" in path or "/tip" in path:
        return True

    # 所有管理员操作都记录
    if "/admin" in path:
        return True

    # 其他操作只写日志文件
    return False


def _determine_action(request: Request) -> str:
    """
    Determine the action name from the request

    This creates a human-readable action name based on the endpoint and method.

    Args:
        request: FastAPI Request object

    Returns:
        Action name string (e.g., "login", "create_post", "get_market_data")
    """
    path = request.url.path.lower()
    method = request.method.lower()

    # Special cases for well-known actions
    if "/login" in path or "/pi-sync" in path:
        return AuditLogger._normalize_action("login")
    if "/logout" in path:
        return AuditLogger._normalize_action("logout")
    if "/payment/approve" in path:
        return AuditLogger._normalize_action("payment_approve")
    if "/payment/complete" in path:
        return AuditLogger._normalize_action("payment_complete")
    if "/premium/upgrade" in path:
        return AuditLogger._normalize_action("upgrade_premium")
    if "/forum/posts" in path and method == "post":
        return AuditLogger._normalize_action("create_post")
    if "/forum/posts" in path and method == "put":
        return AuditLogger._normalize_action("update_post")
    if "/forum/posts" in path and method == "delete":
        return AuditLogger._normalize_action("delete_post")
    if "/forum/comments" in path and method == "post":
        return AuditLogger._normalize_action("add_comment")
    if "/tip" in path:
        return AuditLogger._normalize_action("tip_post")
    if "/friends/request" in path:
        return AuditLogger._normalize_action("send_friend_request")
    if "/scam-tracker/reports" in path and method == "post":
        return AuditLogger._normalize_action("create_scam_report")
    if "/admin" in path:
        return AuditLogger._normalize_action("admin_action")

    # Default: create action from path and method
    # Example: POST /api/market/pulse -> "post_api_market_pulse"
    path_clean = path.strip("/").replace("/", "_").replace("-", "_")
    return AuditLogger._normalize_action(f"{method}_{path_clean}")


async def add_audit_headers(request: Request, call_next):
    """
    Add audit trail ID to response headers (optional middleware)

    This allows clients to track their requests in the audit log.
    """
    response = await call_next(request)

    # Add a correlation ID that can be used to trace this request
    # In production, you might use a proper correlation ID system
    import hashlib
    import time

    trace_id = hashlib.sha256(
        f"{request.client.host if request.client else 'unknown'}"
        f"{request.url.path}{time.time()}".encode()
    ).hexdigest()[:16]

    response.headers["X-Audit-Trace-ID"] = trace_id

    return response
