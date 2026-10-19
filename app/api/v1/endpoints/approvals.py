import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Pagination, get_current_user, require_roles
from app.core.constants import RepairStatus, UserRole
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.repair_request import RepairRequest
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest, ApprovalRecordOut
from app.schemas.repair_request import RepairRequestOut
from app.services import approval_service

router = APIRouter(tags=["approvals"])


async def _load(db: AsyncSession, request_id: uuid.UUID) -> RepairRequest:
    result = await db.execute(
        select(RepairRequest)
        .options(selectinload(RepairRequest.reporter), selectinload(RepairRequest.assigned_mechanic), selectinload(RepairRequest.equipment))
        .where(RepairRequest.id == request_id)
    )
    repair_request = result.scalar_one_or_none()
    if not repair_request:
        raise NotFoundError("Repair request not found.")
    return repair_request


@router.get(
    "/approval-queue", response_model=list[RepairRequestOut],
    dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.MD, UserRole.ADMIN))],
)
async def approval_queue(
    current_user: User = Depends(get_current_user),
    pagination: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.MD:
        target_status = RepairStatus.PENDING_MD_APPROVAL
    else:
        target_status = RepairStatus.PENDING_SUPERVISOR_APPROVAL

    stmt = (
        select(RepairRequest)
        .where(RepairRequest.status == target_status)
        .order_by(RepairRequest.priority.desc(), RepairRequest.created_at.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/repair-requests/{request_id}/supervisor-decision", response_model=RepairRequestOut)
async def supervisor_decision(
    request_id: uuid.UUID, payload: ApprovalDecisionRequest,
    current_user: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repair_request = await _load(db, request_id)
    await approval_service.supervisor_decide(db, repair_request, current_user, payload.decision, payload.comment)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.post("/repair-requests/{request_id}/md-decision", response_model=RepairRequestOut)
async def md_decision(
    request_id: uuid.UUID, payload: ApprovalDecisionRequest,
    current_user: User = Depends(require_roles(UserRole.MD, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repair_request = await _load(db, request_id)
    await approval_service.md_decide(db, repair_request, current_user, payload.decision, payload.comment)
    await db.commit()
    await db.refresh(repair_request)
    return repair_request


@router.get("/repair-requests/{request_id}/approvals", response_model=list[ApprovalRecordOut])
async def approval_history(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _load(db, request_id)
    from app.models.approval import ApprovalRecord

    result = await db.execute(
        select(ApprovalRecord).where(ApprovalRecord.repair_request_id == request_id).order_by(ApprovalRecord.created_at)
    )
    return list(result.scalars().all())
