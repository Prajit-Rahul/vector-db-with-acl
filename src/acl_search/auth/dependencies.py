"""Auth-context dependency.

In production, replace this with JWT/session middleware that injects verified identity.
The API never trusts request-body user_id/tenant_id for authorization scope.
"""

from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ConfigDict


class AuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    tenant_id: UUID


def get_auth_context(request: Request) -> AuthContext:
    """Resolve authenticated user context.

    Priority:
    1) request.state.auth_context (from upstream auth middleware)
    2) fallback headers for local development/testing
    """
    state_ctx = getattr(request.state, "auth_context", None)
    if isinstance(state_ctx, AuthContext):
        return state_ctx

    user_id = request.headers.get("x-authenticated-user-id")
    tenant_id = request.headers.get("x-authenticated-tenant-id")
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing authenticated identity. Ensure auth middleware sets "
                "request.state.auth_context or pass dev headers."
            ),
        )

    try:
        return AuthContext(user_id=UUID(user_id), tenant_id=UUID(tenant_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth context format",
        ) from exc
