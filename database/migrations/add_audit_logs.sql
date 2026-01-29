-- ================================================================
-- Audit Logging System Database Schema
-- Created: 2026-01-29
-- Purpose: Track all sensitive operations for security monitoring
-- ================================================================

-- Main audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- User information
    user_id VARCHAR(255),
    username VARCHAR(255),
    
    -- Action details
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    
    -- Request details
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Request/Response data
    request_data JSONB,
    response_code INTEGER,
    
    -- Status
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    -- Performance
    duration_ms INTEGER,
    
    -- Additional metadata
    metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ================================================================
-- Indexes for query performance
-- ================================================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- Action-based queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- Endpoint tracking
CREATE INDEX IF NOT EXISTS idx_audit_logs_endpoint ON audit_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_audit_logs_method ON audit_logs(method);

-- Security monitoring - sensitive actions
CREATE INDEX IF NOT EXISTS idx_audit_logs_sensitive ON audit_logs(action, success) 
WHERE action IN ('login', 'pi_sync', 'payment_approve', 'payment_complete', 
                 'delete_post', 'delete_user', 'ban_user', 'admin_action', 
                 'permission_change', 'config_change');

-- Failed operations for security alerts
CREATE INDEX IF NOT EXISTS idx_audit_logs_failures ON audit_logs(timestamp DESC, user_id) 
WHERE success = FALSE;

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_time ON audit_logs(user_id, timestamp DESC);

-- ================================================================
-- Views for common queries
-- ================================================================

-- Recent failed logins (potential brute force attacks)
CREATE OR REPLACE VIEW v_failed_logins AS
SELECT 
    user_id,
    username,
    ip_address,
    COUNT(*) as failure_count,
    MAX(timestamp) as last_attempt,
    array_agg(DISTINCT endpoint) as endpoints_tried
FROM audit_logs
WHERE action IN ('login', 'pi_sync', 'dev_login')
  AND success = FALSE
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY user_id, username, ip_address
HAVING COUNT(*) >= 3
ORDER BY failure_count DESC;

-- Suspicious payment activity
CREATE OR REPLACE VIEW v_suspicious_payments AS
SELECT 
    user_id,
    username,
    COUNT(*) as failed_payment_count,
    SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successful_payments,
    MAX(timestamp) as last_activity,
    array_agg(DISTINCT error_message) FILTER (WHERE error_message IS NOT NULL) as errors
FROM audit_logs
WHERE action IN ('payment_approve', 'payment_complete', 'tip_post')
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY user_id, username
HAVING COUNT(*) > 10 OR SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) > 5
ORDER BY failed_payment_count DESC;

-- Admin actions log
CREATE OR REPLACE VIEW v_admin_actions AS
SELECT 
    id,
    timestamp,
    user_id,
    username,
    action,
    resource_type,
    resource_id,
    success,
    error_message,
    endpoint
FROM audit_logs
WHERE action LIKE '%admin%' OR endpoint LIKE '%/admin/%'
ORDER BY timestamp DESC
LIMIT 1000;

-- Recent high-value operations
CREATE OR REPLACE VIEW v_high_value_operations AS
SELECT 
    timestamp,
    user_id,
    username,
    action,
    resource_type,
    resource_id,
    ip_address,
    success
FROM audit_logs
WHERE action IN (
    'payment_approve', 'payment_complete', 'upgrade_premium',
    'delete_post', 'ban_user', 'admin_action', 'config_change'
)
ORDER BY timestamp DESC
LIMIT 500;

-- ================================================================
-- Functions for automated cleanup
-- ================================================================

-- Function to archive old audit logs (keep last 90 days)
CREATE OR REPLACE FUNCTION archive_old_audit_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_logs
    WHERE timestamp < NOW() - INTERVAL '90 days'
      AND success = TRUE  -- Keep all failures for security review
      AND action NOT IN ('payment_approve', 'payment_complete');  -- Keep all payments
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- Comments for documentation
-- ================================================================

COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail of all API operations';
COMMENT ON COLUMN audit_logs.action IS 'Type of action performed (e.g., login, payment_approve, delete_post)';
COMMENT ON COLUMN audit_logs.resource_type IS 'Type of resource affected (e.g., post, user, payment)';
COMMENT ON COLUMN audit_logs.resource_id IS 'ID of the specific resource affected';
COMMENT ON COLUMN audit_logs.request_data IS 'Sanitized request data (sensitive fields removed)';
COMMENT ON COLUMN audit_logs.metadata IS 'Additional context-specific data';
COMMENT ON COLUMN audit_logs.duration_ms IS 'Request processing time in milliseconds';

-- ================================================================
-- Grant permissions (adjust for your database users)
-- ================================================================

-- GRANT SELECT ON audit_logs TO app_readonly;
-- GRANT INSERT ON audit_logs TO app_writer;
-- GRANT ALL ON audit_logs TO app_admin;

-- ================================================================
-- Usage Examples
-- ================================================================

/*
-- Query failed login attempts in last hour
SELECT * FROM v_failed_logins;

-- Query specific user's activity
SELECT * FROM audit_logs WHERE user_id = 'user123' ORDER BY timestamp DESC LIMIT 50;

-- Query all payment operations
SELECT * FROM audit_logs WHERE action LIKE '%payment%' ORDER BY timestamp DESC;

-- Query failed operations by IP
SELECT ip_address, COUNT(*) as failure_count
FROM audit_logs
WHERE success = FALSE AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY ip_address
ORDER BY failure_count DESC;

-- Archive old logs
SELECT archive_old_audit_logs();
*/
