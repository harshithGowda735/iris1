"""Integration tests for the Node hierarchy API."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node import Node, NodeType
from tests.conftest import create_test_node

pytestmark = pytest.mark.asyncio


class TestNodeCreation:
    """POST /api/v1/nodes — hierarchy validation and enforcement."""

    async def test_create_root_college(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/nodes",
            json={"name": "Dr. AIT", "type": "COLLEGE", "parent_id": None},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. AIT"
        assert data["type"] == "COLLEGE"
        assert data["parent_id"] is None

    async def test_create_department_under_college(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        resp = await client.post(
            "/api/v1/nodes",
            json={
                "name": "CSE",
                "type": "DEPARTMENT",
                "parent_id": str(college.id),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == str(college.id)

    async def test_reject_department_without_parent(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/v1/nodes",
            json={"name": "CSE", "type": "DEPARTMENT", "parent_id": None},
        )
        assert resp.status_code == 400

    async def test_reject_department_under_batch(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(
            db_session, "CSE", NodeType.DEPARTMENT, college.id
        )
        batch = await create_test_node(
            db_session, "3rd Sem", NodeType.BATCH, dept.id
        )
        resp = await client.post(
            "/api/v1/nodes",
            json={
                "name": "Orphan Dept",
                "type": "DEPARTMENT",
                "parent_id": str(batch.id),
            },
        )
        assert resp.status_code == 400

    async def test_reject_duplicate_sibling(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        resp = await client.post(
            "/api/v1/nodes",
            json={"name": "Dr. AIT", "type": "COLLEGE", "parent_id": None},
        )
        assert resp.status_code == 409


class TestNodeListing:
    """GET /api/v1/nodes — listing and retrieval."""

    async def test_list_root_nodes(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        await create_test_node(db_session, "RVCE", NodeType.COLLEGE)

        resp = await client.get("/api/v1/nodes")
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert names == {"Dr. AIT", "RVCE"}

    async def test_list_children_of_parent(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        await create_test_node(db_session, "CSE", NodeType.DEPARTMENT, college.id)
        await create_test_node(db_session, "ISE", NodeType.DEPARTMENT, college.id)

        resp = await client.get(
            "/api/v1/nodes", params={"parent_id": str(college.id)}
        )
        assert resp.status_code == 200
        names = {n["name"] for n in resp.json()}
        assert names == {"CSE", "ISE"}

    async def test_get_single_node(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        node = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        resp = await client.get(f"/api/v1/nodes/{node.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(node.id)

    async def test_get_nonexistent_node_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(f"/api/v1/nodes/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestAncestorPath:
    """GET /api/v1/nodes/{id}/ancestors — upward tree traversal."""

    async def test_full_ancestor_path(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        college = await create_test_node(db_session, "Dr. AIT", NodeType.COLLEGE)
        dept = await create_test_node(
            db_session, "CSE", NodeType.DEPARTMENT, college.id
        )
        batch = await create_test_node(
            db_session, "3rd Sem", NodeType.BATCH, dept.id
        )
        section = await create_test_node(
            db_session, "Section B", NodeType.SECTION, batch.id
        )

        resp = await client.get(f"/api/v1/nodes/{section.id}/ancestors")
        assert resp.status_code == 200
        ancestors = resp.json()["ancestors"]
        assert len(ancestors) == 4
        assert ancestors[0]["id"] == str(section.id)
        assert ancestors[-1]["id"] == str(college.id)


class TestNodeHierarchyAndTraversal:
    """Core hierarchy verification: roots and recursive CTE path navigation."""

    async def test_get_roots_returns_root_college(
        self, async_client: AsyncClient, seed_tree: dict[str, Node]
    ) -> None:
        """GET /api/v1/nodes/roots returns root college entities."""
        resp = await async_client.get("/api/v1/nodes/roots")
        assert resp.status_code == 200
        roots = resp.json()
        assert len(roots) >= 1
        assert any(n["id"] == str(seed_tree["college"].id) for n in roots)
        assert all(n["parent_id"] is None for n in roots)
        college_node = next(n for n in roots if n["id"] == str(seed_tree["college"].id))
        assert college_node["name"] == "Dr. AIT"
        assert college_node["type"] == "COLLEGE"

    async def test_get_node_hierarchy_ordered_breadcrumbs(
        self, async_client: AsyncClient, seed_tree: dict[str, Node]
    ) -> None:
        """GET /api/v1/nodes/{section_id}/hierarchy executes recursive CTE

        and returns exact ordered breadcrumb path: College -> Dept -> Batch -> Section.
        """
        section = seed_tree["section_a"]
        resp = await async_client.get(f"/api/v1/nodes/{section.id}/hierarchy")
        assert resp.status_code == 200
        payload = resp.json()

        # Verify active target node
        assert payload["node"]["id"] == str(section.id)
        assert payload["node"]["name"] == "Section A"
        assert payload["node"]["type"] == "SECTION"

        # Verify ordered breadcrumbs from root College down to Section
        breadcrumbs = payload["breadcrumbs"]
        assert len(breadcrumbs) == 4

        # 1. College
        assert breadcrumbs[0]["id"] == str(seed_tree["college"].id)
        assert breadcrumbs[0]["name"] == "Dr. AIT"
        assert breadcrumbs[0]["type"] == "COLLEGE"

        # 2. Department
        assert breadcrumbs[1]["id"] == str(seed_tree["dept"].id)
        assert breadcrumbs[1]["name"] == "CSE"
        assert breadcrumbs[1]["type"] == "DEPARTMENT"

        # 3. Batch
        assert breadcrumbs[2]["id"] == str(seed_tree["batch"].id)
        assert breadcrumbs[2]["name"] == "3rd Sem"
        assert breadcrumbs[2]["type"] == "BATCH"

        # 4. Section
        assert breadcrumbs[3]["id"] == str(section.id)
        assert breadcrumbs[3]["name"] == "Section A"
        assert breadcrumbs[3]["type"] == "SECTION"

    async def test_get_children_endpoint(
        self, async_client: AsyncClient, seed_tree: dict[str, Node]
    ) -> None:
        """GET /api/v1/nodes/{batch_id}/children returns all immediate child sections."""
        batch = seed_tree["batch"]
        resp = await async_client.get(f"/api/v1/nodes/{batch.id}/children")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert names == {"Section A", "Section B"}
        assert all(item["parent_id"] == str(batch.id) for item in data)
