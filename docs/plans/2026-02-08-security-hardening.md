# Security Hardening Implementation Plan

**Date**: 2026-02-08
**Status**: Design Approved
**Author**: Claude Code
**Scope**: Long-term Security System Build

---

## Overview

This document outlines a comprehensive security improvement plan for the Pi Crypto Insight platform. The plan addresses security risks identified in the security assessment and implements a robust security framework for long-term protection.

**Target Deployment**: Single Server (Zeabur/Railway/VPS)
**Implementation Strategy**: Phased (Stage by Stage)
**Timeline**: 6-8 weeks

---

## Risk Summary

### High Priority Risks (Production Blocking)

| Risk | Location | Impact | Fix Stage |
|------|----------|--------|-----------|
| CORS allows all origins (`*`) | `api_server.py:195` | Any site can call API | Stage 1 |
| Hardcoded JWT secret fallback | `api/deps.py:13` | Weak authentication | Stage 1 |
| TEST_MODE may enable in prod | `core/config.py:12` | Bypass security checks | Stage 1 |

### Medium Priority Risks

| Risk | Location | Impact | Fix Stage |
|------|----------|--------|-----------|
| Error messages leak details | `api_server.py:154` | Information disclosure | Stage 2 |
| Static files cached too long | `api_server.py:352` | Stale malicious content | Stage 2 |
| No audit log cleanup | - | Storage exhaustion | Stage 2 |
| Missing security headers | - | Multiple vulnerabilities | Stage 2 |

### Long-term Improvements

| Area | Current State | Target State | Fix Stage |
|------|---------------|--------------|-----------|
| Key Management | Static secret | Auto-rotation system | Stage 3 |
| Monitoring | Manual log check | Automated alerts | Stage 4 |
| Testing | Basic tests | Security test suite | Stage 5 |

---

## Stage 1: Immediate Fixes (Production Blocking)

**Timeline**: Week 1
**Priority**: CRITICAL - Must complete before production deployment

### 1.1 CORS Configuration Fix

**File**: `api_server.py`

```python
# Before (INSECURE):
origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://app.minepi.com",
    "*",  # ❌ Allows all origins
]

# After (SECURE):
origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:8080,https://app.minepi.com")
origins = [origin.strip() for origin in origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

**Environment Variable**:
```bash
CORS_ORIGINS=https://yourdomain.com,https://app.minepi.com
```

### 1.2 JWT Secret Key Enforcement

**File**: `api/deps.py`

```python
# Before (INSECURE):
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "INSECURE_DEV_KEY_MUST_REPLACE")

# After (SECURE):
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "🚨 SECURITY: JWT_SECRET_KEY environment variable is required. "
        "Generate a strong key: openssl rand -hex 32"
    )
if len(SECRET_KEY) < 32:
    raise ValueError("🚨 SECURITY: JWT_SECRET_KEY must be at least 32 characters")
```

**Key Generation**:
```bash
openssl rand -hex 32  # Generate secure key
```

### 1.3 TEST_MODE Multi-layer Protection

**File**: `core/config.py`

```python
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

if TEST_MODE:
    env = os.getenv("ENVIRONMENT", "development").lower()
    additional_checks = [
        os.getenv("TEST_MODE_CONFIRMATION") == "I_UNDERSTAND_THE_RISKS",
        os.getenv("TEST_MODE_IP_WHITELIST", "").count(".") == 3
    ]

    if env in ["production", "prod"] or not all(additional_checks):
        raise ValueError(
            "🚨 SECURITY ALERT: TEST_MODE cannot be enabled in production.\n"
            "To enable TEST_MODE in development, set:\n"
            "  TEST_MODE=true\n"
            "  TEST_MODE_CONFIRMATION=I_UNDERSTAND_THE_RISKS\n"
            "  TEST_MODE_IP_WHITELIST=127.0.0.1"
        )
```

**Startup Alert**:
```python
# api_server.py - lifespan function
from core.config import TEST_MODE

if TEST_MODE:
    logger.warning("⚠️⚠️⚠️ TEST_MODE IS ENABLED! THIS SHOULD NOT BE ON IN PRODUCTION! ⚠️⚠️⚠️")
```

**Acceptance Criteria**:
- [ ] CORS rejects requests from unauthorized origins
- [ ] Application fails to start without JWT_SECRET_KEY
- [ ] TEST_MODE cannot be enabled in production environment
- [ ] All tests pass

---

## Stage 2: Medium-Risk Improvements (1-2 weeks)

**Timeline**: Week 2-3
**Priority**: HIGH

### 2.1 Audit Log Cleanup

**File**: `core/audit.py`

```python
from datetime import timedelta

