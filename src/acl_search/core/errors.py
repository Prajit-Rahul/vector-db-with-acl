"""Domain errors used by the service and API layers."""


class ServiceError(Exception):
    """Base error class for service-specific failures."""


class NotFoundError(ServiceError):
    """Raised when a tenant-scoped entity does not exist."""


class AuthorizationError(ServiceError):
    """Raised on authorization context mismatch or forbidden actions."""


class ValidationError(ServiceError):
    """Raised when user-supplied data fails business validation."""
