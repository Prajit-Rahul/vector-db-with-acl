# src/vecgate/service/app.py
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Type
import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from vecgate.core.config import Settings
from vecgate.core.errors import VecGateError
from fastapi.responses import JSONResponse
from vecgate.service.auth.middleware import DevHeaderMiddleware
from vecgate.service.routes import admin, ingest, search as search_routes

# Paths that bypass auth and DB connection
_NO_AUTH_PATHS = {"/health"}


def create_app(
    settings: Settings | None = None,
    auth_middleware: Type[BaseHTTPMiddleware] | None = None,
) -> FastAPI:
    s = settings or Settings(enable_audit=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = s
        yield

    app = FastAPI(title="VecGate", version="0.1.0", lifespan=lifespan)

    # Exception handler
    @app.exception_handler(VecGateError)
    async def vecgate_error_handler(request: Request, exc: VecGateError):
        status_map = {
            "AUTHORIZATION_ERROR": 403,
            "NOT_FOUND": 404,
            "VALIDATION_ERROR": 422,
            "CONFIG_ERROR": 500,
            "SCHEMA_ERROR": 500,
            "BACKEND_ERROR": 502,
        }
        status = status_map.get(exc.code, 500)
        return JSONResponse({"code": exc.code, "detail": exc.message}, status_code=status)

    # Routes
    app.include_router(search_routes.router)
    app.include_router(ingest.router)
    app.include_router(admin.router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    # Middleware is applied in reverse registration order (last added = outermost = runs first).
    # Register in this order so the execution order is: auth → db → CORS → route.

    # 1. CORS — innermost, registered first
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    # 2. DB connection — middle layer; skips health endpoint
    @app.middleware("http")
    async def db_middleware(request: Request, call_next):
        if request.url.path in _NO_AUTH_PATHS:
            return await call_next(request)
        if not s.database_url:
            return JSONResponse({"detail": "VECGATE_DATABASE_URL not set"}, status_code=500)
        async with await psycopg.AsyncConnection.connect(s.database_url) as conn:
            request.state.db = conn
            response = await call_next(request)
        return response

    # 3. Auth — outermost, registered last; skips health endpoint
    mw = auth_middleware or DevHeaderMiddleware

    class _SkippingAuthMiddleware(mw):  # type: ignore[valid-type]
        async def dispatch(self, request: Request, call_next):
            if request.url.path in _NO_AUTH_PATHS:
                return await call_next(request)
            return await super().dispatch(request, call_next)

    app.add_middleware(_SkippingAuthMiddleware)

    return app
