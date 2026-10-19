from fastapi import APIRouter

from app.api.v1.endpoints import approvals, auth, equipment, notifications, repair_actions, repair_requests, reports, users

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(equipment.router)
api_router.include_router(repair_requests.router)
api_router.include_router(approvals.router)
api_router.include_router(repair_actions.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
