"""
Password hashing and JWT creation/validation.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, expires_delta: timedelta, token_type: Literal["access", "refresh"], extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    to_encode: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
        extra={"role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        "refresh",
    )


def decode_token(token: str) -> dict:
    """Raises JWTError on failure — caller is expected to catch it."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
