import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ApprovalDecision, ApprovalStage, UserRole
from app.db.base import Base, TimestampMixin, UUIDPkMixin


class ApprovalRecord(UUIDPkMixin, TimestampMixin, Base):
    """
    Immutable audit record for every Supervisor/MD decision. Never updated or
    deleted after creation — a new row is always appended, so the full
    approval history of a request is reconstructable from this table alone.
    """
    __tablename__ = "approval_records"

    repair_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repair_requests.id"), nullable=False
    )
    repair_request = relationship("RepairRequest", back_populates="approvals")

    stage: Mapped[ApprovalStage] = mapped_column(
        Enum(ApprovalStage, name="approval_stage", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    decided_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decided_by = relationship("User")

    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision, name="approval_decision", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ApprovalRecord {self.stage}:{self.decision}>"
