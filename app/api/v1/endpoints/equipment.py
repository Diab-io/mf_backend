import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, require_roles
from app.core.constants import EquipmentStatus, UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models.equipment import Equipment
from app.models.user import User
from sqlalchemy.orm import selectinload
from app.schemas.equipment import EquipmentCreate, EquipmentDetailOut, EquipmentOut, EquipmentUpdate

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.post(
    "", response_model=EquipmentOut, status_code=201,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR))],
)
async def create_equipment(payload: EquipmentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Equipment).where(Equipment.registration_number == payload.registration_number))
    if existing.scalar_one_or_none():
        raise ConflictError("Equipment with this registration number already exists.")
    equipment = Equipment(**payload.model_dump())
    db.add(equipment)
    await db.commit()
    await db.refresh(equipment)
    return equipment


@router.get("", response_model=list[EquipmentOut])
async def list_equipment(
    status_filter: EquipmentStatus | None = None,
    site: str | None = None,
    search: str | None = None,
    pagination: Pagination = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Equipment).offset(pagination.offset).limit(pagination.page_size)
    if status_filter:
        stmt = stmt.where(Equipment.status == status_filter)
    if site:
        stmt = stmt.where(Equipment.assigned_site == site)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (Equipment.name.ilike(like))
            | (Equipment.registration_number.ilike(like))
            | (Equipment.serial_number.ilike(like))
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{equipment_id}", response_model=EquipmentDetailOut)
async def get_equipment(equipment_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Equipment).options(selectinload(Equipment.repair_requests)).where(Equipment.id == equipment_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment not found.")
    return equipment


@router.patch(
    "/{equipment_id}", response_model=EquipmentOut,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR))],
)
async def update_equipment(equipment_id: uuid.UUID, payload: EquipmentUpdate, db: AsyncSession = Depends(get_db)):
    equipment = await db.get(Equipment, equipment_id)
    if not equipment:
        raise NotFoundError("Equipment not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    await db.commit()
    await db.refresh(equipment)
    return equipment
