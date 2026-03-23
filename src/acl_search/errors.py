"""Backward-compatible error exports."""

from .core.errors import AuthorizationError, NotFoundError, ServiceError, ValidationError

__all__ = ["ServiceError", "NotFoundError", "AuthorizationError", "ValidationError"]
