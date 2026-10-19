"""
The workflow/state-machine engine for a RepairRequest. All status changes in
the system must go through `transition()` so that:
  - only legal transitions (ALLOWED_TRANSITIONS) are permitted,
  - every change is written to AuditLog,
  - the right people get notified.

Endpoints should never set `repair_request.status = ...` directly.
"""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ApprovalDecision,
    ApprovalStage,
    NotificationType,
    RepairStatus,
    UserRole,
    ALLOWED_TRANSITIONS,
)
from app.core.exceptions import InvalidTransitionError, PermissionDeniedError
from app.models.approval import ApprovalRecord
from app.models.audit_log import AuditLog
from app.models.equipment import Equipment
from app.models.repair_action import RepairAction
from app.models.repair_request import RepairRequest
from app.models.user import User
from app.services.notification_service import notify_role, notify_users


async def transition(
    db: AsyncSession,
    repair_request: RepairRequest,
    new_status: RepairStatus,
    actor: User,
    detail: str | None = None,
) -> None:
    current = repair_request.status
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot move request from '{current.value}' to '{new_status.value}'."
        )
    db.add(
        AuditLog(
            repair_request_id=repair_request.id,
            actor_id=actor.id,
            actor_role=actor.role,
            action="status_transition",
            from_status=current.value,
            to_status=new_status.value,
            detail=detail,
        )
    )
    repair_request.status = new_status


async def submit_request(db: AsyncSession, repair_request: RepairRequest, actor: User) -> None:
    """Mechanic/Supervisor submits a draft (or re-submits a returned request)."""
    if repair_request.status == RepairStatus.DRAFT:
        await transition(db, repair_request, RepairStatus.SUBMITTED, actor)
    if repair_request.status == RepairStatus.SUBMITTED:
        await transition(db, repair_request, RepairStatus.PENDING_SUPERVISOR_APPROVAL, actor)
    elif repair_request.status == RepairStatus.REJECTED_RETURNED:
        await transition(db, repair_request, RepairStatus.SUBMITTED, actor)
        await transition(db, repair_request, RepairStatus.PENDING_SUPERVISOR_APPROVAL, actor)

    await notify_role(
        db,
        UserRole.SUPERVISOR,
        NotificationType.NEW_FAULT_REPORT,
        f"New fault report {repair_request.request_number} requires your approval.",
        repair_request.id,
    )
    if repair_request.priority.value == "critical":
        await notify_role(
            db,
            UserRole.MD,
            NotificationType.CRITICAL_FAULT,
            f"CRITICAL fault reported: {repair_request.request_number}.",
            repair_request.id,
        )


async def supervisor_decide(
    db: AsyncSession,
    repair_request: RepairRequest,
    actor: User,
    decision: ApprovalDecision,
    comment: str | None,
) -> None:
    if actor.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise PermissionDeniedError("Only a Supervisor can record this decision.")
    if repair_request.status != RepairStatus.PENDING_SUPERVISOR_APPROVAL:
        raise InvalidTransitionError("This request is not awaiting Supervisor approval.")
    if repair_request.reported_by_id == actor.id:
        raise PermissionDeniedError("A mechanic cannot approve their own request.")

    db.add(
        ApprovalRecord(
            repair_request_id=repair_request.id,
            stage=ApprovalStage.SUPERVISOR,
            decided_by_id=actor.id,
            decided_by_role=actor.role,
            decision=decision,
            comment=comment,
        )
    )

    if decision == ApprovalDecision.APPROVE:
        await transition(db, repair_request, RepairStatus.SUPERVISOR_APPROVED, actor, comment)
        await transition(db, repair_request, RepairStatus.PENDING_MD_APPROVAL, actor)
        await notify_role(
            db, UserRole.MD, NotificationType.SUPERVISOR_APPROVED,
            f"{repair_request.request_number} approved by Supervisor; awaiting your final approval.",
            repair_request.id,
        )
    elif decision == ApprovalDecision.REJECT_RETURN:
        await transition(db, repair_request, RepairStatus.REJECTED_RETURNED, actor, comment)
        await notify_users(
            db, [repair_request.reporter], NotificationType.REJECTED,
            f"{repair_request.request_number} was returned by your Supervisor: {comment or 'no comment given'}",
            repair_request.id,
        )
    else:  # REQUEST_INFO
        await notify_users(
            db, [repair_request.reporter], NotificationType.REQUEST_MORE_INFO,
            f"Supervisor requested more information on {repair_request.request_number}: {comment or ''}",
            repair_request.id,
        )


