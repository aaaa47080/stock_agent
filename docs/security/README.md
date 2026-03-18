# Security Documentation

This directory contains comprehensive security documentation for the Pi Crypto Insight platform.

## Overview

The platform implements a layered security architecture with the following components:

### Authentication & Authorization
- Pi Network token validation
- JWT-based session management
- Key rotation system (Stage 3)
- PRO membership verification

### Network Security
- CORS configuration (Stage 1)
- Security headers middleware (Stage 2)
- Rate limiting (Stage 2)
- DDoS protection

### Monitoring & Alerting
- Security event logging (Stage 4)
- Alert dispatcher (Stage 4)
- Admin monitoring API

### Data Protection
- Audit logging
- Input validation
- SQL injection prevention
- XSS protection

## Documentation Files

| File | Description |
|------|-------------|
| [README.md](README.md) | This file - security overview |
| [threat-model.md](threat-model.md) | Threat modeling and risk assessment |
| [incident-response.md](incident-response.md) | Incident response procedures |
| [authentication.md](authentication.md) | Authentication system documentation |
| [key-rotation.md](key-rotation.md) | JWT key rotation guide |
| [monitoring-setup.md](monitoring-setup.md) | Monitoring and alerting setup |
| [deployment-checklist.md](deployment-checklist.md) | Pre-deployment checklist |

## Security Stages

The platform's security improvements are implemented in stages:

1. **Stage 1**: Immediate fixes (CORS, JWT secret, TEST_MODE protection)
2. **Stage 2**: Medium-risk improvements (audit cleanup, error handling, security headers, rate limiting)
3. **Stage 3**: Key rotation system
4. **Stage 4**: Security monitoring & alerts
5. **Stage 5**: Testing & documentation

See the full implementation plan in [`../plans/2026-02-08-security-hardening.md`](../plans/2026-02-08-security-hardening.md).

## Environment Variables

### Required for Production
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Authentication
JWT_SECRET_KEY=your-secret-key-min-32-chars

# Or enable key rotation
USE_KEY_ROTATION=true

# CORS
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Environment
ENVIRONMENT=production
```

### Optional (Monitoring & Alerts)
```bash
# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ADMIN_EMAIL=admin@yourdomain.com
```

## Security Best Practices

### Development
- Never commit `.env` files
- Use environment variables for all secrets
- Enable TEST_MODE only with confirmation
- Run security checks before committing

### Production
- Use HTTPS everywhere
- Enable rate limiting
- Monitor security events daily
- Rotate keys monthly
- Keep dependencies updated

### Incident Response
If you detect a security incident:

1. Immediately review security events: `GET /api/admin/security/events`
2. Check for unusual login attempts
3. Verify key rotation status
4. Enable additional monitoring
5. Follow [incident response procedures](incident-response.md)

## Reporting Security Issues

If you discover a security vulnerability:

1. DO NOT create a public issue
2. Email details to: security@yourdomain.com
3. Include steps to reproduce
4. Allow time for patch before disclosure

## Security Testing

Run the security check script regularly:

```bash
./scripts/security-check.sh
```

This includes:
- Dependency vulnerability scan
- Code security linting
- Security test suite
- Configuration validation
- File permissions check

## Contact

For security questions or concerns:
- Email: security@yourdomain.com
- Internal: #security channel on Slack
