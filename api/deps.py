from typing import Optional, Union, Any
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
# 在生產環境中，這些應該從環境變數讀取
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_secret_key_change_in_production_7382")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """
    Verify the token and return the payload.
    Used for WebSocket authentication or where Depends() cannot be used.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Validate the token and return the user_id.
    This dependency can be used to protect endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Validate token and return full user dict.
    In TEST_MODE, automatically return test user without requiring valid token.
    """
    from core.config import TEST_MODE, TEST_USER
    from core.database.user import get_user_by_id
    import asyncio
    
    # If using regular authentication (not skipped via TEST_MODE without token)
    if token:
        # TEST_MODE: Allow raw "test-user-xxx" tokens to switch identities
        if TEST_MODE and token.startswith("test-user-"):
            user_id = token
            # Use mock user logic below
        else:
            try:
                # Normal mode: Validate JWT token
                user_id = await get_current_user_id(token)
            except HTTPException:
                if not TEST_MODE:
                    raise
                # Fallback to default test user if validation fails in TEST_MODE
                user_id = None

    # TEST_MODE Logic: Skip validation if token is missing or is a raw mock token
    if TEST_MODE:
        # Determine ID: Provided raw token OR Default from config
        if not user_id:
            user_id = TEST_USER.get("uid", "test-user-001")
        
        test_user_id = user_id
        
        try:
            loop = asyncio.get_running_loop()
            user = await loop.run_in_executor(None, get_user_by_id, test_user_id)
            
            if user:
                return user
        except Exception as e:
            # If database fetch fails, return mock user
            pass
        
        # Return mock test user for development
        return {
            "user_id": test_user_id,
            "username": f"TestUser_{test_user_id[-3:]}", # Diff names: TestUser_001, TestUser_002
            "pi_uid": test_user_id,
            "is_premium": False,
            "created_at": datetime.utcnow().isoformat(),
        }
    
    # If not in TEST_MODE and no token provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
