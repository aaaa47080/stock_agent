"""Middleware registration — CORS, GZip, rate limiting, security headers, etc."""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.utils import logger


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware and exception handlers on the FastAPI app."""

    # 🔒 Security: Stage 2 - Production environment detection
    is_production = os.getenv("ENVIRONMENT", "development").lower() in [
        "production",
        "prod",
    ]

    # --- Global Exception Handler (Fix 500 Internal Server Error) ---
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catch-all exception handler to ensure all 500 errors return JSON
        and are properly logged with traceback.

        Stage 2 Security: Hide error details in production to prevent
        information leakage.
        """
        import traceback

        error_msg = f"{type(exc).__name__}: {str(exc)}"

        # Log full details for debugging
        logger.error(
            f"🔥 Unhandled 500 Error at {request.method} {request.url.path}: {error_msg}"
        )
        if not is_production:
            logger.error(traceback.format_exc())

        # Response varies by environment - hide details in production
        response_content = {
            "detail": "Internal Server Error",
            "error": error_msg if not is_production else "An error occurred",
            "path": request.url.path,
        }

        return JSONResponse(status_code=500, content=response_content)

    # ================================================================
    # Security Enhancements (Phase 7)
    # ================================================================

    # --- 1. Rate Limiting ---
    try:
        from slowapi.errors import RateLimitExceeded

        from api.middleware.rate_limit import limiter, rate_limit_exceeded_handler

        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
        logger.info("✅ Rate limiting enabled")
    except ImportError as e:
        logger.warning(f"⚠️ Rate limiting not available: {e}")
        logger.warning("Install slowapi: pip install slowapi")

    # --- 2. Audit Logging Middleware ---
    try:
        from api.middleware.audit import audit_middleware

        @app.middleware("http")
        async def audit_logging(request, call_next):
            """Audit all API requests"""
            return await audit_middleware(request, call_next)

        logger.info("✅ Audit logging enabled")
    except ImportError as e:
        logger.warning(f"⚠️ Audit logging not available: {e}")

    # --- 3. CORS ---
    # 🔒 Security: Read allowed origins from environment variable
    # Default to localhost for development, production MUST override this
    _cors_origins_raw = os.getenv(
        "CORS_ORIGINS", "http://localhost:8080,https://app.minepi.com"
    )
    origins = [
        origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()
    ]

    # Security check: warn if wildcard is accidentally configured
    if "*" in origins or "" in origins:
        logger.warning(
            "⚠️ SECURITY: Wildcard CORS origin detected!"
            " This should NOT be used in production."
        )

    logger.info(f"🔒 CORS allowed origins: {origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-OKX-API-KEY",
            "X-OKX-SECRET-KEY",
            "X-OKX-PASSPHRASE",
        ],
    )

    # --- 4. GZip Compression (Performance Optimization) ---
    # 自動壓縮大於1KB的響應，減少帶寬消耗，提升加載速度
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    logger.info("✅ GZip compression enabled")

    # --- 5. Security Headers Middleware (Stage 2 Security) ---
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """
        Stage 2 Security: Add security headers to all responses.

        Headers added:
        - X-Content-Type-Options: Prevent MIME type sniffing
        - X-Frame-Options: Prevent clickjacking
        - X-XSS-Protection: Enable XSS filter
        - Referrer-Policy: Control referrer information
        - Strict-Transport-Security (production): Force HTTPS
        - Content-Security-Policy (production): Control resource loading
        """
        response = await call_next(request)

        # Prevent static assets from being cached
        # (avoids stale JS/CSS after deploys)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        # Basic security headers (always on)
        response.headers["X-Content-Type-Options"] = "nosniff"
        # X-Frame-Options intentionally omitted — Pi Browser loads DApps in
        # WebView; frame-ancestors is controlled via CSP below.
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Production-only headers (require HTTPS)
        if is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                # Pi SDK + CDN libraries (no cdn.tailwindcss.com — migrated to local build)
                "script-src 'self' 'unsafe-inline' https://sdk.minepi.com "
                "https://cdn.minepi.com https://cdn.jsdelivr.net https://unpkg.com "
                "https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
                "https://unpkg.com https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                # Pi API + WebSocket + external data sources
                "connect-src 'self' https://api.minepi.com https://sdk.minepi.com "
                "wss: ws:; "
                # Allow Pi Browser / Pi Sandbox to embed this app
                "frame-ancestors 'self' https://app.minepi.com "
                "https://sandbox.minepi.com"
            )

        return response

    logger.info("✅ Security headers enabled")
