# ========================================
# OKX WebSocket 即時數據服務
# ========================================

import asyncio
import json
import logging
from typing import Dict, Set, Callable, Optional
from datetime import datetime

try:
    import websockets
except ImportError:
    websockets = None

logger = logging.getLogger(__name__)

# OKX WebSocket 端點
# K 線數據需要使用 business 端點，public 端點不支援 K 線
OKX_WS_BUSINESS = "wss://ws.okx.com:8443/ws/v5/business"
# Ticker 數據使用 public 端點
OKX_WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"

# 時間週期映射 (前端格式 -> OKX 格式)
INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "1d": "1D",
    "1w": "1W",
}

class OKXWebSocketManager:
    """管理 OKX WebSocket 連接和訂閱"""

    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, Set[Callable]] = {}  # channel -> callbacks
        self.running = False
        self.reconnect_delay = 5
        self._connect_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    def _get_channel_key(self, symbol: str, interval: str) -> str:
        """生成頻道唯一鍵"""
        return f"{symbol}_{interval}"

    def _get_okx_inst_id(self, symbol: str) -> str:
        """轉換幣種符號為 OKX 格式"""
        # 移除常見後綴，轉換為 OKX 格式
        symbol = symbol.upper().replace("-", "")
        # 只移除結尾的 USDT/USD，避免影響 USDC 等幣種
        if symbol.endswith("USDT"):
            symbol = symbol[:-4]
        elif symbol.endswith("USD") and symbol != "USDC":
            symbol = symbol[:-3]
        return f"{symbol}-USDT"

    async def connect(self):
        """建立 WebSocket 連接"""
        if websockets is None:
            logger.error("websockets 模組未安裝，請執行: pip install websockets")
            return

        self.running = True

        while self.running:
            try:
                logger.info(f"正在連接 OKX WebSocket: {OKX_WS_BUSINESS}")

                async with websockets.connect(
                    OKX_WS_BUSINESS,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self.ws = ws
                    logger.info("OKX WebSocket 連接成功")

                    # 重新訂閱所有頻道
                    await self._resubscribe_all()

                    # 啟動心跳
                    self._ping_task = asyncio.create_task(self._ping_loop())

                    # 接收消息
                    async for message in ws:
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket 連接關閉: {e}")
            except Exception as e:
                logger.error(f"WebSocket 錯誤: {e}")
            finally:
                self.ws = None
                if self._ping_task:
                    self._ping_task.cancel()

            if self.running:
                logger.info(f"{self.reconnect_delay} 秒後重新連接...")
                await asyncio.sleep(self.reconnect_delay)

    async def _ping_loop(self):
        """心跳保持連接"""
        while self.running and self.ws:
            try:
                await asyncio.sleep(25)
                if self.ws:
                    await self.ws.send("ping")
            except Exception:
                break

    async def _resubscribe_all(self):
        """重新訂閱所有頻道"""
        if not self.ws or not self.subscriptions:
            return

        for channel_key in self.subscriptions.keys():
            parts = channel_key.split("_")
            if len(parts) == 2:
                symbol, interval = parts
                await self._send_subscribe(symbol, interval)

    async def _send_subscribe(self, symbol: str, interval: str):
        """發送訂閱請求"""
        if not self.ws:
            return

        inst_id = self._get_okx_inst_id(symbol)
        okx_interval = INTERVAL_MAP.get(interval, "1H")
        channel = f"candle{okx_interval}"

        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "channel": channel,
                "instId": inst_id
            }]
        }

        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"訂閱: {inst_id} {channel}")

    async def _send_unsubscribe(self, symbol: str, interval: str):
        """發送取消訂閱請求"""
        if not self.ws:
            return

        inst_id = self._get_okx_inst_id(symbol)
        okx_interval = INTERVAL_MAP.get(interval, "1H")
        channel = f"candle{okx_interval}"

        unsubscribe_msg = {
            "op": "unsubscribe",
            "args": [{
                "channel": channel,
                "instId": inst_id
            }]
        }

        await self.ws.send(json.dumps(unsubscribe_msg))
        logger.info(f"取消訂閱: {inst_id} {channel}")

    async def _handle_message(self, message: str):
        """處理接收到的消息"""
        if message == "pong":
            return

        try:
            data = json.loads(message)

            # 訂閱確認
            if "event" in data:
                if data["event"] == "subscribe":
                    logger.info(f"訂閱確認: {data.get('arg', {})}")
                elif data["event"] == "error":
                    logger.error(f"訂閱錯誤: {data}")
                return

            # K線數據推送
            if "data" in data and "arg" in data:
                logger.info(f"收到 K 線推送: {data['arg']}")
                arg = data["arg"]
                channel = arg.get("channel", "")
                inst_id = arg.get("instId", "")

                # 解析頻道獲取時間週期
                interval = None
                for front_interval, okx_interval in INTERVAL_MAP.items():
                    if channel == f"candle{okx_interval}":
                        interval = front_interval
                        break

                if interval and inst_id:
                    # 嘗試多種 channel_key 格式來匹配訂閱
                    symbol_variants = [
                        inst_id,  # BREV-USDT
                        inst_id.replace("-USDT", ""),  # BREV
                        inst_id.replace("-", ""),  # BREVUSDT
                    ]

                    # 轉換 K 線數據格式
                    for candle in data["data"]:
                        kline = self._parse_candle(candle)

                        # 嘗試所有可能的 channel_key
                        for symbol in symbol_variants:
                            channel_key = self._get_channel_key(symbol, interval)
                            if channel_key in self.subscriptions:
                                logger.debug(f"收到 K 線數據: {channel_key}")
                                for callback in self.subscriptions[channel_key]:
                                    try:
                                        await callback(symbol, interval, kline)
                                    except Exception as e:
                                        logger.error(f"回調錯誤: {e}")
                                break  # 找到匹配就停止

        except json.JSONDecodeError:
            logger.warning(f"無法解析消息: {message[:100]}")
        except Exception as e:
            logger.error(f"處理消息錯誤: {e}")

    def _parse_candle(self, candle: list) -> dict:
        """解析 OKX K 線數據為標準格式"""
        # OKX 格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        return {
            "time": int(candle[0]) // 1000,  # 毫秒轉秒
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
            "confirmed": candle[8] == "1" if len(candle) > 8 else False
        }

    async def subscribe(self, symbol: str, interval: str, callback: Callable):
        """訂閱 K 線數據"""
        channel_key = self._get_channel_key(symbol, interval)

        if channel_key not in self.subscriptions:
            self.subscriptions[channel_key] = set()
            # 發送訂閱請求
            if self.ws:
                await self._send_subscribe(symbol, interval)

        self.subscriptions[channel_key].add(callback)
        logger.info(f"添加訂閱回調: {channel_key}")

    async def unsubscribe(self, symbol: str, interval: str, callback: Callable = None):
        """取消訂閱"""
        channel_key = self._get_channel_key(symbol, interval)

        if channel_key in self.subscriptions:
            if callback:
                self.subscriptions[channel_key].discard(callback)
            else:
                self.subscriptions[channel_key].clear()

            # 如果沒有訂閱者了，發送取消訂閱
            if not self.subscriptions[channel_key]:
                del self.subscriptions[channel_key]
                if self.ws:
                    await self._send_unsubscribe(symbol, interval)

    async def start(self):
        """啟動 WebSocket 管理器"""
        if self._connect_task is None or self._connect_task.done():
            self._connect_task = asyncio.create_task(self.connect())

    async def stop(self):
        """停止 WebSocket 管理器"""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self._connect_task:
            self._connect_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()