def cleanup_old_logs(days_to_keep: int = 90):
    """Delete audit logs older than specified days"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        cursor.execute("""
            DELETE FROM audit_logs
            WHERE created_at < %s
        """, (cutoff_date,))
        deleted = cursor.rowcount
        conn.commit()
        logger.info(f"🧹 Cleaned up {deleted} old audit logs (older than {days_to_keep} days)")
        return deleted
    finally:
        conn.close()

# Scheduled task
async def audit_log_cleanup_task():
    """Run cleanup daily at 3 AM"""
    import schedule
    while True:
        schedule.every().day.at("03:00").do(
            lambda: await loop.run_in_executor(None, cleanup_old_logs, 90)
        )
        await asyncio.sleep(3600)
```

### 2.2 Error Handling Improvement

**File**: `api_server.py`

```python
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() in ["production", "prod"]

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_msg = f"{type(exc).__name__}: {str(exc)}"

    # Log full details
    logger.error(f"🔥 Unhandled 500 Error at {request.method} {request.url.path}: {error_msg}")
    if not IS_PRODUCTION:
        logger.error(traceback.format_exc())

    # Response varies by environment
    response_content = {
        "detail": "Internal Server Error",
        "error": error_msg if not IS_PRODUCTION else "An error occurred",
        "path": request.url.path
    }

    return JSONResponse(status_code=500, content=response_content)
```

### 2.3 Security Headers Middleware

**File**: `api_server.py`

```python
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.minepi.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.minepi.com"
        )

    return response
```

### 2.4 Persistent Rate Limiting

**File**: `api/middleware/rate_limit.py`

```python
import json
from pathlib import Path

class PersistentRateLimiter:
    def __init__(self, storage_path: str = "data/rate_limits.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(exist_ok=True)
        self._load_state()

    def _load_state(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                self.state = json.load(f)
        else:
            self.state = {}

    def _save_state(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.state, f)

    def check_limit(self, key: str, limit: int, window: int) -> bool:
        now = int(time.time())
        window_start = now - window

        if key not in self.state:
            self.state[key] = []

        self.state[key] = [t for t in self.state[key] if t > window_start]

        if len(self.state[key]) >= limit:
            return False

        self.state[key].append(now)
        self._save_state()
        return True
```

**Acceptance Criteria**:
- [ ] Audit logs auto-cleanup works
- [ ] Production errors hide details
- [ ] All security headers present in responses
- [ ] Rate limits persist across restarts

---

## Stage 3: Key Rotation System (2-4 weeks)

**Timeline**: Week 3-5
**Priority**: HIGH

### 3.1 Architecture: Dual-Key Strategy

- **Primary Key**: Used to sign NEW tokens
- **Deprecated Key**: Still validates OLD tokens (until expiry)
- **Expired Key**: Removed from active validation

### 3.2 KeyRotationManager Class

**File**: `core/key_rotation.py`

```python
import os
import jwt
import secrets
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

class KeyRotationManager:
    """Manages JWT key rotation with dual-key strategy"""

    def __init__(self, config_dir: str = "config/keys"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.config_dir / "jwt_keys.json"
        self.keys = self._load_keys()

    def _load_keys(self) -> Dict:
        """Load all key configurations"""
        if self.keys_file.exists():
            with open(self.keys_file) as f:
                return json.load(f)

        # Initialize: generate primary key
        primary_key = self._generate_key()
        return {
            "primary": primary_key["id"],
            "keys": [primary_key],
            "last_rotation": datetime.utcnow().isoformat()
        }

    def _generate_key(self) -> Dict:
        """Generate a new cryptographic key"""
        key_id = hashlib.sha256(secrets.token_bytes(16)).hexdigest()[:16]
        key_value = secrets.token_urlsafe(32)  # 256-bit

        return {
            "id": key_id,
            "value": key_value,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "status": "active"
        }

    def get_current_key(self) -> str:
        """Get the current primary key"""
        for key in self.keys["keys"]:
            if key["id"] == self.keys["primary"] and key["status"] == "active":
                return key["value"]
        raise RuntimeError("No active primary key found")

    def get_all_active_keys(self) -> Dict[str, str]:
        """Get all active keys for validation"""
        return {
            key["id"]: key["value"]
            for key in self.keys["keys"]
            if key["status"] in ["active", "deprecated"]
        }

    def rotate_key(self) -> Dict:
        """Execute key rotation"""
        old_primary_id = self.keys["primary"]

        # Generate new key
        new_key = self._generate_key()
        self.keys["keys"].append(new_key)

        # Update primary
        self.keys["primary"] = new_key["id"]

        # Deprecate old key
        for key in self.keys["keys"]:
            if key["id"] == old_primary_id:
                key["status"] = "deprecated"
                key["deprecated_at"] = datetime.utcnow().isoformat()

        self.keys["last_rotation"] = datetime.utcnow().isoformat()
        self._save_keys()

        return {
            "old_key_id": old_primary_id,
            "new_key_id": new_key["id"],
            "rotated_at": self.keys["last_rotation"]
        }

    def verify_token_with_any_key(self, token: str) -> Optional[Dict]:
        """Verify token using any active key"""
        all_keys = self.get_all_active_keys()

        for key_id, key_value in all_keys.items():
            try:
                payload = jwt.decode(token, key_value, algorithms=["HS256"])
                payload["_key_id"] = key_id
                return payload
            except jwt.InvalidTokenError:
                continue

        return None

    def _save_keys(self):
        """Save keys with backup"""
        if self.keys_file.exists():
            backup_file = self.config_dir / f"jwt_keys.backup.{int(time.time())}"
            import shutil
            shutil.copy(self.keys_file, backup_file)

        with open(self.keys_file, "w") as f:
            json.dump(self.keys, f, indent=2)

        self.keys_file.chmod(0o600)
```

### 3.3 Integration with JWT Dependencies

**File**: `api/deps.py`

```python
from core.key_rotation import KeyRotationManager

key_manager = KeyRotationManager()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create token with current primary key"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    current_key = key_manager.get_current_key()
    return jwt.encode(to_encode, current_key, algorithm=ALGORITHM)

def verify_token_with_rotation(token: str) -> dict:
    """Verify token using key rotation"""
    payload = key_manager.verify_token_with_any_key(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return payload
```

### 3.4 Auto-Rotation Task

**File**: `api/services.py`

```python
async def key_rotation_task():
    """Auto-rotate keys every 30 days"""
    key_manager = KeyRotationManager()

    def perform_rotation():
        result = key_manager.rotate_key()
        logger.info(f"🔑 Key rotation: {result['old_key_id'][:8]}... -> {result['new_key_id'][:8]}...")
        send_security_alert("Key Rotation Completed", f"JWT key rotated successfully")

    # Schedule for 1st of each month at 2 AM
    import schedule
    schedule.every().month.do(perform_rotation)

    while True:
        schedule.run_pending()
        await asyncio.sleep(3600)
```

### 3.5 Admin API

**File**: `api/routers/security.py`

```python
@router.post("/keys/rotate")
async def manual_rotate_key(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")

    key_manager = KeyRotationManager()
    result = key_manager.rotate_key()

    AuditLogger.log(
        action="key_rotation_manual",
        user_id=current_user["user_id"],
        metadata=result
    )

    return result

@router.get("/keys/status")
async def get_keys_status(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")

    key_manager = KeyRotationManager()
    keys_info = []
    for key in key_manager.keys["keys"]:
        key_copy = key.copy()
        if "value" in key_copy:
            key_copy["value"] = f"{key_copy['value'][:8]}..."
        keys_info.append(key_copy)

    return {
        "primary_id": key_manager.keys["primary"],
        "last_rotation": key_manager.keys["last_rotation"],
        "keys": keys_info
    }
```

**Acceptance Criteria**:
- [ ] New tokens use new key
- [ ] Old tokens remain valid after rotation
- [ ] Manual rotation API works
- [ ] Keys file has correct permissions (0600)
- [ ] Backup files created on rotation

---

## Stage 4: Security Monitoring & Alerts (2-4 weeks)

**Timeline**: Week 4-6
**Priority**: HIGH

### 4.1 Security Event System

**File**: `core/security_monitor.py`

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pathlib import Path

class SecurityEventType(Enum):
    BRUTE_FORCE_ATTEMPT = "brute_force"
    RATE_LIMIT_EXCEEDED = "rate_limit"
    SUSPICIOUS_LOGIN = "suspicious_login"
    TOKEN_THEFT = "token_theft"
    UNUSUAL_ACTIVITY = "unusual_activity"
    FAILED_VERIFICATION = "failed_verification"
    ADMIN_ACCESS = "admin_access"
    KEY_ROTATION = "key_rotation"
    TEST_MODE_ENABLED = "test_mode"

class SeverityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityEvent:
    event_type: SecurityEventType
    severity: SeverityLevel
    title: str
    description: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[Dict] = None
    timestamp: datetime = None
    resolved: bool = False

class SecurityMonitor:
    def __init__(self, storage_path: str = "data/security_events.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: SecurityEvent):
        """Log a security event"""
        event_data = {
            "timestamp": (event.timestamp or datetime.utcnow()).isoformat(),
            "type": event.event_type.value,
            "severity": event.severity.value,
            "title": event.title,
            "description": event.description,
            "user_id": event.user_id,
            "ip_address": event.ip_address,
            "metadata": event.metadata,
            "resolved": event.resolved
        }

        with open(self.storage_path, "a") as f:
            f.write(json.dumps(event_data) + "\n")

        self._check_alerts(event)
        return event_data

    def get_recent_events(self, hours: int = 24) -> List[Dict]:
        """Get recent events"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        events = []

        if not self.storage_path.exists():
            return events

        with open(self.storage_path) as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time >= cutoff:
                        events.append(event)
                except (json.JSONDecodeError, ValueError):
                    continue

        return sorted(events, key=lambda e: e["timestamp"], reverse=True)
