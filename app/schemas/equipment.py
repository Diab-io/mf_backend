import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import EquipmentStatus
from app.schemas.repair_request import RepairRequestOut


class EquipmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    equipment_type: str | None = None
    registration_number: str = Field(min_length=1, max_length=100)
    serial_number: str | None = None
    model_number: str | None = None
    capacity_spec: str | None = None
    current_location: str | None = None
    assigned_site: str | None = None
    next_maintenance_date: date | None = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: str | None = None
    equipment_type: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    capacity_spec: str | None = None
    current_location: str | None = None
    assigned_site: str | None = None
    status: EquipmentStatus | None = None
    next_maintenance_date: date | None = None


class EquipmentOut(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: EquipmentStatus
    last_maintenance_date: date | None
    total_maintenance_cost: float
    created_at: datetime
    updated_at: datetime


class EquipmentDetailOut(EquipmentOut):
    repair_requests: list[RepairRequestOut] = []
