"""Stable business error codes for API responses."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthRequired(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("AUTH_REQUIRED", message, status_code=401)


class InsufficientCredits(AppError):
    def __init__(self, message: str = "Insufficient credits") -> None:
        super().__init__("INSUFFICIENT_CREDITS", message, status_code=402)


class DailyLimitReached(AppError):
    def __init__(self, message: str = "Daily free generation limit reached") -> None:
        super().__init__("DAILY_LIMIT_REACHED", message, status_code=429)


class ConcurrentJobLimit(AppError):
    def __init__(self, message: str = "Too many concurrent generation jobs") -> None:
        super().__init__("CONCURRENT_JOB_LIMIT", message, status_code=429)


class NotFound(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("NOT_FOUND", message, status_code=404)


class Conflict(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)


class ValidationFailed(AppError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(code, message, status_code=422)
