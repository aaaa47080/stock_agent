"""
Market Router Module
Combines REST API and WebSocket endpoints for market data
"""
from fastapi import APIRouter

# Import and combine routers
from .rest import router as rest_router
from .websocket import router as websocket_router
from .helpers import SYMBOL_CACHE

# Create main router
router = APIRouter()
router.include_router(rest_router)
router.include_router(websocket_router)

# Re-export for backward compatibility
__all__ = ["router", "SYMBOL_CACHE"]
