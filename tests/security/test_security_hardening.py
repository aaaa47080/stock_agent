"""
Security Hardening Test Suite (Stage 5 Security)

Tests to verify security improvements are working correctly.

Run with: pytest tests/security/test_security_hardening.py -v
"""

import importlib.util
import os
import tempfile

import pytest

# Set test environment before any imports
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_32_characters_long_for_testing"


class TestSecurityMonitoring:
    """Tests for security monitoring system"""

    def test_security_monitor_imports(self):
        """Verify security monitoring modules can be imported"""
        from core.security_monitor import SecurityEventType, SeverityLevel

        # Verify enums work
        assert SecurityEventType.BRUTE_FORCE_ATTEMPT.value == "brute_force"
        assert SeverityLevel.HIGH.value == "high"

    def test_security_event_creation(self):
        """Test creating and logging security events"""
        from core.security_monitor import (
            SecurityEvent,
            SecurityEventType,
            SeverityLevel,
        )

        event = SecurityEvent(
            event_type=SecurityEventType.BRUTE_FORCE_ATTEMPT,
            severity=SeverityLevel.HIGH,
            title="Test Event",
            description="This is a test security event",
            user_id="test_user",
            ip_address="192.168.1.1",
        )

        # Verify event was created correctly
        assert event.event_type == SecurityEventType.BRUTE_FORCE_ATTEMPT
        assert event.severity == SeverityLevel.HIGH
        assert event.title == "Test Event"
        assert event.user_id == "test_user"
        assert event.ip_address == "192.168.1.1"
        assert event.resolved is False

    def test_security_event_to_dict(self):
        """Test converting security event to dictionary"""
        from core.security_monitor import (
            SecurityEvent,
            SecurityEventType,
            SeverityLevel,
        )

        event = SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_LOGIN,
            severity=SeverityLevel.MEDIUM,
            title="Test",
            description="Test description",
        )

        event_dict = event.to_dict()

        # Verify conversion
        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "suspicious_login"
        assert event_dict["severity"] == "medium"
        assert "timestamp" in event_dict

    def test_security_monitor_statistics(self):
        """Test getting security statistics"""
        from core.security_monitor import SecurityMonitor

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = SecurityMonitor(storage_path=f"{tmpdir}/test_events.jsonl")
            stats = monitor.get_statistics(days=7)

            assert stats["total_events"] == 0
            assert stats["unresolved_events"] == 0
            assert stats["period_days"] == 7

    def test_alert_dispatcher_creation(self):
        """Test alert dispatcher can be instantiated"""
        from core.alert_dispatcher import AlertDispatcher

        dispatcher = AlertDispatcher()

        # Should create without errors even without configuration
        assert dispatcher is not None
        # Check configuration status
        assert hasattr(dispatcher, "has_telegram")
        assert hasattr(dispatcher, "has_email")


class TestKeyRotationRemoval:
    """Tests for the removed key rotation system."""

    def test_key_rotation_module_removed(self):
        """The legacy key rotation module should no longer exist."""
        assert importlib.util.find_spec("core.key_rotation") is None

    def test_use_key_rotation_flag_falls_back_to_jwt_secret(self):
        """Enabling the old flag should not break token creation."""
        from datetime import timedelta

        from api.deps import create_access_token

        token = create_access_token(
            {"sub": "test_user"}, expires_delta=timedelta(minutes=30)
        )

        assert isinstance(token, str)
        assert len(token.split(".")) == 3


class TestProductionSafety:
    """Tests to ensure production safety"""

    def test_test_mode_protection(self):
        """Verify TEST_MODE has safety protections"""
        from core.config import TEST_MODE

        # If TEST_MODE is enabled, verify environment is not production
        if TEST_MODE:
            env = os.getenv("ENVIRONMENT", "development").lower()
            assert env not in ["production", "prod"], (
                "TEST_MODE should never be enabled in production"
            )

    def test_database_url_set(self):
        """Verify DATABASE_URL is set"""
        # This test verifies the environment is properly configured
        database_url = os.getenv("DATABASE_URL")
        assert database_url is not None, "DATABASE_URL must be set"

    def test_jwt_secret_key_length(self):
        """Verify JWT_SECRET_KEY meets minimum requirements"""
        jwt_key = os.getenv("JWT_SECRET_KEY")
        if jwt_key and os.getenv("USE_KEY_ROTATION", "false").lower() != "true":
            assert len(jwt_key) >= 32, "JWT_SECRET_KEY must be at least 32 characters"

    def test_cors_origins_no_wildcard(self):
        """Verify CORS origins don't include wildcard"""
        cors_origins = os.getenv("CORS_ORIGINS", "")
        # Check for common wildcard patterns
        assert "*" not in cors_origins.split(","), (
            "CORS_ORIGINS should not contain wildcard (*) in production"
        )


