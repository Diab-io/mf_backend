import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import settings

logger = structlog.get_logger("mf_backend.email")


def _send_sync(to: str, subject: str, body: str, reply_to: str | None = None) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    """Send an email. Returns True if sent (or logged in development), False on failure.

    Never raises, so it is safe as a background task. Callers that must tell the user
    about a failure (e.g. the contact form) can check the return value.
    """
    if not settings.SMTP_HOST:
        # Dev fallback only: never log message bodies (they may contain links or personal data) in production.
        if settings.ENVIRONMENT == "development":
            logger.info("email_not_configured", to=to, subject=subject, body=body)
            return True
        logger.warning("email_not_configured", to=to, subject=subject)
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, body, reply_to)
        return True
    except Exception:
        logger.exception("email_send_failed", to=to)
        return False
