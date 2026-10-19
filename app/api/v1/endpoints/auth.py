import uuid

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import RefreshRequest, Token
from app.schemas.user import UserOut
from fastapi import status

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
        refresh_token=create_refresh_token(str(user.id)),
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

    return Token(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
