"""
Integration tests for Identity, Membership, and Access Control.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import RoleEnum
from app.models.node import NodeType
from app.models.profile import UserProfile
from tests.conftest import TEST_USER_ID, create_test_node, grant_membership

pytestmark = pytest.mark.asyncio


class TestProfileEndpoints:
    """GET & PATCH /api/v1/auth/me"""

    async def test_get_me(self, client: AsyncClient, test_user: UserProfile) -> None:
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(TEST_USER_ID)
        assert data["roll_number"] == test_user.roll_number
        assert data["full_name"] == test_user.full_name
        # Privacy check: No contact fields
        assert "email" not in data
        assert "phone" not in data

    async def test_get_my_memberships(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        await grant_membership(db_session, test_user.id, college.id, RoleEnum.MEMBER)
        await grant_membership(db_session, test_user.id, dept.id, RoleEnum.CR)

        resp = await client.get("/api/v1/auth/me/memberships")
        assert resp.status_code == 200
        memberships = resp.json()
        assert len(memberships) == 2
        roles = {m["role"] for m in memberships}
        assert roles == {"MEMBER", "CR"}


class TestNodeRoleSecurity:
    """Role-based access control and hierarchical inheritance."""

    async def test_member_can_view_node_roster(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        batch = await create_test_node(db_session, "3rd Sem", NodeType.BATCH, dept.id)
        section = await create_test_node(db_session, "Section A", NodeType.SECTION, batch.id)

        # Grant membership to section
        await grant_membership(db_session, test_user.id, section.id, RoleEnum.MEMBER)

        resp = await client.get(f"/api/v1/nodes/{section.id}/members")
        assert resp.status_code == 200
        roster = resp.json()
        assert len(roster) == 1
        assert roster[0]["user_id"] == str(test_user.id)
        assert roster[0]["profile"]["full_name"] == test_user.full_name

    async def test_non_member_cannot_view_node_roster(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        # test_user has NO membership in dept
        resp = await client.get(f"/api/v1/nodes/{dept.id}/members")
        assert resp.status_code == 403

    async def test_ancestor_admin_inherits_down_to_section(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        batch = await create_test_node(db_session, "3rd Sem", NodeType.BATCH, dept.id)
        section = await create_test_node(db_session, "Section A", NodeType.SECTION, batch.id)

        # User is ADMIN at Department level (grandparent of section), NOT directly in section
        await grant_membership(db_session, test_user.id, dept.id, RoleEnum.ADMIN)

        # Must inherit authority down to section roster
        resp = await client.get(f"/api/v1/nodes/{section.id}/members")
        assert resp.status_code == 200
