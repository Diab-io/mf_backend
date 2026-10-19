import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.constants import UserRole
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.repair_action import RepairAction
from app.models.repair_request import RepairRequest
from app.models.user import User
from app.schemas.repair_action import CompleteRepairRequest, RepairActionCreate, RepairActionOut
from app.schemas.repair_request import RepairRequestOut
from app.services import approval_service

router = APIRouter(prefix="/repair-requests/{request_id}", tags=["repair-actions"])


async def _load(db: AsyncSession, request_id: uuid.UUID) -> RepairRequest:
    result = await db.execute(
        select(RepairRequest).options(selectinload(RepairRequest.equipment)).where(RepairRequest.id == request_id)
    )
    repair_request = result.scalar_one_or_none()
    if not repair_request:
        raise NotFoundError("Repair request not found.")
    return repair_request


def _can_act_on(repair_request: RepairRequest, user: User) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.SUPERVISOR):
        return True
    return user.role == UserRole.MECHANIC and repair_request.assigned_mechanic_id == user.id


@router.post("/start", response_model=RepairRequestOut)
async def start_repair(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _load(db, request_id)
    if not _can_act_on(repair_request, current_user):
        raise PermissionDeniedError("Only the assigned mechanic, a Supervisor or Admin can start this repair.")
    await approval_service.start_repair(db, repair_request, current_user)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post("/pending-parts", response_model=RepairRequestOut)
async def pending_parts(
    request_id: uuid.UUID, note: str | None = None,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _load(db, request_id)
    if not _can_act_on(repair_request, current_user):
        raise PermissionDeniedError("Only the assigned mechanic, a Supervisor or Admin can update this repair.")
    await approval_service.mark_pending_parts(db, repair_request, current_user, note)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post("/resume", response_model=RepairRequestOut)
async def resume_repair(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _load(db, request_id)
    if not _can_act_on(repair_request, current_user):
        raise PermissionDeniedError("Only the assigned mechanic, a Supervisor or Admin can resume this repair.")
    await approval_service.resume_repair(db, repair_request, current_user)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post("/complete", response_model=RepairRequestOut)
async def complete_repair(
    request_id: uuid.UUID, payload: CompleteRepairRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _load(db, request_id)
    if not _can_act_on(repair_request, current_user):
        raise PermissionDeniedError("Only the assigned mechanic, a Supervisor or Admin can complete this repair.")
    await approval_service.complete_repair(db, repair_request, current_user, payload.final_notes)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post(
    "/close", response_model=RepairRequestOut,
    dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.MD))],
)
async def close_repair(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _load(db, request_id)
    await approval_service.close_request(db, repair_request, current_user)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post("/actions", response_model=RepairActionOut, status_code=201)
async def add_repair_action(
    request_id: uuid.UUID, payload: RepairActionCreate,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _load(db, request_id)
    if not _can_act_on(repair_request, current_user):
        raise PermissionDeniedError("Only the assigned mechanic, a Supervisor or Admin can log repair actions.")

    action = RepairAction(
        repair_request_id=repair_request.id,
        performed_by_id=current_user.id,
        **payload.model_dump(),
    )
    approval_service.recompute_total_cost(action)
    db.add(action)

    # Keep the equipment's running total-maintenance-cost in sync.
    repair_request.equipment.total_maintenance_cost = (
        Decimal(repair_request.equipment.total_maintenance_cost) + Decimal(action.total_cost)
    )

    await db.commit()
    await db.refresh(action)
    return action


@router.get("/actions", response_model=list[RepairActionOut])
async def list_repair_actions(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _load(db, request_id)
    result = await db.execute(
        select(RepairAction).where(RepairAction.repair_request_id == request_id).order_by(RepairAction.action_date)
    )
    return list(result.scalars().all())
