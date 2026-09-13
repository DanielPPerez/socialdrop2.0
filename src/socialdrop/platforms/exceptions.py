class PlatformError(Exception):
    """Base exception for all platform-related errors."""


class PlatformAuthError(PlatformError):
    """Raised when authentication fails or token is invalid/expired."""


class PlatformRateLimitError(PlatformError):
    """Raised when the platform responds with a rate-limit status."""


class PlatformValidationError(PlatformError):
    """Raised when request validation fails (e.g., media too large, invalid fields)."""


class PlatformTimeoutError(PlatformError):
    """Raised when a platform request times out."""
