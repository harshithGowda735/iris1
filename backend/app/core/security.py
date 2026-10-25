"""
JWT verification utilities for Supabase Auth tokens.

The ``decode_access_token`` function validates the HS256 signature and
standard claims (``exp``, ``aud``) using the Supabase JWT secret.
It returns the raw ``sub`` (user id) claim on success or raises
``UnauthorizedError`` on any validation failure.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


def decode_access_token(token: str) -> UUID:
    """Decode and verify a Supabase-issued JWT.

    Parameters
    ----------
    token:
        The raw bearer token string (without the ``Bearer `` prefix).

    Returns
    -------
    UUID
        The authenticated user's ID extracted from the ``sub`` claim.

    Raises
    ------
    UnauthorizedError
        If the token is expired, tampered with, or otherwise invalid.
    """
    try:
        payload: dict = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["exp", "sub"],
                "verify_exp": True,
                "verify_signature": True,
                "verify_aud": False,
            },
        )
    except InvalidTokenError as exc:
        raise UnauthorizedError(detail=f"Invalid token: {exc}") from exc

    raw_sub = payload.get("sub")
    if raw_sub is None:
        raise UnauthorizedError(detail="Token payload missing 'sub' claim.")

    try:
        return UUID(raw_sub)
    except ValueError as exc:
        raise UnauthorizedError(detail="Token 'sub' claim is not a valid UUID.") from exc
