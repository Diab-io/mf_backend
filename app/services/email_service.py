import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.core.config import settings

logger = structlog.get_logger("mf_backend.email")


def _send_sync(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        # Dev fallback only: never log message bodies (they contain reset links) in production.
        if settings.ENVIRONMENT == "development":
            logger.info("email_not_configured", to=to, subject=subject, body=body)
        else:
            logger.warning("email_not_configured", to=to, subject=subject)
        return
    try:
        await asyncio.to_thread(_send_sync, to, subject, body)
    except Exception:
        logger.exception("email_send_failed", to=to)
