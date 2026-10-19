"""
Domain-specific exceptions and the handlers that turn them into consistent
JSON error responses. Keeping domain errors free of HTTP concerns (no
HTTPException inside services) keeps the service layer testable and reusable.
"""
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("mf_backend")


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "You do not have permission to perform this action."


class InvalidTransitionError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "This action is not valid for the request's current status."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "The request conflicts with existing data."


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Validation failed."


def _error_body(request_id: str, message: str, details=None):
    body = {"error": {"request_id": request_id, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.warning("app_error", extra={"request_id": request_id, "detail": exc.message})
        return JSONResponse(status_code=exc.status_code, content=_error_body(request_id, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(request_id, "Validation failed.", details=exc.errors()),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error("db_integrity_error", extra={"request_id": request_id, "error": str(exc.orig)})
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(request_id, "A database constraint was violated (duplicate or invalid reference)."),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception("unhandled_error", extra={"request_id": request_id})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(request_id, "Internal server error."),
        )
