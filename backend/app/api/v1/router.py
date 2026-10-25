"""v1 API router — aggregates all endpoint sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, nodes, posts, resources

router = APIRouter(prefix="/api/v1")

# ── Identity & Access Control ────────────────────────────
router.include_router(auth.router, prefix="/auth", tags=["Auth & Profiles"])

# ── Academic Hierarchy & Tree Navigation ─────────────────
router.include_router(nodes.router, prefix="/nodes", tags=["Nodes"])

# ── Content Delivery: CHAT & BOARD ───────────────────────
router.include_router(
    posts.router, prefix="/nodes/{node_id}/posts", tags=["Posts & Board"]
)
router.include_router(
    posts.legacy_router, prefix="/posts", tags=["Posts & Board"], include_in_schema=False
)

# ── Content Delivery: Academic Repository (REPO) ─────────
router.include_router(
    resources.router, prefix="/nodes/{node_id}/resources", tags=["Repo & Resources"]
)
router.include_router(
    resources.legacy_router, prefix="/resources", tags=["Repo & Resources"], include_in_schema=False
)
