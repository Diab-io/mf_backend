from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.constants import EquipmentStatus, RepairStatus, UserRole
from app.db.session import get_db
from app.models.equipment import Equipment
from app.models.repair_action import RepairAction
from app.models.repair_request import RepairRequest
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
async def dashboard_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Role-aware snapshot: counts that matter to the logged-in role."""
    equipment_total = (await db.execute(select(func.count(Equipment.id)))).scalar_one()
    equipment_down = (
        await db.execute(select(func.count(Equipment.id)).where(Equipment.status == EquipmentStatus.OUT_OF_SERVICE))
    ).scalar_one()

    open_requests = (
        await db.execute(
            select(func.count(RepairRequest.id)).where(
                RepairRequest.status.notin_([RepairStatus.CLOSED, RepairStatus.CANCELLED])
            )
        )
    ).scalar_one()

    pending_supervisor = (
        await db.execute(select(func.count(RepairRequest.id)).where(RepairRequest.status == RepairStatus.PENDING_SUPERVISOR_APPROVAL))
    ).scalar_one()
    pending_md = (
        await db.execute(select(func.count(RepairRequest.id)).where(RepairRequest.status == RepairStatus.PENDING_MD_APPROVAL))
    ).scalar_one()
    in_progress = (
        await db.execute(select(func.count(RepairRequest.id)).where(RepairRequest.status == RepairStatus.REPAIR_IN_PROGRESS))
    ).scalar_one()

    summary = {
        "equipment_total": equipment_total,
        "equipment_out_of_service": equipment_down,
        "open_repair_requests": open_requests,
        "repairs_in_progress": in_progress,
    }

    if current_user.role in (UserRole.SUPERVISOR, UserRole.ADMIN):
        summary["pending_supervisor_approval"] = pending_supervisor
    if current_user.role in (UserRole.MD, UserRole.ADMIN):
        summary["pending_md_approval"] = pending_md
    if current_user.role == UserRole.MECHANIC:
        my_open = (
            await db.execute(
                select(func.count(RepairRequest.id)).where(
                    RepairRequest.assigned_mechanic_id == current_user.id,
                    RepairRequest.status.notin_([RepairStatus.CLOSED, RepairStatus.CANCELLED]),
                )
            )
        ).scalar_one()
        summary["my_assigned_open_requests"] = my_open

    return summary


@router.get("/maintenance-cost", dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.MD, UserRole.ADMIN))])
async def maintenance_cost_report(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Total repair cost grouped by equipment, optionally bounded by date range."""
    stmt = (
        select(
            Equipment.id,
            Equipment.name,
            Equipment.registration_number,
            func.coalesce(func.sum(RepairAction.total_cost), 0).label("total_cost"),
            func.count(RepairAction.id).label("action_count"),
        )
        .join(RepairRequest, RepairRequest.equipment_id == Equipment.id, isouter=True)
        .join(RepairAction, RepairAction.repair_request_id == RepairRequest.id, isouter=True)
        .group_by(Equipment.id, Equipment.name, Equipment.registration_number)
    )
    if start_date:
        stmt = stmt.where(RepairAction.action_date >= start_date)
    if end_date:
        stmt = stmt.where(RepairAction.action_date <= end_date)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "equipment_id": row.id,
            "equipment_name": row.name,
            "registration_number": row.registration_number,
            "total_cost": float(row.total_cost or 0),
            "action_count": row.action_count,
        }
        for row in rows
    ]


@router.get("/equipment-downtime", dependencies=[Depends(require_roles(UserRole.SUPERVISOR, UserRole.MD, UserRole.ADMIN))])
async def equipment_status_breakdown(db: AsyncSession = Depends(get_db)):
    """Count of equipment per status — the closest MVP proxy for downtime visibility."""
    stmt = select(Equipment.status, func.count(Equipment.id)).group_by(Equipment.status)
    result = await db.execute(stmt)
    return {status.value: count for status, count in result.all()}
