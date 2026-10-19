import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserRole
from app.db.base import Base, TimestampMixin, UUIDPkMixin


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    site: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    reported_faults = relationship(
        "RepairRequest", back_populates="reporter", foreign_keys="RepairRequest.reported_by_id"
    )
    assigned_repairs = relationship(
        "RepairRequest", back_populates="assigned_mechanic", foreign_keys="RepairRequest.assigned_mechanic_id"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"
