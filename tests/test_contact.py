import pytest

from app.core.config import settings
from app.core.limiter import limiter

URL = "/api/v1/contact"
VALID = {
    "name": "Ada Obi",
    "email": "ada@example.com",
    "phone": "08012345678",
    "company": "Acme Oil",
    "service": "procurement",
    "message": "We need a quote for pipe fittings.",
}


@pytest.fixture(autouse=True)
def _reset_limiter_and_settings(monkeypatch):
    limiter.reset()
    monkeypatch.setattr(settings, "CONTACT_RECIPIENT_EMAIL", "info@mfventures.com")
    yield
    limiter.reset()


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    async def fake_send(to, subject, body, reply_to=None):
        sent.append({"to": to, "subject": subject, "body": body, "reply_to": reply_to})
        return True

    monkeypatch.setattr("app.api.v1.endpoints.contact.send_email", fake_send)
    return sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,label",
    [("security_service", "Security service"), ("procurement", "Procurement"), ("engineering_support", "Engineering support")],
)
async def test_each_service_option_sends_mail(client, outbox, value, label):
    r = await client.post(URL, json={**VALID, "service": value})
    assert r.status_code == 200, r.text
    assert len(outbox) == 1
    mail = outbox[0]
    assert mail["to"] == "info@mfventures.com"
    assert label in mail["subject"]
    assert f"Service:  {label}" in mail["body"]
    assert "Ada Obi" in mail["body"] and "ada@example.com" in mail["body"] and "pipe fittings" in mail["body"]
    assert mail["reply_to"] == "ada@example.com"


@pytest.mark.asyncio
async def test_optional_fields_can_be_omitted(client, outbox):
    r = await client.post(URL, json={k: v for k, v in VALID.items() if k not in ("phone", "company")})
    assert r.status_code == 200
    assert "Phone:    -" in outbox[0]["body"]


@pytest.mark.asyncio
async def test_service_is_required(client, outbox):
    payload = {k: v for k, v in VALID.items() if k != "service"}
    assert (await client.post(URL, json=payload)).status_code == 422
    assert (await client.post(URL, json={**VALID, "service": ""})).status_code == 422
    assert (await client.post(URL, json={**VALID, "service": None})).status_code == 422
    assert outbox == []


@pytest.mark.asyncio
async def test_service_must_be_one_of_the_options(client, outbox):
    assert (await client.post(URL, json={**VALID, "service": "catering"})).status_code == 422
    assert outbox == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [{"email": "not-an-email"}, {"name": "A"}, {"message": "short"}, {"message": "x" * 5001}, {"phone": "1" * 31}],
)
async def test_validation_errors(client, outbox, patch):
    assert (await client.post(URL, json={**VALID, **patch})).status_code == 422
    assert outbox == []


@pytest.mark.asyncio
async def test_honeypot_returns_success_but_sends_nothing(client, outbox):
    r = await client.post(URL, json={**VALID, "website": "http://spam.example"})
    assert r.status_code == 200
    assert outbox == []


@pytest.mark.asyncio
async def test_no_recipient_configured_returns_503(client, outbox, monkeypatch):
    monkeypatch.setattr(settings, "CONTACT_RECIPIENT_EMAIL", "")
    assert (await client.post(URL, json=VALID)).status_code == 503
    assert outbox == []


@pytest.mark.asyncio
async def test_email_failure_returns_503(client, monkeypatch):
    async def failing_send(*args, **kwargs):
        return False

    monkeypatch.setattr("app.api.v1.endpoints.contact.send_email", failing_send)
    assert (await client.post(URL, json=VALID)).status_code == 503


@pytest.mark.asyncio
async def test_endpoint_is_rate_limited(client, outbox):
    codes = [(await client.post(URL, json=VALID)).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


@pytest.mark.asyncio
async def test_no_authentication_required(client, outbox):
    r = await client.post(URL, json=VALID)  # no Authorization header
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_smtp_message_has_reply_to_and_no_header_injection(monkeypatch):
    """Exercise the real message builder with a fake SMTP server."""
    from app.services import email_service

    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            captured["tls"] = True

        def login(self, user, password):
            captured["login"] = (user, password)

        def send_message(self, msg):
            captured["msg"] = msg

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USER", "apikey")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    ok = await email_service.send_email("info@mfventures.com", "Subject", "Body", reply_to="ada@example.com")
    assert ok is True
    msg = captured["msg"]
    assert msg["Reply-To"] == "ada@example.com" and msg["To"] == "info@mfventures.com"
    assert captured["tls"] and captured["login"] == ("apikey", "secret")

    # A bad header value must not raise out of send_email; it reports failure instead.
    assert await email_service.send_email("info@mfventures.com", "Bad\r\nBcc: x@y.z", "Body") is False
