"""
Comprehensive Audit Logging System

Logs all sensitive operations for security monitoring, compliance, and debugging.
Supports both automatic middleware-based logging and manual action logging.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
import json
from core.database import get_connection
from api.utils import logger


class AuditLogger:
    """
    Centralized audit logging system
    
    Provides methods to log security-sensitive operations to the database
    for compliance, monitoring, and incident investigation.
    """
    
    # Actions that are considered sensitive and require extra attention
    SENSITIVE_ACTIONS = {
        'login', 'logout', 'pi_sync', 'dev_login',
        'payment_approve', 'payment_complete', 'tip_post',
        'upgrade_premium', 'delete_post', 'delete_user',
        'ban_user', 'block_user', 'admin_action',
        'permission_change', 'config_change',
        'create_post', 'update_post', 'send_friend_request'
    }
    
    @staticmethod
    def log(
        action: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_code: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Log an audit event to the database
        
        Args:
            action: The action being performed (e.g., 'login', 'payment_approve')
            user_id: ID of the user performing the action
            username: Username of the user
            resource_type: Type of resource being acted upon (e.g., 'post', 'user')
            resource_id: ID of the specific resource
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            ip_address: Client IP address
            user_agent: Client user agent string
            request_data: Sanitized request data (sensitive fields removed)
            response_code: HTTP response code
            success: Whether the operation succeeded
            error_message: Error message if failed
            duration_ms: Request processing time in milliseconds
            metadata: Additional context-specific data
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Sanitize request data - remove sensitive fields
            if request_data:
                sanitized_data = _sanitize_request_data(request_data)
            else:
                sanitized_data = None
            
            cursor.execute("""
                INSERT INTO audit_logs (
                    user_id, username, action, resource_type, resource_id,
                    endpoint, method, ip_address, user_agent, request_data,
                    response_code, success, error_message, duration_ms, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, username, action, resource_type, resource_id,
                endpoint, method, ip_address, user_agent,
                json.dumps(sanitized_data) if sanitized_data else None,
                response_code, success, error_message, duration_ms,
                json.dumps(metadata) if metadata else None
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Also log sensitive actions to application log
            if action in AuditLogger.SENSITIVE_ACTIONS:
                log_level = "WARNING" if not success else "INFO"
                log_msg = (
                    f"AUDIT [{action}]: user={username}({user_id}), "
                    f"resource={resource_type}/{resource_id}, success={success}"
                )
                if not success and error_message:
                    log_msg += f", error={error_message}"
                
                if log_level == "WARNING":
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)
                
        except Exception as e:
            # Never let audit logging break the application
            logger.error(f"Failed to write audit log for action '{action}': {e}")
    
    @staticmethod
    async def log_from_request(
        request: Request,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Log audit event from FastAPI request object
        
        Convenience method that extracts user and request info automatically.
        
        Args:
            request: FastAPI Request object
            action: The action being performed
            resource_type: Type of resource (optional)
            resource_id: ID of resource (optional)
            success: Whether operation succeeded
            error_message: Error message if failed
            metadata: Additional metadata
        """
        user = getattr(request.state, "user", None)
        
        AuditLogger.log(
            action=action,
            user_id=user.get("user_id") if user else None,
            username=user.get("username") if user else None,
            resource_type=resource_type,
            resource_id=resource_id,
            endpoint=str(request.url.path),
            method=request.method,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=success,
            error_message=error_message,
            metadata=metadata
        )


def _sanitize_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive fields from request data before logging
    
    Args:
        data: Original request data
        
    Returns:
        Sanitized copy with sensitive fields removed or masked
    """
    if not isinstance(data, dict):
        return data
    
    # Fields to completely remove
    SENSITIVE_FIELDS_REMOVE = {
        'password', 'secret', 'token', 'access_token',
        'api_key', 'private_key', 'passphrase',
        'credit_card', 'ssn', 'social_security'
    }
    
    # Fields to mask (show first/last few characters)
    SENSITIVE_FIELDS_MASK = {
        'email', 'phone', 'wallet_address'
    }
    
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Remove sensitive fields
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS_REMOVE):
            sanitized[key] = "[REDACTED]"
            continue
        
        # Mask fields
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS_MASK):
            if isinstance(value, str) and len(value) > 6:
                sanitized[key] = f"{value[:3]}***{value[-3:]}"
            else:
                sanitized[key] = "***"
            continue
        
        # Recursively sanitize nested dicts
        if isinstance(value, dict):
            sanitized[key] = _sanitize_request_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_request_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


# Convenience function for quick logging
def audit_log(action: str, **kwargs):
    """
    Shorthand for audit logging
    
    Usage:
        audit_log("payment_approve", user_id="123", resource_id="pay_456", success=True)
    """
    AuditLogger.log(action, **kwargs)


# Decorator for automatic audit logging
def audit(action: str, resource_type: Optional[str] = None):
    """
    Decorator to automatically audit log a function call
    
    Usage:
        @audit(action="delete_post", resource_type="post")
        async def delete_post(post_id: int, user: dict):
            # ... function implementation
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            # Try to extract user from kwargs
            user = kwargs.get('current_user') or kwargs.get('user')
            resource_id = kwargs.get('post_id') or kwargs.get('user_id') or kwargs.get('id')
            
            try:
                result = await func(*args, **kwargs)
                
                # Log success
                audit_log(
                    action=action,
                    user_id=user.get("user_id") if user else None,
                    username=user.get("username") if user else None,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    success=True,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                
                return result
                
            except Exception as e:
                # Log failure
                audit_log(
                    action=action,
                    user_id=user.get("user_id") if user else None,
                    username=user.get("username") if user else None,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    success=False,
                    error_message=str(e),
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                raise
        
        return wrapper
    return decorator
