import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    repair_request_id: uuid.UUID | None
    actor_id: uuid.UUID
    action: str
    from_status: str | None
    to_status: str | None
    detail: str | None
    created_at: datetime

from app.core.constants import UserRole  # noqa: E402  (placed after class to avoid a circular import at module load)

AuditLogOut.model_rebuild()