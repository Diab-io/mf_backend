import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_type: NotificationType
    message: str
    is_read: bool
    repair_request_id: uuid.UUID | None
    created_at: datetime
