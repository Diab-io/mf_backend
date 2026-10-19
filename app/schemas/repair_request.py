import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import FaultType, Priority, RepairStatus
from app.schemas.attachment import AttachmentOut
from app.schemas.repair_action import RepairActionOut
from app.schemas.audit_log import AuditLogOut
from app.schemas.approval import ApprovalRecordOut


class RepairRequestCreate(BaseModel):
    equipment_id: uuid.UUID
    fault_datetime: datetime
    fault_type: FaultType
    priority: Priority
    fault_description: str = Field(min_length=3)
    fault_detected_by: str | None = None
    repair_recommendation: str | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    submit_immediately: bool = Field(
        default=False, description="If true, moves the request straight to Pending Supervisor Approval."
    )


class RepairRequestUpdate(BaseModel):
    """Only allowed while status == draft, and only by the reporting mechanic/admin."""
    fault_datetime: datetime | None = None
    fault_type: FaultType | None = None
    priority: Priority | None = None
    fault_description: str | None = None
    fault_detected_by: str | None = None
    repair_recommendation: str | None = None
    estimated_cost: float | None = Field(default=None, ge=0)


class RepairRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_number: str
    equipment_id: uuid.UUID
    reported_by_id: uuid.UUID
    assigned_mechanic_id: uuid.UUID | None
    fault_detected_by: str | None
    fault_datetime: datetime
    fault_type: FaultType
    priority: Priority
    fault_description: str
    repair_recommendation: str | None
    status: RepairStatus
    estimated_cost: float | None
    created_at: datetime
    updated_at: datetime


class RepairRequestDetailOut(RepairRequestOut):
    attachments: list[AttachmentOut] = []
    repair_actions: list[RepairActionOut] = []
    approvals: list[ApprovalRecordOut] = []
    audit_trail: list[AuditLogOut] = []
    total_repair_cost: float = 0


class AssignMechanicRequest(BaseModel):
    mechanic_id: uuid.UUID


class SetEstimatedCostRequest(BaseModel):
    estimated_cost: float = Field(ge=0)
