import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum

from app.db.base import Base, TimestampMixin, UUIDPkMixin
from app.core.constants import UserRole

class AuditLog(UUIDPkMixin, TimestampMixin, Base):
    """
    Append-only log of every state-changing action on a repair request
    (submission, cancellation, status transitions) that isn't already
    captured by ApprovalRecord. Supports spec section 16: "Records should
    not be silently deleted; use controlled cancellation/archiving."
    """
    __tablename__ = "audit_logs"

    repair_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repair_requests.id"), nullable=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    actor = relationship("User")

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repair_request = relationship("RepairRequest", back_populates="audit_logs")
    actor_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.from_status}->{self.to_status}>"
