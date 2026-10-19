import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    pagination: Pagination = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(notification_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise NotFoundError("Notification not found.")
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/read-all", status_code=204)
async def mark_all_read(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Notification).where(Notification.user_id == current_user.id, Notification.is_read.is_(False)).values(is_read=True)
    )
    await db.commit()
    return None
