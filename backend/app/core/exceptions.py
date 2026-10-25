"""
Domain-specific exception hierarchy.

Every exception that surfaces from the service layer is a subclass of
``IRISError`` so that the FastAPI exception handlers in ``main.py`` can
discriminate domain faults from unexpected crashes.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class IRISError(Exception):
    """Base class for all IRIS domain errors."""

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None, **ctx: Any) -> None:
        self.detail = detail or self.__class__.detail
        self.ctx = ctx
        super().__init__(self.detail)


# ── 4xx Client Errors ─────────────────────────────────────


class NotFoundError(IRISError):
    status_code = 404
    detail = "The requested resource was not found."

    def __init__(self, resource: str = "Resource", id: UUID | str | None = None) -> None:
        msg = f"{resource} not found" if id is None else f"{resource} '{id}' not found"
        super().__init__(detail=msg)


class ForbiddenError(IRISError):
    status_code = 403
    detail = "You do not have permission to perform this action."


class ConflictError(IRISError):
    status_code = 409
    detail = "A resource with the given identifier already exists."


class BadRequestError(IRISError):
    status_code = 400
    detail = "The request was malformed or contained invalid data."


class UnauthorizedError(IRISError):
    status_code = 401
    detail = "Authentication credentials are missing or invalid."
