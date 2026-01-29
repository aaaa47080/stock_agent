"""
Pi Network Access Token Verification

Verifies Pi Access Tokens against the Pi Network API to prevent identity spoofing
"""
import os
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException
from api.utils import logger

PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"

async def verify_pi_access_token(access_token: str, expected_pi_uid: str) -> Dict[str, Any]:
    """
    Verify Pi Access Token against Pi Network API
    
    This function calls the Pi Network API to validate the access token
    and ensure the user's identity matches the expected UID.
    
    Args:
        access_token: The access token provided by the Pi Browser
        expected_pi_uid: The expected Pi UID that should match the token
        
    Returns:
        Dict containing verified user data from Pi Network
        
    Raises:
        HTTPException: If token is invalid, expired, or UID mismatch
    """
    if not access_token:
        raise HTTPException(
            status_code=401, 
            detail="Pi Access Token is required for authentication"
        )
    
    if not PI_API_KEY:
        logger.error("PI_API_KEY not configured - cannot verify Pi tokens")
        raise HTTPException(
            status_code=500, 
            detail="Server configuration error: Pi verification not available"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Call Pi Network API to verify the access token
            # Reference: https://developers.minepi.com/doc/backend#verify-user
            response = await client.get(
                f"{PI_API_BASE}/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Api-Key": PI_API_KEY
                },
                timeout=10.0
            )
            
            if response.status_code == 401:
                logger.warning("Pi token verification failed: Invalid or expired token")
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid or expired Pi Access Token"
                )
            
            if response.status_code != 200:
                logger.error(f"Pi API returned unexpected status: {response.status_code}")
                raise HTTPException(
                    status_code=502, 
                    detail="Pi verification service error"
                )
            
            user_data = response.json()
            actual_uid = user_data.get("uid")
            
            # Verify the UID matches what the client claimed
            if actual_uid != expected_pi_uid:
                logger.warning(
                    f"Pi UID mismatch: client claimed {expected_pi_uid}, "
                    f"but token belongs to {actual_uid}"
                )
                raise HTTPException(
                    status_code=403, 
                    detail="Pi UID mismatch - possible impersonation attempt"
                )
            
            logger.info(f"Pi Access Token successfully verified for uid: {actual_uid}")
            return user_data
            
    except httpx.TimeoutException:
        logger.error("Pi API request timed out")
        raise HTTPException(
            status_code=504, 
            detail="Pi verification service timeout - please try again"
        )
    except httpx.HTTPError as e:
        logger.error(f"Pi API HTTP error: {e}")
        raise HTTPException(
            status_code=502, 
            detail="Unable to connect to Pi verification service"
        )
    except HTTPException:
        # Re-raise our own HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Pi token verification: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error during Pi verification"
        )


async def verify_pi_payment_token(access_token: str, payment_id: str) -> Dict[str, Any]:
    """
    Verify Pi Access Token for payment operations
    
    This is a specialized verification for payment-related operations
    that also validates the token has permission for the specific payment.
    
    Args:
        access_token: The access token from Pi Browser
        payment_id: The payment ID to verify access for
        
    Returns:
        Dict containing payment verification data
        
    Raises:
        HTTPException: If verification fails
    """
    if not PI_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Server configuration error: Pi API not configured"
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Verify the payment with the access token
            response = await client.get(
                f"{PI_API_BASE}/payments/{payment_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Api-Key": PI_API_KEY
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Payment verification failed"
                )
            
            return response.json()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Payment verification failed"
        )
