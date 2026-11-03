import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import RefreshRequest, Token
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, UserOut
from app.services.email_service import send_email

router = APIRouter(prefix="/auth", tags=["auth"])


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Incorrect email or password."


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        raise InvalidCredentialsError()

    return Token(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.hashed_password),
    )


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    class _InvalidRefresh(AppError):
        status_code = status.HTTP_401_UNAUTHORIZED
        default_message = "Invalid or expired refresh token."

    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != "refresh":
            raise _InvalidRefresh()
    except JWTError:
        raise _InvalidRefresh()

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError, TypeError):
        raise _InvalidRefresh()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise _InvalidRefresh()
    # Tokens issued before a password change/reset (or without the claim) are revoked.
    if claims.get("pwd") != password_fingerprint(user.hashed_password):
        raise _InvalidRefresh()

    return Token(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.hashed_password),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user and user.is_active:
        token = create_password_reset_token(str(user.id), user.hashed_password)
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        background_tasks.add_task(
            send_email,
            user.email,
            "Reset your password",
            f"Hi {user.full_name},\n\nUse this link to reset your password "
            f"(valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n{link}\n\n"
            "If you did not request this, ignore this email.",
        )
    # Same response whether or not the email exists, so accounts can't be enumerated.
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    class _InvalidResetToken(AppError):
        status_code = status.HTTP_400_BAD_REQUEST
        default_message = "Invalid or expired reset token."

    try:
        claims = decode_token(payload.token)
        if claims.get("type") != "reset":
            raise _InvalidResetToken()
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError, TypeError):
        raise _InvalidResetToken()

    user = await db.get(User, user_id)
    if (
        not user
        or not user.is_active
        or claims.get("pwd") != password_fingerprint(user.hashed_password)
    ):
        raise _InvalidResetToken()

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Password has been reset. You can now log in."}
