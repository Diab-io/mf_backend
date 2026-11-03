import pytest

from app.core.security import create_password_reset_token, create_refresh_token
from tests.conftest import auth_headers

API = "/api/v1"


# ---------- equipment: tonnage + status on create ----------

@pytest.mark.asyncio
async def test_create_equipment_with_tonnage_and_status(client, admin):
    r = await client.post(
        f"{API}/equipment",
        json={"name": "Excavator", "registration_number": "EX-1", "tonnage": 21.5, "status": "actively_working"},
        headers=auth_headers(admin),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tonnage"] == 21.5
    assert body["status"] == "actively_working"


@pytest.mark.asyncio
async def test_create_equipment_defaults_to_idle(client, admin):
    r = await client.post(
        f"{API}/equipment", json={"name": "Crane", "registration_number": "CR-1"}, headers=auth_headers(admin)
    )
    assert r.status_code == 201
    assert r.json()["status"] == "idle"
    assert r.json()["tonnage"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["operational", "out_of_service", "nonsense"])
async def test_create_equipment_rejects_old_statuses(client, admin, bad):
    r = await client.post(
        f"{API}/equipment",
        json={"name": "X", "registration_number": f"R-{bad}", "status": bad},
        headers=auth_headers(admin),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_equipment_rejects_negative_tonnage(client, admin):
    r = await client.post(
        f"{API}/equipment",
        json={"name": "X", "registration_number": "NEG-1", "tonnage": -1},
        headers=auth_headers(admin),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_equipment_status_and_tonnage_and_dashboard(client, admin):
    created = await client.post(
        f"{API}/equipment", json={"name": "Truck", "registration_number": "T-1"}, headers=auth_headers(admin)
    )
    eid = created.json()["id"]
    r = await client.patch(
        f"{API}/equipment/{eid}", json={"status": "off_hire", "tonnage": 30}, headers=auth_headers(admin)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "off_hire" and r.json()["tonnage"] == 30

    dash = await client.get(f"{API}/reports/dashboard", headers=auth_headers(admin))
    assert dash.json()["equipment_off_hire"] == 1
    breakdown = await client.get(f"{API}/reports/equipment-downtime", headers=auth_headers(admin))
    assert breakdown.json() == {"off_hire": 1}


# ---------- archive users ----------

@pytest.mark.asyncio
async def test_archive_user_blocks_login_and_hides_from_list(client, admin, mechanic):
    r = await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))
    assert r.status_code == 200
    assert r.json()["archived_at"] is not None and r.json()["is_active"] is False

    login = await client.post(
        f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "Password123!"}
    )
    assert login.status_code == 401

    default_list = await client.get(f"{API}/users", headers=auth_headers(admin))
    assert "mechanic@example.com" not in [u["email"] for u in default_list.json()]
    full_list = await client.get(f"{API}/users?include_archived=true", headers=auth_headers(admin))
    assert "mechanic@example.com" in [u["email"] for u in full_list.json()]


@pytest.mark.asyncio
async def test_unarchive_restores_access(client, admin, mechanic):
    await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))
    r = await client.post(f"{API}/users/{mechanic.id}/unarchive", headers=auth_headers(admin))
    assert r.status_code == 200 and r.json()["archived_at"] is None and r.json()["is_active"] is True
    login = await client.post(
        f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "Password123!"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_archive_guards(client, admin, mechanic):
    # cannot archive yourself (also the last active admin)
    assert (await client.post(f"{API}/users/{admin.id}/archive", headers=auth_headers(admin))).status_code == 403
    # already archived
    await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))
    assert (await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))).status_code == 409