```

### 4.2 Alert Dispatcher

**File**: `core/alert_dispatcher.py`

```python
import os
import httpx
import smtplib
from email.mime.text import MIMEText

class AlertDispatcher:
    """Dispatch alerts to multiple channels"""

    def __init__(self):
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.smtp_config = {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT", 587)),
            "username": os.getenv("SMTP_USERNAME"),
            "password": os.getenv("SMTP_PASSWORD"),
        }
        self.admin_email = os.getenv("ADMIN_EMAIL")

    def send(self, channel: str, severity: str, title: str, message: str):
        """Send alert to specified channel"""
        if channel == "telegram":
            self._send_telegram(severity, title, message)
        elif channel == "email":
            self._send_email(severity, title, message)

    def _send_telegram(self, severity: str, title: str, message: str):
        emoji_map = {"low": "🔵", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        emoji = emoji_map.get(severity, "⚪")

        formatted_message = f"{emoji} <b>{title}</b>\n\n{message}"

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"

        with httpx.Client() as client:
            client.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": formatted_message,
                "parse_mode": "HTML"
            })

    def _send_email(self, severity: str, title: str, message: str):
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = f"[{severity.upper()}] {title}"
        msg["From"] = self.smtp_config["username"]
        msg["To"] = self.admin_email

        with smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"]) as server:
            server.starttls()
            server.login(self.smtp_config["username"], self.smtp_config["password"])
            server.send_message(msg)
