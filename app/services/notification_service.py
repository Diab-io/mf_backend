import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import NotificationType, UserRole
from app.models.notification import Notification
from app.models.user import User


async def _users_with_role(db: AsyncSession, *roles: UserRole) -> list[User]:
    result = await db.execute(select(User).where(User.role.in_(roles), User.is_active.is_(True)))
    return list(result.scalars().all())


async def notify_users(
    db: AsyncSession,
    recipients: Iterable[User],
    notification_type: NotificationType,
    message: str,
    repair_request_id: uuid.UUID | None = None,
) -> None:
    for user in recipients:
        db.add(
            Notification(
                recipient_id=user.id,
                repair_request_id=repair_request_id,
                notification_type=notification_type,
                message=message,
            )
        )


async def notify_role(
    db: AsyncSession,
    role: UserRole,
    notification_type: NotificationType,
    message: str,
    repair_request_id: uuid.UUID | None = None,
) -> None:
    recipients = await _users_with_role(db, role)
    await notify_users(db, recipients, notification_type, message, repair_request_id)
