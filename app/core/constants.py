"""
Enumerations shared across models, schemas and services.
Keeping them in one place avoids drift between the DB layer and the API layer.
"""
import enum


class UserRole(str, enum.Enum):
    MECHANIC = "mechanic"
    SUPERVISOR = "supervisor"
    MD = "md"
    ADMIN = "admin"


class EquipmentStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    UNDER_MAINTENANCE = "under_maintenance"
    OUT_OF_SERVICE = "out_of_service"


class FaultType(str, enum.Enum):
    CORRECTIVE = "corrective_maintenance"
    PREVENTIVE = "preventive_maintenance"
    EMERGENCY = "emergency_repair"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RepairStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_SUPERVISOR_APPROVAL = "pending_supervisor_approval"
    SUPERVISOR_APPROVED = "supervisor_approved"
    PENDING_MD_APPROVAL = "pending_md_approval"
    APPROVED = "approved"
    REPAIR_IN_PROGRESS = "repair_in_progress"
    PENDING_PARTS = "pending_parts"
    REPAIR_COMPLETED = "repair_completed"
    CLOSED = "closed"
    REJECTED_RETURNED = "rejected_returned"
    CANCELLED = "cancelled"


# Valid forward transitions. Anything not listed here is rejected by the
# workflow engine (app/services/approval_service.py). This is the single
# source of truth for the state machine.
ALLOWED_TRANSITIONS: dict[RepairStatus, set[RepairStatus]] = {
    RepairStatus.DRAFT: {RepairStatus.SUBMITTED, RepairStatus.CANCELLED},
    RepairStatus.SUBMITTED: {RepairStatus.PENDING_SUPERVISOR_APPROVAL, RepairStatus.CANCELLED},
    RepairStatus.PENDING_SUPERVISOR_APPROVAL: {
        RepairStatus.SUPERVISOR_APPROVED,
        RepairStatus.REJECTED_RETURNED,
        RepairStatus.CANCELLED,
    },
    RepairStatus.SUPERVISOR_APPROVED: {RepairStatus.PENDING_MD_APPROVAL, RepairStatus.CANCELLED},
    RepairStatus.PENDING_MD_APPROVAL: {
        RepairStatus.APPROVED,
        RepairStatus.REJECTED_RETURNED,
        RepairStatus.CANCELLED,
    },
    RepairStatus.APPROVED: {RepairStatus.REPAIR_IN_PROGRESS, RepairStatus.CANCELLED},
    RepairStatus.REPAIR_IN_PROGRESS: {
        RepairStatus.PENDING_PARTS,
        RepairStatus.REPAIR_COMPLETED,
        RepairStatus.CANCELLED,
    },
    RepairStatus.PENDING_PARTS: {RepairStatus.REPAIR_IN_PROGRESS, RepairStatus.CANCELLED},
    RepairStatus.REPAIR_COMPLETED: {RepairStatus.CLOSED},
    RepairStatus.REJECTED_RETURNED: {RepairStatus.SUBMITTED, RepairStatus.CANCELLED},
    RepairStatus.CLOSED: set(),
    RepairStatus.CANCELLED: set(),
}


class ApprovalDecision(str, enum.Enum):
    APPROVE = "approve"
    REJECT_RETURN = "reject_return"
    REQUEST_INFO = "request_info"


class ApprovalStage(str, enum.Enum):
    SUPERVISOR = "supervisor"
    MD = "md"


class NotificationType(str, enum.Enum):
    NEW_FAULT_REPORT = "new_fault_report"
    SUPERVISOR_APPROVED = "supervisor_approved"
    MD_APPROVED = "md_approved"
    REQUEST_MORE_INFO = "request_more_info"
    REPAIR_COMPLETED = "repair_completed"
    CRITICAL_FAULT = "critical_fault"
    REJECTED = "rejected"
