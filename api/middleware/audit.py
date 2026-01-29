"""
Audit Logging Middleware

Automatically logs all API requests for security monitoring and compliance
"""
import time
from fastapi import Request
from core.audit import AuditLogger
from api.utils import logger


async def audit_middleware(request: Request, call_next):
    """
    Middleware to automatically log all API requests
    
    This captures request/response information and logs it to the audit system.
    Automatically tracks timing, user information, and success/failure status.
    
    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in the chain
        
    Returns:
        Response from the next handler
    """
    start_time = time.time()
    
    # Get user from request state (set by auth middleware if authenticated)
    user = getattr(request.state, "user", None)
    
    # Determine action from request
    action = _determine_action(request)
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Determine if this was successful
    success = 200 <= response.status_code < 400
    
    # Log to audit system
    try:
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
            duration_ms=duration_ms
        )
    except Exception as e:
        # Never let audit logging break the application
        logger.error(f"Audit middleware failed: {e}")
    
    return response


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
    if '/login' in path or '/pi-sync' in path:
        return 'login'
    if '/logout' in path:
        return 'logout'
    if '/payment/approve' in path:
        return 'payment_approve'
    if '/payment/complete' in path:
        return 'payment_complete'
    if '/premium/upgrade' in path:
        return 'upgrade_premium'
    if '/forum/posts' in path and method == 'post':
        return 'create_post'
    if '/forum/posts' in path and method == 'put':
        return 'update_post'
    if '/forum/posts' in path and method == 'delete':
        return 'delete_post'
    if '/forum/comments' in path and method == 'post':
        return 'add_comment'
    if '/tip' in path:
        return 'tip_post'
    if '/friends/request' in path:
        return 'send_friend_request'
    if '/admin' in path:
        return 'admin_action'
    
    # Default: create action from path and method
    # Example: POST /api/market/pulse -> "post_api_market_pulse"
    path_clean = path.strip('/').replace('/', '_').replace('-', '_')
    return f"{method}_{path_clean}"


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
    
    trace_id = hashlib.md5(
        f"{request.client.host if request.client else 'unknown'}"
        f"{request.url.path}{time.time()}".encode()
    ).hexdigest()[:16]
    
    response.headers["X-Audit-Trace-ID"] = trace_id
    
    return response
