import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RepairActionCreate(BaseModel):
    action_date: date
    action_taken: str = Field(min_length=1)
    parts_materials_used: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit_cost: float | None = Field(default=None, ge=0)
    labour_cost: float | None = Field(default=None, ge=0)
    notes: str | None = None
    invoice_attachment_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def compute_total(self):
        # total_cost is derived server-side in the service layer from
        # quantity * unit_cost + labour_cost, but we validate inputs here.
        return self


class RepairActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repair_request_id: uuid.UUID
    action_date: date
    action_taken: str
    parts_materials_used: str | None
    quantity: float | None
    unit_cost: float | None
    labour_cost: float | None
    total_cost: float
    performed_by_id: uuid.UUID
    notes: str | None
    invoice_attachment_id: uuid.UUID | None
    created_at: datetime


class CompleteRepairRequest(BaseModel):
    final_notes: str | None = None
