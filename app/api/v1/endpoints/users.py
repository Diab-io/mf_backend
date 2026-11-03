import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, require_roles
from app.core.constants import UserRole
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN))])
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise ConflictError("A user with this email already exists.")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone_number=payload.phone_number,
        site=payload.site,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    role: UserRole | None = None,
    include_archived: bool = False,
    pagination: Pagination = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Any authenticated user may list users filtered by role (e.g. a
    # Supervisor populating a "assign mechanic" dropdown); only Admin may
    # list the full unfiltered directory.
    if role is None and current_user.role != UserRole.ADMIN:
        role = UserRole.MECHANIC

    stmt = select(User).offset(pagination.offset).limit(pagination.page_size)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if not (include_archived and current_user.role == UserRole.ADMIN):
        stmt = stmt.where(User.archived_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found.")
    return user


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/archive", response_model=UserOut)
async def archive_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found.")
    if user.id == current_user.id:
        raise PermissionDeniedError("You cannot archive your own account.")
    if user.archived_at is not None:
        raise ConflictError("User is already archived.")

    if user.role == UserRole.ADMIN:
        active_admins = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.role == UserRole.ADMIN, User.is_active.is_(True), User.archived_at.is_(None)
                )
            )
        ).scalar_one()
        if active_admins <= 1:
            raise ConflictError("Cannot archive the last active admin.")

    user.archived_at = datetime.now(timezone.utc)
    user.is_active = False  # blocks login, refresh and API access, and drops them from notifications
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/unarchive", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.ADMIN))])
async def unarchive_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found.")
    user.archived_at = None
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user
