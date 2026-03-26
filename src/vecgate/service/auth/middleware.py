# src/vecgate/service/auth/middleware.py
"""Auth middleware contract and dev-mode implementation.

Production usage: subclass BaseHTTPMiddleware and set request.state.user_id (int).
Dev mode: reads X-User-Id header — trusts the caller; for local development only.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class DevHeaderMiddleware(BaseHTTPMiddleware):
    """Read X-User-Id header as the authenticated user. Dev only."""

    async def dispatch(self, request: Request, call_next):
        user_id_str = request.headers.get("X-User-Id")
        if user_id_str is None:
            return JSONResponse({"detail": "X-User-Id header required (dev mode)"}, status_code=401)
        try:
            request.state.user_id = int(user_id_str)
        except ValueError:
            return JSONResponse({"detail": "X-User-Id must be an integer"}, status_code=400)
        return await call_next(request)