```

### 4.3 Monitoring API

**File**: `api/routers/security_monitor.py`

```python
from fastapi import APIRouter, Depends, Query
from core.security_monitor import SecurityMonitor

router = APIRouter(prefix="/api/admin/security", tags=["security-monitor"])

@router.get("/events")
async def get_security_events(
    hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")

    monitor = SecurityMonitor()
    events = monitor.get_recent_events(hours=hours)

    return {"events": events, "total": len(events)}

@router.get("/statistics")
async def get_security_statistics(
    days: int = Query(7, ge=1, le=30),
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("is_admin"):
        raise HTTPException(403, "Admin access required")

    monitor = SecurityMonitor()
    stats = monitor.get_statistics(days=days)

    return stats
```

### 4.4 Environment Configuration

```bash
# .env - Alert Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ADMIN_EMAIL=admin@yourdomain.com
```

**Acceptance Criteria**:
- [ ] Security events are logged
- [ ] Alerts sent to Telegram work
- [ ] Alerts sent to email work
- [ ] Monitoring API returns data
- [ ] Dashboard displays events correctly

---

## Stage 5: Testing & Documentation (Ongoing)

**Timeline**: Week 6-8 (and ongoing)
**Priority**: MEDIUM

### 5.1 Security Test Suite

**File**: `tests/security/test_security_hardening.py`

```python
import pytest
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)

class TestSecurityHeaders:
    def test_security_headers_present(self):
        response = client.get("/")
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

class TestAuthentication:
    def test_jwt_secret_required(self):
        import os
        original = os.environ.pop("JWT_SECRET_KEY", None)
        with pytest.raises(ValueError, match="JWT_SECRET_KEY.*required"):
            from api.deps import create_access_token
        if original:
            os.environ["JWT_SECRET_KEY"] = original

class TestRateLimiting:
    def test_login_rate_limit(self):
        for i in range(10):
            response = client.post("/api/user/login", json={
                "username": "test", "password": "wrong"
            })
        assert response.status_code == 429

class TestInputValidation:
    def test_sql_injection_prevention(self):
        payloads = ["'; DROP TABLE users; --", "' OR '1'='1"]
        for payload in payloads:
            response = client.post("/api/user/login", json={
                "username": payload, "password": "test"
            })
            assert response.status_code in [401, 400]
```

### 5.2 Security Check Script

**File**: `scripts/security-check.sh`

```bash
#!/bin/bash
set -e

echo "🔒 Running Security Checks..."

# Dependency vulnerability scan
echo "📦 Checking for vulnerable dependencies..."
pip-audit || true

# Code security scan
echo "🔍 Running bandit security linter..."
bandit -r . -f json -o security-report.json || true

# Run security tests
echo "🧪 Running security tests..."
pytest tests/security/ -v

echo "✅ Security checks complete!"
```

### 5.3 Documentation Structure

```
docs/
├── security/
│   ├── README.md                    # Security overview
│   ├── threat-model.md              # Threat modeling
│   ├── incident-response.md         # Incident response procedures
│   ├── authentication.md            # Authentication documentation
│   ├── key-rotation.md              # Key rotation guide
│   ├── monitoring-setup.md          # Monitoring setup guide
│   └── deployment-checklist.md      # Pre-deployment checklist
```

### 5.4 Deployment Checklist

```markdown
# Pre-Production Deployment Checklist

### Must Complete Before Deployment

- [ ] CORS configured without "*", only specific domains
- [ ] JWT_SECRET_KEY set (at least 32 characters)
- [ ] DATABASE_URL uses SSL/TLS
- [ ] TEST_MODE confirmed as "false"
- [ ] HTTPS enabled with valid certificate
- [ ] Rate limiting enabled and tested
- [ ] All alerts tested and working

### Post-Deployment Verification

- [ ] /health endpoint returns 200
- [ ] Security headers present
- [ ] Alert notifications working
- [ ] Audit logs recording
- [ ] Monitoring dashboard accessible

### Regular Maintenance

- [ ] Monthly: Review security event logs
- [ ] Monthly: Run security-check.sh
- [ ] Quarterly: Update dependencies
- [ ] Quarterly: Review user permissions
- [ ] Annually: Penetration testing
```

**Acceptance Criteria**:
- [ ] All security tests pass
- [ ] Security check script runs without errors
- [ ] Documentation is complete
- [ ] Deployment checklist validated

---

## Implementation Order

```
Week 1: Stage 1 (Immediate Fixes)
  ├─ CORS fix
  ├─ JWT secret enforcement
  └─ TEST_MODE protection

Week 2-3: Stage 2 (Medium-Risk)
  ├─ Audit log cleanup
  ├─ Error handling
  ├─ Security headers
  └─ Persistent rate limiting

Week 3-5: Stage 3 (Key Rotation)
  ├─ KeyRotationManager
  ├─ JWT integration
  ├─ Auto-rotation task
  └─ Admin API

Week 4-6: Stage 4 (Monitoring)
  ├─ Security event system
  ├─ Alert dispatcher
  ├─ Monitoring API
  └─ Dashboard

Week 6-8+: Stage 5 (Testing & Docs)
  ├─ Security test suite
  ├─ Check scripts
  └─ Documentation
```

---

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Critical Vulnerabilities | 3 | 0 | 0 |
| Security Test Coverage | 0% | 80% | >70% |
| Mean Time to Detect (MTTD) | Manual | <5 min | <15 min |
| Mean Time to Respond (MTTR) | N/A | <1 hour | <4 hours |
| Audit Log Retention | Forever | 90 days | 90 days |
| Key Rotation Frequency | Never | Monthly | Quarterly |

---

## Dependencies

### Required Python Packages
```txt
# Add to requirements.txt
secrets  # For key generation
schedule # For scheduled tasks
httpx    # For API calls
```

### External Services
- Telegram Bot (for alerts)
- SMTP Server (for email alerts)
- Optional: SMS API for critical alerts

---

## Rollback Plan

Each stage includes rollback capability:

- **Stage 1-2**: Revert code changes, update environment variables
- **Stage 3**: Restore from key backup files
- **Stage 4**: Disable monitoring tasks
- **Stage 5**: No rollback needed (testing only)

---

## Next Steps

1. Review and approve this design document
2. Create implementation plan with detailed tasks
3. Set up git worktree for isolated development
4. Begin Stage 1 implementation

---

**Document Version**: 1.0
**Last Updated**: 2026-02-08
