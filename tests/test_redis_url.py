from core.redis_url import resolve_redis_url


def test_resolve_redis_url_prefers_explicit_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example-redis:6379/3")
    monkeypatch.setenv("REDIS_HOST", "ignored-host")

    url, source = resolve_redis_url()

    assert source == "REDIS_URL"
    assert url == "redis://example-redis:6379/3"


def test_resolve_redis_url_builds_from_host(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "service-abc")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "0")

    url, source = resolve_redis_url()

    assert source == "REDIS_HOST"
    assert url == "redis://service-abc:6379/0"


def test_resolve_redis_url_empty_when_missing(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)

    url, source = resolve_redis_url()

    assert source == ""
    assert url == ""


def test_resolve_redis_url_builds_auth(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "service-auth")
    monkeypatch.setenv("REDIS_PASSWORD", "pass@word")
    monkeypatch.setenv("REDIS_DB", "1")

    url, source = resolve_redis_url()

    assert source == "REDIS_HOST"
    assert url == "redis://:pass%40word@service-auth:6379/1"
