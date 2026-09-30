"""Core exception hierarchy for SkyLock."""


class SkyLockError(Exception):
    """Base exception for all SkyLock errors."""


class FrameError(SkyLockError):
    """Raised when frame data violates shape, dtype, or constraints."""


class GeometryError(SkyLockError):
    """Raised when geometric or angular transformations fail."""
