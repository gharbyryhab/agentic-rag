"""Rate-limiting infrastructure — single module so routers and main.py
can all import the same `limiter` singleton without circular imports.
"""
from __future__ import annotations

import os

from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

# Read independently from backend.auth so this module stays self-contained.
# If JWT_SECRET is absent the decode fails silently and we fall back to IP.
_JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
_JWT_ALGO = "HS256"


def get_user_or_ip(request: Request) -> str:
    """Rate-limit key for the chat endpoints.

    Authenticated callers each get their own bucket keyed on `user:<id>` so a
    single user cannot exhaust the quota for everyone sharing a NAT address.
    Falls back to the remote IP when no valid Bearer token is present.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        try:
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
            user_id: str | None = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except (JWTError, Exception):
            pass
    return get_remote_address(request)


# ── Global limiter singleton ──────────────────────────────────────────────────
# default_limits is enforced by SlowAPIMiddleware for every route that is NOT
# decorated with @limiter.limit(); decorated routes use their own limit instead.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)