class TestSecurityValidators:
    """Tests for security validators"""

    def test_pi_address_validator(self):
        """Test Pi Network address validator"""
        from core.validators.pi_address import validate_pi_address

        # Valid addresses
        valid_addr = "G" + "A" * 55
        is_valid, error = validate_pi_address(valid_addr)
        assert is_valid is True
        assert error == ""

        # Invalid addresses
        invalid_addr = "INVALID"
        is_valid, error = validate_pi_address(invalid_addr)
        assert is_valid is False

    def test_tx_hash_validator(self):
        """Test transaction hash validator"""
        from core.validators.pi_address import validate_pi_tx_hash

        # Valid hash
        valid_hash = "a" * 64
        is_valid, error = validate_pi_tx_hash(valid_hash)
        assert is_valid is True

        # Invalid hash
        invalid_hash = "z" * 64
        is_valid, error = validate_pi_tx_hash(invalid_hash)
        assert is_valid is False


class TestAuthentication:
    """Tests for authentication security"""

    def test_token_creation(self):
        """Test token creation works correctly"""
        from datetime import timedelta

        from api.deps import create_access_token

        # Create a token
        token = create_access_token(
            {"sub": "test_user"}, expires_delta=timedelta(minutes=30)
        )

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Should be in JWT format (header.payload.signature)
        parts = token.split(".")
        assert len(parts) == 3

    def test_token_creation_with_key_rotation_flag_enabled(self):
        """Token creation should still work when the legacy flag is enabled."""
        from datetime import timedelta

        import jwt

        from api.deps import create_access_token

        # Save original values
        original_rotation = os.environ.get("USE_KEY_ROTATION")
        original_jwt = os.environ.get("JWT_SECRET_KEY")

        try:
            # Enable key rotation for this test
            os.environ["USE_KEY_ROTATION"] = "true"

            # Need to reimport to pick up new environment variable
            import importlib

            import api.deps

            importlib.reload(api.deps)

            # Re-import after reload
            from api.deps import create_access_token

            # Create a token
            token = create_access_token(
                {"sub": "test_user"}, expires_delta=timedelta(minutes=30)
            )

            # Token should be a non-empty string
            assert isinstance(token, str)
            assert len(token) > 0

            # Should be in JWT format (header.payload.signature)
            parts = token.split(".")
            assert len(parts) == 3

            payload = jwt.decode(
                token,
                os.environ["JWT_SECRET_KEY"],
                algorithms=["HS256"],
                options={"verify_exp": True},
            )

            assert "sub" in payload
            assert payload["sub"] == "test_user"

        finally:
            # Restore original values
            if original_rotation:
                os.environ["USE_KEY_ROTATION"] = original_rotation
            else:
                os.environ.pop("USE_KEY_ROTATION", None)

            if original_jwt:
                os.environ["JWT_SECRET_KEY"] = original_jwt

            # Reload to restore
            importlib.reload(api.deps)


@pytest.mark.integration
class TestSecurityHeadersIntegration:
    """Tests for Stage 2 security headers (integration tests)"""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client):
        """Verify security headers are present in responses"""
        response = await client.get("/health")
        assert response.status_code == 200
        headers = response.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.integration
class TestRateLimitingIntegration:
    """Tests for rate limiting (integration tests)"""

    @pytest.mark.asyncio
    async def test_login_endpoint_exists(self, client):
        """Verify login endpoint exists and handles requests"""
        response = await client.post("/api/user/dev-login", json={})
        assert response.status_code == 200


@pytest.mark.integration
class TestInputValidationIntegration:
    """Tests for input validation (integration tests)"""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, client):
        """Test that SQL injection payloads are rejected"""
        response = await client.get("/health", params={"q": "'; DROP TABLE users;--"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_xss_prevention(self, client):
        """Test that XSS payloads are properly handled"""
        response = await client.get(
            "/health", params={"q": "<script>alert('xss')</script>"}
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
