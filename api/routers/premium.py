"""
Premium 會員相關 API
"""

from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from api.pi_verification import PI_API_BASE, PI_API_KEY
from api.utils import logger, run_sync
from core.config import TEST_MODE
from core.database.user import upgrade_to_pro
from core.orm.repositories import user_repo

router = APIRouter(prefix="/api/premium", tags=["Premium"])

PLAN_MONTHS = {
    "premium_monthly": 1,
    "premium_yearly": 12,
}


def _record_used_payment(payment_id: str, user_id: str) -> None:
    from core.database.connection import get_connection

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO used_payments (payment_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (payment_id, user_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise ValueError("payment already used")
    finally:
        conn.close()


class UpgradeRequest(BaseModel):
    plan: Literal["premium_monthly", "premium_yearly"] = "premium_monthly"
    tx_hash: Optional[str] = None
    payment_id: Optional[str] = None
    months: int = Field(default=1, ge=1, le=24)


async def _verify_pi_payment(payment_id: str) -> dict:
    """
    Verify a Pi payment by calling the Pi Server API.

    Returns the payment data from Pi API if valid.

    Raises HTTPException if verification fails.
    """
    if not PI_API_KEY or PI_API_KEY == "your_pi_api_key_here":
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Pi API not configured",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PI_API_BASE}/payments/{payment_id}",
                headers={"Authorization": f"Key {PI_API_KEY}"},
                timeout=10.0,
            )

            if response.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail="Payment not found on Pi Network",
                )

            response.raise_for_status()
            payment_data = response.json()

            status = payment_data.get("status", "")
            if status not in ("approved", "completed"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment has not been approved yet (status: {status})",
                )

            return payment_data

    except httpx.TimeoutException:
        logger.error("Pi API request timed out during payment verification")
        raise HTTPException(
            status_code=504,
            detail="Pi verification service timeout",
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "Pi API error during payment verification: %s - %s",
            e.response.status_code,
            e.response.text,
        )
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Pi API verification failed",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment verification error: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Payment verification failed",
        )


@router.get("/pricing")
async def get_pricing_plans():
    from core.config import PI_PAYMENT_PRICES

    return {
        "success": True,
        "pricing": {
            "premium": {
                "monthly": PI_PAYMENT_PRICES.get("premium_monthly", 5.0),
                "yearly": PI_PAYMENT_PRICES.get("premium_yearly", 40.0),
            }
        },
        "pi_price_usd": 0.17,
        "savings": {
            "premium_yearly_save": 20.0,
        },
    }


@router.post("/upgrade")
@limiter.limit("10/minute")
async def upgrade_to_premium(
    request: Request,
    body: UpgradeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Upgrade to Premium membership.

    In production: requires a valid payment_id that is verified against Pi Server API.
    In TEST_MODE: tx_hash is optional and verification is skipped.
    """
    user_id = current_user["user_id"]

    plan = (body.plan or "premium_monthly").strip().lower()
    if plan not in PLAN_MONTHS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    months = PLAN_MONTHS[plan]

    tx_hash = body.tx_hash

    if not TEST_MODE:
        if not body.payment_id:
            raise HTTPException(
                status_code=400,
                detail="payment_id is required for premium upgrade",
            )

        payment_data = await _verify_pi_payment(body.payment_id)

        try:
            await run_sync(lambda: _record_used_payment(body.payment_id, user_id))
        except Exception:
            logger.warning(
                "Payment already used or failed to record: %s", body.payment_id
            )

        blockchain_txid = payment_data.get("transaction", {}).get("_id")
        if blockchain_txid:
            tx_hash = blockchain_txid
        elif not tx_hash:
            raise HTTPException(
                status_code=400,
                detail="No blockchain transaction found for this payment",
            )

        actual_amount = payment_data.get("amount", 0)
        from core.config import PI_PAYMENT_PRICES

        expected_amount = PI_PAYMENT_PRICES.get(plan, 5.0)
        if abs(float(actual_amount) - float(expected_amount)) > 0.001:
            logger.warning(
                "Premium upgrade amount mismatch: expected=%s, actual=%s, user=%s",
                expected_amount,
                actual_amount,
                user_id,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Payment amount mismatch: expected {expected_amount} Pi, got {actual_amount} Pi",
            )
    else:
        if not tx_hash:
            import uuid

            tx_hash = f"test_{uuid.uuid4().hex[:16]}"

    try:
        current_membership = await user_repo.get_membership(user_id)

        if not current_membership:
            raise HTTPException(status_code=404, detail="User not found")

        success = await run_sync(
            lambda: upgrade_to_pro(
                user_id=user_id,
                months=months,
                tx_hash=tx_hash,
            )
        )

        if not success:
            raise HTTPException(status_code=500, detail="Upgrade failed")

        new_membership = await user_repo.get_membership(user_id)

        logger.info(
            "User %s upgraded to Premium, plan=%s, months=%d, tx_hash=%s",
            user_id,
            plan,
            months,
            tx_hash[:16] if tx_hash else "none",
        )

        return {
            "success": True,
            "message": f"Successfully upgraded to Premium for {months} month(s)!",
            "plan": plan,
            "months": months,
            "membership": new_membership,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Premium upgrade failed for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=500, detail="Upgrade failed, please try again later"
        )


@router.get("/status")
async def get_premium_status(
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]
        membership = await user_repo.get_membership(user_id)

        if not membership:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "success": True,
            "membership": membership,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get premium status for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to get status")
