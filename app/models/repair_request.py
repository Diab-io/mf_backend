import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import FaultType, Priority, RepairStatus
from app.db.base import Base, TimestampMixin, UUIDPkMixin


class RepairRequest(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "repair_requests"

    request_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)

    equipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipment.id"), nullable=False)
    equipment = relationship("Equipment", back_populates="repair_requests")

    reported_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reporter = relationship("User", back_populates="reported_faults", foreign_keys=[reported_by_id])

    fault_detected_by: Mapped[str | None] = mapped_column(String(150), nullable=True)

    assigned_mechanic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assigned_mechanic = relationship("User", back_populates="assigned_repairs", foreign_keys=[assigned_mechanic_id])

    fault_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fault_type: Mapped[FaultType] = mapped_column(
        Enum(FaultType, name="fault_type", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority", values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    fault_description: Mapped[str] = mapped_column(Text, nullable=False)
    repair_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[RepairStatus] = mapped_column(
        Enum(RepairStatus, name="repair_status", values_callable=lambda x: [e.value for e in x]),
        default=RepairStatus.DRAFT, nullable=False, index=True
    )

    estimated_cost: Mapped[float | None] = mapped_column(nullable=True)

    attachments = relationship("Attachment", back_populates="repair_request", cascade="all, delete-orphan")
    approvals = relationship(
        "ApprovalRecord", back_populates="repair_request", cascade="all, delete-orphan",
        order_by="ApprovalRecord.created_at",
    )
    repair_actions = relationship(
        "RepairAction", back_populates="repair_request", cascade="all, delete-orphan",
        order_by="RepairAction.action_date",
    )
    audit_logs = relationship("AuditLog", back_populates="repair_request", order_by="AuditLog.created_at")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RepairRequest {self.request_number} ({self.status})>"
    
    @property
    def total_repair_cost(self) -> float:
        return float(sum((a.total_cost or 0) for a in self.repair_actions))
