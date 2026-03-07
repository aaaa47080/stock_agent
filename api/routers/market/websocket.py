"""
Market WebSocket Endpoints
Real-time K-line and Ticker data streaming
"""
import asyncio
import json
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.utils import logger

router = APIRouter()


# ============================================================================
# K-line WebSocket Manager
# ============================================================================

class KlineConnectionManager:
    """Manage K-line WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: dict = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.debug(f"K-line WebSocket connected, total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.debug(f"K-line WebSocket disconnected, total: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, symbol: str, interval: str):
        self.subscriptions[websocket] = {"symbol": symbol, "interval": interval}
        logger.debug(f"Client subscribed: {symbol} {interval}")

    def unsubscribe(self, websocket: WebSocket):
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    async def broadcast_kline(self, symbol: str, interval: str, kline: dict):
        """Broadcast K-line data to subscribed clients."""
        for ws, sub in list(self.subscriptions.items()):
            if sub["symbol"].upper() == symbol.upper() and sub["interval"] == interval:
                try:
                    await ws.send_json({
                        "type": "kline",
                        "symbol": symbol,
                        "interval": interval,
                        "data": kline
                    })
                except Exception as e:
                    logger.error(f"Broadcast failed: {e}")


kline_manager = KlineConnectionManager()
okx_ws_started = False


async def start_okx_websocket():
    """Start OKX WebSocket connection for K-lines."""
    global okx_ws_started
    if okx_ws_started:
        return

    try:
        from data.okx_websocket import okx_ws_manager
        okx_ws_started = True
        await okx_ws_manager.start()
    except ImportError as e:
        logger.error(f"Cannot import OKX WebSocket module: {e}")
    except Exception as e:
        logger.error(f"Failed to start OKX WebSocket: {e}")


@router.websocket("/ws/klines")
async def websocket_klines(websocket: WebSocket):
    """
    WebSocket endpoint for real-time K-line data.

    Client subscription format:
    {"action": "subscribe", "symbol": "BTC", "interval": "1m"}
    {"action": "unsubscribe"}
    """
    await kline_manager.connect(websocket)

    try:
        from data.okx_websocket import okx_ws_manager

        asyncio.create_task(start_okx_websocket())

        current_subscription = None

        async def on_kline_update(symbol: str, interval: str, kline: dict):
            """Callback when OKX K-line updates."""
            try:
                await websocket.send_json({
                    "type": "kline",
                    "symbol": symbol,
                    "interval": interval,
                    "data": kline
                })
            except Exception as e:
                logger.debug(f"Failed to send kline update: {e}")

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "subscribe":
                    symbol = message.get("symbol", "BTC").upper()
                    interval = message.get("interval", "1m")

                    if current_subscription:
                        old_symbol, old_interval = current_subscription
                        await okx_ws_manager.unsubscribe(old_symbol, old_interval, on_kline_update)

                    kline_manager.subscribe(websocket, symbol, interval)
                    await okx_ws_manager.subscribe(symbol, interval, on_kline_update)
                    current_subscription = (symbol, interval)

                    await websocket.send_json({
                        "type": "subscribed",
                        "symbol": symbol,
                        "interval": interval
                    })

                elif action == "unsubscribe":
                    if current_subscription:
                        old_symbol, old_interval = current_subscription
                        await okx_ws_manager.unsubscribe(old_symbol, old_interval, on_kline_update)
                        current_subscription = None

                    kline_manager.unsubscribe(websocket)
                    await websocket.send_json({"type": "unsubscribed"})

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info("K-line WebSocket client disconnected")
    except Exception as e:
        logger.error(f"K-line WebSocket error: {e}")
    finally:
        if current_subscription:
            try:
                from data.okx_websocket import okx_ws_manager
                old_symbol, old_interval = current_subscription
                await okx_ws_manager.unsubscribe(old_symbol, old_interval)
            except Exception as e:
                logger.debug(f"Failed to cleanup kline subscription: {e}")
        kline_manager.disconnect(websocket)


# ============================================================================
# Ticker WebSocket Manager
# ============================================================================

class TickerConnectionManager:
    """Manage Ticker WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscribed_symbols: dict = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscribed_symbols[websocket] = set()
        logger.debug(f"Ticker WebSocket connected, total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if websocket in self.subscribed_symbols:
            del self.subscribed_symbols[websocket]
        logger.debug(f"Ticker WebSocket disconnected, total: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, symbols: list):
        if websocket not in self.subscribed_symbols:
            self.subscribed_symbols[websocket] = set()
        self.subscribed_symbols[websocket].update(symbols)

    def unsubscribe(self, websocket: WebSocket, symbols: list = None):
        if websocket in self.subscribed_symbols:
            if symbols:
                self.subscribed_symbols[websocket] -= set(symbols)
            else:
                self.subscribed_symbols[websocket].clear()


ticker_manager = TickerConnectionManager()
okx_ticker_ws_started = False


async def start_okx_ticker_websocket():
    """Start OKX Ticker WebSocket connection."""
    global okx_ticker_ws_started
    if okx_ticker_ws_started:
        logger.info("OKX Ticker WebSocket already running")
        return

    try:
        from data.okx_websocket import okx_ticker_ws_manager
        logger.info("Starting OKX Ticker WebSocket...")
        okx_ticker_ws_started = True
        await okx_ticker_ws_manager.start()
        logger.info("OKX Ticker WebSocket started")
    except ImportError as e:
        logger.error(f"Cannot import OKX Ticker WebSocket module: {e}")
        okx_ticker_ws_started = False
    except Exception as e:
        logger.error(f"Failed to start OKX Ticker WebSocket: {e}")
        okx_ticker_ws_started = False


@router.websocket("/ws/tickers")
async def websocket_tickers(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Ticker data (Market Watch).

    Client subscription format:
    {"action": "subscribe", "symbols": ["BTC", "ETH", "SOL"]}
    {"action": "unsubscribe", "symbols": ["BTC"]}
    {"action": "unsubscribe_all"}
    """
    await ticker_manager.connect(websocket)

    try:
        from data.okx_websocket import okx_ticker_ws_manager

        asyncio.create_task(start_okx_ticker_websocket())

        current_callbacks = {}

        async def create_ticker_callback(symbol: str):
            """Create callback function for specific symbol."""
            async def on_ticker_update(sym: str, ticker: dict):
                try:
                    await websocket.send_json({
                        "type": "ticker",
                        "symbol": symbol,
                        "data": ticker
                    })
                except Exception as e:
                    logger.debug(f"Failed to send ticker update: {e}")
            return on_ticker_update

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "subscribe":
                    symbols = message.get("symbols", [])
                    if isinstance(symbols, str):
                        symbols = [symbols]

                    logger.debug(f"Ticker subscription request: {symbols}")

                    for symbol in symbols:
                        symbol = symbol.upper()
                        if symbol not in current_callbacks:
                            callback = await create_ticker_callback(symbol)
                            current_callbacks[symbol] = callback
                            await okx_ticker_ws_manager.subscribe(symbol, callback)
                            logger.debug(f"Subscribed to Ticker: {symbol}")

                    ticker_manager.subscribe(websocket, symbols)
                    await websocket.send_json({
                        "type": "subscribed",
                        "symbols": symbols
                    })

                elif action == "unsubscribe":
                    symbols = message.get("symbols", [])
                    if isinstance(symbols, str):
                        symbols = [symbols]

                    for symbol in symbols:
                        symbol = symbol.upper()
                        if symbol in current_callbacks:
                            await okx_ticker_ws_manager.unsubscribe(symbol, current_callbacks[symbol])
                            del current_callbacks[symbol]

                    ticker_manager.unsubscribe(websocket, symbols)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "symbols": symbols
                    })

                elif action == "unsubscribe_all":
                    for symbol, callback in list(current_callbacks.items()):
                        await okx_ticker_ws_manager.unsubscribe(symbol, callback)
                    current_callbacks.clear()
                    ticker_manager.unsubscribe(websocket)
                    await websocket.send_json({"type": "unsubscribed_all"})

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info("Ticker WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Ticker WebSocket error: {e}")
    finally:
        try:
            from data.okx_websocket import okx_ticker_ws_manager
            for symbol, callback in current_callbacks.items():
                await okx_ticker_ws_manager.unsubscribe(symbol, callback)
        except Exception as e:
            logger.debug(f"Failed to cleanup ticker subscriptions: {e}")
        ticker_manager.disconnect(websocket)
