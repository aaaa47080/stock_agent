# Pre-Production Deployment Checklist

Use this checklist to verify security configuration before deploying to production.

## ✅ Must Complete Before Deployment

### Environment Variables
- [ ] `DATABASE_URL` is set with SSL/TLS connection string
- [ ] `JWT_SECRET_KEY` is set (at least 32 characters) OR `USE_KEY_ROTATION=true`
- [ ] `CORS_ORIGINS` contains specific domains only (NO wildcard `*`)
- [ ] `ENVIRONMENT=production` is set
- [ ] `TEST_MODE` is NOT set or is `false`
- [ ] `ADMIN_API_KEY` is set for admin operations

### Security Configuration
- [ ] HTTPS is enabled with valid SSL certificate
- [ ] Rate limiting is enabled and configured
- [ ] Security headers middleware is active
- [ ] Audit logging is enabled
- [ ] Key rotation is enabled (recommended)
- [ ] Alert channels (Telegram/Email) are configured

### Database Security
- [ ] Database user has minimal required permissions
- [ ] Connection uses SSL/TLS
- [ ] Backup strategy is in place
- [ ] Connection pooling is configured
- [ ] Sensitive data is encrypted at rest

### Application Configuration
- [ ] Debug mode is disabled
- [ ] Error messages don't leak sensitive information
- [ ] Static files have proper cache headers
- [ ] File upload limits are configured
- [ ] Session timeout is configured
- [ ] Kubernetes `ephemeral-storage` requests/limits are configured
- [ ] Namespace `LimitRange` / `ResourceQuota` are applied

## ✅ Post-Deployment Verification

### Health Checks
- [ ] `/health` endpoint returns 200
- [ ] `/ready` endpoint shows all components healthy
- [ ] Database connection is working
- [ ] OKX API connection is working (if applicable)
- [ ] `scripts/post_deploy_smoke.sh` passes against production URL

### Security Verification
- [ ] Security headers are present in responses
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Strict-Transport-Security` (production only)
  - `Content-Security-Policy` (production only)

- [ ] CORS rejects requests from unauthorized origins
- [ ] Rate limiting is working (test with rapid requests)
- [ ] Authentication is working (test login)
- [ ] Alert notifications are working

### Monitoring Verification
- [ ] Security events are being logged
- [ ] Audit logs are being written
- [ ] `/api/admin/security/events` returns events
- [ ] `/api/admin/security/statistics` returns statistics
- [ ] Alert channels (Telegram/Email) receive alerts

## ✅ Regular Maintenance Schedule

### Daily
- [ ] Review security event logs for anomalies
- [ ] Check error logs for issues
- [ ] Verify backup completion

### Weekly
- [ ] Review failed authentication attempts
- [ ] Check rate limit violations
- [ ] Verify alert system functionality
- [ ] Run `scripts/refresh_lock_and_audit.sh` and commit lockfile updates if changed

### Monthly
- [ ] Run security check script: `./scripts/security-check.sh`
- [ ] Review and rotate JWT keys (if using key rotation)
- [ ] Review user access permissions
- [ ] Check for dependency updates
- [ ] Review audit log cleanup

### Quarterly
- [ ] Update all dependencies
- [ ] Run full security audit
- [ ] Review and update security policies
- [ ] Conduct penetration testing (optional)
- [ ] Review incident response procedures

### Annually
- [ ] Full security assessment
- [ ] Review and update threat model
- [ ] Security training for team
- [ ] Review compliance requirements

## 🚨 Emergency Procedures

### If Security Breach is Suspected

1. **Immediately**
   - [ ] Check `/api/admin/security/events` for suspicious activity
   - [ ] Enable additional logging
   - [ ] Notify security team

2. **Within 1 Hour**
   - [ ] Review authentication logs
   - [ ] Check for unusual API usage
   - [ ] Verify data integrity

3. **Within 24 Hours**
   - [ ] Rotate all JWT keys
   - [ ] Force password resets if applicable
   - [ ] Document incident details
   - [ ] Notify affected users if needed

### If Service is Down

1. **Check Services**
   - [ ] Database connection
   - [ ] OKX API status
   - [ ] Server resources (CPU, memory, disk)

2. **Check Logs**
   - [ ] Application logs
   - [ ] Error logs
   - [ ] Security event logs

3. **Restart Services**
   - [ ] Application server
   - [ ] Database connection pool
   - [ ] Background tasks

## 📋 Deployment Steps

### 1. Preparation
```bash
# Run security checks
./scripts/security-check.sh

# Run all tests
pytest tests/ -v

# Create backup
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql
```

### 2. Deploy
```bash
# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations (if any)
python -m alembic upgrade head

# Restart application
systemctl restart pi-crypto-insight
```

### 3. Verification
```bash
# Check health
curl https://yourdomain.com/health

# Post-deploy smoke checks
API_URL=https://yourdomain.com bash scripts/post_deploy_smoke.sh

# Check security headers
curl -I https://yourdomain.com/

# Run security tests
pytest tests/security/ -v
```

## 🔍 Additional Notes

### Kubernetes Storage Baseline
- Namespace baseline: `deploy/k8s/storage-baseline.yaml`
- Deployment patch example: `deploy/k8s/deployment-storage-patch.yaml`

### Backup Strategy
- Database: Daily automated backups
- Keys: Manual backup before rotation
- Config: Version controlled in private repo
- Logs: Retained per compliance requirements

### Monitoring Setup
See [monitoring-setup.md](monitoring-setup.md) for detailed monitoring configuration.

### Kubernetes Storage
See [k8s-storage-runbook.md](k8s-storage-runbook.md) for `ephemeral-storage` baseline and eviction prevention controls.

### Key Rotation
See [key-rotation.md](key-rotation.md) for key rotation procedures.

---

**Last Updated**: 2025-02-08
**Version**: 1.0.0
