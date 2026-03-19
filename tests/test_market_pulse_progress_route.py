"""Regression tests for market-pulse route ordering."""

from api.routers.market.rest import router as market_rest_router


def test_progress_route_is_registered_before_symbol_route():
    """Static /progress route must precede dynamic /{symbol} route to avoid 422s."""
    routes = [route.path for route in market_rest_router.routes]

    assert "/api/market-pulse/progress" in routes
    assert "/api/market-pulse/{symbol}" in routes
    assert routes.index("/api/market-pulse/progress") < routes.index(
        "/api/market-pulse/{symbol}"
    )
