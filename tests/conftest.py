"""
Pytest configuration and fixtures
"""

import os
from unittest.mock import AsyncMock

os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
for _key in list(os.environ):
    if _key.startswith("POSTGRESQL_") or _key == "POSTGRES_DB":
        os.environ.pop(_key)
os.environ["REDIS_URL"] = "memory://"
for _key in list(os.environ):
    if _key.startswith("REDIS_") and _key != "REDIS_URL":
        os.environ.pop(_key)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-1234567890")
os.environ.setdefault("PI_API_KEY", "test-pi-api-key")
os.environ.setdefault("PI_WALLET_PRIVATE_SEED", "test-wallet-seed")
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("TEST_MODE_CONFIRMATION", "I_UNDERSTAND_THE_RISKS")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("ENVIRONMENT", "development")


import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    from api_server import app

    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    from api.deps import create_access_token

    token = create_access_token(data={"sub": "test-user-001"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return {"X-Admin-Key": os.getenv("ADMIN_API_KEY", "test-admin-key")}


@pytest.fixture
def mock_llm_client():
    return AsyncMock()
