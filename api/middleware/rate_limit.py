"""
API Rate Limiting Middleware

Implements per-IP and per-user rate limiting to prevent API abuse and DDoS attacks
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from typing import Callable

def get_user_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting
    - Use user_id from JWT if authenticated
    - Fallback to IP address for unauthenticated requests
    """
    # Try to get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        user_id = user.get('user_id', 'unknown')
        return f"user:{user_id}"
    
    # Fallback to IP address for unauthenticated requests
    ip = get_remote_address(request)
    return f"ip:{ip}"


# Initialize rate limiter
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["1000/hour", "100/minute"],  # Global default limits
    storage_uri="memory://",  # Use in-memory storage (or redis:// for distributed systems)
    strategy="fixed-window"  # Fixed window strategy
)


# Custom rate limits for different endpoint types
RATE_LIMITS = {
    # Authentication endpoints (very strict to prevent brute force)
    "auth": "5/minute",
    
    # Write operations (stricter)
    "write": "30/minute",
    
    # Payment operations (strict to prevent abuse)
    "payment": "10/minute",
    
    # Read operations (more lenient)
    "read": "100/minute",
    
    # Admin operations (moderate)
    "admin": "50/hour",
    
    # Public endpoints (lenient)
    "public": "200/minute",
}


def get_rate_limit_for_route(request: Request) -> str:
    """
    Determine appropriate rate limit based on route and method
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limit string (e.g., "30/minute")
    """
    method = request.method.lower()
    path = request.url.path.lower()
    
    # Authentication endpoints
    if any(x in path for x in ['/login', '/pi-sync', '/dev-login']):
        return RATE_LIMITS["auth"]
    
    # Payment endpoints
    if '/payment' in path or '/tip' in path:
        return RATE_LIMITS["payment"]
    
    # Admin endpoints
    if '/admin' in path:
        return RATE_LIMITS["admin"]
    
    # Write operations
    if method in ['post', 'put', 'patch', 'delete']:
        return RATE_LIMITS["write"]
    
    # Public read endpoints (forum, market data)
    if any(x in path for x in ['/forum/posts', '/forum/boards', '/market', '/agents/']):
        return RATE_LIMITS["public"]
    
    # Default read operations
    if method == 'get':
        return RATE_LIMITS["read"]
    
    # Default fallback
    return "100/minute"


# Exception handler for rate limit exceeded
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors
    
    Returns a JSON response with retry information
    """
    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down and try again later.",
            "retry_after": exc.retry_after,
            "limit": str(exc.limit),
        },
        headers={
            "Retry-After": str(exc.retry_after),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
        }
    )
