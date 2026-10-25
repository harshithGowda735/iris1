"""
Integration tests for Content Delivery: Posts (CHAT & BOARD) and Academic REPO.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import RoleEnum
from app.models.node import NodeType
from app.models.profile import UserProfile
from tests.conftest import create_test_node, grant_membership

pytestmark = pytest.mark.asyncio


class TestScopedNodePosts:
    """GET and POST on /api/v1/nodes/{node_id}/posts"""

    async def test_member_can_post_and_read_chat(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        batch = await create_test_node(db_session, "3rd Sem", NodeType.BATCH, dept.id)
        section = await create_test_node(db_session, "Section A", NodeType.SECTION, batch.id)
        await grant_membership(db_session, test_user.id, section.id, RoleEnum.MEMBER)

        # 1. Post to CHAT
        create_resp = await client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "CHAT", "content": "Does anyone have the assignment 2 brief?"},
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["tab"] == "CHAT"
        assert data["content"] == "Does anyone have the assignment 2 brief?"
        assert data["author"]["full_name"] == test_user.full_name
        assert data["author"]["roll_number"] == test_user.roll_number

        # 2. Read back paginated CHAT feed
        get_resp = await client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "CHAT", "limit": 10, "offset": 0},
        )
        assert get_resp.status_code == 200
        feed = get_resp.json()
        assert feed["total"] == 1
        assert len(feed["items"]) == 1
        assert feed["items"][0]["content"] == "Does anyone have the assignment 2 brief?"

    async def test_board_enforces_cr_or_faculty_privilege(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        section = await create_test_node(db_session, "Section A", NodeType.SECTION, dept.id)

        # Regular member attempt on BOARD must be rejected
        await grant_membership(db_session, test_user.id, section.id, RoleEnum.MEMBER)
        member_resp = await client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "BOARD", "content": "Unverified Announcement"},
        )
        assert member_resp.status_code == 403

        # Elevate user to CR on section using ProfileService.assign_node_role
        from app.services.profile_service import ProfileService
        await ProfileService(db_session).assign_node_role(test_user.id, section.id, RoleEnum.CR)
        await db_session.commit()
        cr_resp = await client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "BOARD", "content": "Official Announcement: Lab rescheduled."},
        )
        assert cr_resp.status_code == 201
        assert cr_resp.json()["tab"] == "BOARD"


class TestScopedNodeResources:
    """GET and POST on /api/v1/nodes/{node_id}/resources"""

    async def test_academic_resource_lifecycle(
        self, client: AsyncClient, test_user: UserProfile, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        section = await create_test_node(db_session, "Section A", NodeType.SECTION, dept.id)
        await grant_membership(db_session, test_user.id, section.id, RoleEnum.MEMBER)

        # 1. Generate signed upload destination URL
        upload_resp = await client.post(
            f"/api/v1/nodes/{section.id}/resources/upload-url",
            json={"file_name": "Operating_Systems_Lab1.pdf"},
        )
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert "upload_url" in upload_data
        assert "file_path" in upload_data
        assert str(section.id) in upload_data["file_path"]

        # 2. Register uploaded resource
        create_resp = await client.post(
            f"/api/v1/nodes/{section.id}/resources",
            json={
                "file_name": "Operating_Systems_Lab1.pdf",
                "file_url": "https://storage.supabase.co/campus-docs/os_lab1.pdf",
                "subject_code": "21cs32",  # lower-case to test auto-capitalization
            },
        )
        assert create_resp.status_code == 201
        res_data = create_resp.json()
        assert res_data["subject_code"] == "21CS32"
        assert res_data["file_name"] == "Operating_Systems_Lab1.pdf"
        assert res_data["uploader_name"] == test_user.full_name

        # 3. Retrieve filtered resources
        filter_resp = await client.get(
            f"/api/v1/nodes/{section.id}/resources",
            params={"subject_code": "21CS32"},
        )
        assert filter_resp.status_code == 200
        items = filter_resp.json()
        assert len(items) == 1
        assert items[0]["subject_code"] == "21CS32"
