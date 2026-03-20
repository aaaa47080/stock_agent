"""
Tip-related API endpoints
"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Depends, Request

from api.utils import logger, run_sync
from api.deps import get_current_user
from api.middleware.rate_limit import limiter
from core.database import (
    get_post_by_id,
    create_tip,
    get_tips_sent,
    get_tips_received,
    get_tips_total_received,
)
from .models import CreateTipRequest

router = APIRouter(prefix="/api/forum", tags=["Forum - Tips"])

PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"
TEST_MODE = os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes")


async def _verify_tip_payment(payment_id: str) -> dict:
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
                raise HTTPException(status_code=400, detail="Payment not found on Pi Network")

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
        logger.error("Pi API timeout during tip payment verification")
        raise HTTPException(status_code=504, detail="Pi verification service timeout")
    except httpx.HTTPStatusError as e:
        logger.error("Pi API error during tip verification: %s - %s", e.response.status_code, e.response.text)
        raise HTTPException(status_code=e.response.status_code, detail="Pi API verification failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tip payment verification error: %s", e)
        raise HTTPException(status_code=500, detail="Payment verification failed")


@router.post("/posts/{post_id}/tip")
@limiter.limit("10/minute")
async def tip_post(
    request: Request,
    post_id: int,
    body: CreateTipRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]

        tx_hash = body.tx_hash

        if not TEST_MODE:
            if not body.payment_id:
                raise HTTPException(status_code=400, detail="payment_id is required for tips")

            payment_data = await _verify_tip_payment(body.payment_id)

            blockchain_txid = payment_data.get("transaction", {}).get("_id")
            if blockchain_txid:
                tx_hash = blockchain_txid
            elif not tx_hash:
                raise HTTPException(status_code=400, detail="No blockchain transaction found for this payment")

            actual_amount = payment_data.get("amount", 0)
            if abs(float(actual_amount) - float(body.amount)) > 0.001:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tip amount mismatch: expected {body.amount} Pi, got {actual_amount} Pi",
                )
        else:
            if not tx_hash:
                import uuid
                tx_hash = f"test_tip_{uuid.uuid4().hex[:16]}"

        post = await run_sync(lambda: get_post_by_id(post_id, increment_view=False))
        if not post or post["is_hidden"]:
            raise HTTPException(status_code=404, detail="Post not found")

        if post["user_id"] == user_id:
            raise HTTPException(status_code=400, detail="Cannot tip your own post")

        tip_id = await run_sync(
            lambda: create_tip(
                post_id=post_id,
                from_user_id=user_id,
                to_user_id=post["user_id"],
                amount=request.amount,
                tx_hash=tx_hash,
            )
        )

        logger.info(
            "Tip created: post=%d, from=%s, to=%s, amount=%.2f, tx=%s",
            post_id, user_id, post["user_id"], body.amount,
            tx_hash[:16] if tx_hash else "none",
        )

        return {
            "success": True,
            "message": "Tip successful",
            "tip_id": tip_id,
            "amount": body.amount,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Tip failed, please try again later")


@router.get("/tips/sent")
async def get_sent_tips(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]

        tips = await run_sync(lambda: get_tips_sent(user_id, limit=limit, offset=offset))
        return {"success": True, "tips": tips, "count": len(tips)}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get tip records")


@router.get("/tips/received")
async def get_received_tips(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user["user_id"]

        tips = await run_sync(lambda: get_tips_received(user_id, limit=limit, offset=offset))
        total = await run_sync(get_tips_total_received, user_id)
        return {"success": True, "tips": tips, "count": len(tips), "total_received": total}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get tip records")
