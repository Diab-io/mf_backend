import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.constants import UserRole
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User

logger = structlog.get_logger("mf_backend.startup")


async def ensure_first_admin() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
        if result.scalars().first():
            return

        admin = User(
            full_name=settings.FIRST_ADMIN_FULL_NAME,
            email=settings.FIRST_ADMIN_EMAIL,
            hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        logger.info("bootstrap_admin_created", email=settings.FIRST_ADMIN_EMAIL)
