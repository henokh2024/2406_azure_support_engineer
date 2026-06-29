import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status

#In productiion, replace this with an actual secret and use os.getenv() to get the secret

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "7bca9c84-1e2b-4f3a-9c5d-8f7e6a9b0c1d")
JWT_ALGORITHM ="HS256"
TOKEN_EXPIRATION_MINUTES = 30

def create_access_token(username: str) -> str:
    """Encodes user identity details into a cryptographically signed JWT token for authentication."""
    isued_at = datetime.now(timezone.utc)
    expiration_time = isued_at + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)

    payload = {
        "sub": username,
        "iat": isued_at.timestamp(),
        "exp": expiration_time.timestamp()
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_verify_token(token: str) -> dict:
    """Decodes and verifies the JWT token, returning the username if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
       raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )   