from fastapi import APIRouter, Request, status

from app.core.config import settings
from app.core.constants import CONTACT_SERVICE_LABELS
from app.core.exceptions import AppError
from app.core.limiter import limiter
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email_service import send_email

router = APIRouter(prefix="/contact", tags=["contact"])

SUCCESS_MESSAGE = "Thank you for contacting us. We will get back to you shortly."


class ContactUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "We could not send your message right now. Please try again later."


@router.post("", response_model=ContactResponse)
@limiter.limit(settings.CONTACT_RATE_LIMIT)
async def submit_contact_form(request: Request, payload: ContactRequest):
    """Public endpoint (no auth): emails the enquiry to the company."""
    if payload.website:
        # Honeypot filled: pretend success, send nothing.
        return ContactResponse(message=SUCCESS_MESSAGE)

    if not settings.CONTACT_RECIPIENT_EMAIL:
        raise ContactUnavailableError()

    service_label = CONTACT_SERVICE_LABELS[payload.service]
    body = (
        "New enquiry from the website contact form\n"
        "=========================================\n\n"
        f"Service:  {service_label}\n"
        f"Name:     {payload.name}\n"
        f"Email:    {payload.email}\n"
        f"Phone:    {payload.phone or '-'}\n"
        f"Company:  {payload.company or '-'}\n\n"
        "Message:\n"
        f"{payload.message}\n"
    )
    sent = await send_email(
        to=settings.CONTACT_RECIPIENT_EMAIL,
        subject=f"New website enquiry: {service_label}",
        body=body,
        reply_to=str(payload.email),  # hitting Reply in the mailbox goes straight to the enquirer
    )
    if not sent:
        raise ContactUnavailableError()
    return ContactResponse(message=SUCCESS_MESSAGE)
