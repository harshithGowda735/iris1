"""Integration tests for the Post API — channel access control and pagination."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.models.node import Node

pytestmark = pytest.mark.asyncio


class TestChannelAccessControl:
    """Rigorous business rules verification for CHAT and BOARD channels.

    - CHAT: Permitted for any verified MEMBER.
    - BOARD: Strictly restricted to CR / FACULTY / ADMIN.
    """

    async def test_member_can_post_to_chat(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_student: dict[str, str],
    ) -> None:
        """A regular student with MEMBER role can post messages to CHAT (201 Created)."""
        section = seed_tree["section_a"]
        resp = await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={
                "tab": "CHAT",
                "content": "Hello everyone! Are lab files due tomorrow?",
            },
            headers=auth_headers_student,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tab"] == "CHAT"
        assert data["content"] == "Hello everyone! Are lab files due tomorrow?"
        assert data["node_id"] == str(section.id)
        assert data["author"] is not None
        assert data["author"]["roll_number"] == "1AY21CS001"

    async def test_member_forbidden_from_posting_to_board(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_student: dict[str, str],
    ) -> None:
        """A regular student with MEMBER role is strictly forbidden from posting to BOARD (403 Forbidden)."""
        section = seed_tree["section_a"]
        resp = await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={
                "tab": "BOARD",
                "content": "Unauthorized Announcement: Tomorrow is a holiday.",
            },
            headers=auth_headers_student,
        )
        assert resp.status_code == 403
        assert "board" in resp.json()["detail"].lower()

    async def test_cr_can_post_to_board(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_cr: dict[str, str],
    ) -> None:
        """A Class Representative (CR) can successfully publish announcements to BOARD (201 Created)."""
        section = seed_tree["section_a"]
        resp = await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={
                "tab": "BOARD",
                "content": "Official Announcement: Mid-term schedule released.",
            },
            headers=auth_headers_cr,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tab"] == "BOARD"
        assert data["content"] == "Official Announcement: Mid-term schedule released."
        assert data["author"]["roll_number"] == "1AY21CS002"


class TestPostPagination:
    """Pagination and tab filtering on GET /api/v1/nodes/{node_id}/posts."""

    async def test_chat_posts_pagination(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_student: dict[str, str],
    ) -> None:
        """Verify limit, offset, and total count on paginated CHAT messages."""
        section = seed_tree["section_a"]

        # Seed 5 consecutive chat messages with advancing timestamps
        for i in range(1, 6):
            post_resp = await async_client.post(
                f"/api/v1/nodes/{section.id}/posts",
                json={"tab": "CHAT", "content": f"Message {i}"},
                headers=auth_headers_student,
            )
            assert post_resp.status_code == 201
            await asyncio.sleep(0.01)

        # Page 1: limit=2, offset=0
        resp1 = await async_client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "CHAT", "limit": 2, "offset": 0},
            headers=auth_headers_student,
        )
        assert resp1.status_code == 200
        p1 = resp1.json()
        assert p1["total"] == 5
        assert p1["limit"] == 2
        assert p1["offset"] == 0
        assert len(p1["items"]) == 2

        # Page 2: limit=2, offset=2
        resp2 = await async_client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "CHAT", "limit": 2, "offset": 2},
            headers=auth_headers_student,
        )
        assert resp2.status_code == 200
        p2 = resp2.json()
        assert p2["total"] == 5
        assert p2["limit"] == 2
        assert p2["offset"] == 2
        assert len(p2["items"]) == 2

        # Page 3: limit=2, offset=4 (last remaining item)
        resp3 = await async_client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "CHAT", "limit": 2, "offset": 4},
            headers=auth_headers_student,
        )
        assert resp3.status_code == 200
        p3 = resp3.json()
        assert p3["total"] == 5
        assert p3["limit"] == 2
        assert p3["offset"] == 4
        assert len(p3["items"]) == 1

        # Verify exact partitioning and no duplication across paginated pages
        p1_ids = [item["id"] for item in p1["items"]]
        p2_ids = [item["id"] for item in p2["items"]]
        p3_ids = [item["id"] for item in p3["items"]]
        assert len(set(p1_ids).intersection(set(p2_ids))) == 0
        assert len(set(p2_ids).intersection(set(p3_ids))) == 0

        all_contents = [item["content"] for item in p1["items"] + p2["items"] + p3["items"]]
        assert set(all_contents) == {
            "Message 1",
            "Message 2",
            "Message 3",
            "Message 4",
            "Message 5",
        }

    async def test_tab_isolation(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_student: dict[str, str],
        auth_headers_cr: dict[str, str],
    ) -> None:
        """Verify that CHAT posts and BOARD posts are partitioned by the tab parameter."""
        section = seed_tree["section_a"]

        # Post 1 to CHAT, 1 to BOARD
        await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "CHAT", "content": "Chat message 1"},
            headers=auth_headers_student,
        )
        await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "BOARD", "content": "Board message 1"},
            headers=auth_headers_cr,
        )

        # Query BOARD tab only
        board_resp = await async_client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "BOARD"},
            headers=auth_headers_student,
        )
        assert board_resp.status_code == 200
        board_data = board_resp.json()
        assert board_data["total"] == 1
        assert board_data["items"][0]["tab"] == "BOARD"
        assert board_data["items"][0]["content"] == "Board message 1"

        # Query CHAT tab only
        chat_resp = await async_client.get(
            f"/api/v1/nodes/{section.id}/posts",
            params={"tab": "CHAT"},
            headers=auth_headers_student,
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert chat_data["total"] == 1
        assert chat_data["items"][0]["tab"] == "CHAT"
        assert chat_data["items"][0]["content"] == "Chat message 1"


class TestPostDeletion:
    """DELETE /api/v1/posts/{post_id} — author and role checks."""

    async def test_author_can_delete_own_post(
        self,
        async_client: AsyncClient,
        seed_tree: dict[str, Node],
        auth_headers_student: dict[str, str],
    ) -> None:
        """An author can cleanly delete their own post."""
        section = seed_tree["section_a"]
        create_resp = await async_client.post(
            f"/api/v1/nodes/{section.id}/posts",
            json={"tab": "CHAT", "content": "Draft message to be deleted"},
            headers=auth_headers_student,
        )
        assert create_resp.status_code == 201
        post_id = create_resp.json()["id"]

        del_resp = await async_client.delete(
            f"/api/v1/posts/{post_id}", headers=auth_headers_student
        )
        assert del_resp.status_code == 204

        # Verify post is removed
        get_resp = await async_client.get(f"/api/v1/posts/{post_id}")
        assert get_resp.status_code == 404
