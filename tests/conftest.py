import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("FIRST_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FIRST_ADMIN_PASSWORD", "AdminPass123!")
os.environ.setdefault("STORAGE_DIR", "./test_uploads")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.constants import UserRole
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_user(db_session, email, role, password="Password123!"):
    user = User(
        full_name=email.split("@")[0].title(),
        email=email,
        phone_number="08000000000",
        site="HQ",
        role=role,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def mechanic(db_session):
    return await _make_user(db_session, "mechanic@example.com", UserRole.MECHANIC)


@pytest_asyncio.fixture
async def supervisor(db_session):
    return await _make_user(db_session, "supervisor@example.com", UserRole.SUPERVISOR)


@pytest_asyncio.fixture
async def md(db_session):
    return await _make_user(db_session, "md@example.com", UserRole.MD)


@pytest_asyncio.fixture
async def admin(db_session):
    return await _make_user(db_session, "admin2@example.com", UserRole.ADMIN)


def auth_headers(user):
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return {"Authorization": f"Bearer {token}"}
