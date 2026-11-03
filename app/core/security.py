"""
Password hashing and JWT creation/validation.
"""
import hashlib
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


def _create_token(subject: str, expires_delta: timedelta, token_type: Literal["access", "refresh", "reset"], extra: dict | None = None) -> str:
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


def create_refresh_token(subject: str, hashed_password: str) -> str:
    # The password fingerprint ties the token to the current password, so a reset revokes it.
    return _create_token(
        subject,
        timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
        "refresh",
        extra={"pwd": password_fingerprint(hashed_password)},
    )


def password_fingerprint(hashed_password: str) -> str:
    """Short digest of the current password hash; ties a reset token to one password state (single-use)."""
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_password_reset_token(subject: str, hashed_password: str) -> str:
    return _create_token(
        subject,
        timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        "reset",
        extra={"pwd": password_fingerprint(hashed_password)},
    )


def decode_token(token: str) -> dict:
    """Raises JWTError on failure — caller is expected to catch it."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
