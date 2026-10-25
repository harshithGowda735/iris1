"""
Shared pytest fixtures and configuration for IRIS backend tests.

Configured for Python 3.12+ and pytest-asyncio. Uses an in-memory SQLite
database with StaticPool (via ``aiosqlite``) ensuring isolated, high-performance
test executions without external database dependencies.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator

import jwt
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.base import Base
from app.models.membership import NodeMembership, RoleEnum
from app.models.node import Node, NodeType
from app.models.post import Post  # noqa: F401 — ensure table registration
from app.models.profile import UserProfile
from app.models.resource import Resource  # noqa: F401

# ── Deterministic Test User Identities ───────────────────
TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_USER_ROLL = "1AY21CS000"
TEST_USER_NAME = "Test Student"

STUDENT_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STUDENT_USER_ROLL = "1AY21CS001"
STUDENT_USER_NAME = "Regular Student"

CR_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CR_USER_ROLL = "1AY21CS002"
CR_USER_NAME = "Class Representative"

# ── In-Memory SQLite Engine (StaticPool for Session Sharing) ─────────
_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(
    _TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_session_factory = async_sessionmaker(
    bind=_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def _setup_database() -> AsyncGenerator[None, None]:
    """Create all schema tables before each test and drop after teardown."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency override yield yielding an active test AsyncSession."""
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct database session fixture for test assertions and setup."""
    async for session in _get_test_db():
        yield session


# ── Canonical User Fixtures ──────────────────────────────


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserProfile:
    """Insert and return the canonical test user profile."""
    profile = UserProfile(
        id=TEST_USER_ID,
        roll_number=TEST_USER_ROLL,
        full_name=TEST_USER_NAME,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


async def _mock_current_user() -> UserProfile:
    """Mock user dependency override for legacy tests."""
    return UserProfile(
        id=TEST_USER_ID,
        roll_number=TEST_USER_ROLL,
        full_name=TEST_USER_NAME,
    )


# ── Client Fixtures ──────────────────────────────────────


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to FastAPI with only get_db overridden.

    Allows genuine JWT bearer tokens in Authorization headers to be decoded
    and verified by `get_current_user`.
    """
    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client(test_user: UserProfile) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with both get_db and get_current_user mocked.

    Maintains backwards compatibility for existing unit/integration tests.
    """
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_current_user] = _mock_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Hierarchy Tree Fixture ───────────────────────────────


@pytest_asyncio.fixture
async def seed_tree(db_session: AsyncSession) -> dict[str, Node]:
    """Creates a complete academic hierarchy tree.

    Structure:
        College (Dr. AIT)
          └── Department (CSE)
                └── Batch (3rd Sem)
                      ├── Section (Section A)
                      └── Section (Section B)
    """
    college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
    dept = await create_test_node(
        db_session, "CSE", NodeType.DEPARTMENT, parent_id=college.id
    )
    batch = await create_test_node(
        db_session, "3rd Sem", NodeType.BATCH, parent_id=dept.id
    )
    section_a = await create_test_node(
        db_session, "Section A", NodeType.SECTION, parent_id=batch.id
    )
    section_b = await create_test_node(
        db_session, "Section B", NodeType.SECTION, parent_id=batch.id
    )
    return {
        "college": college,
        "dept": dept,
        "batch": batch,
        "section_a": section_a,
        "section_b": section_b,
        "section": section_a,
    }


# ── Auth & JWT Fixtures ──────────────────────────────────


def _create_test_jwt(user_id: uuid.UUID) -> str:
    """Encode a valid HS256 JWT using the configured Supabase secret."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "exp": now + 3600,
        "iat": now,
        "aud": "authenticated",
        "role": "authenticated",
    }
    return jwt.encode(
        payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm
    )


@pytest_asyncio.fixture
async def auth_headers_student(
    db_session: AsyncSession, seed_tree: dict[str, Node]
) -> dict[str, str]:
    """Generates a valid mocked JWT header for a regular student (MEMBER role).

    Ensures the student profile exists and is assigned MEMBER role on Section A.
    """
    profile = await db_session.get(UserProfile, STUDENT_USER_ID)
    if profile is None:
        profile = UserProfile(
            id=STUDENT_USER_ID,
            roll_number=STUDENT_USER_ROLL,
            full_name=STUDENT_USER_NAME,
            primary_section_id=seed_tree["section_a"].id,
        )
        db_session.add(profile)
        await db_session.commit()

    stmt = select(NodeMembership).where(
        NodeMembership.user_id == STUDENT_USER_ID,
        NodeMembership.node_id == seed_tree["section_a"].id,
    )
    existing = (await db_session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        await grant_membership(
            db_session, STUDENT_USER_ID, seed_tree["section_a"].id, RoleEnum.MEMBER
        )

    token = _create_test_jwt(STUDENT_USER_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_cr(
    db_session: AsyncSession, seed_tree: dict[str, Node]
) -> dict[str, str]:
    """Generates a valid mocked JWT header for a Class Representative (CR role).

    Ensures the CR profile exists and is assigned CR role on Section A.
    """
    profile = await db_session.get(UserProfile, CR_USER_ID)
    if profile is None:
        profile = UserProfile(
            id=CR_USER_ID,
            roll_number=CR_USER_ROLL,
            full_name=CR_USER_NAME,
            primary_section_id=seed_tree["section_a"].id,
        )
        db_session.add(profile)
        await db_session.commit()

    stmt = select(NodeMembership).where(
        NodeMembership.user_id == CR_USER_ID,
        NodeMembership.node_id == seed_tree["section_a"].id,
    )
    membership = (await db_session.execute(stmt)).scalar_one_or_none()
    if membership is None:
        await grant_membership(
            db_session, CR_USER_ID, seed_tree["section_a"].id, RoleEnum.CR
        )
    elif membership.role != RoleEnum.CR:
        membership.role = RoleEnum.CR
        await db_session.commit()

    token = _create_test_jwt(CR_USER_ID)
    return {"Authorization": f"Bearer {token}"}


# ── Helper Factories ─────────────────────────────────────


async def create_test_node(
    db: AsyncSession,
    name: str = "Dr. AIT",
    node_type: NodeType = NodeType.COLLEGE,
    parent_id: uuid.UUID | None = None,
) -> Node:
    """Helper to persist a test node."""
    node = Node(name=name, type=node_type, parent_id=parent_id)
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def grant_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    node_id: uuid.UUID,
    role: RoleEnum = RoleEnum.MEMBER,
) -> NodeMembership:
    """Helper to persist a node membership."""
    membership = NodeMembership(user_id=user_id, node_id=node_id, role=role)
    db.add(membership)
    await db.commit()
    return membership