# 全局實例
okx_ws_manager = OKXWebSocketManager()


class OKXTickerWebSocketManager:
    """管理 OKX Ticker WebSocket 連接和訂閱"""

    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, Set[Callable]] = {}  # symbol -> callbacks
        self.running = False
        self.reconnect_delay = 5
        self._connect_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    def _get_okx_inst_id(self, symbol: str) -> str:
        """轉換幣種符號為 OKX 格式"""
        symbol = symbol.upper().replace("-", "")
        # 只移除結尾的 USDT/USD，避免影響 USDC 等幣種
        if symbol.endswith("USDT"):
            symbol = symbol[:-4]
        elif symbol.endswith("USD") and symbol != "USDC":
            symbol = symbol[:-3]
        return f"{symbol}-USDT"

    async def connect(self):
        """建立 WebSocket 連接"""
        if websockets is None:
            logger.error("websockets 模組未安裝，請執行: pip install websockets")
            return

        self.running = True

        while self.running:
            try:
                logger.info(f"正在連接 OKX Ticker WebSocket: {OKX_WS_PUBLIC}")

                async with websockets.connect(
                    OKX_WS_PUBLIC,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self.ws = ws
                    logger.info("OKX Ticker WebSocket 連接成功")

                    # 重新訂閱所有頻道
                    await self._resubscribe_all()

                    # 啟動心跳
                    self._ping_task = asyncio.create_task(self._ping_loop())

                    # 接收消息
                    async for message in ws:
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Ticker WebSocket 連接關閉: {e}")
            except Exception as e:
                logger.error(f"Ticker WebSocket 錯誤: {e}")
            finally:
                self.ws = None
                if self._ping_task:
                    self._ping_task.cancel()

            if self.running:
                logger.info(f"{self.reconnect_delay} 秒後重新連接 Ticker WebSocket...")
                await asyncio.sleep(self.reconnect_delay)

    async def _ping_loop(self):
        """心跳保持連接"""
        while self.running and self.ws:
            try:
                await asyncio.sleep(25)
                if self.ws:
                    await self.ws.send("ping")
            except Exception:
                break

    async def _resubscribe_all(self):
        """重新訂閱所有頻道"""
        if not self.ws or not self.subscriptions:
            return

        for symbol in self.subscriptions.keys():
            await self._send_subscribe(symbol)

    async def _send_subscribe(self, symbol: str):
        """發送訂閱請求"""
        if not self.ws:
            return

        inst_id = self._get_okx_inst_id(symbol)
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "channel": "tickers",
                "instId": inst_id
            }]
        }

        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"訂閱 Ticker: {inst_id}")

    async def _send_unsubscribe(self, symbol: str):
        """發送取消訂閱請求"""
        if not self.ws:
            return

        inst_id = self._get_okx_inst_id(symbol)
        unsubscribe_msg = {
            "op": "unsubscribe",
            "args": [{
                "channel": "tickers",
                "instId": inst_id
            }]
        }

        await self.ws.send(json.dumps(unsubscribe_msg))
        logger.info(f"取消訂閱 Ticker: {inst_id}")

    async def _handle_message(self, message: str):
        """處理接收到的消息"""
        if message == "pong":
            return

        try:
            data = json.loads(message)

            # 訂閱確認
            if "event" in data:
                if data["event"] == "subscribe":
                    logger.info(f"Ticker 訂閱確認: {data.get('arg', {})}")
                elif data["event"] == "error":
                    logger.error(f"Ticker 訂閱錯誤: {data}")
                return

            # Ticker 數據推送
            if "data" in data and "arg" in data:
                arg = data["arg"]
                if arg.get("channel") == "tickers":
                    inst_id = arg.get("instId", "")

                    for ticker_data in data["data"]:
                        parsed = self._parse_ticker(ticker_data)

                        # 嘗試多種 symbol 格式來匹配訂閱
                        symbol_variants = [
                            inst_id,  # BTC-USDT
                            inst_id.replace("-USDT", ""),  # BTC
                            inst_id.replace("-", ""),  # BTCUSDT
                        ]

                        for symbol in symbol_variants:
                            if symbol in self.subscriptions:
                                for callback in self.subscriptions[symbol]:
                                    try:
                                        await callback(symbol, parsed)
                                    except Exception as e:
                                        logger.error(f"Ticker 回調錯誤: {e}")
                                break

        except json.JSONDecodeError:
            logger.warning(f"無法解析 Ticker 消息: {message[:100]}")
        except Exception as e:
            logger.error(f"處理 Ticker 消息錯誤: {e}")

    def _parse_ticker(self, ticker: dict) -> dict:
        """解析 OKX Ticker 數據為標準格式"""
        # OKX Ticker 格式:
        # instId, last, lastSz, askPx, askSz, bidPx, bidSz, open24h, high24h, low24h, volCcy24h, vol24h, ts, ...
        return {
            "symbol": ticker.get("instId", ""),
            "last": float(ticker.get("last", 0)),
            "open24h": float(ticker.get("open24h", 0)),
            "high24h": float(ticker.get("high24h", 0)),
            "low24h": float(ticker.get("low24h", 0)),
            "vol24h": float(ticker.get("vol24h", 0)),
            "volCcy24h": float(ticker.get("volCcy24h", 0)),
            "change24h": self._calc_change(ticker.get("last"), ticker.get("open24h")),
            "ts": int(ticker.get("ts", 0))
        }

    def _calc_change(self, last, open24h) -> float:
        """計算 24 小時漲跌幅"""
        try:
            last = float(last)
            open24h = float(open24h)
            if open24h == 0:
                return 0
            return ((last - open24h) / open24h) * 100
        except:
            return 0

    async def subscribe(self, symbol: str, callback: Callable):
        """訂閱 Ticker 數據"""
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = set()
            if self.ws:
                await self._send_subscribe(symbol)

        self.subscriptions[symbol].add(callback)
        logger.info(f"添加 Ticker 訂閱回調: {symbol}")

    async def unsubscribe(self, symbol: str, callback: Callable = None):
        """取消訂閱"""
        if symbol in self.subscriptions:
            if callback:
                self.subscriptions[symbol].discard(callback)
            else:
                self.subscriptions[symbol].clear()

            if not self.subscriptions[symbol]:
                del self.subscriptions[symbol]
                if self.ws:
                    await self._send_unsubscribe(symbol)

    async def subscribe_many(self, symbols: list, callback: Callable):
        """批量訂閱多個幣種"""
        for symbol in symbols:
            await self.subscribe(symbol, callback)

    async def unsubscribe_all(self):
        """取消所有訂閱"""
        symbols = list(self.subscriptions.keys())
        for symbol in symbols:
            await self.unsubscribe(symbol)

    async def start(self):
        """啟動 WebSocket 管理器"""
        if self._connect_task is None or self._connect_task.done():
            self._connect_task = asyncio.create_task(self.connect())

    async def stop(self):
        """停止 WebSocket 管理器"""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self._connect_task:
            self._connect_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()


# Ticker 全局實例
okx_ticker_ws_manager = OKXTickerWebSocketManager()
