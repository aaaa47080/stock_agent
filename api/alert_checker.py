"""
Price Alert Background Checker

Polls current prices every 60 seconds and fires notifications when
alert conditions are met. Integrates with existing notification system.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60  # seconds


def is_condition_met(
    condition: str,
    target: float,
    current_price: float,
    open_price: float,
) -> bool:
    """Evaluate whether an alert condition is triggered."""
    if condition == "above":
        return current_price >= target
    if condition == "below":
        return current_price <= target
    if open_price == 0:
        return False
    pct_change = (current_price - open_price) / open_price * 100
    if condition == "change_pct_up":
        return pct_change >= target
    if condition == "change_pct_down":
        return (-pct_change) >= target
    return False


def build_alert_body(alert: dict, current_price: float) -> str:
    """Build human-readable notification body for a triggered alert."""
    symbol = alert["symbol"]
    condition = alert["condition"]
    target = alert["target"]

    condition_labels = {
        "above": f"已突破目標價 {target:,.2f}",
        "below": f"已跌破目標價 {target:,.2f}",
        "change_pct_up": f"漲幅已達 {target:.1f}%",
        "change_pct_down": f"跌幅已達 {target:.1f}%",
    }
    label = condition_labels.get(condition, "條件已觸發")
    return f"{symbol} {label}，當前價格：{current_price:,.2f}"


async def _fetch_price(symbol: str, market: str) -> Optional[tuple]:
    """
    Fetch (current_price, open_price) for a symbol.
    Returns None on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        if market == "crypto":
            from core.tools.crypto_tools import get_crypto_price
            result = await loop.run_in_executor(None, get_crypto_price, symbol)
            price = result.get("price") or result.get("last")
            return (float(price), float(price)) if price else None

        if market == "tw_stock":
            from core.tools.tw_stock_tools import tw_stock_price
            result = await loop.run_in_executor(None, tw_stock_price, symbol)
            price = result.get("close") or result.get("price")
            open_p = result.get("open", price)
            return (float(price), float(open_p)) if price else None

        if market == "us_stock":
            from core.tools.us_stock_tools import us_stock_price
            result = await loop.run_in_executor(None, us_stock_price, symbol)
            price = result.get("regularMarketPrice") or result.get("price")
            open_p = result.get("regularMarketOpen") or result.get("open", price)
            return (float(price), float(open_p)) if price else None

    except Exception as e:
        logger.debug(f"Price fetch failed for {symbol} ({market}): {e}")
    return None


async def _check_all_alerts():
    """Run one check cycle across all active alerts."""
    from core.database import get_active_alerts, mark_alert_triggered
    from api.routers.notifications import create_and_push_notification

    loop = asyncio.get_running_loop()
    alerts = await loop.run_in_executor(None, get_active_alerts)

    if not alerts:
        return

    logger.debug(f"Checking {len(alerts)} active alerts")

    for alert in alerts:
        prices = await _fetch_price(alert["symbol"], alert["market"])
        if prices is None:
            continue

        current_price, open_price = prices
        triggered = is_condition_met(
            alert["condition"], alert["target"], current_price, open_price
        )

        if triggered:
            body = build_alert_body(alert, current_price)
            try:
                from functools import partial
                await loop.run_in_executor(
                    None,
                    partial(
                        create_and_push_notification,
                        user_id=alert["user_id"],
                        notification_type="price_alert",
                        title=f"🔔 {alert['symbol']} 價格警報",
                        body=body,
                        data={
                            "symbol": alert["symbol"],
                            "market": alert["market"],
                            "current_price": current_price,
                            "alert_id": alert["id"],
                        },
                    ),
                )
                logger.info(f"Alert triggered: {alert['symbol']} ({alert['condition']} {alert['target']})")
            except Exception as e:
                logger.error(f"Failed to send alert notification: {e}")
                continue

            repeat = bool(alert.get("repeat"))
            await loop.run_in_executor(
                None, mark_alert_triggered, alert["id"], repeat
            )


async def price_alert_check_task():
    """
    Background task: check all active alerts every POLL_INTERVAL seconds.
    Launched from api_server.py lifespan.
    """
    await asyncio.sleep(30)  # delay startup to let DB initialize
    logger.info("Price alert checker started")

    while True:
        try:
            await _check_all_alerts()
        except Exception as e:
            logger.error(f"Alert checker error: {e}")
        await asyncio.sleep(POLL_INTERVAL)
