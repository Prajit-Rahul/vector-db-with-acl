# src/vecgate/core/errors.py


class VecGateError(Exception):
    code: str = "VECGATE_ERROR"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

class ConfigError(VecGateError):
    code = "CONFIG_ERROR"

class SchemaError(VecGateError):
    code = "SCHEMA_ERROR"

    def __init__(self, message: str = "Schema not initialised — run: vecgate init"):
        super().__init__(message)

class AuthorizationError(VecGateError):
    code = "AUTHORIZATION_ERROR"

class ValidationError(VecGateError):
    code = "VALIDATION_ERROR"

class NotFoundError(VecGateError):
    code = "NOT_FOUND"

class BackendError(VecGateError):
    code = "BACKEND_ERROR"
