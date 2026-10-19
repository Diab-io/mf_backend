import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class RepairAction(UUIDPkMixin, TimestampMixin, Base):
    """
    One row per repair action / cost entry. Always linked to a
    Repair Request ID so every cost stays traceable (spec section 11).
    """
    __tablename__ = "repair_actions"

    repair_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repair_requests.id"), nullable=False
    )
    repair_request = relationship("RepairRequest", back_populates="repair_actions")

    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    parts_materials_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    labour_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    performed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    performed_by = relationship("User")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id"), nullable=True
    )
    invoice_attachment = relationship("Attachment")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RepairAction {self.repair_request_id} {self.action_date}>"
