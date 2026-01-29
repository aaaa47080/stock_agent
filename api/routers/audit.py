"""
Audit Log Query and Analysis API (Admin Only)

Provides endpoints for administrators to query, analyze, and monitor audit logs
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from api.routers.admin import verify_admin_key
from core.database import get_connection
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/audit", tags=["Audit Logs"])


class AuditLogEntry(BaseModel):
    """Audit log entry model"""
    id: int
    timestamp: datetime
    user_id: Optional[str]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    endpoint: str
    method: str
    ip_address: Optional[str]
    response_code: Optional[int]
    success: bool
    error_message: Optional[str]
    duration_ms: Optional[int]


@router.get("/logs", dependencies=[Depends(verify_admin_key)])
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[datetime] = Query(None, description="Start date for time range"),
    end_date: Optional[datetime] = Query(None, description="End date for time range"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(100, le=1000, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """
    Get audit logs with optional filtering
    
    Returns a paginated list of audit log entries matching the specified criteria.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build query with filters
        query = """
            SELECT id, timestamp, user_id, username, action, resource_type, resource_id,
                   endpoint, method, ip_address, response_code, success, error_message, duration_ms
            FROM audit_logs 
            WHERE 1=1
        """
        params = []
        
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        if action:
            query += " AND action = %s"
            params.append(action)
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        if success is not None:
            query += " AND success = %s"
            params.append(success)
        
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Get total count
        count_query = "SELECT COUNT(*) FROM audit_logs WHERE 1=1"
        if user_id:
            count_query += " AND user_id = %s"
        if action:
            count_query += " AND action = %s"
        if start_date:
            count_query += " AND timestamp >= %s"
        if end_date:
            count_query += " AND timestamp <= %s"
        if success is not None:
            count_query += " AND success = %s"
        
        cursor.execute(count_query, params[:-2])  # Exclude limit and offset
        total_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "logs": logs,
            "count": len(logs),
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query audit logs: {str(e)}")


@router.get("/suspicious", dependencies=[Depends(verify_admin_key)])
async def get_suspicious_activity(
    days: int = Query(7, le=30, description="Number of days to look back")
):
    """
    Get suspicious activity patterns
    
    Identifies potential security issues such as:
    - Multiple failed login attempts
    - High volume of failed operations
    - Unusual access patterns
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        # Failed login attempts
        cursor.execute("""
            SELECT user_id, username, ip_address, COUNT(*) as failure_count
            FROM audit_logs
            WHERE success = FALSE
            AND timestamp >= %s
            AND action IN ('login', 'pi_sync', 'dev_login')
            GROUP BY user_id, username, ip_address
            HAVING COUNT(*) >= 3
            ORDER BY failure_count DESC
        """, (since,))
        
        columns = [desc[0] for desc in cursor.description]
        failed_logins = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Failed payment attempts
        cursor.execute("""
            SELECT user_id, username, COUNT(*) as failure_count,
                   array_agg(DISTINCT error_message) as errors
            FROM audit_logs
            WHERE success = FALSE
            AND timestamp >= %s
            AND action IN ('payment_approve', 'payment_complete')
            GROUP BY user_id, username
            HAVING COUNT(*) >= 3
            ORDER BY failure_count DESC
        """, (since,))
        
        columns = [desc[0] for desc in cursor.description]
        failed_payments = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return {
            "time_range_days": days,
            "failed_logins": failed_logins,
            "failed_payments": failed_payments,
            "alert_count": len(failed_logins) + len(failed_payments)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze suspicious activity: {str(e)}")


@router.get("/user/{user_id}", dependencies=[Depends(verify_admin_key)])
async def get_user_activity(
    user_id: str,
    days: int = Query(7, le=90, description="Number of days to retrieve"),
    limit: int = Query(100, le=1000)
):
    """
    Get complete activity history for a specific user
    
    Useful for investigating user behavior or troubleshooting issues.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT id, timestamp, action, resource_type, resource_id, endpoint, 
                   method, response_code, success, error_message, duration_ms
            FROM audit_logs
            WHERE user_id = %s AND timestamp >= %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (user_id, since, limit))
        
        columns = [desc[0] for desc in cursor.description]
        logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_actions,
                SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successful_actions,
                SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as failed_actions,
                AVG(duration_ms) as avg_duration_ms,
                COUNT(DISTINCT DATE(timestamp)) as active_days
            FROM audit_logs
            WHERE user_id = %s AND timestamp >= %s
        """, (user_id, since))
        
        stats_row = cursor.fetchone()
        stats = {
            "total_actions": stats_row[0] or 0,
            "successful_actions": stats_row[1] or 0,
            "failed_actions": stats_row[2] or 0,
            "avg_duration_ms": round(stats_row[3], 2) if stats_row[3] else 0,
            "active_days": stats_row[4] or 0
        }
        
        cursor.close()
        conn.close()
        
        return {
            "user_id": user_id,
            "time_range_days": days,
            "logs": logs,
            "statistics": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user activity: {str(e)}")


@router.get("/stats", dependencies=[Depends(verify_admin_key)])
async def get_audit_stats(
    days: int = Query(7, le=90, description="Number of days for statistics")
):
    """
    Get overall audit log statistics
    
    Provides system-wide metrics for monitoring and analysis.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        # Overall statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT ip_address) as unique_ips,
                SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as failed_requests,
                AVG(duration_ms) as avg_duration_ms,
                MAX(duration_ms) as max_duration_ms
            FROM audit_logs
            WHERE timestamp >= %s
        """, (since,))
        
        stats_row = cursor.fetchone()
        overall_stats = {
            "total_requests": stats_row[0] or 0,
            "unique_users": stats_row[1] or 0,
            "unique_ips": stats_row[2] or 0,
            "successful_requests": stats_row[3] or 0,
            "failed_requests": stats_row[4] or 0,
            "avg_duration_ms": round(stats_row[5], 2) if stats_row[5] else 0,
            "max_duration_ms": stats_row[6] or 0
        }
        
        # Top actions
        cursor.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= %s
            GROUP BY action
            ORDER BY count DESC
            LIMIT 10
        """, (since,))
        
        top_actions = [{"action": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return{
            "time_range_days": days,
            "overall": overall_stats,
            "top_actions": top_actions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit statistics: {str(e)}")