@pytest.mark.asyncio
async def test_cannot_archive_last_active_admin(client, admin, db_session):
    from app.core.constants import UserRole
    from tests.conftest import _make_user

    other_admin = await _make_user(db_session, "other-admin@example.com", UserRole.ADMIN)
    # other_admin archiving admin is fine while two admins exist
    r = await client.post(f"{API}/users/{admin.id}/archive", headers=auth_headers(other_admin))
    assert r.status_code == 200
    # now other_admin is the last active admin; a different (archived) admin cannot act, and self-archive is blocked
    r = await client.post(f"{API}/users/{other_admin.id}/archive", headers=auth_headers(other_admin))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_archive(client, supervisor, mechanic):
    r = await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(supervisor))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_archived_user_token_and_refresh_rejected(client, admin, mechanic):
    headers = auth_headers(mechanic)
    refresh = create_refresh_token(str(mechanic.id), mechanic.hashed_password)
    await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))
    assert (await client.get(f"{API}/auth/me", headers=headers)).status_code == 401
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})).status_code == 401


# ---------- forgot / reset password ----------

@pytest.mark.asyncio
async def test_forgot_password_same_response_for_unknown_email(client, mechanic):
    known = await client.post(f"{API}/auth/forgot-password", json={"email": "mechanic@example.com"})
    unknown = await client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


@pytest.mark.asyncio
async def test_forgot_password_sends_email_with_working_token(client, mechanic, monkeypatch):
    sent = []

    async def fake_send(to, subject, body):
        sent.append((to, body))

    monkeypatch.setattr("app.api.v1.endpoints.auth.send_email", fake_send)
    r = await client.post(f"{API}/auth/forgot-password", json={"email": "mechanic@example.com"})
    assert r.status_code == 200
    assert len(sent) == 1 and sent[0][0] == "mechanic@example.com"
    token = sent[0][1].split("token=")[1].split()[0]

    reset = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "BrandNew123!"})
    assert reset.status_code == 200
    ok = await client.post(f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "BrandNew123!"})
    assert ok.status_code == 200
    old = await client.post(f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "Password123!"})
    assert old.status_code == 401


@pytest.mark.asyncio
async def test_reset_token_is_single_use(client, mechanic):
    token = create_password_reset_token(str(mechanic.id), mechanic.hashed_password)
    first = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "FirstNew123!"})
    assert first.status_code == 200
    second = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "SecondNew123!"})
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_wrong_token_types_and_garbage(client, mechanic):
    access = auth_headers(mechanic)["Authorization"].split()[1]
    refresh = create_refresh_token(str(mechanic.id), mechanic.hashed_password)
    for bad in (access, refresh, "garbage"):
        r = await client.post(f"{API}/auth/reset-password", json={"token": bad, "new_password": "Whatever123!"})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_reset_rejects_short_password(client, mechanic):
    token = create_password_reset_token(str(mechanic.id), mechanic.hashed_password)
    r = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "short"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reset_rejected_for_archived_user(client, admin, mechanic):
    token = create_password_reset_token(str(mechanic.id), mechanic.hashed_password)
    await client.post(f"{API}/users/{mechanic.id}/archive", headers=auth_headers(admin))
    r = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Whatever123!"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_revokes_existing_refresh_tokens(client, mechanic):
    login = await client.post(
        f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "Password123!"}
    )
    old_refresh = login.json()["refresh_token"]
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})).status_code == 200

    token = create_password_reset_token(str(mechanic.id), mechanic.hashed_password)
    await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "BrandNew123!"})

    # old session is dead, a fresh login works and its refresh token is valid
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})).status_code == 401
    new_login = await client.post(
        f"{API}/auth/login", data={"username": "mechanic@example.com", "password": "BrandNew123!"}
    )
    new_refresh = new_login.json()["refresh_token"]
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": new_refresh})).status_code == 200


@pytest.mark.asyncio
async def test_refresh_token_without_pwd_claim_is_rejected(client, mechanic):
    from app.core.security import _create_token
    from datetime import timedelta

    legacy = _create_token(str(mechanic.id), timedelta(minutes=5), "refresh")
    assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": legacy})).status_code == 401
