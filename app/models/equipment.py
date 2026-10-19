from datetime import date

from sqlalchemy import Date, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EquipmentStatus
from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Equipment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "equipment"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    equipment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registration_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity_spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    assigned_site: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(EquipmentStatus, name="equipment_status", values_callable=lambda x: [e.value for e in x]),
        default=EquipmentStatus.OPERATIONAL, nullable=False
    )
    last_maintenance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_maintenance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_maintenance_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    repair_requests = relationship("RepairRequest", back_populates="equipment")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Equipment {self.registration_number}>"