async def md_decide(
    db: AsyncSession,
    repair_request: RepairRequest,
    actor: User,
    decision: ApprovalDecision,
    comment: str | None,
) -> None:
    if actor.role not in (UserRole.MD, UserRole.ADMIN):
        raise PermissionDeniedError("Only the Managing Director can record this decision.")
    if repair_request.status != RepairStatus.PENDING_MD_APPROVAL:
        raise InvalidTransitionError("This request is not awaiting MD approval.")

    db.add(
        ApprovalRecord(
            repair_request_id=repair_request.id,
            stage=ApprovalStage.MD,
            decided_by_id=actor.id,
            decided_by_role=actor.role,
            decision=decision,
            comment=comment,
        )
    )

    if decision == ApprovalDecision.APPROVE:
        await transition(db, repair_request, RepairStatus.APPROVED, actor, comment)
        recipients = [repair_request.assigned_mechanic] if repair_request.assigned_mechanic else [repair_request.reporter]
        await notify_users(
            db, recipients, NotificationType.MD_APPROVED,
            f"{repair_request.request_number} received final approval and is authorised for repair.",
            repair_request.id,
        )
    elif decision == ApprovalDecision.REJECT_RETURN:
        await transition(db, repair_request, RepairStatus.REJECTED_RETURNED, actor, comment)
        await notify_users(
            db, [repair_request.reporter], NotificationType.REJECTED,
            f"{repair_request.request_number} was returned by the MD: {comment or 'no comment given'}",
            repair_request.id,
        )
    else:  # REQUEST_INFO
        await notify_users(
            db, [repair_request.reporter], NotificationType.REQUEST_MORE_INFO,
            f"MD requested more information on {repair_request.request_number}: {comment or ''}",
            repair_request.id,
        )


async def assign_mechanic(db: AsyncSession, repair_request: RepairRequest, mechanic: User, actor: User) -> None:
    if repair_request.status not in (RepairStatus.APPROVED, RepairStatus.PENDING_SUPERVISOR_APPROVAL, RepairStatus.SUPERVISOR_APPROVED, RepairStatus.PENDING_MD_APPROVAL):
        raise InvalidTransitionError("Mechanics can only be assigned before or after full approval, not on closed/cancelled requests.")
    if mechanic.role != UserRole.MECHANIC:
        raise PermissionDeniedError("Only a user with the Mechanic role can be assigned to a repair.")
    repair_request.assigned_mechanic_id = mechanic.id
    db.add(
        AuditLog(
            repair_request_id=repair_request.id,
            actor_id=actor.id,
            actor_role=actor.role,
            action="assign_mechanic",
            detail=f"Assigned to {mechanic.full_name}",
        )
    )


async def start_repair(db: AsyncSession, repair_request: RepairRequest, actor: User) -> None:
    await transition(db, repair_request, RepairStatus.REPAIR_IN_PROGRESS, actor)
    repair_request.equipment.status = repair_request.equipment.status.__class__.UNDER_MAINTENANCE


async def mark_pending_parts(db: AsyncSession, repair_request: RepairRequest, actor: User, note: str | None) -> None:
    await transition(db, repair_request, RepairStatus.PENDING_PARTS, actor, note)


async def resume_repair(db: AsyncSession, repair_request: RepairRequest, actor: User) -> None:
    await transition(db, repair_request, RepairStatus.REPAIR_IN_PROGRESS, actor)


async def complete_repair(db: AsyncSession, repair_request: RepairRequest, actor: User, final_notes: str | None) -> None:
    await transition(db, repair_request, RepairStatus.REPAIR_COMPLETED, actor, final_notes)
    equipment: Equipment = repair_request.equipment
    equipment.status = equipment.status.__class__.OPERATIONAL
    equipment.last_maintenance_date = date.today()
    await notify_role(
        db, UserRole.SUPERVISOR, NotificationType.REPAIR_COMPLETED,
        f"Repair completed for {repair_request.request_number}; pending verification.",
        repair_request.id,
    )
    await notify_role(
        db, UserRole.ADMIN, NotificationType.REPAIR_COMPLETED,
        f"Repair completed for {repair_request.request_number}; pending verification.",
        repair_request.id,
    )


async def close_request(db: AsyncSession, repair_request: RepairRequest, actor: User) -> None:
    if actor.role not in (UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.MD):
        raise PermissionDeniedError("Only a Supervisor, MD or Admin can verify and close a repair request.")
    await transition(db, repair_request, RepairStatus.CLOSED, actor)


async def cancel_request(db: AsyncSession, repair_request: RepairRequest, actor: User, reason: str | None) -> None:
    await transition(db, repair_request, RepairStatus.CANCELLED, actor, reason)


def recompute_total_cost(action: RepairAction) -> None:
    quantity = action.quantity or 0
    unit_cost = action.unit_cost or 0
    labour = action.labour_cost or 0
    action.total_cost = (quantity * unit_cost) + labour
