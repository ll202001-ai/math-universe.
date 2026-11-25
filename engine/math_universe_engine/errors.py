"""Códigos de error uniformes (parte de la API estable)."""


class EngineError(Exception):
    code = "INTERNAL_ERROR"

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidRequest(EngineError):
    code = "INVALID_REQUEST"


class ParseError(EngineError):
    code = "PARSE_ERROR"


class MathDomainError(EngineError):
    code = "DOMAIN_ERROR"  # p. ej. división por cero


class NotImplementedOperation(EngineError):
    code = "NOT_IMPLEMENTED"


class DependencyMissing(EngineError):
    code = "DEPENDENCY_MISSING"


class LimitExceeded(EngineError):
    code = "LIMIT_EXCEEDED"


class NotSolved(EngineError):
    """El motor no encontró solución (NO implica que no exista)."""
    code = "NOT_SOLVED"


class VersionMismatch(EngineError):
    code = "VERSION_MISMATCH"


class TimeoutExceeded(EngineError):
    code = "TIMEOUT"


class VerificationFailed(EngineError):
    code = "VERIFICATION_FAILED"
