"""
Admin Authentication Module
Provides authentication utilities for admin endpoints
"""

import os
from typing import Optional

from fastapi import Header, HTTPException

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """驗證管理員 API Key"""
    key = ADMIN_API_KEY or os.getenv("ADMIN_API_KEY")
    if not key:
        # Avoid leaking internal configuration details
        # Return 403 Forbidden to mask the fact that the key is not configured
        raise HTTPException(
            status_code=403, detail="Forbidden: Admin access not configured"
        )

    if not x_admin_key or x_admin_key != key:
        raise HTTPException(status_code=403, detail="Invalid or missing admin API key")
    return True
