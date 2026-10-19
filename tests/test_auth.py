import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_login_success(client, mechanic):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "mechanic@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, mechanic):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "mechanic@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client, mechanic):
    response = await client.get("/api/v1/auth/me", headers=auth_headers(mechanic))
    assert response.status_code == 200
    assert response.json()["email"] == "mechanic@example.com"


@pytest.mark.asyncio
async def test_refresh_token(client, mechanic):
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "mechanic@example.com", "password": "Password123!"},
    )
    refresh_token = login.json()["refresh_token"]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
