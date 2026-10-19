import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import ApprovalDecision, ApprovalStage, UserRole


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    comment: str | None = None


class ApprovalRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repair_request_id: uuid.UUID
    stage: ApprovalStage
    decided_by_id: uuid.UUID
    decision: ApprovalDecision
    comment: str | None
    created_at: datetime
    decided_by_role: UserRole
