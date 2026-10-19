import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Pagination, get_current_user, require_roles
from app.core.constants import Priority, RepairStatus, UserRole
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.equipment import Equipment
from app.models.repair_request import RepairRequest
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.schemas.repair_request import (
    AssignMechanicRequest,
    RepairRequestCreate,
    RepairRequestDetailOut,
    RepairRequestOut,
    RepairRequestUpdate,
    SetEstimatedCostRequest,
)
from app.services import approval_service, file_storage
from app.services.numbering import generate_request_number
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut
from datetime import datetime

router = APIRouter(prefix="/repair-requests", tags=["repair-requests"])


async def _get_request_or_404(db: AsyncSession, request_id: uuid.UUID) -> RepairRequest:
    result = await db.execute(
        select(RepairRequest)
        .options(selectinload(RepairRequest.attachments),
                 selectinload(RepairRequest.equipment), selectinload(RepairRequest.reporter),
                 selectinload(RepairRequest.assigned_mechanic), selectinload(RepairRequest.repair_actions), selectinload(RepairRequest.approvals))
        .where(RepairRequest.id == request_id)
    )
    repair_request = result.scalar_one_or_none()
    if not repair_request:
        raise NotFoundError("Repair request not found.")
    return repair_request


@router.post(
    "", response_model=RepairRequestDetailOut, status_code=201,
    dependencies=[Depends(require_roles(UserRole.MECHANIC, UserRole.SUPERVISOR, UserRole.ADMIN))],
)
async def create_repair_request(
    payload: RepairRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    equipment = await db.get(Equipment, payload.equipment_id)
    if not equipment:
        raise NotFoundError("Equipment not found.")

    request_number = await generate_request_number(db)
    repair_request = RepairRequest(
        request_number=request_number,
        equipment_id=equipment.id,
        reported_by_id=current_user.id,
        fault_detected_by=payload.fault_detected_by,
        fault_datetime=payload.fault_datetime,
        fault_type=payload.fault_type,
        priority=payload.priority,
        fault_description=payload.fault_description,
        estimated_cost=payload.estimated_cost,
        repair_recommendation=payload.repair_recommendation,
        status=RepairStatus.DRAFT,
    )
    db.add(repair_request)
    await db.flush()
    repair_request.reporter = current_user
    repair_request.equipment = equipment

    if payload.submit_immediately:
        await approval_service.submit_request(db, repair_request, current_user)

    await db.commit()
    return await _get_request_or_404(db, repair_request.id)


@router.get("", response_model=list[RepairRequestOut])
async def list_repair_requests(
    status_filter: RepairStatus | None = None,
    priority: Priority | None = None,
    equipment_id: uuid.UUID | None = None,
    assigned_mechanic_id: uuid.UUID | None = None,
    site: str | None = None,
    search: str | None = None,
    fault_date_from: datetime | None = None,
    fault_date_to: datetime | None = None,
    mine: bool = False,
    pagination: Pagination = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RepairRequest).offset(pagination.offset).limit(pagination.page_size).order_by(RepairRequest.created_at.desc())

    if current_user.role == UserRole.MECHANIC:
        stmt = stmt.where(
            (RepairRequest.reported_by_id == current_user.id)
            | (RepairRequest.assigned_mechanic_id == current_user.id)
        )
    elif mine:
        stmt = stmt.where(RepairRequest.reported_by_id == current_user.id)

    if status_filter:
        stmt = stmt.where(RepairRequest.status == status_filter)
    if priority:
        stmt = stmt.where(RepairRequest.priority == priority)
    if equipment_id:
        stmt = stmt.where(RepairRequest.equipment_id == equipment_id)
    if assigned_mechanic_id:
        stmt = stmt.where(RepairRequest.assigned_mechanic_id == assigned_mechanic_id)
    if fault_date_from:
        stmt = stmt.where(RepairRequest.fault_datetime >= fault_date_from)
    if fault_date_to:
        stmt = stmt.where(RepairRequest.fault_datetime <= fault_date_to)

    if site or search:
        stmt = stmt.join(Equipment, Equipment.id == RepairRequest.equipment_id)
    if site:
        stmt = stmt.where(Equipment.assigned_site == site)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (RepairRequest.request_number.ilike(like))
            | (Equipment.registration_number.ilike(like))
            | (Equipment.serial_number.ilike(like))
            | (Equipment.name.ilike(like))
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{request_id}", response_model=RepairRequestDetailOut)
async def get_repair_request(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _get_request_or_404(db, request_id)
    if current_user.role == UserRole.MECHANIC and current_user.id not in (
        repair_request.reported_by_id, repair_request.assigned_mechanic_id,
    ):
        raise PermissionDeniedError("You can only view your own reported or assigned repair requests.")
    return repair_request


@router.patch("/{request_id}", response_model=RepairRequestDetailOut)
async def update_repair_request(
    request_id: uuid.UUID, payload: RepairRequestUpdate,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    if repair_request.status not in (RepairStatus.DRAFT, RepairStatus.REJECTED_RETURNED):
        raise ValidationFailedError("Only draft or returned requests can be edited.")
    if current_user.role not in (UserRole.ADMIN,) and repair_request.reported_by_id != current_user.id:
        raise PermissionDeniedError("You can only edit your own requests.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(repair_request, field, value)
    await db.commit()
    return await _get_request_or_404(db, request_id)


@router.post("/{request_id}/submit", response_model=RepairRequestDetailOut)
async def submit_repair_request(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _get_request_or_404(db, request_id)
    if current_user.role not in (UserRole.ADMIN,) and repair_request.reported_by_id != current_user.id:
        raise PermissionDeniedError("You can only submit your own requests.")
    await approval_service.submit_request(db, repair_request, current_user)
    await db.commit()
    return await _get_request_or_404(db, request_id)


@router.post(
    "/{request_id}/assign-mechanic", response_model=RepairRequestDetailOut,
    dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.MD))],
)
async def assign_mechanic(
    request_id: uuid.UUID, payload: AssignMechanicRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    mechanic = await db.get(User, payload.mechanic_id)
    if not mechanic:
        raise NotFoundError("Mechanic not found.")
    await approval_service.assign_mechanic(db, repair_request, mechanic, current_user)
    await db.commit()
    return await _get_request_or_404(db, request_id)


@router.post(
    "/{request_id}/estimated-cost", response_model=RepairRequestDetailOut,
    dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.ADMIN))],
)
async def set_estimated_cost(
    request_id: uuid.UUID, payload: SetEstimatedCostRequest, db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    repair_request.estimated_cost = payload.estimated_cost
    await db.commit()
    return await _get_request_or_404(db, request_id)


@router.post("/{request_id}/cancel", response_model=RepairRequestDetailOut)
async def cancel_repair_request(
    request_id: uuid.UUID, reason: str | None = None,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.MD) and repair_request.reported_by_id != current_user.id:
        raise PermissionDeniedError("You cannot cancel this request.")
    await approval_service.cancel_request(db, repair_request, current_user, reason)
    await db.commit()
    return await _get_request_or_404(db, request_id)


@router.post("/{request_id}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    request_id: uuid.UUID, file: UploadFile = File(...),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    stored_filename, size = await file_storage.save_upload(file)
    attachment = Attachment(
        repair_request_id=repair_request.id,
        uploaded_by_id=current_user.id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=file.content_type,
        size_bytes=size,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{request_id}/attachments", response_model=list[AttachmentOut])
async def list_attachments(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_request_or_404(db, request_id)  # 404 / existence check
    result = await db.execute(select(Attachment).where(Attachment.repair_request_id == request_id))
    return list(result.scalars().all())


@router.get("/{request_id}/attachments/{attachment_id}/download")
async def download_attachment(
    request_id: uuid.UUID, attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    repair_request = await _get_request_or_404(db, request_id)
    if current_user.role == UserRole.MECHANIC and current_user.id not in (
        repair_request.reported_by_id, repair_request.assigned_mechanic_id,
    ):
        raise PermissionDeniedError("You can only download attachments on your own requests.")

    attachment = await db.get(Attachment, attachment_id)
    if not attachment or attachment.repair_request_id != request_id:
        raise NotFoundError("Attachment not found.")

    path = file_storage.resolve_path(attachment.stored_filename)
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_filename)


@router.get("/{request_id}/audit-trail", response_model=list[AuditLogOut])
async def audit_trail(request_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repair_request = await _get_request_or_404(db, request_id)
    if current_user.role == UserRole.MECHANIC and current_user.id not in (
        repair_request.reported_by_id, repair_request.assigned_mechanic_id,
    ):
        raise PermissionDeniedError("You can only view the audit trail on your own or assigned requests.")

    result = await db.execute(
        select(AuditLog).where(AuditLog.repair_request_id == request_id).order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())
