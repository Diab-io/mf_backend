import uuid

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.exceptions import PermissionDeniedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    from app.core.exceptions import AppError
    from fastapi import status

    class _Unauthorized(AppError):
        status_code = status.HTTP_401_UNAUTHORIZED
        default_message = "Could not validate credentials."

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise _Unauthorized("Invalid token type; expected access token.")
        user_id = payload.get("sub")
        if user_id is None:
            raise _Unauthorized()
    except JWTError:
        raise _Unauthorized()

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _Unauthorized("User not found or inactive.")
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: raises 403 unless the current user's role is in `roles`."""

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError(
                f"This action requires one of the following roles: {', '.join(r.value for r in roles)}."
            )
        return current_user

    return checker


class Pagination:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200)):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
