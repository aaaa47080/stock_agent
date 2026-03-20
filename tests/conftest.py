"""
Pytest configuration and fixtures
"""

import os

# Set test environment variables before any imports
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-1234567890")
os.environ.setdefault("PI_API_KEY", "test-pi-api-key")
os.environ.setdefault("PI_WALLET_PRIVATE_SEED", "test-wallet-seed")
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("TEST_MODE_CONFIRMATION", "I_UNDERSTAND_THE_RISKS")


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (requires database)"
    )
    config.addinivalue_line("markers", "slow: Slow running tests")
